"""
spatial_autocorr.py
-------------------
시도 단위 급식 식문화 지표의 공간 자기상관 분석 (GIS 핵심).

질문: 급식 식문화가 공간적으로 구조화돼 있는가 — 인접 시도끼리 닮는가,
어디가 hot/cold spot이고 어디가 공간 이상치(예: 제주)인가?

방법 (수식은 포스터 구석 '방법'으로, 결론은 그림으로)
1. 공간가중행렬 W: Queen 인접(경계 공유). 제주는 섬이라 무연결 -> 최근접(전남) 수동 연결.
2. Global Moran's I: 전국이 '끼리끼리'인지 한 숫자(-1~+1)로. 999회 순열검정 p.
3. Local Moran's I (LISA): 지역별 HH/LL/HL/LH 분류 + 순열 p -> hot/cold spot·이상치 지도.
4. Moran 산점도: x=지역값(z), y=이웃평균(Wz), 기울기=Moran's I.

산출: 콘솔 표 + figures/*.png (LISA 지도, Moran 산점도)
"""
import json
import os

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from libpysal.weights import Queen, KNN, W, lag_spatial
from esda.moran import Moran, Moran_Local

SEED = 0
PERM = 999
FIG_DIR = "figures"

# geojson 전체명 -> 지표 JSON의 짧은 시도명
NAME_MAP = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전라북도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주",
}

# 분석할 지표 (라벨)
METRICS = {
    "rice": "밥 점유율", "bread": "빵 점유율", "noodle": "면 점유율",
    "seafood_share": "해산물 사용도", "protein_index": "단백질 사용도",
    "con_sea_meat": "해산물↔육류", "con_noodle_rice": "면↔밥",
    "con_spicy_mild": "매운↔순한", "con_west_korean": "양식↔한식",
    "PC1": "주축1(전통↔표준화)", "PC2": "주축2(해안성)",
}
# LISA 4분류 색 (paper 팔레트)
Q_COLOR = {0: "#e8e2d5", 1: "#c0392b", 2: "#a9cce3", 3: "#2c6f9b", 4: "#f1948a"}
Q_LABEL = {0: "유의하지 않음", 1: "HH 다같이 높음", 2: "LH 외딴(낮은 섬)",
           3: "LL 다같이 낮음", 4: "HL 외딴(높은 섬)"}


def _set_korean_font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f or "NanumGothic" in f:
            fm.fontManager.addfont(f)
            try:
                matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name()
            except Exception:
                continue
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


def load_gdf():
    d = json.load(open("region_metrics.json", encoding="utf-8"))
    gdf = gpd.read_file("skorea_provinces.json")
    gdf["sido"] = gdf["name"].map(NAME_MAP)
    gdf = gdf.dropna(subset=["sido"]).reset_index(drop=True)
    for m in ["rice", "bread", "noodle", "seafood_share", "protein_index",
              "con_sea_meat", "con_noodle_rice", "con_spicy_mild", "con_west_korean"]:
        gdf[m] = gdf["sido"].map(lambda s: d[s][m])
    # 주축(PCA) 추가
    base = ["rice", "bread", "noodle", "seafood_share", "protein_index",
            "con_sea_meat", "con_noodle_rice", "con_spicy_mild", "con_west_korean"]
    Z = StandardScaler().fit_transform(gdf[base].values)
    pcs = PCA(n_components=2, random_state=SEED).fit_transform(Z)
    gdf["PC1"], gdf["PC2"] = pcs[:, 0], pcs[:, 1]
    return gdf


def build_weights(gdf):
    """Queen 인접 + 섬(제주) 최근접 연결, 행표준화."""
    w = Queen.from_dataframe(gdf, use_index=True)
    if w.islands:
        knn1 = KNN.from_dataframe(gdf, k=1)
        neigh = {i: list(w.neighbors[i]) for i in w.id_order}
        wts = {i: list(w.weights[i]) for i in w.id_order}
        links = []
        for isl in w.islands:
            j = knn1.neighbors[isl][0]
            links.append((gdf.loc[isl, "sido"], gdf.loc[j, "sido"]))
            for a, b in [(isl, j), (j, isl)]:
                if b not in neigh[a]:
                    neigh[a].append(b); wts[a].append(1.0)
        w = W(neigh, wts)
        print("  섬 연결(경계 무접촉 -> 최근접):", ", ".join(f"{a}~{b}" for a, b in links))
    w.transform = "r"
    return w


def global_moran(gdf, w):
    rows = []
    for m, label in METRICS.items():
        y = gdf[m].values.astype(float)
        np.random.seed(SEED)
        mi = Moran(y, w, permutations=PERM)
        verdict = ("끼리끼리(군집)" if mi.I > 0 else "흩어짐(분산)")
        sig = "유의" if mi.p_sim <= 0.05 else ("경향" if mi.p_sim <= 0.1 else "무작위")
        rows.append({"지표": label, "MoranI": round(mi.I, 3),
                     "p": round(mi.p_sim, 3), "판정": f"{verdict}·{sig}"})
    return pd.DataFrame(rows).sort_values("MoranI", ascending=False).reset_index(drop=True)


