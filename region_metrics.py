"""
region_metrics.py
-----------------
학교 벡터 + 군집 + FastText 모델 -> 시도별 지표 JSON (지도 시각화 입력).

지표 두 갈래
1) 명시 점유율: 밥/빵/면 form 점유율, 해산물·단백질 사용도(속성 비율)
2) 임베딩 키워드 유사도: 각 학교 임베딩과 키워드 벡터('해산물','단백질','밥'...)
   코사인 유사도 -> 시도 평균 -> 지역 비교 위해 z-score 표준화
3) 군집 구성: 시도별 군집 점유율 + 우세 군집

출력: region_metrics.json
"""
import json
import numpy as np
import pandas as pd
from gensim.models import FastText
from menu_attributes import FEATURE_COLUMNS

# 유사도용 키워드 (FastText는 OOV도 부분단어로 처리)
KEYWORDS = {
    "sim_seafood": ["해산물", "생선", "오징어", "새우"],
    "sim_protein": ["단백질", "고기", "육류"],
    "sim_rice":    ["밥", "쌀밥"],
    "sim_bread":   ["빵", "버거"],
    "sim_noodle":  ["면", "국수"],
}
PROTEIN_COLS = [c for c in FEATURE_COLUMNS if c.startswith("protein_")]


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd > 1e-9 else s * 0.0


def keyword_vector(model, words):
    vs = [model.wv[w] for w in words]          # 부분단어로 항상 벡터 존재
    return np.mean(vs, axis=0)


def main():
    raw = pd.read_parquet("school_vectors_raw.parquet")        # 속성 비율 + sido
    clusters = pd.read_parquet("school_clusters.parquet")[["school_code", "cluster"]]
    emb = pd.read_parquet("school_embeddings.parquet")
    emb_cols = [c for c in emb.columns if c.startswith("emb_")]
    model = FastText.load("fasttext.model")

    df = raw.merge(clusters, on="school_code").merge(emb, on="school_code")

    # 학교별 키워드 코사인 유사도
    E = df[emb_cols].values
    En = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
    for name, words in KEYWORDS.items():
        k = keyword_vector(model, words)
        k = k / (np.linalg.norm(k) + 1e-9)
        df[name] = En @ k

    # 시도 집계
    out = {}
    n_clusters = int(clusters["cluster"].max()) + 1
    sido_rows = []
    for sido, g in df.groupby("sido"):
        row = {
            "n_schools": int(len(g)),
            # 명시 점유율
            "rice":          float(g["form_rice"].mean()),
            "bread":         float(g["form_bread"].mean()),
            "noodle":        float(g["form_noodle"].mean()),
            "seafood_share": float(g["protein_seafood"].mean()),
            "protein_index": float(g[PROTEIN_COLS].sum(axis=1).mean()),
            # 군집 구성
            "dominant_cluster": int(g["cluster"].mode().iat[0]),
            "cluster_share": {str(c): float((g["cluster"] == c).mean())
                              for c in range(n_clusters)},
        }
        for name in KEYWORDS:
            row[name + "_mean"] = float(g[name].mean())
        out[sido] = row
        sido_rows.append({"sido": sido, **{name: out[sido][name + "_mean"] for name in KEYWORDS}})

    # 유사도는 지역 비교용으로 z-score 표준화 후 덮어쓰기
    sdf = pd.DataFrame(sido_rows).set_index("sido")
    for name in KEYWORDS:
        z = _zscore(sdf[name])
        for sido in out:
            out[sido][name] = float(z[sido])
            del out[sido][name + "_mean"]

    with open("region_metrics.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"시도 {len(out)}개 지표 저장 -> region_metrics.json")
    print(json.dumps(list(out.items())[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
