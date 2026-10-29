"""검색 성능 테스트. tests/retrieval_cases.json 의 각 질문이 Top-K 안에서 정답 조문/섹션을 찾는지 확인.

expect 는 label()과 정확히 같아야 함 ('형법 제329조', '3단계 결정 - 1. 송치 결정').
HIT = expect 중 하나 이상 찾음, Recall = 찾은 expect 수 / 전체 expect 수.

사용법:
    python test_retrieval.py            # 전체 케이스
    python test_retrieval.py -k 3       # Top-3 기준
    python test_retrieval.py -q "무인 매장에서 물건을 훔치면?"   # 질문 하나만 확인
"""
import argparse
import json
import sys

import config
from src.chunking import label
from src.kb import get_vectorstore

CASES_PATH = config.ROOT / "tests" / "retrieval_cases.json"


def show(db, query: str, k: int):
    res = db.similarity_search_with_score(query, k=k)
    for rank, (doc, score) in enumerate(res, 1):
        print(f"   {rank}. {label(doc):<28} score={score:.3f}")
    return [label(d) for d, _ in res]


def main(k: int, query: str | None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔에서 한글 깨짐 방지
    db = get_vectorstore()

    if query:
        print(f"Q. {query}")
        show(db, query, k)
        return

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    hit = n_found = n_expect = 0
    for case in cases:
        print(f"Q. {case['query']}   (정답: {', '.join(case['expect'])})")
        found = set(show(db, case["query"], k))
        got = [e for e in case["expect"] if e in found]  # 부분 문자열이 아닌 정확 일치
        hit += bool(got)
        n_found += len(got)
        n_expect += len(case["expect"])
        print("   ->", "✅ HIT" if got else "❌ MISS", f"({len(got)}/{len(case['expect'])})\n")
    print(f"Hit@{k}: {hit}/{len(cases)}   Recall@{k}: {n_found}/{n_expect}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=config.TOP_K)
    ap.add_argument("-q", "--query")
    args = ap.parse_args()
    main(args.k, args.query)