def lisa(gdf, w, metric):
    y = gdf[metric].values.astype(float)
    np.random.seed(SEED)
    loc = Moran_Local(y, w, permutations=PERM, seed=SEED)
    cat = np.where(loc.p_sim <= 0.05, loc.q, 0)
    return loc, cat


def _draw_map(ax, gdf, cat, title):
    colors = [Q_COLOR[c] for c in cat]
    gdf.plot(ax=ax, color=colors, edgecolor="#6f6657", linewidth=0.6)
    for _, r in gdf.iterrows():
        c = r.geometry.representative_point()
        ax.annotate(r["sido"], (c.x, c.y), ha="center", va="center", fontsize=7,
                    color="#211d17",
                    path_effects=[])
    ax.set_title(title, fontsize=12, color="#211d17")
    ax.axis("off")


def fig_lisa_map(gdf, cat, metric, fname):
    fig, ax = plt.subplots(figsize=(6, 7))
    fig.patch.set_facecolor("#f6f1e7"); ax.set_facecolor("#f6f1e7")
    _draw_map(ax, gdf, cat, f"LISA: {METRICS[metric]}")
    handles = [plt.Rectangle((0, 0), 1, 1, fc=Q_COLOR[k], ec="#6f6657")
               for k in [1, 3, 4, 2, 0]]
    ax.legend(handles, [Q_LABEL[k] for k in [1, 3, 4, 2, 0]],
              loc="lower left", fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(fname, dpi=150, facecolor="#f6f1e7"); plt.close(fig)


def fig_moran_scatter(gdf, w, metric, mi_I, fname):
    y = gdf[metric].values.astype(float)
    z = (y - y.mean()) / y.std()
    wz = lag_spatial(w, z)
    fig, ax = plt.subplots(figsize=(6, 6))
    fig.patch.set_facecolor("#f6f1e7"); ax.set_facecolor("#fffdf8")
    ax.axhline(0, color="#b0a890", lw=.8); ax.axvline(0, color="#b0a890", lw=.8)
    ax.scatter(z, wz, s=60, color="#b6452c", edgecolor="#211d17", zorder=3)
    xs = np.array([z.min() - .3, z.max() + .3])
    ax.plot(xs, mi_I * xs, color="#211d17", lw=1.6, label=f"기울기 = Moran's I = {mi_I:.2f}")
    for i, r in gdf.iterrows():
        ax.annotate(r["sido"], (z[i], wz[i]), fontsize=7, xytext=(3, 3),
                    textcoords="offset points", color="#3a342a")
    ax.set_xlabel("우리 지역 값 (z)"); ax.set_ylabel("이웃 평균 값 (Wz)")
    ax.set_title(f"Moran 산점도: {METRICS[metric]}", fontsize=12)
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    fig.tight_layout(); fig.savefig(fname, dpi=150, facecolor="#f6f1e7"); plt.close(fig)


def fig_lisa_panel(gdf, w, metrics4, fname):
    fig, axes = plt.subplots(1, len(metrics4), figsize=(4.2 * len(metrics4), 5.2))
    fig.patch.set_facecolor("#f6f1e7")
    for ax, m in zip(axes, metrics4):
        ax.set_facecolor("#f6f1e7")
        _, cat = lisa(gdf, w, m)
        _draw_map(ax, gdf, cat, METRICS[m])
    fig.tight_layout(); fig.savefig(fname, dpi=150, facecolor="#f6f1e7"); plt.close(fig)


def main():
    _set_korean_font()
    os.makedirs(FIG_DIR, exist_ok=True)
    gdf = load_gdf()
    print(f"시도 {len(gdf)}개 로드")
    w = build_weights(gdf)

    print("\n=== Global Moran's I (전역 공간 자기상관) ===")
    table = global_moran(gdf, w)
    print(table.to_string(index=False))

    # 헤드라인 축 = 유의하면서 |I| 최대
    sigtab = table.copy()
    sigtab["abs"] = sigtab["MoranI"].abs()
    head_label = sigtab.sort_values("abs", ascending=False).iloc[0]["지표"]
    head = {v: k for k, v in METRICS.items()}[head_label]
    head_I = float(table[table["지표"] == head_label]["MoranI"].iloc[0])
    print(f"\n헤드라인 축: {head_label} (Moran's I={head_I:.3f})")

    loc, cat = lisa(gdf, w, head)
    print("\n=== LISA 분류 (유의한 지역만, p<=0.05) ===")
    for i, r in gdf.iterrows():
        if cat[i]:
            print(f"  {r['sido']:4s} {Q_LABEL[cat[i]]} (p={loc.p_sim[i]:.3f})")

    fig_lisa_map(gdf, cat, head, f"{FIG_DIR}/lisa_{head}.png")
    fig_moran_scatter(gdf, w, head, head_I, f"{FIG_DIR}/moran_scatter_{head}.png")
    fig_lisa_panel(gdf, w, ["seafood_share", "con_spicy_mild", "con_west_korean", "PC1"],
                   f"{FIG_DIR}/lisa_panel.png")
    print(f"\n그림 저장: {FIG_DIR}/lisa_{head}.png, moran_scatter_{head}.png, lisa_panel.png")


if __name__ == "__main__":
    main()
