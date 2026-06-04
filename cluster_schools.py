"""
cluster_schools.py
------------------
속성 블록(43, CLR) + 학습형 임베딩 블록(64) 결합 -> 군집 -> 지역 경향성.

핵심: 두 블록을 각각 표준화 후 결합한다. dense 임베딩이 거리를 지배하지
않도록 블록 가중(EMB_WEIGHT)으로 균형을 맞춘다.
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from scipy.stats import chi2_contingency
from menu_attributes import FEATURE_COLUMNS

K_RANGE = range(3, 11)
PCA_VAR = 0.90
# 임베딩 블록 상대 가중 (0이면 속성만 사용).
# 임베딩(128차원)을 1.0으로 두면 속성(43차원)을 압도해 거대 군집 1개 + 이상치로
# 붕괴하고 지역 변별력(Cramér's V)이 떨어진다. 스윕 결과 0.25 부근이 군집 균형과
# 지역 변별력을 유지하면서 임베딩의 잠재 정보를 소량 반영하는 지점이었다.
# (임베딩의 의미 정보는 region_metrics.py의 키워드 유사도 지표에서 더 직접적으로 쓰인다.)
EMB_WEIGHT = 0.25


def cramers_v(confusion):
    chi2 = chi2_contingency(confusion)[0]
    n = confusion.sum()
    r, k = confusion.shape
    return float(np.sqrt((chi2 / n) / (min(r, k) - 1)))


def load_features():
    clr = pd.read_parquet("school_vectors_clr.parquet")
    raw = pd.read_parquet("school_vectors_raw.parquet")
    try:
        emb = pd.read_parquet("school_embeddings.parquet")
        emb_cols = [c for c in emb.columns if c.startswith("emb_")]
    except FileNotFoundError:
        emb, emb_cols = None, []
        print("주의: school_embeddings.parquet 없음 -> 속성 블록만 사용")

    df = clr.copy()
    if emb is not None:
        df = df.merge(emb, on="school_code", how="inner")
    return df, raw, emb_cols


def build_matrix(df, emb_cols):
    """블록별 표준화 후 결합."""
    attr = StandardScaler().fit_transform(df[FEATURE_COLUMNS].values)
    blocks = [attr]
    if emb_cols and EMB_WEIGHT > 0:
        emb = StandardScaler().fit_transform(df[emb_cols].values) * EMB_WEIGHT
        blocks.append(emb)
    X = np.hstack(blocks)
    print(f"결합 행렬: {X.shape} (속성 {len(FEATURE_COLUMNS)} + 임베딩 {len(emb_cols)})")
    return X


def run():
    df, raw, emb_cols = load_features()
    X = build_matrix(df, emb_cols)
    pca = PCA(n_components=PCA_VAR, random_state=0)
    Xp = pca.fit_transform(X)
    print(f"PCA: {Xp.shape[1]}성분, 분산 {pca.explained_variance_ratio_.sum():.2f}")

    best_k, best_s = None, -1
    for k in K_RANGE:
        lab = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Xp)
        s = silhouette_score(Xp, lab)
        print(f"  k={k}  silhouette={s:.3f}")
        if s > best_s:
            best_k, best_s = k, s
    print(f"선택 k={best_k} (silhouette={best_s:.3f})")

    labels = KMeans(n_clusters=best_k, n_init=10, random_state=0).fit_predict(Xp)
    out = df[["school_code", "sido"]].copy()
    out["cluster"] = labels
    # 해석은 원 비율(raw) 속성으로
    prof = out.merge(raw[["school_code"] + FEATURE_COLUMNS], on="school_code")

    overall = prof[FEATURE_COLUMNS].mean()
    print("\n=== 군집별 변별 속성 (전국 평균 대비) ===")
    for c in sorted(prof["cluster"].unique()):
        sub = prof[prof["cluster"] == c]
        diff = (sub[FEATURE_COLUMNS].mean() - overall).sort_values(ascending=False)
        top = ", ".join(f"{k}+{v:.2f}" for k, v in diff.head(5).items())
        print(f"  군집{c} (n={len(sub)}): ↑ {top}")

    ct = pd.crosstab(out["cluster"], out["sido"])
    print(f"\n군집 x 시도 Cramér's V = {cramers_v(ct.values):.3f}")
    share = pd.crosstab(out["sido"], out["cluster"], normalize="index")
    print("\n시도별 우세 군집:")
    print(share.idxmax(axis=1).to_string())

    out.to_parquet("school_clusters.parquet", index=False)
    return out


if __name__ == "__main__":
    run()
