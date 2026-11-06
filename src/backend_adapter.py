"""백엔드(app/ai/interfaces.py) 연결용 어댑터.

백엔드의 Retriever.search는 document_chunks.id 목록(RetrievalHit)만 받는다.
이 파일은 백엔드 타입을 import하지 않고 dict로 돌려주므로, 백엔드 쪽 Retriever 구현에서
RetrievalHit(**hit)로 감싸기만 하면 된다. 예시는 docs/rag_output_schema.md '백엔드 연결' 참고.

chunk_id는 export_chunks.py가 만드는 document_chunks의 id와 같다.
"""
from typing import Any

from src.rag_service import retrieve_for_segment


def query_to_segment(query: Any, segment_id: str = "backend_query") -> dict:
    """RetrievalQuery(event_type, summary, claims, uncertain_points) -> retrieve_for_segment 입력 dict.

    RetrievalQuery에는 segment_id가 없으므로 자리표시 값을 넣는다 (결과 연결은 백엔드가 한다).
    confidence도 없으므로 확신도 경고는 붙지 않는다 (승인된 사건만 검색하므로 백엔드가 판단).
    """
    return {
        "segment_id": segment_id,
        "event_type": query.event_type,
        "summary": query.summary,
        "claims": list(query.claims or []),
        "uncertain_points": list(query.uncertain_points or []),
    }


def result_to_hits(result: dict) -> list[dict]:
    """retrieve_for_segment 결과 -> [{'chunk_id', 'rank', 'score'}]. 법령(rank 순) 다음 절차(진행 순).

    score: 검색 조문은 질의와의 거리(작을수록 가까움), 규칙 조문과 절차는 None. 순서는 rank를 따른다.
    status가 skipped(normal, unclear, 모르는 유형)면 빈 목록 = 백엔드의 '결과 없음'.
    """
    refs = result["legal_references"] + result["procedure_references"]
    return [{"chunk_id": r["chunk_id"], "rank": i, "score": r.get("distance")}
            for i, r in enumerate(refs, 1)]


def search_hits(query: Any, k_law: int = 3, store=None) -> list[dict]:
    """Retriever.search 본체. 장애(인덱스 없음 등)는 예외로 올라가므로 백엔드에서 RetrievalError로 감싼다."""
    return result_to_hits(retrieve_for_segment(query_to_segment(query), k_law=k_law, store=store))
