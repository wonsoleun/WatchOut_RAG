"""VLM 출력(JSON)의 event_type -> 검색 질의 / 설정 매핑.

event_type 값은 VLM 담당자와 합의한 목록과 같아야 합니다.
검색어를 바꾸고 싶으면 이 파일의 EVENT_CONFIG만 고치면 됩니다.
"""

# covered=False : 현재 지식 베이스(형법 6개 조문, 개인정보 보호법 3개 조문)에 해당 법령이 없음
EVENT_CONFIG: dict[str, dict] = {
    "unpaid_exit": {
        "label": "미결제 반출",
        "covered": True,
        "search": True,
        "legal_queries": ["무인 매장에서 결제하지 않고 물건을 가지고 나간 절도의 처벌"],
    },
    "vandalism": {
        "label": "기물 파손",
        "covered": True,
        "search": True,
        "legal_queries": ["매장 기물을 부수거나 파손한 경우 재물손괴의 처벌"],
    },
    "long_stay": {
        "label": "장시간 체류",
        "covered": True,
        "search": True,
        "legal_queries": [
            "매장에서 퇴거 요구를 받고도 나가지 않는 경우",
            "매장에서 소란을 피워 영업을 방해하는 경우",
        ],
    },
    "smoking": {
        "label": "매장 내 흡연",
        "covered": False,  # 금연 관련 법령(국민건강증진법 등)이 아직 지식 베이스에 없음
        "search": True,
        "legal_queries": ["매장 내 흡연으로 영업을 방해하거나 시설을 훼손한 경우"],
    },
    "normal": {"label": "이상 없음", "covered": True, "search": False},
    "unclear": {"label": "판단 어려움", "covered": True, "search": False},
}

# 이상행동이 확인된 경우 공통으로 붙이는 경찰 수사 절차 질의
PROCEDURE_QUERY = "고소장 접수 후 경찰 수사와 송치 불송치 결정 절차"


def build_queries(segment: dict) -> dict:
    """segment(JSON dict) -> {'legal': [질의...], 'procedure': [질의...]}"""
    cfg = EVENT_CONFIG[segment["event_type"]]
    legal = list(cfg.get("legal_queries", []))
    summary = (segment.get("summary") or "").strip()
    if summary:
        legal.append(summary)  # VLM이 쓴 사건 설명도 질의로 사용
    return {"legal": legal, "procedure": [PROCEDURE_QUERY]}
