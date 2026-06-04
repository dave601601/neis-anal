"""
collect_neis.py
---------------
NEIS 오픈 API에서 전국 '고등학교'의 '중식'(MMEAL_SC_CODE=2) 식단을
2021-01-01 ~ 오늘까지 수집해 parquet로 저장한다.

사전 준비
- https://open.neis.go.kr 에서 인증키(KEY) 발급 후 환경변수 NEIS_KEY 설정.
    export NEIS_KEY="발급받은키"
- 키 없이도 소량 호출은 되지만, 전국·다년치는 키가 사실상 필수.

주의
- 이 스크립트는 외부 NEIS 도메인에 접속하므로, 인터넷이 허용된
  본인 환경(로컬/서버)에서 실행하라. (이 분석 샌드박스에선 도메인 차단됨)
- API는 페이지당 최대 1000행. pIndex로 페이지네이션.
"""

import os
import time
import datetime as dt
import requests
import pandas as pd

BASE = "https://open.neis.go.kr/hub"
KEY = os.environ.get("NEIS_KEY", "")          # 발급 키
PAGE_SIZE = 1000
LUNCH = "2"                                    # 1=조식 2=중식 3=석식
# 수집 기간/규모: 환경변수로 조절 (미설정 시 기존 동작 = 전국 전체·다년치)
FROM_YMD = os.environ.get("NEIS_FROM_YMD", "20210101")
TO_YMD = os.environ.get("NEIS_TO_YMD", dt.date.today().strftime("%Y%m%d"))
# 시도(교육청)당 학교 수 상한 (0 = 제한 없음). 빠른 테스트용 샘플링.
SCHOOLS_PER_OFFICE = int(os.environ.get("NEIS_SCHOOLS_PER_OFFICE", "0"))

# 17개 시도교육청 코드 (검증 후 사용)
OFFICES = {
    "B10": "서울", "C10": "부산", "D10": "대구", "E10": "인천", "F10": "광주",
    "G10": "대전", "H10": "울산", "I10": "세종", "J10": "경기", "K10": "강원",
    "M10": "충북", "N10": "충남", "P10": "전북", "Q10": "전남", "R10": "경북",
    "S10": "경남", "T10": "제주",
}


def _get(endpoint: str, params: dict) -> list[dict]:
    """단일 API 호출 -> row 리스트 (페이지네이션 호출자가 관리)."""
    q = {"KEY": KEY, "Type": "json", "pSize": PAGE_SIZE, **params}
    r = requests.get(f"{BASE}/{endpoint}", params=q, timeout=30)
    r.raise_for_status()
    js = r.json()
    if endpoint not in js:                     # 결과 없음/에러
        return []
    body = js[endpoint]
    rows = body[1].get("row", []) if len(body) > 1 else []
    return rows


def fetch_high_schools() -> pd.DataFrame:
    """전국 고등학교 목록(학교코드 + 지역)."""
    out = []
    for office, sido in OFFICES.items():
        page = 1
        n_office = 0                                # 이 교육청에서 모은 학교 수
        while True:
            rows = _get("schoolInfo", {
                "ATPT_OFCDC_SC_CODE": office,
                "SCHUL_KND_SC_NM": "고등학교",
                "pIndex": page,
            })
            if not rows:
                break
            for r in rows:
                out.append({
                    "office": office, "sido": sido,
                    "school_code": r["SD_SCHUL_CODE"],
                    "school_name": r["SCHUL_NM"],
                    "addr": r.get("ORG_RDNMA", ""),
                })
                n_office += 1
                if SCHOOLS_PER_OFFICE and n_office >= SCHOOLS_PER_OFFICE:
                    break
            if SCHOOLS_PER_OFFICE and n_office >= SCHOOLS_PER_OFFICE:
                break                               # 샘플 상한 도달 -> 다음 교육청
            if len(rows) < PAGE_SIZE:
                break
            page += 1
            time.sleep(0.1)
    return pd.DataFrame(out)


def fetch_lunches(office: str, school_code: str) -> list[dict]:
    """한 학교의 기간 내 중식 식단 전체."""
    out, page = [], 1
    while True:
        rows = _get("mealServiceDietInfo", {
            "ATPT_OFCDC_SC_CODE": office,
            "SD_SCHUL_CODE": school_code,
            "MMEAL_SC_CODE": LUNCH,
            "MLSV_FROM_YMD": FROM_YMD,
            "MLSV_TO_YMD": TO_YMD,
            "pIndex": page,
        })
        if not rows:
            break
        for r in rows:
            out.append({
                "school_code": school_code,
                "date": r["MLSV_YMD"],
                "ddish_nm": r["DDISH_NM"],
            })
        if len(rows) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.05)
    return out


def main():
    if not KEY:
        print("경고: NEIS_KEY 미설정. 소량만 반환되거나 실패할 수 있음.")
    schools = fetch_high_schools()
    schools.to_parquet("schools.parquet", index=False)
    print(f"고등학교 {len(schools)}개 수집")

    meals = []
    for i, row in schools.iterrows():
        meals.extend(fetch_lunches(row["office"], row["school_code"]))
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(schools)} 학교 처리, 누적 {len(meals)} 끼")
        time.sleep(0.05)
    meals_df = pd.DataFrame(meals)
    meals_df.to_parquet("meals_lunch.parquet", index=False)
    print(f"중식 {len(meals_df)} 끼 저장 -> meals_lunch.parquet")


if __name__ == "__main__":
    main()
