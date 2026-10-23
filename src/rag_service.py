"""VLM 세그먼트 JSON -> 관련 법령/수사 절차 JSON.

리포트 담당자는 이 파일의 retrieve_for_segment()만 호출하면 됩니다.
출력 양식은 docs/rag_output_schema.md 참고.
"""
import re

from langchain_core.documents import Document

import config
from src.chunking import label
from src.kb import get_vectorstore
from src.query_builder import EVENT_CONFIG, build_queries

SCHEMA_VERSION = "1.0"
REQUIRED_FIELDS = ("segment_id", "event_type")
KEYWORD_LINE_RE = re.compile(r"^\(관련 키워드:.*\)$")


def _clean_text(doc: Document) -> str:
    """검색용 머리말과 보강 키워드 줄을 제거하고 조문/절차 본문만 남긴다."""
    lines = doc.page_content.splitlines()
    if lines and lines[0].startswith("["):
        lines = lines[1:]
    return "\n".join(ln for ln in lines if not KEYWORD_LINE_RE.match(ln.strip())).strip()


def _search(store, queries: list[str], doc_type: str, k: int) -> list[tuple[Document, float]]:
    """여러 질의의 결과를 합치고, 같은 문서는 가장 가까운 거리만 남겨 상위 k개를 반환."""
    best: dict[str, tuple[Document, float]] = {}
    for q in queries:
        for doc, dist in store.similarity_search_with_score(q, k=k, filter={"doc_type": doc_type}):
            key = f"{doc.metadata['source']}::{label(doc)}::{hash(doc.page_content)}"
            if key not in best or dist < best[key][1]:
                best[key] = (doc, dist)
    return sorted(best.values(), key=lambda x: x[1])[:k]


def _law_item(rank: int, doc: Document, dist: float) -> dict:
    m = doc.metadata
    return {
        "rank": rank,
        "law_name": m["law_name"],
        "article_no": m["article_no"],
        "article_title": m["article_title"],
        "text": _clean_text(doc),
        "source_file": m["source"],
        "enforcement": m.get("enforcement", ""),
        "distance": round(float(dist), 4),
    }


def _procedure_item(rank: int, doc: Document, dist: float) -> dict:
    m = doc.metadata
    return {
        "rank": rank,
        "section": m["section"],
        "text": _clean_text(doc),
        "source_file": m["source"],
        "distance": round(float(dist), 4),
    }


def retrieve_for_segment(segment: dict, k_law: int = 3, k_procedure: int = 2, store=None) -> dict:
    """VLM 세그먼트 1개 -> RAG 결과 1개."""
    for f in REQUIRED_FIELDS:
        if not segment.get(f):
            raise ValueError(f"필수 필드 누락: {f}")

    event_type = segment["event_type"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "segment_id": segment["segment_id"],
        "video_id": segment.get("video_id"),
        "event_type": event_type,
        "status": "ok",
        "warnings": [],
        "queries": {"legal": [], "procedure": []},
        "legal_references": [],
        "procedure_references": [],
    }

    cfg = EVENT_CONFIG.get(event_type)
    if cfg is None:
        result["status"] = "skipped"
        result["warnings"].append(f"알 수 없는 event_type: {event_type}")
        return result
    if not cfg["search"]:
        result["status"] = "skipped"
        result["warnings"].append(f"event_type '{event_type}'은(는) 법령 검색 대상이 아닙니다.")
        return result

    store = store or get_vectorstore()
    queries = build_queries(segment)
    result["queries"] = queries

    laws = _search(store, queries["legal"], "law", k_law)
    procs = _search(store, queries["procedure"], "manual", k_procedure)
    result["legal_references"] = [_law_item(i, d, s) for i, (d, s) in enumerate(laws, 1)]
    result["procedure_references"] = [_procedure_item(i, d, s) for i, (d, s) in enumerate(procs, 1)]

    if not cfg["covered"]:
        result["warnings"].append(
            f"'{cfg['label']}'에 해당하는 법령이 지식 베이스에 없습니다. legal_references는 참고용이며 근거로 인용하지 마세요."
        )
    return result
