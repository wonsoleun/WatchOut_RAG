# CCTV 법률·대응 절차 RAG 지식 베이스

무인점포 CCTV 이상행동 리포트에 들어갈 **법령 조문**과 **경찰 수사 절차**를 검색하는 RAG 지식 베이스입니다.
(로컬 ChromaDB + 로컬 임베딩 `BAAI/bge-m3`, API 키 불필요)

## 폴더 구조

```
rag_kb/
├─ config.py                  # 경로·임베딩 모델·청킹 설정 (팀 공통)
├─ build_kb.py                # 인덱싱 (chroma_db 생성)
├─ pdf_to_json.py             # 법령 PDF -> laws.json 초안 (법령 추가/개정 때만)
├─ test_retrieval.py          # Top-K 검색 테스트
├─ test_segments.py           # event_type별 결과 규칙 테스트
├─ run_segment.py             # VLM JSON 1개 -> RAG 출력 JSON 확인
├─ requirements.txt
├─ data/
│  ├─ laws/
│  │  ├─ laws.json            # 검수된 조문 데이터 + 일상어 키워드 (인덱싱은 이 파일만 읽음)
│  │  └─ *.pdf                # 법제처 원본 PDF (증빙 보관용)
│  └─ manuals/
│     ├─ police_procedure.md  # 경찰 수사 절차 안내도를 텍스트로 옮긴 파일
│     └─ police_procedure_original.jpg
├─ src/
│  ├─ loaders.py              # laws.json / MD 로드, 메타데이터
│  ├─ chunking.py             # 조문 단위 청킹
│  ├─ kb.py                   # get_retriever() — 검색기
│  ├─ query_builder.py        # event_type -> 핵심 조문, 검색 질의, 절차 단계 설정
│  ├─ rag_service.py          # retrieve_for_segment() — 팀원이 호출하는 진입점
│  └─ prompt_formatter.py     # RAG 결과 -> 리포트 AI 프롬프트용 텍스트
├─ docs/rag_output_schema.md  # RAG 출력 JSON 양식 (리포트 담당자용)
├─ examples/                  # sample_input.json (VLM 출력 예시), sample_report_prompt.txt
├─ tests/                     # retrieval_cases.json (검색), segment_cases.json (세그먼트 결과)
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
python test_segments.py        # event_type별 결과 테스트
```

## 협업 규칙

- **Git에 올리는 것**: 코드, `data/`, `tests/`, `requirements.txt`
- **Git에 올리지 않는 것**: `chroma_db/`, `.venv/`, `.env` (`.gitignore`에 설정됨)
- `git pull` 후 `data/`, `config.py`가 바뀌었다면 `python build_kb.py`를 다시 실행합니다. (인덱스가 오래되면 검색할 때 경고가 나옵니다)
- 임베딩 모델과 청킹 값은 `config.py`에서만 바꾸고, 바꾼 뒤에는 `test_retrieval.py` 결과(Hit@K)를 PR에 적어 주세요.
- 브랜치를 따서 작업하고 Pull Request로 합칩니다.

## 법령·매뉴얼 추가하기

1. 법제처 국가법령정보센터에서 조문 PDF를 받아 `data/laws/`에 넣습니다. (파일명은 영문 권장)
2. `python pdf_to_json.py` → `data/laws/laws_draft.json` 초안이 생깁니다. 출력의 `[검수]` 목록(PDF 줄바꿈을 이어 붙인 곳)을 원문과 대조해 띄어쓰기를 고치고, 비어 있는 `chapter`를 채운 뒤 새 조문을 `laws.json`에 옮깁니다. (기존 조문의 `keywords`는 초안에 자동으로 옮겨집니다)
3. 일상어 검색이 필요하면 그 조문의 `keywords` 목록에 추가합니다. 키워드는 검색 보강용이며 출력 `text`에는 들어가지 않습니다.
4. 새 매뉴얼은 `data/manuals/`에 Markdown으로 넣고, 주제별로 `## 제목` 섹션을 나눕니다.
5. 특정 event_type에 항상 넣을 조문이나 절차는 `src/query_builder.py`의 `core_articles`, `procedures`에 적습니다. 긴 조문은 `{"article": "국민건강증진법 제9조", "paragraphs": ["④", "⑧"]}`처럼 필요한 항만 넣을 수 있습니다.
6. `tests/retrieval_cases.json`에 질문과 정답(`expect`, label과 정확히 같은 문자열)을 추가하고 `python build_kb.py` → `python test_retrieval.py` → `python test_segments.py`.

## VLM 파이프라인에서 쓰기

VLM이 만든 세그먼트 JSON을 넣으면 관련 법령과 수사 절차가 JSON으로 나옵니다. 출력 양식은 [docs/rag_output_schema.md](docs/rag_output_schema.md)를 보세요.

### 실행 흐름 (영상 세그먼트마다)

