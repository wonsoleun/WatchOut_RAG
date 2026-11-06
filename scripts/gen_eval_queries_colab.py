# RAG 평가용 질의 생성 (Google Colab에서 실행)
#
# 로컬 rag_kb에는 openai를 설치하지 않습니다. 이 파일의 셀(# %% 단위)을 Colab에 복사해 실행하세요.
#
# 준비: Colab 왼쪽 🔑(보안 비밀)에 OPENAI_API_KEY 추가 -> '노트북 액세스' 켜기
# 결과: eval_draft.json 다운로드 -> rag_kb/tests/eval_draft.json에 저장
#       -> 사람이 검수(summary가 장면과 맞는지, expect가 맞는지) -> tests/eval_cases.json으로 저장
#       -> 로컬에서 python eval_rag.py --save results/baseline.json
#
# 원칙
# - 정답(expect)은 GPT가 아니라 아래 SCENARIOS에 사람이 정한 값이다. GPT는 장면 문장만 만든다.
# - GPT에게 조문 본문을 주지 않고, 법률 용어도 쓰지 못하게 한다 (쓰면 검색이 쉬워져 점수가 부풀려짐).
# - 한 번 만들고 검수한 파일은 고정한다. 다시 생성하면 문장이 달라져 이전 점수와 비교할 수 없다.

# %% [1] 설치
# !pip install -q openai

# %% [2] 설정
import json
import random
import re

from google.colab import userdata
from openai import OpenAI

client = OpenAI(api_key=userdata.get("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"
SEED = 42  # dev/test 분할용

# expect: 이 장면에서 RAG가 찾아야 하는 조문 (chunking.label() 형식과 정확히 같아야 함). []이면 "맞는 조문 없음"
SCENARIOS = [
    {"scenario": "unpaid_exit_clear", "event_type": "unpaid_exit", "n": 10,
     "expect": ["형법 제329조"],
     "scene": "손님이 매장 상품을 집은 뒤 키오스크에서 결제하지 않고 그대로 출입문으로 나간다. 결제하지 않은 것이 화면에서 분명히 보인다."},
    {"scenario": "unpaid_exit_ambiguous", "event_type": "unpaid_exit", "n": 5,
     "expect": ["형법 제329조"],
     "scene": "손님이 상품을 들고 나가는데, 키오스크 쪽이 가려지거나 동작이 빨라 결제를 했는지 확실히 보이지 않는다."},
    {"scenario": "vandalism", "event_type": "vandalism", "n": 10,
     "expect": ["형법 제366조"],
     "scene": "사람이 매장 안의 기물(냉장고 문, 진열대, 키오스크, 유리, 의자 등)을 발로 차거나 내리치거나 던져서 부수거나 망가뜨린다."},
    {"scenario": "smoking", "event_type": "smoking", "n": 10,
     "expect": ["국민건강증진법 제9조", "국민건강증진법 제34조"],
     "scene": "사람이 매장 안에서 담배나 전자담배를 피운다. 연기가 보이거나 담배를 입에 무는 동작이 보인다."},
    {"scenario": "long_stay_refuse_leave", "event_type": "long_stay", "n": 5,
     "expect": ["형법 제319조"],
     "scene": "사람이 매장에 오래 머무르고, 점주나 관리자가 와서(또는 스피커로) 나가 달라고 요구했는데도 나가지 않고 버틴다."},
    {"scenario": "long_stay_disturbance", "event_type": "long_stay", "n": 5,
     "expect": ["형법 제314조"],
     "scene": "사람이 매장에 오래 머무르며 큰 소리로 소란을 피우거나 다른 손님의 이용을 막아 매장 영업이 어려워진다."},
    {"scenario": "long_stay_only", "event_type": "long_stay", "n": 5,
     "expect": [],
     "scene": "사람이 매장 의자나 구석에 오래 앉아 있거나 서성이지만 소란, 파손, 결제 회피 같은 다른 행동은 없다."},
    {"scenario": "abandonment", "event_type": "abandonment", "n": 10,
     "expect": [],
     "scene": "사람이 쓰레기, 봉투, 상자, 먹다 남은 음식, 개인 물건 등을 매장 안이나 입구에 두고 그냥 나간다."},
]

BANNED = ["절도", "절취", "손괴", "범죄", "범행", "처벌", "위반", "불법", "형법", "과태료", "금연구역",
          "업무방해", "퇴거불응", "투기", "유기", "도둑", "훔"]

PROMPT = """당신은 무인점포 CCTV 영상을 보고 사건 요약을 쓰는 영상 분석 모델입니다.
아래 장면에 해당하는 사건 요약 문장을 서로 다르게 {n}개 만드세요.

장면: {scene}

규칙:
- 영상에 보이는 행동만 쓴다. 판단, 추측, 법률 용어(예: {banned})는 쓰지 않는다.
- 한 문장, 30~90자, 한국어 평서문 ("~함", "~음"으로 끝나는 보고서체).
- 인물(성별·연령대·옷차림·인원), 물건, 위치, 시간대, 동작 순서를 다양하게 바꾼다.
- 문장끼리 표현이 겹치지 않게 한다.

JSON으로만 답하세요: {{"summaries": ["...", "..."]}}"""


def generate(sc: dict) -> list[str]:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.9,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": PROMPT.format(
            n=sc["n"] + 3, scene=sc["scene"], banned=", ".join(BANNED[:8]))}],  # 걸러질 것 대비 3개 더
    )
    out = json.loads(resp.choices[0].message.content)["summaries"]
    clean, seen = [], set()
    for s in out:
        s = re.sub(r"\s+", " ", s).strip()
        if any(b in s for b in BANNED) or s in seen:
            print(f"  [제외] {s}")
            continue
        seen.add(s)
        clean.append(s)
    return clean[:sc["n"]]


# %% [3] 생성
rng = random.Random(SEED)
cases = []
for sc in SCENARIOS:
    print(f"== {sc['scenario']}")
    summaries = generate(sc)
    if len(summaries) < sc["n"]:
        print(f"  [경고] {len(summaries)}/{sc['n']}개만 생성됨 -> 이 셀을 다시 실행하거나 직접 추가")
    splits = (["dev", "test"] * len(summaries))[:len(summaries)]
    rng.shuffle(splits)
    for i, (s, split) in enumerate(zip(summaries, splits), 1):
        cases.append({
            "id": f"{sc['scenario']}_{i:02d}",
            "scenario": sc["scenario"],
            "event_type": sc["event_type"],
            "summary": s,
            "expect": sc["expect"],
            "split": split,
            "reviewed": False,  # 검수 후 true로
        })
        print(f"  [{split}] {s}")
print(f"\n총 {len(cases)}개")

# %% [4] 저장·다운로드
with open("eval_draft.json", "w", encoding="utf-8") as f:
    json.dump({"generator": {"model": MODEL, "seed": SEED, "prompt": PROMPT, "scenarios": SCENARIOS},
               "cases": cases}, f, ensure_ascii=False, indent=2)

from google.colab import files
files.download("eval_draft.json")
