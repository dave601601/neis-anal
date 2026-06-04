"""
build_vectors.py
----------------
meals_lunch.parquet + schools.parquet -> 학교별 중식 속성 벡터(43차원).
(학습형 임베딩 64차원은 embeddings.py가 별도 생성, cluster 단계에서 결합)

1. 끼 -> 속성 비율 벡터
2. 학교별 평균
3. 표본수 필터 + 전국평균 수축
4. CLR 변환(조성 거리 왜곡 방지) -> _clr 저장
"""
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from menu_attributes import parse_menu_string, meal_feature_vector, FEATURE_COLUMNS

MIN_MEALS = 100
SHRINK_K = 50
# 끼→속성벡터 변환은 CPU 바운드 순수 파이썬 -> 프로세스 풀로 병렬화.
# 0/미설정이면 os.cpu_count(). 환경변수 VEC_WORKERS로 조절.
VEC_WORKERS = int(os.environ.get("VEC_WORKERS", "0")) or None


def _meal_vec(ddish_nm: str):
    """한 끼 문자열 -> 속성 비율 벡터(dict) 또는 None. 워커가 pickle하므로 모듈 최상위."""
    dishes = parse_menu_string(ddish_nm)
    return meal_feature_vector(dishes, normalize=True) if dishes else None


def build_meal_vectors(meals_df: pd.DataFrame, workers=VEC_WORKERS) -> pd.DataFrame:
    names = meals_df["ddish_nm"].tolist()
    codes = meals_df["school_code"].tolist()
    # executor.map은 입력 순서를 보존 -> 직렬 버전과 행 순서·값이 동일(결정적).
    # chunksize로 470k개 태스크의 IPC 오버헤드를 분산.
    with ProcessPoolExecutor(max_workers=workers) as ex:
        vecs = ex.map(_meal_vec, names, chunksize=4000)
    recs = []
    for code, v in zip(codes, vecs):
        if v is None:
            continue
        v["school_code"] = code
        recs.append(v)
    return pd.DataFrame(recs)


def build_school_vectors(meal_vecs: pd.DataFrame) -> pd.DataFrame:
    grp = meal_vecs.groupby("school_code")
    school = grp[FEATURE_COLUMNS].mean()
    school["n_meals"] = grp.size()
    school = school[school["n_meals"] >= MIN_MEALS].copy()

    mu = school[FEATURE_COLUMNS].mean()
    n = school["n_meals"].values[:, None]
    school[FEATURE_COLUMNS] = (n * school[FEATURE_COLUMNS].values + SHRINK_K * mu.values) / (n + SHRINK_K)
    return school.reset_index()          # school_code를 컬럼으로


def clr_transform(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    x = df[cols].values.astype(float) + 1e-6
    log_x = np.log(x)
    clr = log_x - log_x.mean(axis=1, keepdims=True)
    out = df.copy()
    out[cols] = clr
    return out


def main():
    meals_df = pd.read_parquet("meals_lunch.parquet")
    schools = pd.read_parquet("schools.parquet")[["school_code", "sido", "school_name"]]

    meal_vecs = build_meal_vectors(meals_df)
    school_vecs = build_school_vectors(meal_vecs).merge(schools, on="school_code", how="left")

    school_vecs.to_parquet("school_vectors_raw.parquet", index=False)
    clr_transform(school_vecs, FEATURE_COLUMNS).to_parquet("school_vectors_clr.parquet", index=False)
    print(f"학교 속성 벡터 {len(school_vecs)}개 x {len(FEATURE_COLUMNS)}차원 저장")


if __name__ == "__main__":
    main()
