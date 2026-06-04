"""
collect_neis.py
---------------
NEIS 오픈 API에서 전국 '고등학교'의 '중식'(MMEAL_SC_CODE=2) 식단을
기간 내 수집해 parquet로 저장한다. (학교목록·식단 수집을 스레드 풀로 병렬화)

사전 준비
- https://open.neis.go.kr 에서 인증키 발급 후 repo 루트 `.env`에 NEIS_API_KEY 설정.
    NEIS_API_KEY=발급받은키
  (실행 시 자동 로딩. 환경변수로 직접 export 해도 됨.)
- 키 없이도 소량 호출은 되지만 응답이 5행으로 제한되어 전국·다년치는 키가 사실상 필수.

환경변수
- NEIS_FROM_YMD / NEIS_TO_YMD : 수집 기간 (기본 2021-01-01 ~ 오늘)
- NEIS_SCHOOLS_PER_OFFICE     : 시도(교육청)당 학교 수 상한 (0=전체)
- NEIS_WORKERS                : 동시 요청 스레드 수 (기본 12)

주의
- 외부 NEIS 도메인에 접속하므로 인터넷이 허용된 환경에서 실행하라.
- API는 페이지당 최대 1000행. pIndex로 페이지네이션.
- I/O 바운드(네트워크 대기)라 스레드 병렬화로 큰 폭의 속도 향상을 얻는다.
"""

import os
import time
import threading
import datetime as dt
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pandas as pd
from dotenv import load_dotenv

# .env 로딩: repo 루트(패키지 상위)와 패키지 내부 양쪽을 시도한다.
# 이미 설정된 환경변수는 덮어쓰지 않는다(override=False 기본).
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE.parent / ".env")
load_dotenv(_HERE / ".env")

BASE = "https://open.neis.go.kr/hub"
KEY = os.environ.get("NEIS_API_KEY", "")      # 발급 키 (.env: NEIS_API_KEY)
PAGE_SIZE = 1000
LUNCH = "2"                                    # 1=조식 2=중식 3=석식
# 수집 기간/규모: 환경변수로 조절 (미설정 시 기존 동작 = 전국 전체·다년치)
FROM_YMD = os.environ.get("NEIS_FROM_YMD", "20210101")
TO_YMD = os.environ.get("NEIS_TO_YMD", dt.date.today().strftime("%Y%m%d"))
# 시도(교육청)당 학교 수 상한 (0 = 제한 없음). 빠른 테스트용 샘플링.
SCHOOLS_PER_OFFICE = int(os.environ.get("NEIS_SCHOOLS_PER_OFFICE", "0"))
# 동시 요청 스레드 수. 너무 크면 rate limit 위험.
WORKERS = int(os.environ.get("NEIS_WORKERS", "12"))
MAX_RETRY = 3

# 17개 시도교육청 코드 (검증 후 사용)
OFFICES = {
    "B10": "서울", "C10": "부산", "D10": "대구", "E10": "인천", "F10": "광주",
    "G10": "대전", "H10": "울산", "I10": "세종", "J10": "경기", "K10": "강원",
    "M10": "충북", "N10": "충남", "P10": "전북", "Q10": "전남", "R10": "경북",
    "S10": "경남", "T10": "제주",
}

# 스레드별 Session 재사용 (커넥션 풀링). requests.Session은 스레드 공유가
# 보장되지 않으므로 thread-local로 스레드마다 하나씩 둔다.
_local = threading.local()


def _session() -> requests.Session:
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        _local.session = s
    return s


def _get(endpoint: str, params: dict) -> list[dict]:
    """단일 API 호출 -> row 리스트 (페이지네이션 호출자가 관리). 재시도 포함."""
    q = {"KEY": KEY, "Type": "json", "pSize": PAGE_SIZE, **params}
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            r = _session().get(f"{BASE}/{endpoint}", params=q, timeout=30)
            r.raise_for_status()
            js = r.json()
            if endpoint not in js:                 # 결과 없음/에러 코드
                return []
            body = js[endpoint]
            return body[1].get("row", []) if len(body) > 1 else []
        except (requests.RequestException, ValueError) as e:
            last_err = e
            time.sleep(0.4 * (attempt + 1))        # 선형 백오프
    print(f"  [경고] {endpoint} 호출 실패(재시도 {MAX_RETRY}회): {last_err}")
    return []


def _fetch_office_schools(office: str, sido: str) -> list[dict]:
    """한 교육청의 고등학교 목록 (SCHOOLS_PER_OFFICE 상한 적용)."""
    out, page = [], 1
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
            if SCHOOLS_PER_OFFICE and len(out) >= SCHOOLS_PER_OFFICE:
                return out                          # 샘플 상한 도달
        if len(rows) < PAGE_SIZE:
            break
        page += 1
    return out


def fetch_high_schools() -> pd.DataFrame:
    """전국 고등학교 목록(학교코드 + 지역). 교육청 단위로 병렬 수집."""
    out = []
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(OFFICES))) as ex:
        futs = {ex.submit(_fetch_office_schools, o, s): o
                for o, s in OFFICES.items()}
        for fut in as_completed(futs):
            out.extend(fut.result())
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
    return out


def main():
    if not KEY:
        print("경고: NEIS_API_KEY 미설정(.env 확인). 응답이 5행으로 제한될 수 있음.")
    t0 = time.time()

    schools = fetch_high_schools()
    schools.to_parquet("schools.parquet", index=False)
    print(f"고등학교 {len(schools)}개 수집 ({time.time()-t0:.1f}s)")

    # 학교별 중식 식단 병렬 수집
    meals = []
    done = 0
    lock = threading.Lock()
    total = len(schools)
    records = schools[["office", "school_code"]].to_dict("records")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(fetch_lunches, r["office"], r["school_code"])
                for r in records]
        for fut in as_completed(futs):
            rows = fut.result()
            with lock:
                meals.extend(rows)
                done += 1
                if done % 50 == 0 or done == total:
                    print(f"  {done}/{total} 학교 처리, 누적 {len(meals)} 끼")

    meals_df = pd.DataFrame(meals)
    meals_df.to_parquet("meals_lunch.parquet", index=False)
    print(f"중식 {len(meals_df)} 끼 저장 -> meals_lunch.parquet "
          f"(총 {time.time()-t0:.1f}s, workers={WORKERS})")


if __name__ == "__main__":
    main()
