"""법제처 PDF -> data/laws/laws.json 초안 생성 (법령을 추가/개정할 때 1회 실행).

PDF 줄바꿈은 원래 띄어쓰기였는지 알 수 없어서 공백 없이 이어 붙인다.
출력의 '[검수]' 목록을 보고 laws.json을 원문과 대조해 손으로 고친 뒤 커밋하세요.
build_kb.py는 PDF가 아니라 laws.json만 읽습니다.

사용법:
    python pdf_to_json.py                 # data/laws/*.pdf -> data/laws/laws_draft.json
    python pdf_to_json.py -o data/laws/laws.json   # 기존 파일을 덮어씀 (검수 내용이 사라지니 주의)
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import pymupdf  # pymupdf >= 1.24.3
except ImportError:  # 구버전 호환
    import fitz as pymupdf

import config

# 줄 시작에서 "제329조(절도)" 형태만 조문 제목으로 인정.
# 제목에 숫자가 없어야 "제28조의2(제26조제8항에 따라..." 같은 본문 속 인용을 걸러낼 수 있음.
ARTICLE_RE = re.compile(r"^[ \t]*(제\d+조(?:의\d+)?)\(([^)\d]{1,30})\)", re.MULTILINE)
CHAPTER_RE = re.compile(r"^제\d+장\s*[^\n]+", re.MULTILINE)
ENFORCE_RE = re.compile(r"\[시행\s*([^\]]+)\]")
FOOTER_RE = re.compile(r"^법제처\s*\d*\s*국가법령정보센터\s*$")
CONTACT_RE = re.compile(r"^.+\(.*\)\s*[\d~\-, ]+$")  # "법무부 (형사법제과) 02-2110-3307~8"
PHONE_TAIL_RE = re.compile(r"^[\d, ]+$")  # 연락처가 줄바꿈되어 남은 숫자 줄
# 새 줄로 유지할 시작: 항(①), 호(1.), 목(가.), 조문 제목
BREAK_BEFORE_RE = re.compile(r"^([①-⑳]|\d+\.\s|[가-하]\.\s|제\d+조(?:의\d+)?\()")
# "<개\n정 1995. 12. 29.>"처럼 표시 중간에서 줄이 끊긴 경우도 잡는다
AMEND_RE = re.compile(
    r"\s*(<\s*(?:개\s*정|신\s*설|전\s*문\s*개\s*정)[^>]*>|\[\s*(?:제\s*목\s*개\s*정|전\s*문\s*개\s*정|본\s*조\s*신\s*설)[^\]]*\])"
)


def _clean_lines(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or FOOTER_RE.match(ln) or CONTACT_RE.match(ln) or PHONE_TAIL_RE.match(ln):
            continue
        out.append(ln)
    return out


def _join_wrapped(lines: list[str], review: list[str]) -> str:
    """PDF 폭 때문에 끊긴 줄을 이어 붙인다. 이어 붙인 지점은 review에 기록."""
    out: list[str] = []
    for ln in lines:
        if out and not BREAK_BEFORE_RE.match(ln):
            review.append(f"...{out[-1][-8:]}|{ln[:8]}...")
            out[-1] += ln
        else:
            out.append(ln)
    return "\n".join(out)


def _normalize_amendment(raw: str) -> str:
    """'<개\n정 2016. 3. 29.>' -> '개정 2016. 3. 29.'"""
    m = re.match(r"([^\d]*)(.*)", raw.strip("<>[] \n"), re.DOTALL)
    kind = re.sub(r"\s+", "", m.group(1))
    dates = re.sub(r"\s+", " ", m.group(2)).strip()
    return f"{kind} {dates}"


def parse_pdf(path: Path, keywords: dict[str, list[str]]) -> list[dict]:
    with pymupdf.open(path) as pdf:
        raw = "\n".join(page.get_text() for page in pdf)

    lines = _clean_lines(raw)
    law_name = lines[0]  # 머리말 첫 줄이 법령명 ("형법", "개인정보 보호법")
    enforce = (ENFORCE_RE.search(raw) or [None, ""])[1].strip()
    text = "\n".join(lines)

    items = []
    matches = list(ARTICLE_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        article_no, title = m.group(1), m.group(2).strip()
        key = f"{law_name} {article_no}"
        body = text[m.end():end]
        # 개정 표시는 줄바꿈을 걸쳐 있을 수 있으므로 이어 붙이기 전에 떼어 낸다
        amendments = [_normalize_amendment(a) for a in AMEND_RE.findall(body)]
        body = AMEND_RE.sub("", body)
        review: list[str] = []
        body = _join_wrapped(body.strip().splitlines(), review)
        chapters = CHAPTER_RE.findall(text[:m.start()])
        items.append({
            "law_name": law_name,
            "article_no": article_no,
            "article_title": title,
            "chapter": chapters[-1].strip() if chapters else "",
            "enforcement": enforce,
            "text": body,
            "amendments": amendments,
            "keywords": keywords.get(key, []),
            "source_pdf": path.name,
        })
        print(f"[검수] {key}: 이어 붙인 곳 {len(review)}개" + ("" if items[-1]["chapter"] else ", chapter 비어 있음"))
        for r in review:
            print(f"    {r}")
    if not matches:
        print(f"[경고] 조문을 찾지 못했습니다: {path.name}")
    return items


def main(output: Path) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    # 키워드는 사람이 관리하는 값이므로 기존 laws.json에서 그대로 가져온다
    keywords = {}
    if config.LAW_JSON.exists():
        for a in json.loads(config.LAW_JSON.read_text(encoding="utf-8")):
            keywords[f"{a['law_name']} {a['article_no']}"] = a.get("keywords", [])
    items: list[dict] = []
    for p in sorted(config.LAW_DIR.glob("*.pdf")):
        items += parse_pdf(p, keywords)
    output.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n조문 {len(items)}개 -> {output}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, default=config.LAW_DIR / "laws_draft.json")
    main(ap.parse_args().output)
