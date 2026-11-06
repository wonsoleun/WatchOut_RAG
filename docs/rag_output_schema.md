# RAG 출력 양식 (schema_version 1.1)

VLM 세그먼트 JSON 1개를 넣으면 관련 법령 조문과 경찰 수사 절차를 JSON 1개로 돌려줍니다.
리포트 생성 담당자는 이 양식만 알면 RAG 내부 코드를 몰라도 됩니다.

## 호출 방법

```python
from src.rag_service import retrieve_for_segment

result = retrieve_for_segment(segment_json)   # segment_json: VLM이 만든 dict
```

파일로 확인할 때: `python run_segment.py examples/sample_input.json`

## 입력 (VLM 담당자가 주는 JSON)

VLM README(4장 출력 JSON, 5장 이벤트 유형, 6.2 상대 시간)와 맞춘 양식입니다. VLM JSON을 필드명 그대로 넘기면 됩니다.

| 필드 | 타입 | 필수 | 읽는 곳 | 용도 |
|---|---|---|---|---|
| `segment_id` | string | O | 검색 | 결과를 어느 세그먼트와 연결할지 식별 (출력에 그대로 복사) |
| `video_id` | string | | 검색 | 출력에 그대로 복사 |
| `start_time` / `end_time` | number 또는 string | | 프롬프트 | 숫자면 원본 영상 기준 초 (Backend README, 예: `14.0`), 문자열이면 실제 촬영 시각 (예: `"2026-10-12T21:13:40"`). 있으면 `start_sec`보다 우선 |
| `start_sec` / `end_sec` | number | | 프롬프트 | 영상 시작 기준 초 (VLM README 6.2). `start_time`이 없을 때 사용 |
| `event_type` | string | O | 검색 | 어떤 법령/절차를 넣을지 결정 (아래 값 목록) |
| `summary` | string | | 검색, 프롬프트 | 검색 질의에 추가 |
| `claims` | list[object] | | 프롬프트 | 각 항목 `{"claim_id": str, "text": str, "frame_ids": [str]}`. `frame_ids`는 전처리가 부여한 ID (`f_0012`) |
| `people_count` | int | | 프롬프트 | 관찰 인원 |
| `confidence` | `"high"` / `"medium"` / `"low"` | | 검색, 프롬프트 | `"low"`이면 `warnings`에 확신도 경고 추가 (보정된 확률이 아닌 정성적 값) |
| `uncertain_points` | list[str] | | 프롬프트 | 리포트의 '판단 한계'에 들어감 |

- "검색"은 `retrieve_for_segment`, "프롬프트"는 `build_report_prompt`가 읽는다는 뜻입니다. 위에 없는 필드는 무시합니다.
- 시간이 초 단위(숫자)면 프롬프트에 "영상 시작 기준, 실제 촬영 시각 아님"으로 표기하고, 리포트 AI가 실제 시각을 만들어 내지 않도록 작성 규칙에 넣었습니다.

`event_type` 값 (VLM README 5.1의 6개 + `long_stay`, 그 외 값은 `skipped`):

| `event_type` | 의미 | `status` | 법령 / 절차 |
|---|---|---|---|
| `unpaid_exit` | 미결제 반출 | `ok` | 형법 제329조(절도) + 경찰 수사 절차 |
| `vandalism` | 기물 파손 | `ok` | 형법 제366조(재물손괴) + 경찰 수사 절차 |
| `smoking` | 매장 내 흡연 | `ok` | 국민건강증진법 제9조·제34조 해당 항, 절차 없음 (과태료 사안) |
| `abandonment` (= `dumping`) | 물건 유기·방치 | `ok` | 지식 베이스에 해당 법령 없음 → 검색 결과는 참고용 경고, 절차 없음. VLM README는 `abandonment`, Backend README는 `dumping`이라 둘 다 받음 (`EVENT_TYPE_ALIASES`). 출력 `event_type`은 입력 값 그대로 |
| `normal` | 이상행동 없음 | `skipped` | - |
| `unclear` | 판단 어려움 | `skipped` | - |
| `long_stay` | 장시간 체류 | `ok` | VLM README 6개 값에는 없지만 Backend 사건 유형에는 있음. 전처리가 계산한 체류 시간으로 지정되는 유형 (VLM README 8장) |

`smoking`은 형사 사건이 아니라 과태료 사안이라 `procedure_references`가 비어 있고, 대신 `warnings`에 과태료 안내가 들어갑니다.
`abandonment`는 경범죄 처벌법·폐기물관리법이 아직 지식 베이스에 없어서, `warnings`에 "법령이 지식 베이스에 없습니다" 경고가 붙습니다. 해당 법령 PDF를 추가하면 `core_articles`를 채울 수 있습니다.

## 출력

