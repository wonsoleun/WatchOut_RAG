"""조문/섹션 단위를 기본으로 하고, 길이가 긴 것만 분할."""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config


def chunk(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_MAX_LEN,
        chunk_overlap=config.CHUNK_OVERLAP,
        # 법령 JSON은 항·호마다 줄이 바뀌므로 줄바꿈이 곧 항·호 경계 -> 문장 끝 -> 공백 순
        separators=["\n\n", "\n", ". ", "다. ", " ", ""],
    )
    out: list[Document] = []
    for d in docs:
        keywords = d.metadata.get("keywords")
        if len(d.page_content) <= config.CHUNK_MAX_LEN:
            pieces = [d.page_content]
        else:
            header = d.page_content.split("\n", 1)[0]  # "[법령명 제N조(제목)]" 머리말
            # 분할된 뒤쪽 조각에도 어느 조문인지 머리말을 붙임
            pieces = [p if j == 0 else f"{header}\n{p}"
                      for j, p in enumerate(splitter.split_text(d.page_content))]
        for piece in pieces:
            if keywords:  # 일상어 검색 보강용 키워드는 모든 조각에 붙임
                piece += f"\n(관련 키워드: {keywords})"
            out.append(Document(page_content=piece, metadata=dict(d.metadata)))
    return out


def label(doc: Document) -> str:
    """검색 결과 표시/테스트 판정용 식별자. 예) '형법 제329조' / '3단계 결정 - 1. 송치 결정'"""
    m = doc.metadata
    if m.get("doc_type") == "law":
        return f"{m['law_name']} {m['article_no']}"
    return m.get("section", m.get("source", "?"))
