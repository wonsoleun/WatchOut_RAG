"""지식 베이스 인덱싱. 데이터/설정이 바뀔 때마다 다시 실행하면 DB를 새로 만듭니다.

사용법:
    python build_kb.py             # 인덱싱 (chroma_db 재생성)
    python build_kb.py --dry-run   # 임베딩 없이 청크만 확인 (모델 다운로드 불필요)
"""
import argparse

import config
from src.chunking import chunk, label
from src.loaders import load_all


def main(dry_run: bool) -> None:
    docs = load_all()
    chunks = chunk(docs)
    print(f"문서 {len(docs)}개 -> 청크 {len(chunks)}개")

    for c in chunks:
        print(f"  - {label(c):<28} {len(c.page_content):>4}자  ({c.metadata['source']})")

    if dry_run:
        print("\n[dry-run] 임베딩/저장은 건너뜀")
        return

    from langchain_chroma import Chroma

    from src.kb import get_embeddings  # 모델 로드는 필요할 때만

    embeddings = get_embeddings()

    # 같은 DB에 중복 저장되지 않도록 기존 컬렉션을 지우고 다시 만든다.
    Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(config.CHROMA_DIR),
    ).delete_collection()

    ids = [f"{c.metadata['source']}::{i}" for i, c in enumerate(chunks)]
    Chroma.from_documents(
        chunks,
        embeddings,
        ids=ids,
        collection_name=config.COLLECTION_NAME,
        persist_directory=str(config.CHROMA_DIR),
    )
    print(f"\n{len(chunks)}개 청크를 {config.CHROMA_DIR} 에 저장했습니다.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
