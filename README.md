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
├─ export_chunks.py           # 조문·절차 -> 백엔드 document_chunks 적재용 JSON
├─ eval_rag.py                # baseline 측정 (검색 단계 + 파이프라인 단계)
├─ scripts/gen_eval_queries_colab.py  # 평가 질의 생성 (Colab + gpt-4o-mini)
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
│  ├─ backend_adapter.py      # search_hits() — 백엔드 Retriever.search 연결용
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
python export_chunks.py        # 백엔드 DB 적재용 document_chunks.json (모델 불필요)
```

## 협업 규칙

- **Git에 올리는 것**: 코드, `data/`, `tests/`, `requirements.txt`
- **Git에 올리지 않는 것**: `chroma_db/`, `.venv/`, `.env`, `document_chunks.json` (`.gitignore`에 설정됨)
- `git pull` 후 `data/`, `config.py`가 바뀌었다면 `python build_kb.py`를 다시 실행합니다. (인덱스가 오래되면 검색할 때 경고가 나옵니다)
- `data/`가 바뀌면 `python export_chunks.py`도 다시 실행해 백엔드 `document_chunks`에 다시 적재합니다.
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
   │  RAG가 읽는 필드: segment_id, video_id, event_type, summary, confidence
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

VLM README의 출력 필드(4.3)와 이름이 그대로 같아서, VLM JSON을 바꾸지 않고 넘기면 됩니다.

| VLM 필드 | 법령 검색에 쓰이나 | 쓰이는 곳 |
|---|---|---|
| `segment_id`, `video_id` | 안 쓰임 | 출력에 그대로 복사 (`segment_id` 필수) |
| `event_type` | **핵심** | 어떤 조문과 절차를 넣을지 결정 (필수) |
| `summary` | 보조 | 벡터 검색 질의로 추가 |
| `confidence` | 경고만 | `low`이면 경고 추가 (`high`/`medium`/`low`) |
| `start_time`, `end_time` / `start_sec`, `end_sec` | 안 쓰임 | 리포트 프롬프트의 시간. 숫자면 "영상 시작 기준 초"로 표기 |
| `claims` | 안 쓰임 | 리포트 프롬프트의 [확인된 사실과 근거 프레임] |
| `people_count` | 안 쓰임 | 리포트 프롬프트의 인원 |
| `uncertain_points` | 안 쓰임 | 리포트 프롬프트의 [불확실한 점] |

- 어떤 범죄인지는 VLM의 `event_type`으로 정해집니다. `event_type`이 틀리면 조문도 틀립니다.
- event_type별 핵심 조문·검색 질의·절차는 `src/query_builder.py`의 `EVENT_CONFIG`에서 설정합니다.
- 시간: VLM은 영상 시작 기준 초(`start_sec`), 백엔드는 숫자 `start_time`(초)을 씁니다. 둘 다 받으며, 리포트에는 "실제 촬영 시각 아님"으로 표기하고 리포트 AI가 실제 시각을 만들어 내지 않도록 규칙에 넣었습니다.

### event_type별 처리

| `event_type` | 의미 | 법령 | 경찰 절차 |
|---|---|---|---|
| `unpaid_exit` | 미결제 반출 | 형법 제329조(절도) | 접수 → 수사 → 결정 |
| `vandalism` | 기물 파손 | 형법 제366조(재물손괴) | 접수 → 수사 → 결정 |
| `smoking` | 매장 내 흡연 | 국민건강증진법 제9조·제34조 해당 항 | 없음 (과태료 사안) |
| `abandonment` = `dumping` | 물건 유기·방치 | 없음 (지식 베이스에 법령 없음 경고) | 없음 |
| `long_stay` | 장시간 체류 | 검색 결과만 (범죄 단정 금지 경고) | 접수 → 수사 → 결정 |
| `normal`, `unclear` | 이상 없음 / 판단 어려움 | 검색 안 함 (`skipped`) | - |

- 유기 유형을 VLM은 `abandonment`, 백엔드는 `dumping`으로 부릅니다. RAG는 둘 다 받고 출력에는 들어온 값을 그대로 돌려줍니다 (`src/query_builder.py`의 `EVENT_TYPE_ALIASES`).
- `long_stay`는 VLM의 6개 유형에는 없고 백엔드 유형에만 있습니다 (전처리가 계산한 체류 시간으로 지정).

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

## 성능 측정 (baseline)

`test_retrieval.py`(질문 11개)는 빠른 확인용이고, baseline은 검수된 평가 세트로 `eval_rag.py`를 돌려 잽니다.

**1. 평가 세트 만들기 (Colab)**: `scripts/gen_eval_queries_colab.py`의 셀을 Colab에 붙여 실행합니다 (🔑 보안 비밀에 `OPENAI_API_KEY`). 로컬에는 `openai`를 설치하지 않습니다.
- 시나리오 8개(미결제 반출 명확/애매, 파손, 흡연, 체류+퇴거 거부, 체류+소란, 단순 체류, 유기), 총 60개 문장을 VLM `summary` 형태로 만듭니다.
- **정답(`expect`)은 GPT가 아니라 스크립트의 `SCENARIOS`에 사람이 정한 값**입니다. GPT에게는 조문을 보여 주지 않고 법률 용어도 금지합니다 (쓰면 점수가 부풀려짐).
- 받은 `eval_draft.json`을 검수합니다: 문장이 장면과 맞는지 확인하고, 틀린 문장은 고치거나 지운 뒤 `reviewed: true`로 바꿔 `tests/eval_cases.json`으로 저장합니다. **이후에는 다시 생성하지 않습니다.**

**2. 측정**

```powershell
python eval_rag.py                                  # test 세트, K=3
python eval_rag.py --split dev                      # 키워드·질의 조정은 dev로만
python eval_rag.py --save results/exp_xxx.json      # 설정·커밋·점수·케이스별 결과 저장
```

| 단계 | 지표 | 의미 |
|---|---|---|
| 검색 (순수 벡터 검색) | Hit@K, Recall@K, MRR | `summary`만으로 정답 조문이 몇 위에 오는가 (임베딩·청킹·키워드 품질) |
| 파이프라인 (`retrieve_for_segment`) | Precision, Recall, 정확 일치, 오탐률 | 백엔드가 받는 최종 조문이 맞는가. 오탐률 = 정답이 없는 장면(단순 체류, 유기)인데 조문이 나온 비율 |

- `dev`는 키워드나 `EVENT_CONFIG` 질의를 고칠 때 보는 세트, `test`는 고치지 않고 점수만 보는 세트입니다. test를 보며 고치면 점수가 부풀려집니다.
- 개선 실험은 `results/baseline_*.json`과 같은 평가 세트(`eval_set.sha256`)로 비교합니다.

### Baseline (2026-11-06, 커밋 `9e8381c`, 평가 세트 `737b1507168f`)

`bge-m3`, 청크 800/100, `LAW_MAX_DISTANCE` 0.95, K=3. 원본: `results/baseline_test.json`, `results/baseline_dev.json`

| | test (26개) | dev (30개) |
|---|---|---|
| 검색 Hit@3 / Recall@3 | 1.000 / 1.000 | 0.957 / 0.964 |
| 검색 MRR | 0.792 | 0.830 |
| 파이프라인 Precision / Recall | 0.758 / 1.000 | 0.700 / 1.000 |
| 파이프라인 정확 일치 | 0.769 | 0.700 |
| 파이프라인 오탐률 (정답 조문 없는 장면) | 0.333 | 0.429 |

- 미결제 반출·파손·흡연·유기는 정확 일치 100%. **틀린 케이스는 전부 `long_stay`**: 퇴거 거부에 제314조, 소란에 제319조, 단순 체류에 둘 다 붙음 (`EVENT_CONFIG["long_stay"]`가 두 질의를 항상 검색하기 때문).
- 순수 벡터 검색에서는 미결제 반출에 형법 제319조가, 파손에 제329조가 1위로 오는 경우가 있어 MRR이 1보다 낮습니다. 최종 결과는 규칙 조문(`rule`)이 덮어 주므로 영향이 없지만, 키워드·임베딩을 바꿀 때 MRR로 변화를 봅니다.

## 백엔드에서 쓰기

백엔드(`app/ai/interfaces.py`)의 검색 모듈 `Retriever.search`는 조문 본문이 아니라 **백엔드 DB `document_chunks`의 ID 목록**(`RetrievalHit`)을 돌려줘야 합니다. 그래서 RAG는 다음 두 가지를 제공합니다.

```
[적재] data/ ──export_chunks.py──> document_chunks.json ──(백엔드가 적재)──> document_chunks 테이블
[검색] RetrievalQuery ──search_hits()──> [{chunk_id, rank, score}] ──> RetrievalHit
                         └─ chunk_id = document_chunks.id
