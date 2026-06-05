"""
trend_spatial.py
----------------
트렌드 수용의 '진짜' 공간 분석 — 시군구(237) 단위.

기존 발견3(수도권 역설)은 시도(16) 평균·줄세우기라 비평을 받았다("엑셀 피벗이지 공간분석이
아니다"). 그래서 같은 트렌드 바스켓(마라·두바이·탕후루·약과·그릭·바질·비건)의 등장률을
시군구(237)로 올리고, Queen 인접 가중치 위에서
  - Global Moran's I  : 트렌드 수용이 공간적으로 군집하는가(무작위가 아닌가)?
  - LISA(Local Moran) : 어디가 핫스팟(HH)·콜드스팟(LL)인가?
  - Getis-Ord Gi*     : 핫스팟/콜드스팟 z-검정(군집 강도)
를 검정한다. 매핑·가중치는 spatial_sigungu.py를 그대로 재사용.

산출: figures/trend_lisa.png, figures/trend_gistar.png + 콘솔(Moran's I·p·핫/콜드 목록).
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from libpysal.weights import lag_spatial
from esda.moran import Moran, Moran_Local
from esda.getisord import G_Local

from spatial_sigungu import (load_municipalities, school_sigungu, build_weights,
                             _font, Q_COLOR, Q_LABEL, FIG_DIR)

TREND = ["마라", "두바이", "탕후루", "약과", "그릭", "바질", "비건"]
EXCLUDE = {"전북"}                  # 중식 2024부터라 2025 비교서 제외
YEAR = 2025
SEED, PERM = 0, 999
MIN_SCH_T = 5                       # 트렌드는 sparse -> 시군구당 학교 5교 이상만
PAPER, INK = "#f6f1e7", "#211d17"


def sigungu_trend_rate(gkeys):
    """시군구별 2025 트렌드 바스켓 등장률(천 끼당) + 학교수."""
    sg = school_sigungu(gkeys)                                  # school_code, sido, jname
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["y"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["y"] == YEAR].merge(sg, on="school_code")
    m = m[~m["sido"].isin(EXCLUDE)]
    pat = "|".join(TREND)
    m["hit"] = m["ddish_nm"].str.contains(pat, na=False, regex=True)
    grp = m.groupby(["sido", "jname"])
    out = pd.DataFrame({
        "trend": grp["hit"].sum() / grp.size() * 1000,
        "n_sch": grp["school_code"].nunique(),
    }).reset_index()
    return out[out["n_sch"] >= MIN_SCH_T].reset_index(drop=True)


def fig_cluster(gall, prov, g, cat, title, fname, labels=Q_LABEL, colors=Q_COLOR):
    fig, ax = plt.subplots(figsize=(7.2, 8.4))
    fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    gall.plot(ax=ax, color="#efe8d8", edgecolor="#d8cdb8", linewidth=0.25)
    g.plot(ax=ax, color=[colors[c] for c in cat], edgecolor="#b8ab92", linewidth=0.25)
    prov.boundary.plot(ax=ax, color="#6f6657", linewidth=0.9)
    ax.set_title(title, fontsize=13, color=INK); ax.axis("off")
    keys = [k for k in labels if k in set(cat)] or list(labels)
    handles = [plt.Rectangle((0, 0), 1, 1, fc=colors[k], ec="#9a8f78") for k in keys]
    ax.legend(handles, [labels[k] for k in keys], loc="lower left", fontsize=9, frameon=False)
    fig.tight_layout(); fig.savefig(fname, dpi=200, facecolor=PAPER); plt.close(fig)


def main():
    _font(); os.makedirs(FIG_DIR, exist_ok=True)
    gall, gkeys, prov = load_municipalities()
    rate = sigungu_trend_rate(gkeys)
    g = gall.merge(rate, on=["sido", "jname"], how="inner")
    print(f"분석 단위: 시군구 {len(g)}개 (>= {MIN_SCH_T}교, 2025, 전북 제외)")
    print(f"트렌드 등장률 범위: {g['trend'].min():.1f} ~ {g['trend'].max():.1f} (천 끼당)")

    w = build_weights(g)
    y = g["trend"].values.astype(float)

    # 1) Global Moran's I — 공간적으로 군집하는가?
    np.random.seed(SEED)
    mi = Moran(y, w, permutations=PERM)
    print(f"\n=== Global Moran's I (트렌드 수용, 시군구 {len(g)}) ===")
    print(f"  I = {mi.I:+.3f},  p(순열 {PERM}) = {mi.p_sim:.3f},  z = {mi.z_sim:+.2f}")
    print(f"  -> {'공간 군집(유의)' if mi.p_sim <= 0.05 else '무작위'}  (양수 I = 끼리끼리 뭉침)")

    # 2) LISA — 핫스팟(HH)/콜드스팟(LL)
    loc = Moran_Local(y, w, permutations=PERM, seed=SEED)
    cat = np.where(loc.p_sim <= 0.05, loc.q, 0)
    hh = [(g.iloc[i]["sido"], g.iloc[i]["jname"]) for i in range(len(g)) if cat[i] == 1]
    ll = [(g.iloc[i]["sido"], g.iloc[i]["jname"]) for i in range(len(g)) if cat[i] == 3]
    print(f"\n=== LISA: 핫스팟 HH {len(hh)}곳 · 콜드스팟 LL {len(ll)}곳 ===")
    print("  HH(다같이 높음):", ", ".join(f"{s}{n}" for s, n in hh[:18]))
    print("  LL(다같이 낮음):", ", ".join(f"{s}{n}" for s, n in ll[:18]))
    hh_sido = pd.Series([s for s, _ in hh]).value_counts()
    ll_sido = pd.Series([s for s, _ in ll]).value_counts()
    print("  HH 시도 분포:", dict(hh_sido)); print("  LL 시도 분포:", dict(ll_sido))
    fig_cluster(gall, prov, g, cat, f"시군구 트렌드 수용 LISA  (Moran's I={mi.I:.2f}, p={mi.p_sim:.3f})",
                f"{FIG_DIR}/trend_lisa.png")

    # 3) Getis-Ord Gi* — 핫/콜드 z-검정
    np.random.seed(SEED)
    gi = G_Local(y, w, star=True, permutations=PERM, seed=SEED)
    z = gi.Zs
    gcat = np.where((gi.p_sim <= 0.05) & (z > 0), 1,
                    np.where((gi.p_sim <= 0.05) & (z < 0), 3, 0))
    gi_lab = {0: "유의하지 않음", 1: "Gi* 핫스팟", 3: "Gi* 콜드스팟"}
    gi_col = {0: "#e8e2d5", 1: "#c0392b", 3: "#2c6f9b"}
    print(f"\n=== Getis-Ord Gi* (z>0 핫, z<0 콜드, p<=.05) ===")
    print(f"  핫스팟 {int((gcat==1).sum())}곳 · 콜드스팟 {int((gcat==3).sum())}곳")
    fig_cluster(gall, prov, g, gcat, f"시군구 트렌드 수용 Gi* 핫스팟",
                f"{FIG_DIR}/trend_gistar.png", labels=gi_lab, colors=gi_col)
    print("\n그림: figures/trend_lisa.png, figures/trend_gistar.png")


if __name__ == "__main__":
    main()
