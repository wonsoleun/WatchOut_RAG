"""벡터 DB 접근 공용 모듈. VLM 파이프라인에서도 이 파일의 get_retriever()만 부르면 됩니다."""
import hashlib
import warnings
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import config

# 청크 메타데이터 구조를 바꾸면 올림 -> 예전 인덱스를 쓰면 재빌드 경고가 나옴
INDEX_FORMAT = "2"  # 2: article_text 추가


def build_fingerprint() -> str:
    """인덱스에 영향을 주는 데이터·설정의 해시. build_kb.py가 컬렉션에 저장하고, 열 때 비교한다."""
    h = hashlib.sha256()
    for p in [config.LAW_JSON, *sorted(config.MANUAL_DIR.glob("*.md"))]:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    h.update(f"{config.EMBEDDING_MODEL}|{config.CHUNK_MAX_LEN}|{config.CHUNK_OVERLAP}".encode())
    h.update(INDEX_FORMAT.encode())
    return h.hexdigest()[:16]


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    # 모델 로딩이 무거우므로(bge-m3 약 2GB) 프로세스당 한 번만 로드
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def _default_store() -> Chroma:
    store = Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(config.CHROMA_DIR),
    )
    built = (store._collection.metadata or {}).get("build_fingerprint")
    if built != build_fingerprint():
        warnings.warn(
            "chroma_db가 현재 data/ 또는 config.py와 다릅니다. `python build_kb.py`로 다시 인덱싱하세요.",
            stacklevel=3,
        )
    return store


def get_vectorstore(embeddings=None) -> Chroma:
    if embeddings is None:
        return _default_store()
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(config.CHROMA_DIR),
    )


def get_retriever(k: int = config.TOP_K, doc_type: str | None = None):
    """doc_type: 'law' 또는 'manual' 로 제한할 수 있음 (None이면 전체)."""
    kwargs = {"k": k}
    if doc_type:
        kwargs["filter"] = {"doc_type": doc_type}
    return get_vectorstore().as_retriever(search_kwargs=kwargs)
