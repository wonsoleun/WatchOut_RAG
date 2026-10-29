"""RAG 결과(JSON dict)를 리포트 생성 AI의 프롬프트에 넣을 수 있는 텍스트로 변환.

- format_rag_context(): [참고 법령] / [경찰 수사 절차] / [주의] 블록만 만든다.
  리포트 담당자가 자기 프롬프트 틀에 이 블록만 끼워 넣을 수 있다.
- build_report_prompt(): VLM 세그먼트 + RAG 결과로 프롬프트 전체를 만든다. (기본 틀)
  리포트 담당자가 이미 정한 틀이 있으면 이 함수는 쓰지 않아도 된다.
"""
from src.query_builder import EVENT_CONFIG

DISCLAIMER = (
    "위 법령·절차는 검색된 참고 자료이며 법률 판단이 아니다. "
    "해당 행위에 적용될 수 있는 조문으로만 서술하고, 범죄 성립이나 유죄 여부를 단정하지 않는다."
)


def _indent(text: str, prefix: str = "   ") -> str:
    return "\n".join(prefix + ln for ln in text.splitlines())


def format_rag_context(result: dict, max_laws: int = 2, max_procedures: int = 5) -> str:
    """RAG 결과 -> 프롬프트용 텍스트 블록.

    max_laws: 법령은 1~2위만 쓰는 것을 권장 (뒤 순위에는 관련 없는 조문이 섞일 수 있음)
    max_procedures: 절차는 접수 -> 수사 -> 결정 순서로 들어 있으므로 앞에서부터 자른다
    """
    if result.get("status") != "ok":
        reasons = " ".join(result.get("warnings", []))
        return (
            "[참고 법령]\n해당 없음 (이 구간은 법령 검색 대상이 아니므로 법령·절차 항목을 작성하지 않는다.)\n"
            + (f"사유: {reasons}\n" if reasons else "")
        )

    parts: list[str] = []

    laws = result.get("legal_references", [])[:max_laws]
    parts.append("[참고 법령]")
    if laws:
        for i, law in enumerate(laws, 1):
            enforce = f" (시행 {law['enforcement']})" if law.get("enforcement") else ""
            parts.append(f"{i}. {law['law_name']} {law['article_no']}({law['article_title']}){enforce}")
            parts.append(_indent(law["text"]))
    else:
        parts.append("검색된 법령 없음")

    procs = result.get("procedure_references", [])[:max_procedures]
    parts.append("")
    parts.append("[경찰 수사 절차]")
    if procs:
        for p in procs:
            parts.append(f"- {p['section']}: " + p["text"].replace("\n", "\n  "))
    else:
        parts.append("검색된 절차 없음")

    notes = list(result.get("warnings", []))
    parts.append("")
    parts.append("[주의]")
    for n in notes:
        parts.append(f"- {n}")
    parts.append(f"- {DISCLAIMER}")

    return "\n".join(parts) + "\n"


def _format_incident(segment: dict) -> str:
    cfg = EVENT_CONFIG.get(segment.get("event_type", ""), {})
    label = cfg.get("label", segment.get("event_type", ""))
    lines = [
        "[사건 정보]",
        f"- 구간 ID: {segment.get('segment_id')} (영상: {segment.get('video_id')})",
        f"- 시간: {segment.get('start_time')} ~ {segment.get('end_time')}",
        f"- 유형: {label} ({segment.get('event_type')})",
        f"- 인원: {segment.get('people_count')}명",
        f"- 분석 확신도: {segment.get('confidence')}",
        f"- 요약: {segment.get('summary')}",
        "",
        "[확인된 사실과 근거 프레임]",
    ]
    claims = segment.get("claims") or []
    if claims:
        for c in claims:
            frames = ", ".join(c.get("frame_ids", []))
            lines.append(f"- ({c.get('claim_id')}) {c.get('text')}  [프레임: {frames}]")
    else:
        lines.append("- 없음")
    lines.append("")
    lines.append("[불확실한 점]")
    unc = segment.get("uncertain_points") or []
    lines += [f"- {u}" for u in unc] if unc else ["- 없음"]
    return "\n".join(lines) + "\n"


REPORT_INSTRUCTIONS = """당신은 무인점포 CCTV 이상행동 리포트를 작성하는 보조자입니다.
아래 [사건 정보]와 [참고 법령], [경찰 수사 절차]만 근거로 리포트를 작성하세요.

작성 규칙:
1. 제공되지 않은 사실, 법령, 조문 번호를 만들어 내지 않는다.
2. 법령은 [참고 법령]에 있는 조문만 인용하고, 조문 번호와 제목을 그대로 쓴다.
3. 사실 서술에는 근거 프레임 ID를 함께 적는다.
4. [불확실한 점]은 리포트에 '판단 한계'로 반드시 적는다.
5. "해당 행위에 적용될 수 있는 조문"으로 표현하고, 범죄 성립이나 유죄 여부를 단정하지 않는다.
6. [주의]에 경고가 있으면 리포트에 반영한다.

리포트 구성:
1) 사건 개요  2) 확인된 사실(근거 프레임)  3) 관련 법령  4) 권장 대응 절차  5) 판단 한계"""


def build_report_prompt(segment: dict, result: dict, **kwargs) -> str:
    """리포트 생성 AI에게 줄 프롬프트 전체 (기본 틀)."""
    return "\n".join([
        REPORT_INSTRUCTIONS,
        "",
        _format_incident(segment),
        format_rag_context(result, **kwargs),
    ])