```

1. **문서 적재**: `python export_chunks.py` → 조문 1개 / 절차 섹션 1개당 행 1개 (현재 법령 11개, 절차 11개).
2. **검색**: `src/backend_adapter.search_hits(query)`가 `RetrievalQuery`를 받아 `[{chunk_id, rank, score}]`를 돌려줍니다. 백엔드에서는 `RetrievalHit(**h)`로 감싸고, 예외는 `RetrievalError`로 바꾸면 됩니다. 예시 코드는 [docs/rag_output_schema.md](docs/rag_output_schema.md)의 '백엔드 연결'에 있습니다.

`chunk_id`는 `law:형법 제329조`, `manual:<절차 섹션 이름>` 형식의 고정 ID라서 인덱스를 다시 만들어도 바뀌지 않습니다. 검색 결과의 `chunk_id`가 export 파일에 없으면 `test_segments.py`가 실패합니다.

## 🤝 백엔드와 논의할 부분

백엔드 README의 Open Decisions 중 "문서 적재 및 검색 결과 형식"에 해당합니다. RAG 쪽 제안을 함께 적었습니다.

| # | 논의할 것 | 왜 문제인가 | RAG 쪽 제안 |
|---|---|---|---|
| 1 | **`document_chunks.id` 형식** | RAG의 ID는 `law:형법 제329조` 같은 한글 문자열입니다. 컬럼이 UUID·정수라면 그대로 넣을 수 없습니다. | 문자열 컬럼이면 그대로 사용. 안 되면 별도 `external_id` 컬럼을 두고 그것으로 연결 |
| 2 | **`document_chunks` 적재 방법** | `document_chunks.json`을 언제, 누가 DB에 넣을지 정해지지 않았습니다. 현재 백엔드에는 mock 문서용 `seed_mock_documents`만 있습니다. | 백엔드에 `seed_rag_documents` 같은 스크립트를 두고, RAG `data/`가 바뀔 때마다 다시 실행 |
| 3 | **경고 문구(`warnings`) 전달** | `RetrievalHit`에는 ID만 있어서 "흡연은 과태료 대상", "해당 법령 없음", "장시간 체류만으로는 범죄 아님" 같은 경고가 리포트까지 가지 못합니다. | `ReportGenerator`(RAG 담당) 안에서 같은 사건으로 `retrieve_for_segment()`를 다시 불러 경고를 씀. 같은 입력이면 결과가 같음. 또는 `RetrievalHit`/검색 결과에 `notes` 필드 추가 |
| 4 | **일부 항만 고른 조문** | 흡연은 국민건강증진법 제9조 중 ④⑦⑧항만 씁니다. `document_chunks`에는 조문 전체가 들어가므로 ID만으로는 어느 항인지 알 수 없습니다. | 3번과 같이 `ReportGenerator`가 RAG 결과의 `paragraphs`를 사용 |
| 5 | **`score`의 의미** | RAG는 **거리**(작을수록 가까움)를 넣고, 고정 조문·절차는 `None`입니다. 백엔드가 "클수록 좋음"으로 정렬하면 순서가 뒤집힙니다. | 정렬은 `rank`로 하고 `score`는 참고용으로만 저장 |
| 6 | **`confidence` 미전달** | `RetrievalQuery`에 `confidence`가 없어서 RAG의 "확신도 낮음" 경고가 나오지 않습니다. | 승인된 사건만 검색하므로 그대로 두어도 됨. 필요하면 `RetrievalQuery`에 `confidence` 추가 |
| 7 | **유기 유형 이름** | VLM은 `abandonment`, 백엔드는 `dumping`. | RAG는 둘 다 받음. 팀에서 하나로 확정하면 별칭 정리 |
| 8 | **시간 필드** | VLM README는 `start_sec`/`end_sec`, 백엔드 예시는 숫자 `start_time`/`end_time`. | RAG는 둘 다 받음. 백엔드 Open Decision "VLM 출력 시간 표현과 기준"이 정해지면 하나로 정리 |
| 9 | **`long_stay` 유지 여부** | VLM 6개 유형에는 없고 백엔드에만 있습니다. | 전처리의 체류 시간으로 지정하는 유형으로 유지 |
| 10 | **RAG 코드 연결 방식** | 백엔드가 RAG를 import하려면 `rag_kb` 경로와 의존성(langchain, chromadb, bge-m3), `chroma_db/` 위치가 필요합니다. | 백엔드 `requirements`에 RAG 의존성을 추가하고 `PYTHONPATH`로 연결. 나중에 필요하면 별도 API 서버로 분리 |

## 변경 이력

### 2026-11-06 — VLM·백엔드 README와 입력·출력 맞춤

- **입력**: VLM 출력 필드 10개 전체를 문서화했습니다. 시간은 `start_sec`/`end_sec`, 숫자 `start_time`/`end_time`(초), 문자열 `start_time`(실제 시각)을 모두 받습니다.
- **event_type**: `abandonment`(물건 유기·방치)를 추가하고, 백엔드 이름 `dumping`도 같은 유형으로 받습니다. 해당 법령(경범죄 처벌법, 폐기물관리법)이 아직 없어 경고만 붙습니다.
- **출력**: `legal_references`, `procedure_references`의 각 항목에 `chunk_id`를 추가했습니다 (필드 추가라 `schema_version`은 1.1 그대로).
- **백엔드 연결**: `export_chunks.py`(document_chunks 적재용), `src/backend_adapter.py`(`search_hits`)를 추가했습니다.
- **리포트 프롬프트**: 시간이 초 단위면 "영상 시작 기준, 실제 촬영 시각 아님"으로 표기하고, 작성 규칙에 "실제 촬영 시각을 만들어 내지 않는다"를 추가했습니다. `claims`가 문자열 목록으로 와도 처리합니다.
- **성능 측정**: `eval_rag.py`(검색·파이프라인 두 단계, `--save`)와 Colab용 평가 질의 생성 스크립트를 추가하고, 검수된 평가 세트 56개(`tests/eval_cases.json`)로 baseline을 측정했습니다.
- **예시·테스트**: `examples/sample_input.json`을 상대 시간과 실제 프레임 ID 형식(`f_0012`)으로 바꿨습니다. `tests/segment_cases.json`에 `abandonment`, `dumping` 케이스를 추가했고, `test_segments.py`가 `chunk_id`와 export 파일의 일치를 검사합니다.

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
- 물건 유기·방치(`abandonment`/`dumping`)에 쓸 경범죄 처벌법(쓰레기 등 투기)·폐기물관리법은 아직 없습니다. 추가하면 `EVENT_CONFIG["abandonment"]`의 `core_articles`, `covered`를 고칩니다.
- 흡연(`smoking`)은 국민건강증진법 제9조(금연구역)와 제34조(과태료)를 씁니다. 형사 사건이 아니라 과태료 사안이라 경찰 절차는 넣지 않습니다. 무인점포가 금연구역인지는 매장마다 다르므로(제9조제4항 시설 해당 여부, 조례 지정 등) 리포트에서 단정하지 않습니다.
- `health_promotion_act_art9.pdf`에는 제34조도 함께 들어 있습니다. `pdf_to_json.py`는 여러 PDF에 같은 조문이 있으면 파일 이름 순으로 먼저 나온 것만 씁니다.
- 법령은 개정될 수 있으므로 PDF 상단의 시행일(메타데이터 `enforcement`)을 확인하세요.
