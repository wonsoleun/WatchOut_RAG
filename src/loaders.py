"""법령 PDF / 매뉴얼 Markdown -> LangChain Document 변환."""
import json
import re
from pathlib import Path

try:
    import pymupdf  # pymupdf >= 1.24.3
except ImportError:  # 구버전 호환
    import fitz as pymupdf

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

import config

# 줄 시작에서 "제329조(절도)" 형태만 조문 제목으로 인정.
# 제목에 숫자가 없어야 "제28조의2(제26조제8항에 따라..." 같은 본문 속 인용을 걸러낼 수 있음.
ARTICLE_RE = re.compile(r"^[ \t]*(제\d+조(?:의\d+)?)\(([^)\d]{1,30})\)", re.MULTILINE)
CHAPTER_RE = re.compile(r"제\d+장\s*[^\n]+")
ENFORCE_RE = re.compile(r"\[시행\s*([^\]]+)\]")
FOOTER_RE = re.compile(r"^법제처\s*\d*\s*국가법령정보센터\s*$")
CONTACT_RE = re.compile(r"^(법무부|개인정보보호위원회)\s*\(.*")
PHONE_TAIL_RE = re.compile(r"^[\d, ]+$")  # 연락처가 줄바꿈되어 남은 숫자 줄


def _load_keywords() -> dict[str, str]:
    """data/keywords.json: '형법 제329조' -> '도둑, 훔치다, ...' (일상어 검색 보강용)"""
    path = config.ROOT / "data" / "keywords.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_lines(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or FOOTER_RE.match(ln) or CONTACT_RE.match(ln) or PHONE_TAIL_RE.match(ln):
            continue
        out.append(ln)
    return out


def load_law_pdf(path: Path, keywords: dict[str, str] | None = None) -> list[Document]:
    keywords = keywords if keywords is not None else _load_keywords()
    with pymupdf.open(path) as pdf:
        raw = "\n".join(page.get_text() for page in pdf)

    law_name = "개인정보 보호법" if "개인정보 보호법" in raw[:200] else "형법"
    enforce = (ENFORCE_RE.search(raw) or [None, ""])[1]

    # 노이즈 제거 후 조문 단위로 분리
    lines = _clean_lines(raw)
    # 머리말(법령명 2줄, [시행...] 줄)은 조문 이전 영역이므로 조문 시작 전 줄은 장(chapter) 추출에만 사용
    text = "\n".join(lines)
    matches = list(ARTICLE_RE.finditer(text))
    docs = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end].strip()
        chapter_m = CHAPTER_RE.findall(text[:m.start()])
        article_no, title = m.group(1), m.group(2).strip()
        key = f"{law_name} {article_no}"
        header = f"[{law_name} {article_no}({title})]"
        content = f"{header}\n{body}"
        extra = keywords.get(key)
        if extra:
            content += f"\n(관련 키워드: {extra})"
        docs.append(Document(
            page_content=content,
            metadata={
                "doc_type": "law",
                "law_name": law_name,
                "article_no": article_no,
                "article_title": title,
                "chapter": chapter_m[-1].strip() if chapter_m else "",
                "enforcement": enforce,
                "source": path.name,
            },
        ))
    if not docs:
        print(f"[경고] 조문을 찾지 못했습니다: {path.name}")
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
    keywords = _load_keywords()
    docs: list[Document] = []
    for p in sorted(config.LAW_DIR.glob("*.pdf")):
        docs += load_law_pdf(p, keywords)
    for p in sorted(config.MANUAL_DIR.glob("*.md")):
        docs += load_manual_md(p)
    return docs