```
VLM 세그먼트 JSON
   │  RAG가 읽는 필드: segment_id, event_type, summary, confidence
   ▼
retrieve_for_segment()                    (src/rag_service.py)
   ├─ event_type → 핵심 조문 고정 포함 (예: unpaid_exit → 형법 제329조)
   ├─ 미리 정한 질의 + summary → 벡터 검색으로 관련 조문 추가 (거리 config.LAW_MAX_DISTANCE 이하만)
   ├─ 경찰 절차: 접수 → 수사 → 결정 순서로 고정
   └─ 경고: 확신도 낮음, 장시간 체류 등
   ▼
RAG 출력 JSON (legal_references, procedure_references, warnings)
   ▼
build_report_prompt(세그먼트, RAG 결과)    (src/prompt_formatter.py)
   └─ claims(근거 프레임), uncertain_points 등을 여기서 함께 넣음
   ▼
리포트 생성 LLM → 리포트
```

| VLM 필드 | 법령 검색에 쓰이나 | 쓰이는 곳 |
|---|---|---|
| `event_type` | **핵심** | 어떤 조문과 절차를 넣을지 결정 |
| `summary` | 보조 | 벡터 검색 질의로 추가 |
| `confidence` | 경고만 | `low`이면 경고 추가 |
| `claims` | 안 쓰임 | 리포트 프롬프트의 [확인된 사실과 근거 프레임] |
| `uncertain_points` | 안 쓰임 | 리포트 프롬프트의 [불확실한 점] |

- 어떤 범죄인지는 VLM의 `event_type`으로 정해집니다. `event_type`이 틀리면 조문도 틀립니다.
- event_type별 핵심 조문·검색 질의·절차는 `src/query_builder.py`의 `EVENT_CONFIG`에서 설정합니다.

```python
from src.prompt_formatter import build_report_prompt
from src.rag_service import retrieve_for_segment

result = retrieve_for_segment(segment_json)
prompt = build_report_prompt(segment_json, result)   # 리포트 생성 LLM에 넣을 프롬프트
```

검색기만 직접 쓸 때는 아래처럼 합니다.

```python
from src.kb import get_retriever

retriever = get_retriever(k=3)                 # doc_type="law" / "manual" 로 제한 가능
docs = retriever.invoke("야간 매장 기물 파손 시 법적 조치 절차는?")
context = "\n\n".join(d.page_content for d in docs)
```

## ⚠️ 출력 JSON 변경 주의 (schema_version 1.0 → 1.1)

RAG 출력을 받아 쓰는 코드(리포트 생성, 백엔드)가 1.0 기준이면 아래를 확인하세요. 자세한 양식은 [docs/rag_output_schema.md](docs/rag_output_schema.md)에 있습니다.

| 변경 | 내용 | 받는 쪽에서 할 일 |
|---|---|---|
| `legal_references[].match` 추가 | `rule`(event_type별 고정 조문) / `search`(벡터 검색으로 찾은 조문) | `rule` 위주로 쓰고 `search`는 참고 수준으로 |
| `legal_references[].distance` | `rule`이면 `null` | 숫자라고 가정하고 계산·정렬하면 오류. `null` 처리 필요 |
| `legal_references[].paragraphs` 추가 | 조문 중 일부 항만 넣었으면 그 항 목록 (예: 흡연의 제9조 `["④", "⑦", "⑧"]`) | 인용할 때 "제9조제8항"처럼 항을 밝히기. 비어 있으면 일부 항만 고른 게 아님 |
| `legal_references[].text` | 조문 머리말(`제329조(절도)`)과 개정 표시(`<개정 …>`)가 빠짐 | 조문 표기는 `article_no`, `article_title`로 만들기 |
| `legal_references` 개수 | 검색 조문은 거리 기준을 넘으면 빠짐 → 0~3개 | 빈 리스트일 수 있음. 비면 "해당 조문 없음"으로 |
| `procedure_references` | 검색 대신 정해진 단계(접수 → 수사 → 결정)를 순서대로. `distance` 삭제. `smoking`은 빈 리스트(과태료 사안) | `rank`를 진행 순서로 쓰기. 빈 리스트 처리 필요 |
| `queries.procedure` 삭제 | `queries`에는 `legal`만 남음 | 이 필드를 읽던 코드 삭제 |
| `warnings` 종류 추가 | VLM 확신도 `low`, 장시간 체류(범죄 단정 금지), 흡연(과태료 안내), 법령 없음 | 리포트에 그대로 반영 |

## 알아둘 점

- `laws.json`의 `keywords`는 검색 보강용으로 팀에서 추가한 것이며 법령 원문이 아닙니다. 리포트에 조문을 인용할 때는 출력의 `text`를 기준으로 하세요.
- 현재 개인정보 보호법은 제4조, 제59조, 제71조만 들어 있습니다. CCTV 관련 조항(제25조 등)은 추가가 필요합니다.
- 흡연(`smoking`)은 국민건강증진법 제9조(금연구역)와 제34조(과태료)를 씁니다. 형사 사건이 아니라 과태료 사안이라 경찰 절차는 넣지 않습니다. 무인점포가 금연구역인지는 매장마다 다르므로(제9조제4항 시설 해당 여부, 조례 지정 등) 리포트에서 단정하지 않습니다.
- `health_promotion_act_art9.pdf`에는 제34조도 함께 들어 있습니다. `pdf_to_json.py`는 여러 PDF에 같은 조문이 있으면 파일 이름 순으로 먼저 나온 것만 씁니다.
- 법령은 개정될 수 있으므로 PDF 상단의 시행일(메타데이터 `enforcement`)을 확인하세요.