```json
{
  "schema_version": "1.1",
  "segment_id": "vid03_seg02",
  "video_id": "vid03",
  "event_type": "unpaid_exit",
  "status": "ok",
  "warnings": [],
  "queries": {
    "legal": ["무인 매장에서 결제하지 않고 ...", "남성 1명이 냉장 진열대에서 ..."]
  },
  "legal_references": [
    {
      "rank": 1,
      "chunk_id": "law:형법 제329조",
      "match": "rule",
      "paragraphs": [],
      "law_name": "형법",
      "article_no": "제329조",
      "article_title": "절도",
      "text": "타인의 재물을 절취한 자는 6년 이하의 징역 또는 1천만원 이하의 벌금에 처한다.",
      "source_file": "criminal_code_art329.pdf",
      "enforcement": "2026. 10. 2.",
      "distance": null
    }
  ],
  "procedure_references": [
    {
      "rank": 1,
      "chunk_id": "manual:1단계 접수 - 고소장 등 접수 및 담당 경찰관 배정",
      "section": "1단계 접수 - 고소장 등 접수 및 담당 경찰관 배정",
      "text": "고소장, 고발장, 진정서를 작성한 후 경찰서 민원실에 접수한다. ...",
      "source_file": "police_procedure.md"
    }
  ]
}
```

### 1.0 -> 1.1 변경점

- `legal_references[].match` 추가: `rule`(event_type별로 고정된 핵심 조문) / `search`(벡터 검색으로 찾은 조문). `rule`은 `distance`가 `null`
- 검색 조문은 거리가 `config.LAW_MAX_DISTANCE` 이하인 것만 들어감 → 개수가 0~3개로 달라짐
- 같은 조문은 한 번만 나옴 (긴 조문이 여러 청크로 나뉘어도)
- `procedure_references`는 검색하지 않고 event_type별로 정한 단계(접수 → 수사 → 결정)를 순서대로 넣음. `distance` 삭제
- `queries.procedure` 삭제
- `text`에서 조문 머리말(`제329조(절도)`)과 개정 표시(`<개정 1995. 12. 29.>`)가 빠짐. 인용할 때는 `article_no`, `article_title`로 표기

## 필드 설명

| 필드 | 설명 |
|---|---|
| `chunk_id` | 조문/섹션의 고정 ID (`law:법령명 제N조`, `manual:섹션 이름`). 백엔드 `document_chunks.id`와 같음. 인덱스를 다시 만들어도 바뀌지 않음 |
| `status` | `ok` 검색함 / `skipped` 검색 안 함 (`normal`, `unclear`, 알 수 없는 `event_type`) |
| `warnings` | 사람이 읽을 경고 문구 목록. 비어 있으면 문제 없음 |
| `queries` | 실제로 검색에 쓴 질의. 결과가 이상할 때 원인을 찾는 용도 |
| `legal_references` | 관련 법령 조문 (최대 3개). `match: rule`이 앞에, 그 뒤에 `search`가 거리순 |
| `match` | `rule` 고정 조문 / `search` 검색으로 찾은 조문 (참고 수준) |
| `paragraphs` | 조문 중 일부 항만 넣었을 때 그 항 목록 (예: `smoking`의 제9조는 `["④", "⑦", "⑧"]`). 비어 있으면 조문 전체(`rule`) 또는 검색된 부분(`search`). 인용할 때 "제9조제8항"처럼 항을 밝히세요 |
| `procedure_references` | 경찰 수사 절차 단계. `rank` 순서가 진행 순서 (접수 → 수사 → 결정) |
| `text` | 조문/절차 본문. 검색용 머리말과 보강 키워드는 제거한 원문 |
| `article_no`, `article_title` | 인용 표기용. 예: `형법 제329조(절도)` |
| `enforcement` | 법령 시행일. 인용할 때 기준일로 표기 |
| `source_file` | 근거가 된 원본 파일 |
| `distance` | 질의와의 **거리**. 작을수록 비슷함. 확률이나 정확도가 아님. `rule`이면 `null` |

## 백엔드 연결 (`app/ai/interfaces.py`)

백엔드의 `Retriever.search`는 `document_chunks.id` 목록(`RetrievalHit`)만 받습니다. 그래서 두 가지를 맞춥니다.

**1. 문서 적재**: `python export_chunks.py -o document_chunks.json` → 조문 1개 / 매뉴얼 섹션 1개당 행 1개.
`id`가 RAG 결과의 `chunk_id`와 같으므로 이 파일로 백엔드 `document_chunks`를 채웁니다. `data/`를 바꾸면 `build_kb.py`와 함께 다시 실행해 다시 적재합니다.

| 필드 | 설명 |
|---|---|
| `id` | `chunk_id`와 같은 고정 ID |
| `doc_type` | `law` / `manual` |
| `title` | 표시용 이름 (`형법 제329조`, 섹션 이름) |
| `text` | 조문 전체 / 섹션 본문 (검색용 머리말·키워드 제외) |
| `source_file`, `law_name`, `article_no`, `article_title`, `enforcement`, `section` | 출처·인용 정보 (해당 없으면 `null`) |

`smoking`처럼 일부 항만 고른 조문도 `document_chunks`에는 조문 전체가 들어갑니다. 고른 항은 RAG 결과의 `paragraphs`/`text`에 있습니다.

