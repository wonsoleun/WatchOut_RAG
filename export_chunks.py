"""지식 베이스 문서를 백엔드 document_chunks 적재용 JSON으로 내보낸다.

조문 1개 / 매뉴얼 섹션 1개 = 행 1개. id는 retrieve_for_segment 결과의 chunk_id와 같다.
data/ 를 고치면 build_kb.py와 함께 이것도 다시 실행해 백엔드에 다시 적재한다.
모델이나 chroma_db/ 없이 data/만 읽는다.

사용법:
    python export_chunks.py                       # -> document_chunks.json
    python export_chunks.py -o path/to/out.json
"""
import argparse
import json
import sys
from pathlib import Path

from src.chunking import chunk_id, label
from src.loaders import load_all


def to_row(doc) -> dict:
    m = doc.metadata
    if m["doc_type"] == "law":
        text = m["article_text"]
    else:
        text = doc.page_content.split("\n", 1)[1].strip()  # "[제목 | 섹션]" 머리말 제거
    return {
        "id": chunk_id(doc),
        "doc_type": m["doc_type"],
        "title": label(doc),
        "text": text,
        "source_file": m["source"],
        "law_name": m.get("law_name"),
        "article_no": m.get("article_no"),
        "article_title": m.get("article_title"),
        "enforcement": m.get("enforcement") or None,
        "section": m.get("section"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, default=Path("document_chunks.json"))
    args = ap.parse_args()

    rows = [to_row(d) for d in load_all()]
    ids = [r["id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        sys.exit(f"[오류] 중복 id: {sorted(dup)}")
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"저장: {args.output} (법령 {sum(r['doc_type'] == 'law' for r in rows)}개, "
          f"매뉴얼 {sum(r['doc_type'] == 'manual' for r in rows)}개)")


if __name__ == "__main__":
    main()
