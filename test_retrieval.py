"""검색 성능 테스트. tests/retrieval_cases.json 의 각 질문이 Top-K 안에서 정답 조문/섹션을 찾는지 확인.

사용법:
    python test_retrieval.py            # 전체 케이스
    python test_retrieval.py -k 3       # Top-3 기준
    python test_retrieval.py -q "무인 매장에서 물건을 훔치면?"   # 질문 하나만 확인
"""
import argparse
import json

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
    db = get_vectorstore()

    if query:
        print(f"Q. {query}")
        show(db, query, k)
        return

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    hit = 0
    for case in cases:
        print(f"Q. {case['query']}   (정답: {', '.join(case['expect'])})")
        found = show(db, case["query"], k)
        ok = any(e in f for e in case["expect"] for f in found)
        hit += ok
        print("   ->", "✅ HIT" if ok else "❌ MISS", "\n")
    print(f"Hit@{k}: {hit}/{len(cases)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=config.TOP_K)
    ap.add_argument("-q", "--query")
    args = ap.parse_args()
    main(args.k, args.query)
