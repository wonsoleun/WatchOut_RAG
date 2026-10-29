"""retrieve_for_segment() 골든 테스트. tests/segment_cases.json 의 각 세그먼트 결과가 기대와 맞는지 확인.

검색 품질(test_retrieval.py)과 달리, event_type별 규칙(핵심 조문, 절차 순서, 경고)이 지켜지는지 본다.
또한 중복 조문이 없는지, 설정된 절차 섹션이 모두 지식 베이스에 있는지도 확인한다.

사용법:
    python test_segments.py
"""
import json
import sys

import config
from src.kb import get_vectorstore
from src.query_builder import EVENT_CONFIG
from src.rag_service import retrieve_for_segment

CASES_PATH = config.ROOT / "tests" / "segment_cases.json"


def check(case: dict, result: dict) -> list[str]:
    errors = []
    if result["status"] != case["status"]:
        errors.append(f"status {result['status']} != {case['status']}")
    laws = [f"{r['law_name']} {r['article_no']}" for r in result["legal_references"]]
    if len(laws) != len(set(laws)):
        errors.append(f"중복 조문: {laws}")
    if "law_rank1" in case and (not laws or laws[0] != case["law_rank1"]):
        errors.append(f"1순위 조문 {laws[:1]} != {case['law_rank1']}")
    for key in case.get("laws_include", []):
        if key not in laws:
            errors.append(f"조문 {key} 없음: {laws}")
    texts = "\n".join(r["text"] for r in result["legal_references"])
    for s in case.get("text_contains", []):
        if s not in texts:
            errors.append(f"조문 본문에 '{s}' 없음")
    procs = [p["section"] for p in result["procedure_references"]]
    if "first_procedure" in case and (not procs or procs[0] != case["first_procedure"]):
        errors.append(f"첫 절차 {procs[:1]} != {case['first_procedure']}")
    if case.get("no_procedures") and procs:
        errors.append(f"절차가 없어야 함: {procs}")
    if "warning_contains" in case and not any(case["warning_contains"] in w for w in result["warnings"]):
        errors.append(f"경고에 '{case['warning_contains']}' 없음: {result['warnings']}")
    if any("지식 베이스에 없습니다: " in w for w in result["warnings"]):
        errors.append(f"설정과 지식 베이스 불일치: {result['warnings']}")
    return errors


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔에서 한글 깨짐 방지
    store = get_vectorstore()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    # 케이스에 없는 event_type도 설정(핵심 조문/절차 이름) 오류는 잡히도록 전부 한 번씩 돌림
    covered = {c["segment"]["event_type"] for c in cases}
    cases += [{"name": f"설정 확인: {et}", "segment": {"segment_id": "cfg", "event_type": et},
               "status": "ok" if cfg["search"] else "skipped"}
              for et, cfg in EVENT_CONFIG.items() if et not in covered]

    failed = 0
    for case in cases:
        result = retrieve_for_segment(case["segment"], store=store)
        errors = check(case, result)
        laws = ", ".join(f"{r['law_name']} {r['article_no']}({r['match']})" for r in result["legal_references"])
        print(f"{'✅' if not errors else '❌'} {case['name']}")
        print(f"   법령: {laws or '-'}")
        for e in errors:
            print(f"   - {e}")
        failed += bool(errors)
    print(f"\n통과 {len(cases) - failed}/{len(cases)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
