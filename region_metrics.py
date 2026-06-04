"""
region_metrics.py
-----------------
학교 벡터 + 군집 + FastText 모델 + 원시 식단 -> 시도별 지표 JSON (지도 입력).

지표 갈래
1) 명시 점유율: 밥/빵/면 form 점유율, 해산물·단백질 사용도(속성 비율)
2) 대비(contrast) 임베딩 유사도: 반대 개념 키워드 투영의 '차'를 학교 임베딩에
   적용 -> 시도평균 -> z-표준화. 단일 키워드 유사도가 지역 단위 전역 편향에
   오염되는 문제를 상쇄하고, '해산물↔육류'처럼 실제 지역 대비를 드러낸다.
3) 군집 구성: 시도별 군집 점유율 + 우세 군집
4) 지역 시그니처: 전국 대비 그 지역에서 유독 자주 나오는 메뉴(학교 단위 lift).
   예) 제주-동초나물무침, 대구-동인동찜갈비, 강원-닭갈비.

출력: region_metrics.json
"""
import re
import json
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from gensim.models import FastText
from menu_attributes import FEATURE_COLUMNS, parse_menu_string

PROTEIN_COLS = [c for c in FEATURE_COLUMNS if c.startswith("protein_")]

# 대비 축: (한쪽 키워드, 반대쪽 키워드). 점수 = proj(한쪽) - proj(반대쪽).
CONTRASTS = {
    "con_sea_meat":    (["해산물", "생선", "고등어", "갈치", "오징어"],
                        ["고기", "삼겹", "불고기", "제육"]),
    "con_noodle_rice": (["국수", "우동", "라면", "칼국수"],
                        ["밥", "쌀밥", "잡곡밥"]),
    "con_spicy_mild":  (["매운", "고추장", "불닭", "청양"],
                        ["크림", "치즈", "버터", "담백"]),
    "con_west_korean": (["파스타", "스테이크", "피자", "그라탕"],
                        ["된장", "나물", "김치", "비빔밥"]),
}
CONTRAST_LABELS = {
    "con_sea_meat": "해산물↔육류", "con_noodle_rice": "면↔밥",
    "con_spicy_mild": "매운↔순한", "con_west_korean": "양식↔한식",
}

# 지역 시그니처(특색 메뉴) 파라미터
_PAREN = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")     # 괄호 안 내용 전부
_NOISE = re.compile(r"[0-9%*★!#~\-_/.·]+")
_HANGUL = re.compile(r"[가-힣]")
SIG_MIN_NAT_SCH = 8        # 전국에서 최소 이만큼의 학교가 내야(노이즈 컷)
SIG_MIN_REGION_RATE = 0.4  # 지역 학교의 이 비율 이상이 내야
SIG_TOPN = 6


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd > 1e-9 else s * 0.0


def keyword_vector(model, words):
    vs = [model.wv[w] for w in words]          # 부분단어로 항상 벡터 존재
    v = np.mean(vs, axis=0)
    return v / (np.linalg.norm(v) + 1e-9)


def _norm_dish(d: str) -> str:
    d = _PAREN.sub("", d)
    d = _NOISE.sub("", d)
    return re.sub(r"\s+", "", d).strip()


