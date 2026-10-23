"""팀 공통 설정. 경로는 모두 이 파일 기준 상대경로라 PC가 달라도 동작합니다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 데이터 / 저장 위치
LAW_DIR = ROOT / "data" / "laws"
MANUAL_DIR = ROOT / "data" / "manuals"
CHROMA_DIR = ROOT / "chroma_db"          # Git에 올리지 않음 (build_kb.py로 재생성)
COLLECTION_NAME = "store_kb"

# 임베딩 모델: 팀원 모두 같은 모델을 써야 검색 결과가 같습니다.
# 용량이 부담되면 "jhgan/ko-sroberta-multitask"(약 400MB)로 바꾸고 재인덱싱하세요.
EMBEDDING_MODEL = "BAAI/bge-m3"

# 청킹 설정 (바꾸면 반드시 재인덱싱)
CHUNK_MAX_LEN = 800
CHUNK_OVERLAP = 100

# 검색 기본값
TOP_K = 4
