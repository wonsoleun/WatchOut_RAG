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

SCHEMA_VERSION = "1.1"
REQUIRED_FIELDS = ("segment_id", "event_type")
KEYWORD_LINE_RE = re.compile(r"^\(관련 키워드:.*\)$")
PARAGRAPH_RE = re.compile(r"^[①-⑳]", re.MULTILINE)  # 항 표시 ①~⑳
LOW_CONFIDENCE = {"low", "낮음"}


def _clean_text(doc: Document) -> str:
    """검색용 머리말과 보강 키워드 줄을 제거하고 조문/절차 본문만 남긴다."""
    lines = doc.page_content.splitlines()
    if lines and lines[0].startswith("["):
        lines = lines[1:]
    return "\n".join(ln for ln in lines if not KEYWORD_LINE_RE.match(ln.strip())).strip()


def _get_docs(store, where: dict) -> list[Document]:
    """메타데이터 조건으로 청크를 가져온다 (인덱싱 순서대로)."""
    res = store.get(where=where, include=["documents", "metadatas"])
    rows = sorted(zip(res["ids"], res["documents"], res["metadatas"]),
                  key=lambda r: int(r[0].rsplit("::", 1)[1]))
    return [Document(page_content=d, metadata=m) for _, d, m in rows]


def _split_paragraphs(text: str) -> dict[str, str]:
    """조문 본문 -> {'④': '④ 다음 각 호의 ...\\n1. ...', ...}. 항 표시(①)로 시작하는 줄 기준."""
    parts: dict[str, str] = {}
    starts = [m.start() for m in PARAGRAPH_RE.finditer(text)]
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        parts[text[s]] = text[s:end].strip()
    return parts


def _core_articles(store, entries: list) -> tuple[list[tuple[Document, str, list[str]]], list[str]]:
    """EVENT_CONFIG의 core_articles -> [(조문 청크, 넣을 본문, 고른 항)], 지식 베이스에 없는 항목.

    항목은 '형법 제329조'(조문 전체) 또는 {'article': ..., 'paragraphs': ['④', '⑧']}(그 항만).
    청크가 아니라 조문 전체 본문(metadata article_text)에서 잘라 내므로, 긴 조문이 어떻게 나뉘었든 결과가 같다.
    """
    found, missing = [], []
    for entry in entries:
        key, wanted = (entry, []) if isinstance(entry, str) else (entry["article"], entry["paragraphs"])
        law_name, article_no = key.rsplit(" ", 1)
        docs = _get_docs(store, {"$and": [
            {"doc_type": "law"}, {"law_name": law_name}, {"article_no": article_no},
        ]})
        if not docs:
            missing.append(key)
            continue
        full = docs[0].metadata["article_text"]
        if not wanted:
            found.append((docs[0], full, []))
            continue
        parts = _split_paragraphs(full)
        missing += [f"{key} {p}" for p in wanted if p not in parts]
        picked = [p for p in parts if p in wanted]  # 조문 순서대로
        if picked:
            found.append((docs[0], "\n".join(parts[p] for p in picked), picked))
    return found, missing


def _search(store, queries: list[str], doc_type: str, k: int,
            max_distance: float | None = None) -> list[tuple[Document, float]]:
    """여러 질의의 결과를 합치고, 같은 조문/섹션은 가장 가까운 청크 하나만 남겨 상위 k개를 반환."""
    best: dict[str, tuple[Document, float]] = {}
    for q in queries:
        for doc, dist in store.similarity_search_with_score(q, k=k, filter={"doc_type": doc_type}):
            if max_distance is not None and dist > max_distance:
                continue
            key = label(doc)  # 긴 조문이 여러 청크로 나뉘어도 결과에는 한 번만
            if key not in best or dist < best[key][1]:
                best[key] = (doc, dist)
    return sorted(best.values(), key=lambda x: x[1])[:k]


def _law_item(rank: int, doc: Document, dist: float | None,
              text: str | None = None, paragraphs: list[str] | None = None) -> dict:
    m = doc.metadata
    return {
        "rank": rank,
        "match": "rule" if dist is None else "search",
        "law_name": m["law_name"],
        "article_no": m["article_no"],
        "article_title": m["article_title"],
        "paragraphs": paragraphs or [],  # 일부 항만 넣었으면 그 항 목록 (예: ['④', '⑧']), 비어 있으면 아님
        "text": text if text is not None else _clean_text(doc),
        "source_file": m["source"],
        "enforcement": m.get("enforcement", ""),
        "distance": None if dist is None else round(float(dist), 4),
    }


def _procedure_item(rank: int, doc: Document) -> dict:
    m = doc.metadata
    return {
        "rank": rank,
        "section": m["section"],
        "text": _clean_text(doc),
        "source_file": m["source"],
    }


def retrieve_for_segment(segment: dict, k_law: int = 3, store=None) -> dict:
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
        "queries": {"legal": []},
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

    if str(segment.get("confidence", "")).strip().lower() in LOW_CONFIDENCE:
        result["warnings"].append(
            "VLM 분석 확신도가 낮습니다. 이상행동 자체가 확인되지 않았을 수 있으니 사람이 영상을 검토한 뒤 법령을 적용하세요."
        )
    if cfg.get("note"):
        result["warnings"].append(cfg["note"])

    store = store or get_vectorstore()

    # 1) 규칙으로 고정된 조문 -> 2) 벡터 검색으로 찾은 관련 조문 (거리 임계값 이내, 중복 제외)
    queries = build_queries(segment)
    result["queries"]["legal"] = queries
    core, missing = _core_articles(store, cfg.get("core_articles", []))
    for key in missing:
        result["warnings"].append(f"설정된 핵심 조문이 지식 베이스에 없습니다: {key}")
    items = [_law_item(0, d, None, text, picked) for d, text, picked in core]
    taken = {label(d) for d, _, _ in core}
    for doc, dist in _search(store, queries, "law", k_law, config.LAW_MAX_DISTANCE):
        if label(doc) not in taken and len(items) < k_law:
            items.append(_law_item(0, doc, dist))
    for i, item in enumerate(items, 1):
        item["rank"] = i
    result["legal_references"] = items

    # 절차는 검색하지 않고 설정된 섹션을 순서대로 가져온다
    sections = cfg.get("procedures", [])
    if sections:
        docs = {d.metadata["section"]: d for d in _get_docs(store, {"$and": [
            {"doc_type": "manual"}, {"section": {"$in": sections}},
        ]})}
        for s in sections:
            if s not in docs:
                result["warnings"].append(f"설정된 절차 섹션이 지식 베이스에 없습니다: {s}")
        ordered = [docs[s] for s in sections if s in docs]
        result["procedure_references"] = [_procedure_item(i, d) for i, d in enumerate(ordered, 1)]

    if not cfg["covered"]:
        result["warnings"].append(
            f"'{cfg['label']}'에 해당하는 법령이 지식 베이스에 없습니다. legal_references는 참고용이며 근거로 인용하지 마세요."
        )
    if not result["legal_references"]:
        result["warnings"].append("관련성이 충분한 법령을 찾지 못했습니다. 법령 항목은 '해당 조문 없음'으로 작성하세요.")
    return result