def region_signatures(meals_df: pd.DataFrame, schools: pd.DataFrame) -> dict:
    """전국 대비 그 지역에서 유독 자주 나오는 메뉴(학교 단위 doc-freq lift)."""
    sido_of = dict(zip(schools["school_code"], schools["sido"]))
    school_dishes = defaultdict(set)           # 학교 -> 등장 메뉴 집합
    for r in meals_df.itertuples():
        for d in parse_menu_string(r.ddish_nm):
            nd = _norm_dish(d)
            if len(_HANGUL.findall(nd)) >= 2:  # 한글 2자 이상만
                school_dishes[r.school_code].add(nd)

    nat_sch = Counter()                        # 메뉴를 내는 전국 학교 수
    region_sch = defaultdict(Counter)          # 지역별 메뉴 내는 학교 수
    region_n = Counter()
    for sc, dishes in school_dishes.items():
        sido = sido_of.get(sc)
        if sido is None:
            continue
        region_n[sido] += 1
        for d in dishes:
            nat_sch[d] += 1
            region_sch[sido][d] += 1

    tot = sum(region_n.values())
    sig = {}
    for sido, n in region_n.items():
        rows = []
        for d, c in region_sch[sido].items():
            if nat_sch[d] < SIG_MIN_NAT_SCH:
                continue
            region_rate = c / n
            if region_rate < SIG_MIN_REGION_RATE:
                continue
            lift = region_rate / (nat_sch[d] / tot)
            rows.append((d, lift, region_rate))
        rows.sort(key=lambda r: r[1], reverse=True)
        sig[sido] = [{"item": d, "lift": round(lift, 1), "rate": round(rr, 3)}
                     for d, lift, rr in rows[:SIG_TOPN]]
    return sig


def main():
    raw = pd.read_parquet("school_vectors_raw.parquet")        # 속성 비율 + sido
    clusters = pd.read_parquet("school_clusters.parquet")[["school_code", "cluster"]]
    emb = pd.read_parquet("school_embeddings.parquet")
    emb_cols = [c for c in emb.columns if c.startswith("emb_")]
    model = FastText.load("fasttext.model")
    meals_df = pd.read_parquet("meals_lunch.parquet")
    schools = pd.read_parquet("schools.parquet")[["school_code", "sido"]]

    df = raw.merge(clusters, on="school_code").merge(emb, on="school_code")

    # 학교별 임베딩 정규화 (코사인 투영용)
    E = df[emb_cols].values
    En = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)

    # 대비 축: proj(A) - proj(B). 같은 학교 임베딩에서 차를 취해 전역 편향 상쇄.
    for name, (a, b) in CONTRASTS.items():
        df[name] = En @ keyword_vector(model, a) - En @ keyword_vector(model, b)

    # 지역 시그니처(특색 메뉴)
    signatures = region_signatures(meals_df, schools)

    # 시도 집계
    out = {}
    n_clusters = int(clusters["cluster"].max()) + 1
    con_rows = []
    for sido, g in df.groupby("sido"):
        row = {
            "n_schools": int(len(g)),
            "rice":          float(g["form_rice"].mean()),
            "bread":         float(g["form_bread"].mean()),
            "noodle":        float(g["form_noodle"].mean()),
            "seafood_share": float(g["protein_seafood"].mean()),
            "protein_index": float(g[PROTEIN_COLS].sum(axis=1).mean()),
            "dominant_cluster": int(g["cluster"].mode().iat[0]),
            "cluster_share": {str(c): float((g["cluster"] == c).mean())
                              for c in range(n_clusters)},
            "signature": signatures.get(sido, []),
        }
        for name in CONTRASTS:
            row[name + "_mean"] = float(g[name].mean())
        out[sido] = row
        con_rows.append({"sido": sido,
                         **{name: out[sido][name + "_mean"] for name in CONTRASTS}})

    # 대비 유사도는 지역 비교용으로 z-표준화 후 덮어쓰기
    cdf = pd.DataFrame(con_rows).set_index("sido")
    for name in CONTRASTS:
        z = _zscore(cdf[name])
        for sido in out:
            out[sido][name] = float(z[sido])
            del out[sido][name + "_mean"]

    with open("region_metrics.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"시도 {len(out)}개 지표 저장 -> region_metrics.json")
    # 시그니처 미리보기
    for sido in ["제주", "대구", "강원"]:
        if sido in out:
            items = ", ".join(s["item"] for s in out[sido]["signature"][:5])
            print(f"  {sido} 특색: {items}")


if __name__ == "__main__":
    main()
