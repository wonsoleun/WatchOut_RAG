"""VLM 세그먼트 JSON 파일 1개를 넣어 RAG 출력 JSON을 확인한다.

사용법:
    python run_segment.py examples/sample_input.json
    python run_segment.py examples/sample_input.json -o out.json
"""
import argparse
import json
import sys
from pathlib import Path

from src.rag_service import retrieve_for_segment


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    segment = json.loads(args.input.read_text(encoding="utf-8"))
    result = retrieve_for_segment(segment)
    text = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"저장: {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
