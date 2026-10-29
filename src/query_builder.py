"""VLM 출력(JSON)의 event_type -> 검색 질의 / 설정 매핑.

event_type 값은 VLM 담당자와 합의한 목록과 같아야 합니다.
검색어를 바꾸고 싶으면 이 파일의 EVENT_CONFIG만 고치면 됩니다.

- core_articles: 이 유형이면 항상 넣는 조문 ('법령명 제N조', laws.json에 있어야 함). 검색 순위와 무관하게 앞에 옴
- legal_queries: 그 외 관련 조문을 찾는 벡터 검색 질의 (거리 config.LAW_MAX_DISTANCE 이하만 채택)
- procedures: 넣을 경찰 절차 섹션 이름 (police_procedure.md의 '## ' 제목과 정확히 같아야 함)
- note: 결과에 항상 붙일 경고 문구
"""

# 이상행동이 확인된 경우 점주에게 안내할 기본 수사 흐름 (접수 -> 수사 -> 결정)
CRIME_PROCEDURES = [
    "1단계 접수 - 고소장 등 접수 및 담당 경찰관 배정",
    "2단계 수사 - 고소인, 피의자 조사 및 증거수집",
    "3단계 결정 - 1. 송치 결정",
    "3단계 결정 - 2. 불송치 결정",
    "3단계 결정 - 3. 수사중지 결정",
]

# covered=False : 현재 지식 베이스(형법 6개 조문, 개인정보 보호법 3개 조문)에 해당 법령이 없음
EVENT_CONFIG: dict[str, dict] = {
    "unpaid_exit": {
        "label": "미결제 반출",
        "covered": True,
        "search": True,
        "core_articles": ["형법 제329조"],
        "legal_queries": ["무인 매장에서 결제하지 않고 물건을 가지고 나간 절도의 처벌"],
        "procedures": CRIME_PROCEDURES,
    },
    "vandalism": {
        "label": "기물 파손",
        "covered": True,
        "search": True,
        "core_articles": ["형법 제366조"],
        "legal_queries": ["매장 기물을 부수거나 파손한 경우 재물손괴의 처벌"],
        "procedures": CRIME_PROCEDURES,
    },
    "long_stay": {
        "label": "장시간 체류",
        "covered": True,
        "search": True,
        "core_articles": [],  # 체류만으로는 적용 조문을 단정할 수 없음
        "legal_queries": [
            "매장에서 퇴거 요구를 받고도 나가지 않는 경우",
            "매장에서 소란을 피워 영업을 방해하는 경우",
        ],
        "procedures": CRIME_PROCEDURES,
        "note": "장시간 체류만으로는 범죄가 아닙니다. 퇴거 요구에 응하지 않았거나 소란으로 영업을 방해한 사실이 "
                "영상에서 확인될 때만 아래 조문이 적용될 수 있습니다.",
    },
    "normal": {"label": "이상 없음", "covered": True, "search": False},
    "unclear": {"label": "판단 어려움", "covered": True, "search": False},
}


def build_queries(segment: dict) -> list[str]:
    """segment(JSON dict) -> 법령 검색 질의 목록"""
    cfg = EVENT_CONFIG[segment["event_type"]]
    legal = list(cfg.get("legal_queries", []))
    summary = (segment.get("summary") or "").strip()
    if summary:
        legal.append(summary)  # VLM이 쓴 사건 설명도 질의로 사용
    return legal
