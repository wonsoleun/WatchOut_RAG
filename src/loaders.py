"""법령 JSON / 매뉴얼 Markdown -> LangChain Document 변환.

법령 PDF 파싱은 pdf_to_json.py가 담당하고, 여기서는 검수된 data/laws/laws.json만 읽는다.
"""
import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

import config


def load_law_json(path: Path = config.LAW_JSON) -> list[Document]:
    docs = []
    for a in json.loads(path.read_text(encoding="utf-8")):
        header = f"[{a['law_name']} {a['article_no']}({a['article_title']})]"
        docs.append(Document(
            page_content=f"{header}\n{a['text']}",
            metadata={
                "doc_type": "law",
                "law_name": a["law_name"],
                "article_no": a["article_no"],
                "article_title": a["article_title"],
                "chapter": a.get("chapter", ""),
                "enforcement": a.get("enforcement", ""),
                # Chroma 메타데이터는 리스트를 못 넣으므로 문자열로 저장. 청킹 때 본문 끝에 붙임.
                "keywords": ", ".join(a.get("keywords", [])),
                # 조문 전체 본문. 청크와 상관없이 규칙 조문(core_articles)의 항을 골라 내는 데 씀
                "article_text": a["text"],
                "source": a["source_pdf"],
            },
        ))
    return docs


def load_manual_md(path: Path) -> list[Document]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "title"), ("##", "section")],
        strip_headers=True,
    )
    docs = []
    for d in splitter.split_text(path.read_text(encoding="utf-8")):
        section = d.metadata.get("section")
        if not section:  # '## ' 없는 머리말(출처 줄 등)은 제외
            continue
        title = d.metadata.get("title", path.stem)
        docs.append(Document(
            page_content=f"[{title} | {section}]\n{d.page_content}",
            metadata={
                "doc_type": "manual",
                "section": section,
                "title": title,
                "source": path.name,
            },
        ))
    return docs


def load_all() -> list[Document]:
    docs = load_law_json()
    for p in sorted(config.MANUAL_DIR.glob("*.md")):
        docs += load_manual_md(p)
    return docs