**2. Retriever 구현**: `src/backend_adapter.search_hits()`가 `RetrievalQuery`를 받아 `[{"chunk_id", "rank", "score"}]`를 돌려줍니다.

```python
# backend/app/ai/rag_retriever.py (예시)
from app.ai.interfaces import ModuleInfo, RetrievalError, RetrievalHit
from src.backend_adapter import search_hits   # rag_kb를 PYTHONPATH에 추가

class RagRetriever:
    info = ModuleInfo(name="rag_kb", model_version="BAAI/bge-m3")

    def search(self, query, options):
        try:
            hits = search_hits(query, k_law=options.get("k_law", 3))
        except Exception as e:      # 인덱스 없음, 모델 로딩 실패 등
            raise RetrievalError(str(e)) from e
        return [RetrievalHit(**h) for h in hits]
```

- 순서: 법령(`rule` → `search` 거리순) 다음 절차(접수 → 수사 → 결정). `rank`가 그 순서입니다.
- `score`: 검색 조문은 질의와의 **거리**(작을수록 가까움), 규칙 조문과 절차는 `None`. 정렬은 `rank`로 하세요.
- `normal`, `unclear`, 모르는 유형은 빈 목록(= 결과 없음, `NOT_FOUND`)입니다.
- `RetrievalQuery`에는 `confidence`가 없어서 확신도 경고는 붙지 않습니다.
- **`warnings`는 `RetrievalHit`에 담을 수 없습니다.** 흡연 과태료 안내, 법령 미보유 경고 같은 내용이 리포트에 들어가야 하므로, `ReportGenerator`는 같은 사건으로 `retrieve_for_segment()`를 다시 불러 `warnings`와 고른 항 본문을 쓰세요 (결정적이라 결과가 같습니다).

## 리포트 담당자가 알아야 할 점

1. **`status`가 `skipped`이면** 법령 섹션을 만들지 말고 `warnings`를 확인하세요. 두 리스트는 비어 있습니다.
2. **`warnings`가 있으면 리포트에 반영하세요.** 예를 들어 `long_stay`는 체류만으로는 범죄가 아니라는 경고가 붙으며, 해당 법령이 지식 베이스에 없는 유형이라는 경고가 있으면 `legal_references`는 참고용이므로 근거로 인용하면 안 됩니다.
3. **`match: search` 조문은 참고 수준입니다.** `rule` 조문을 중심으로 쓰고, `search` 조문은 사람이 검토한 뒤 쓰세요. `legal_references`가 비어 있으면 법령 항목을 "해당 조문 없음"으로 쓰세요.
4. **법률 판단이 아니라 조문 검색 결과입니다.** 리포트에는 "해당 행위에 적용될 수 있는 조문"처럼 표현하고 유죄 여부를 단정하지 마세요.
5. 조문을 인용할 때는 `text`의 원문을 그대로 쓰고, `enforcement` 시행일 기준임을 밝히세요.

## 변경 규칙

- 필드를 **추가**하는 것은 `schema_version`을 올리지 않아도 됩니다.
- 필드 이름을 **바꾸거나 삭제**할 때는 `schema_version`을 올리고 리포트 담당자에게 먼저 알립니다.
- `event_type`을 추가할 때는 `src/query_builder.py`의 `EVENT_CONFIG`에 항목을 넣고, `tests/segment_cases.json`에 케이스를 추가한 뒤 `python test_segments.py`로 확인합니다.

## 프롬프트에 넣을 수 있는 텍스트로 변환

JSON 결과를 리포트 생성 AI의 프롬프트에 넣을 수 있게 글로 바꿔 주는 함수가 `src/prompt_formatter.py`에 있습니다.

```python
from src.rag_service import retrieve_for_segment
from src.prompt_formatter import format_rag_context, build_report_prompt

result = retrieve_for_segment(segment_json)

context = format_rag_context(result)             # [참고 법령] [경찰 수사 절차] [주의] 블록만
prompt  = build_report_prompt(segment_json, result)   # 프롬프트 전체 (기본 틀)
```

- **`format_rag_context`**: 리포트 담당자가 이미 정한 프롬프트 틀이 있다면, 이 블록만 그 틀의 원하는 위치에 끼워 넣으면 됩니다. 법령은 기본으로 1~2위만 넣습니다 (`max_laws`로 조절).
- **`build_report_prompt`**: 사건 정보, 근거 프레임, 불확실한 점, 작성 규칙까지 포함한 기본 틀입니다. 규칙과 리포트 구성은 `REPORT_INSTRUCTIONS`에서 바꿀 수 있습니다.
- `status`가 `skipped`이면 "해당 없음" 블록이 나오므로, 프롬프트가 깨지지 않습니다.

파일로 확인할 때:

```
python run_segment.py examples/sample_input.json --format context
python run_segment.py examples/sample_input.json --format prompt
```

결과 예시는 `examples/sample_report_prompt.txt`를 보세요.
