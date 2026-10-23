# RAG 출력 양식 (schema_version 1.0)

VLM 세그먼트 JSON 1개를 넣으면 관련 법령 조문과 경찰 수사 절차를 JSON 1개로 돌려줍니다.
리포트 생성 담당자는 이 양식만 알면 RAG 내부 코드를 몰라도 됩니다.

## 호출 방법

```python
from src.rag_service import retrieve_for_segment

result = retrieve_for_segment(segment_json)   # segment_json: VLM이 만든 dict
```

파일로 확인할 때: `python run_segment.py examples/sample_input.json`

## 입력 (VLM 담당자가 주는 JSON)

RAG가 실제로 사용하는 필드는 아래 3개입니다. 나머지(`claims`, `confidence`, `uncertain_points` 등)는 RAG가 읽지 않으니 리포트 담당자가 VLM JSON에서 직접 쓰면 됩니다.

| 필드 | 필수 | 용도 |
|---|---|---|
| `segment_id` | O | 결과를 어느 세그먼트와 연결할지 식별 (출력에 그대로 복사) |
| `event_type` | O | 어떤 법령을 찾을지 결정 |
| `summary` | | 검색 질의에 추가 |

`event_type` 값: `unpaid_exit`, `vandalism`, `long_stay`, `smoking`, `normal`, `unclear`

## 출력

```json
{
  "schema_version": "1.0",
  "segment_id": "vid03_seg02",
  "video_id": "vid03",
  "event_type": "unpaid_exit",
  "status": "ok",
  "warnings": [],
  "queries": {
    "legal": ["무인 매장에서 결제하지 않고 ...", "남성 1명이 냉장 진열대에서 ..."],
    "procedure": ["고소장 접수 후 경찰 수사와 ..."]
  },
  "legal_references": [
    {
      "rank": 1,
      "law_name": "형법",
      "article_no": "제329조",
      "article_title": "절도",
      "text": "제329조(절도) 타인의 재물을 절취한 자는 6년 이하의 징역 또는 1천만원 이하의 벌금에 처한다. ...",
      "source_file": "criminal_code_art329.pdf",
      "enforcement": "2026. 10. 2.",
      "distance": 0.52
    }
  ],
  "procedure_references": [
    {
      "rank": 1,
      "section": "3단계 결정 - 불송치 결정",
      "text": "혐의없음, 죄가안됨, 공소권없음에 해당하면 ...",
      "source_file": "police_procedure.md",
      "distance": 0.61
    }
  ]
}
```

위 `distance` 값은 양식을 보여 주기 위한 예시입니다. 실제 값은 임베딩 모델과 질의에 따라 달라집니다.

## 필드 설명

| 필드 | 설명 |
|---|---|
| `status` | `ok` 검색함 / `skipped` 검색 안 함 (`normal`, `unclear`, 알 수 없는 `event_type`) |
| `warnings` | 사람이 읽을 경고 문구 목록. 비어 있으면 문제 없음 |
| `queries` | 실제로 검색에 쓴 질의. 결과가 이상할 때 원인을 찾는 용도 |
| `legal_references` | 관련 법령 조문. `rank` 1이 가장 관련 높음 (기본 3개) |
| `procedure_references` | 경찰 수사 절차 단계. 이상행동이 확인된 경우에만 채워짐 (기본 2개) |
| `text` | 조문/절차 본문. 검색용 머리말과 보강 키워드는 제거한 원문 |
| `article_no`, `article_title` | 인용 표기용. 예: `형법 제329조(절도)` |
| `enforcement` | 법령 시행일. 인용할 때 기준일로 표기 |
| `source_file` | 근거가 된 원본 파일 |
| `distance` | 질의와의 **거리**. 작을수록 비슷함. 확률이나 정확도가 아님 |

## 리포트 담당자가 알아야 할 점

1. **`status`가 `skipped`이면** 법령 섹션을 만들지 말고 `warnings`를 확인하세요. 두 리스트는 비어 있습니다.
2. **`warnings`가 있으면 리포트에 반영하세요.** 예를 들어 `smoking`은 해당 법령이 지식 베이스에 없어서 `legal_references`가 참고용입니다. 근거로 인용하면 안 됩니다.
3. **rank 1이 항상 정답은 아닙니다.** 뒤쪽 순위에는 관련 없는 조문이 섞일 수 있으니, 리포트에는 `rank` 1~2 위주로 쓰거나 사람이 검토하세요.
4. **법률 판단이 아니라 조문 검색 결과입니다.** 리포트에는 "해당 행위에 적용될 수 있는 조문"처럼 표현하고 유죄 여부를 단정하지 마세요.
5. 조문을 인용할 때는 `text`의 원문을 그대로 쓰고, `enforcement` 시행일 기준임을 밝히세요.

## 변경 규칙

- 필드를 **추가**하는 것은 `schema_version`을 올리지 않아도 됩니다.
- 필드 이름을 **바꾸거나 삭제**할 때는 `schema_version`을 올리고 리포트 담당자에게 먼저 알립니다.
- `event_type`을 추가할 때는 `src/query_builder.py`의 `EVENT_CONFIG`에 항목을 넣습니다.

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

결과 예시는 `examples/sample_report_prompt.txt`를 보세요. 이 예시는 임시 임베딩으로 만든 것이라 법령 순위가 실제와 다를 수 있습니다.
