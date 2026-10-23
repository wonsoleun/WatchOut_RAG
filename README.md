# CCTV 법률·대응 절차 RAG 지식 베이스

무인점포 CCTV 이상행동 리포트에 들어갈 **법령 조문**과 **경찰 수사 절차**를 검색하는 RAG 지식 베이스입니다.
(로컬 ChromaDB + 로컬 임베딩 `BAAI/bge-m3`, API 키 불필요)

## 폴더 구조

```
rag_kb/
├─ config.py                  # 경로·임베딩 모델·청킹 설정 (팀 공통)
├─ build_kb.py                # 인덱싱 (chroma_db 생성)
├─ test_retrieval.py          # Top-K 검색 테스트
├─ run_segment.py             # VLM JSON 1개 -> RAG 출력 JSON 확인
├─ requirements.txt
├─ data/
│  ├─ laws/                   # 법제처 PDF (형법, 개인정보 보호법 조문)
│  ├─ manuals/
│  │  ├─ police_procedure.md  # 경찰 수사 절차 안내도를 텍스트로 옮긴 파일
│  │  └─ police_procedure_original.jpg
│  └─ keywords.json           # 조문별 일상어 키워드 (검색 보강용)
├─ src/
│  ├─ loaders.py              # PDF/MD 로드, 노이즈 제거, 메타데이터
│  ├─ chunking.py             # 조문 단위 청킹
│  ├─ kb.py                   # get_retriever() — 검색기
│  ├─ query_builder.py        # event_type -> 검색 질의 매핑
│  ├─ rag_service.py          # retrieve_for_segment() — 팀원이 호출하는 진입점
│  └─ prompt_formatter.py     # RAG 결과 -> 리포트 AI 프롬프트용 텍스트
├─ docs/rag_output_schema.md  # RAG 출력 JSON 양식 (리포트 담당자용)
├─ examples/                  # sample_input.json (VLM 출력 예시), sample_report_prompt.txt
├─ tests/retrieval_cases.json # 검색 테스트 질문과 정답 조문
└─ chroma_db/                 # 자동 생성, Git 제외
```

## 시작하기 (Windows / VS Code)

OneDrive 바깥의 영문 경로(예: `C:\projects\rag_kb`)에 두는 것을 권장합니다.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python build_kb.py --dry-run   # 모델 다운로드 없이 청크 확인
python build_kb.py             # 인덱싱 (첫 실행은 bge-m3 약 2GB 다운로드)
python test_retrieval.py       # 검색 테스트
python test_retrieval.py -q "무인 매장에서 물건을 훔치면?"
```

## 협업 규칙

- **Git에 올리는 것**: 코드, `data/`, `tests/`, `requirements.txt`
- **Git에 올리지 않는 것**: `chroma_db/`, `.venv/`, `.env` (`.gitignore`에 설정됨)
- `git pull` 후 `data/`, `keywords.json`, `config.py`가 바뀌었다면 `python build_kb.py`를 다시 실행합니다.
- 임베딩 모델과 청킹 값은 `config.py`에서만 바꾸고, 바꾼 뒤에는 `test_retrieval.py` 결과(Hit@K)를 PR에 적어 주세요.
- 브랜치를 따서 작업하고 Pull Request로 합칩니다.

## 법령·매뉴얼 추가하기

1. 법제처 국가법령정보센터에서 조문 PDF를 받아 `data/laws/`에 넣습니다. (파일명은 영문 권장)
2. 일상어 검색이 필요하면 `data/keywords.json`에 `"형법 제329조": "키워드, ..."` 형태로 추가합니다.
3. 새 매뉴얼은 `data/manuals/`에 Markdown으로 넣고, 주제별로 `## 제목` 섹션을 나눕니다.
4. `tests/retrieval_cases.json`에 질문과 정답(`expect`)을 추가하고 `python build_kb.py` → `python test_retrieval.py`.

## VLM 파이프라인에서 쓰기

VLM이 만든 세그먼트 JSON을 넣으면 관련 법령과 수사 절차가 JSON으로 나옵니다. 출력 양식은 [docs/rag_output_schema.md](docs/rag_output_schema.md)를 보세요.

```python
from src.rag_service import retrieve_for_segment

result = retrieve_for_segment(segment_json)
```

검색기만 직접 쓸 때는 아래처럼 합니다.

```python
from src.kb import get_retriever

retriever = get_retriever(k=3)                 # doc_type="law" / "manual" 로 제한 가능
docs = retriever.invoke("야간 매장 기물 파손 시 법적 조치 절차는?")
context = "\n\n".join(d.page_content for d in docs)
```

## 알아둘 점

- `keywords.json`의 키워드는 검색 보강용으로 팀에서 추가한 것이며 법령 원문이 아닙니다. 리포트에 조문을 인용할 때는 `[법령명 제N조(제목)]` 아래의 원문 부분을 기준으로 하세요.
- 현재 개인정보 보호법은 제4조, 제59조, 제71조만 들어 있습니다. CCTV 관련 조항(제25조 등)은 추가가 필요합니다.
- 법령은 개정될 수 있으므로 PDF 상단의 시행일(메타데이터 `enforcement`)을 확인하세요.
