"""
_test_synthetic.py
------------------
NEIS 접속 없이 파이프라인을 검증하기 위한 합성 데이터.
지역마다 식단 경향을 다르게 주어, 군집이 실제로 지역과 연관되는지 확인한다.
(실제 사용 시에는 collect_neis.py 산출물 parquet을 그대로 쓰면 됨)
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)

# 지역별 '스타일' 메뉴 풀 (경향성을 의도적으로 다르게)
POOLS = {
    "해안형": {  # 어패류·국물 강함
        "main": ["기장밥", "흰쌀밥", "잡곡밥"],
        "soup": ["북어국", "미역국", "대구탕", "동태찌개", "매운탕"],
        "side": ["고등어구이", "갈치조림", "오징어볶음", "코다리조림", "새우튀김", "어묵볶음"],
        "extra": ["배추김치", "요구르트", "도라지무침"],
    },
    "내륙육류형": {  # 육류·볶음 강함
        "main": ["흰쌀밥", "잡곡밥", "볶음밥"],
        "soup": ["된장찌개", "김치찌개", "육개장"],
        "side": ["제육볶음", "불고기", "돈까스", "닭갈비", "함박스테이크", "장조림"],
        "extra": ["배추김치", "콩나물무침", "우유"],
    },
    "양식혼합형": {  # 양식·면 비중
        "main": ["크림파스타", "토마토스파게티", "볶음밥", "흰쌀밥"],
        "soup": ["콘스프", "미네스트로네", "북엇국"],
        "side": ["치킨가라아게", "그라탕", "함박스테이크", "샐러드", "치즈스틱튀김"],
        "extra": ["단무지", "요구르트", "과일"],
    },
}
REGION_STYLE = {  # 시도 -> 스타일 (간단히 매핑)
    "부산": "해안형", "인천": "해안형", "전남": "해안형", "경남": "해안형", "제주": "해안형",
    "대구": "내륙육류형", "경북": "내륙육류형", "충북": "내륙육류형", "강원": "내륙육류형", "전북": "내륙육류형",
    "서울": "양식혼합형", "경기": "양식혼합형", "대전": "양식혼합형", "세종": "양식혼합형",
    "광주": "내륙육류형", "울산": "해안형", "충남": "내륙육류형",
}


def make_meal(style: str) -> str:
    p = POOLS[style]
    dishes = [rng.choice(p["main"]),
              rng.choice(p["soup"]),
              rng.choice(p["side"]),
              rng.choice(p["side"]),
              rng.choice(p["extra"])]
    # NEIS 포맷 흉내: <br/> 구분 + 일부 알레르기 숫자
    return "<br/>".join(d + (" (5.6)" if rng.random() < 0.4 else "") for d in dishes)


def main():
    schools, meals = [], []
    sc = 0
    for sido, style in REGION_STYLE.items():
        for _ in range(12):                      # 시도당 12개 학교
            sc += 1
            code = f"S{sc:04d}"
            schools.append({"school_code": code, "sido": sido,
                            "school_name": f"{sido}고{sc}"})
            for _ in range(150):                 # 학교당 150끼
                meals.append({"school_code": code,
                              "date": "20230101",
                              "ddish_nm": make_meal(style)})
    pd.DataFrame(schools).to_parquet("schools.parquet", index=False)
    pd.DataFrame(meals).to_parquet("meals_lunch.parquet", index=False)
    print(f"합성: 학교 {len(schools)}개 / 중식 {len(meals)}끼")


if __name__ == "__main__":
    main()
