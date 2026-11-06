"""RAG baseline 측정. tests/eval_cases.json(검수된 평가 세트)으로 두 단계를 잰다.

1) 검색 단계 (순수 벡터 검색, 법령만): summary 하나로 검색했을 때 정답 조문이 몇 위에 오는가
   - Hit@K, Recall@K, MRR  (expect가 비어 있는 케이스는 제외)
2) 파이프라인 단계 (retrieve_for_segment, 백엔드가 실제로 쓰는 경로): 최종으로 나온 조문이 맞는가
   - precision, recall, 정확 일치율, 오탐률(expect가 []인데 조문이 나온 비율)

평가 세트는 scripts/gen_eval_queries_colab.py로 만들고 사람이 검수한다.
dev는 키워드·질의 조정용, test는 고치지 않고 점수만 보는 용도.

사용법:
    python eval_rag.py                                   # test 세트, K=3
    python eval_rag.py --split dev
    python eval_rag.py --split all -k 1
    python eval_rag.py --save results/baseline.json      # 설정·점수·케이스별 결과 저장
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

import config
from src.chunking import label
from src.kb import get_vectorstore
from src.rag_service import retrieve_for_segment

DEFAULT_CASES = config.ROOT / "tests" / "eval_cases.json"
SEARCH_DEPTH = 20  # MRR 계산용으로 이 깊이까지 순위를 본다


def load_cases(path, split: str) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data
    unreviewed = sum(not c.get("reviewed", False) for c in cases)
    if unreviewed:
        print(f"[경고] 검수되지 않은 케이스 {unreviewed}개 (reviewed: false). 점수를 baseline으로 쓰기 전에 검수하세요.")
    return [c for c in cases if split == "all" or c["split"] == split]


def law_ranking(store, query: str) -> list[str]:
    """법령만 검색해 label 순위 목록 (긴 조문의 여러 청크는 한 번만)."""
    out = []
    for doc, _ in store.similarity_search_with_score(query, k=SEARCH_DEPTH, filter={"doc_type": "law"}):
        if label(doc) not in out:
            out.append(label(doc))
    return out


def ratio(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def evaluate(cases: list[dict], k: int, store) -> dict:
    per_case = []
    r_hit = r_found = r_expect = r_n = 0
    rr_sum = 0.0
    p_tp = p_ret = p_exp = p_exact = 0
    neg_n = neg_fp = 0
    by_scn = defaultdict(lambda: {"n": 0, "tp": 0, "ret": 0, "exp": 0, "exact": 0})

    for c in cases:
        expect = set(c["expect"])

        # 1) 검색 단계
        ranking = law_ranking(store, c["summary"])
        rank = next((i for i, l in enumerate(ranking, 1) if l in expect), None)
        if expect:
            got = expect & set(ranking[:k])
            r_n += 1
            r_hit += bool(got)
            r_found += len(got)
            r_expect += len(expect)
            rr_sum += 1 / rank if rank else 0.0

        # 2) 파이프라인 단계
        res = retrieve_for_segment({"segment_id": c["id"], "event_type": c["event_type"], "summary": c["summary"]},
                                   store=store)
        returned = [f"{r['law_name']} {r['article_no']}" for r in res["legal_references"]]
        tp = len(expect & set(returned))
        exact = set(returned) == expect
        p_tp += tp
        p_ret += len(returned)
        p_exp += len(expect)
        p_exact += exact
        if not expect:
            neg_n += 1
            neg_fp += bool(returned)
        s = by_scn[c["scenario"]]
        s["n"] += 1
        s["tp"] += tp
        s["ret"] += len(returned)
        s["exp"] += len(expect)
        s["exact"] += exact

        per_case.append({
            "id": c["id"], "split": c["split"], "expect": sorted(expect),
            "search_top": ranking[:k], "first_hit_rank": rank,
            "returned": returned, "match": [r["match"] for r in res["legal_references"]],
            "extra": [l for l in returned if l not in expect],
            "missing": sorted(expect - set(returned)),
        })

    return {
        "retrieval": {
            "n": r_n,
            f"hit@{k}": ratio(r_hit, r_n),
            f"recall@{k}": ratio(r_found, r_expect),
            "mrr": ratio(rr_sum, r_n),
        },
        "pipeline": {
            "n": len(cases),
            "precision": ratio(p_tp, p_ret),
            "recall": ratio(p_tp, p_exp),
            "exact_match": ratio(p_exact, len(cases)),
            "negatives": neg_n,
            "false_positive_rate": ratio(neg_fp, neg_n),
        },
        "by_scenario": {
            name: {"n": s["n"], "precision": ratio(s["tp"], s["ret"]), "recall": ratio(s["tp"], s["exp"]),
                   "exact_match": ratio(s["exact"], s["n"])}
            for name, s in sorted(by_scn.items())
        },
        "cases": per_case,
    }


def git_state() -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True).stdout.strip()
        except OSError:
            return None
    # 추적 중인 파일의 변경만 본다 (저장할 results/ 같은 새 파일 때문에 dirty가 되지 않게)
    return {"commit": run("rev-parse", "--short", "HEAD"),
            "dirty": bool(run("status", "--porcelain", "--untracked-files=no"))}


def fmt(v) -> str:
    return "-" if v is None else f"{v:.3f}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--split", choices=["dev", "test", "all"], default="test")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--save")
    args = ap.parse_args()

    cases_path = args.cases
    cases = load_cases(cases_path, args.split)
    if not cases:
        sys.exit(f"[오류] {args.split} 케이스가 없습니다: {cases_path}")

    m = evaluate(cases, args.k, get_vectorstore())
    r, p = m["retrieval"], m["pipeline"]
    print(f"\n[{args.split}] 케이스 {len(cases)}개\n")
    print(f"검색 단계 (법령 정답 있는 {r['n']}개)")
    print(f"  Hit@{args.k} {fmt(r[f'hit@{args.k}'])}   Recall@{args.k} {fmt(r[f'recall@{args.k}'])}   MRR {fmt(r['mrr'])}")
    print("파이프라인 단계 (retrieve_for_segment)")
    print(f"  Precision {fmt(p['precision'])}   Recall {fmt(p['recall'])}   정확 일치 {fmt(p['exact_match'])}"
          f"   오탐률 {fmt(p['false_positive_rate'])} (정답 없음 {p['negatives']}개 중)")
    print("\n시나리오별 (파이프라인)")
    for name, s in m["by_scenario"].items():
        print(f"  {name:<24} n={s['n']:<3} P {fmt(s['precision'])}  R {fmt(s['recall'])}  일치 {fmt(s['exact_match'])}")
    wrong = [c for c in m["cases"] if c["extra"] or c["missing"]]
    if wrong:
        print(f"\n틀린 케이스 {len(wrong)}개")
        for c in wrong:
            print(f"  {c['id']:<28} 추가 {c['extra'] or '-'}  누락 {c['missing'] or '-'}")

    if args.save:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "measured_at": datetime.now().isoformat(timespec="seconds"),
            "git": git_state(),
            "config": {
                "embedding_model": config.EMBEDDING_MODEL,
                "chunk_max_len": config.CHUNK_MAX_LEN,
                "chunk_overlap": config.CHUNK_OVERLAP,
                "law_max_distance": config.LAW_MAX_DISTANCE,
                "k": args.k,
            },
            "eval_set": {
                "file": cases_path.name,
                "sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest()[:12],
                "split": args.split,
                "n": len(cases),
            },
            **m,
        }
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
