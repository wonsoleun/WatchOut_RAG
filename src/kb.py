"""벡터 DB 접근 공용 모듈. VLM 파이프라인에서도 이 파일의 get_retriever()만 부르면 됩니다."""
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import config


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )


def get_vectorstore(embeddings=None) -> Chroma:
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=embeddings or get_embeddings(),
        persist_directory=str(config.CHROMA_DIR),
    )


def get_retriever(k: int = config.TOP_K, doc_type: str | None = None):
    """doc_type: 'law' 또는 'manual' 로 제한할 수 있음 (None이면 전체)."""
    kwargs = {"k": k}
    if doc_type:
        kwargs["filter"] = {"doc_type": doc_type}
    return get_vectorstore().as_retriever(search_kwargs=kwargs)
