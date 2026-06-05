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
from scipy.stats import pearsonr
from libpysal.weights import lag_spatial
from esda.moran import Moran, Moran_Local
from esda.getisord import G_Local

from spatial_sigungu import (load_municipalities, school_sigungu, build_weights,
                             aggregate, _font, Q_COLOR, Q_LABEL, FIG_DIR)

TREND = ["마라", "두바이", "탕후루", "약과", "그릭", "바질", "비건"]
NONMARA = [k for k in TREND if k != "마라"]
EXCLUDE = {"전북"}                  # 중식 2024부터라 2025 비교서 제외
YEAR = 2025
SEED, PERM = 0, 999
MIN_SCH_T = 5                       # 트렌드는 sparse -> 시군구당 학교 5교 이상만
PAPER, INK = "#f6f1e7", "#211d17"


def sigungu_trend_rate(gkeys):
    """시군구별 2025 등장률(천 끼당) — 바스켓/마라/비마라 동일 단위 + 학교수."""
    sg = school_sigungu(gkeys)                                  # school_code, sido, jname
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["y"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["y"] == YEAR].merge(sg, on="school_code")
    m = m[~m["sido"].isin(EXCLUDE)]
    grp = m.groupby(["sido", "jname"])
    den = grp.size()
    d = m["ddish_nm"]

    def rate(kws):
        h = m[d.str.contains("|".join(kws), na=False, regex=True)].groupby(["sido", "jname"]).size()
        return (h / den * 1000)

    out = pd.DataFrame({
        "trend": rate(TREND), "mara": rate(["마라"]), "nonmara": rate(NONMARA),
        "n_sch": grp["school_code"].nunique(),
    }).fillna(0.0).reset_index()
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


def lisa_cat(y, w):
    loc = Moran_Local(np.asarray(y, float), w, permutations=PERM, seed=SEED)
    return np.where(loc.p_sim <= 0.05, loc.q, 0)


def main():
    _font(); os.makedirs(FIG_DIR, exist_ok=True)
    gall, gkeys, prov = load_municipalities()
    df = sigungu_trend_rate(gkeys)
    g = gall.merge(df, on=["sido", "jname"], how="inner")
    print(f"분석 단위: 시군구 {len(g)}개 (>= {MIN_SCH_T}교, 2025, 전북 제외)")
    w = build_weights(g)

    # 1) 공간 자기상관 '분해' — 바스켓의 군집은 누가 만드나?
    print("\n=== Global Moran's I 분해 (트렌드 수용) ===")
    for col, lab in [("mara", "마라 단독"), ("trend", "바스켓 7종"), ("nonmara", "비마라 6종")]:
        np.random.seed(SEED)
        mi = Moran(g[col].values.astype(float), w, permutations=PERM)
        tag = "공간 군집(유의)" if mi.p_sim <= 0.05 else "무작위(비유의)"
        print(f"  {lab:9s} I={mi.I:+.3f}  p={mi.p_sim:.3f}  -> {tag}")
    share = g["mara"].sum() / g["trend"].sum() * 100
    print(f"  (바스켓 등장 중 '마라' 비중 ~ {share:.0f}%)")

    # 2) 마라 단독 LISA — 바스켓 군집의 사실상 전부, 주력 지도
    np.random.seed(SEED); mi_m = Moran(g["mara"].values.astype(float), w, permutations=PERM)
    cat = lisa_cat(g["mara"].values, w)
    hh = [(g.iloc[i]["sido"], g.iloc[i]["jname"]) for i in range(len(g)) if cat[i] == 1]
    ll = [(g.iloc[i]["sido"], g.iloc[i]["jname"]) for i in range(len(g)) if cat[i] == 3]
    print(f"\n=== '마라' LISA (I={mi_m.I:.3f}, p={mi_m.p_sim:.3f}): HH {len(hh)} · LL {len(ll)} ===")
    print("  HH(핫스팟):", ", ".join(f"{s}{n}" for s, n in hh[:18]))
    print("  LL(콜드스팟):", ", ".join(f"{s}{n}" for s, n in ll[:18]))
    fig_cluster(gall, prov, g, cat,
                f"시군구 '마라' 수용 LISA  (Moran's I={mi_m.I:.2f}, p={mi_m.p_sim:.3f})",
                f"{FIG_DIR}/trend_mara_lisa.png")

    # 3) 마라의 공간 vs '매운맛 식문화'의 공간 — 같은가?(순환성 점검)
    agg, _, _ = aggregate(gkeys)                       # con_spicy_mild(매운↔순한) 시군구 z
    cmp = g.merge(agg[["sido", "jname", "con_spicy_mild"]], on=["sido", "jname"])
    wc = build_weights(cmp)
    r, p = pearsonr(cmp["mara"].values, cmp["con_spicy_mild"].values)
    m_cat = lisa_cat(cmp["mara"].values, wc)
    s_cat = lisa_cat(cmp["con_spicy_mild"].values, wc)
    both = int(((m_cat == 1) & (s_cat == 1)).sum())
    print(f"\n=== 마라 공간 vs 매운맛 공간 (공통 {len(cmp)} 시군구) ===")
    print(f"  상관 r={r:+.2f} (p={p:.3f}) | 마라 HH {(m_cat==1).sum()} · 매운맛 HH {(s_cat==1).sum()} · 둘 다 HH {both}곳")
    print(f"  -> r이 0~음수면 '마라=도시 외식 트렌드' ≠ '매운맛=식문화'(다른 공간)")
    print("\n그림: figures/trend_mara_lisa.png")


if __name__ == "__main__":
    main()
