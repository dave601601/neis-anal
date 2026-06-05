"""
trend_sensitivity.py
--------------------
사회 음식 트렌드에 지역이 얼마나 민감/둔감한가.

전국적으로 떠오른 유행 메뉴 바스켓을 정하고, 시도별로
- 최근 수용 수준(2025 등장률) + 증가 속도(2021→2025) 를 z-합친 '트렌드 수용 지수',
- 수도권/서울거리와의 관계, 유행별 지역 편차(CV).
산출: figures/trend_sens_*.png + 콘솔.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from scipy.stats import pearsonr

YEARS = [2021, 2022, 2023, 2024, 2025]
TREND = ["마라", "두바이", "탕후루", "약과", "그릭", "바질", "비건"]  # 마라탕 제외(마라 부분집합=이중계수)
SUDO = {"서울", "경기", "인천"}
FIG_DIR = "figures"
PAPER, INK, ACC, COOL = "#f6f1e7", "#211d17", "#b6452c", "#2c6f7a"
NAME_MAP = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
 "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
 "경기도": "경기", "강원도": "강원", "충청북도": "충북", "충청남도": "충남", "전라북도": "전북",
 "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주"}
EXCLUDE = {"전북"}      # NEIS 중식 2024부터라 연도 비교 불가


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name(); break
    matplotlib.rcParams["axes.unicode_minus"] = False


def _z(s):
    return (s - s.mean()) / (s.std(ddof=0) + 1e-9)


def main():
    _font()
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["y"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["y"].isin(YEARS)]
    sido = pd.read_parquet("schools.parquet")[["school_code", "sido"]]
    m = m.merge(sido, on="school_code")
    m = m[~m["sido"].isin(EXCLUDE)]

    den = m.groupby(["sido", "y"]).size()
    # 유행별 (sido,year) 등장률(천 끼당)
    rate = {}
    for kw in TREND:
        hit = m[m["ddish_nm"].str.contains(kw, na=False, regex=False)]
        rate[kw] = (hit.groupby(["sido", "y"]).size() / den * 1000).unstack().reindex(columns=YEARS).fillna(0)

    sidos = rate[TREND[0]].index.tolist()
    # 바스켓(유행 합) per (sido,year)
    basket = sum(rate[kw] for kw in TREND)

    # 트렌드 수용 지수 = z(2025 수준) + z(2021→2025 증가) 평균, 유행별로 z 후 합
    lvl = pd.DataFrame({kw: _z(rate[kw][2025]) for kw in TREND}).mean(axis=1)
    grw = pd.DataFrame({kw: _z(rate[kw][2025] - rate[kw][2021]) for kw in TREND}).mean(axis=1)
    sens = ((lvl + grw) / 2).sort_values(ascending=False)

    print("=== 트렌드 수용 지수 (민감 ↑ / 둔감 ↓) ===")
    print(f"{'시도':4s} {'지수':>6s} {'2025바스켓':>9s} {'증가':>7s}")
    for s in sens.index:
        tag = "수도권" if s in SUDO else ""
        print(f"  {s:4s} {sens[s]:+6.2f}  {basket.loc[s,2025]:8.1f}  "
              f"{basket.loc[s,2025]-basket.loc[s,2021]:+6.1f} {tag}")

    print(f"\n바스켓 2025 등장률 범위: {basket[2025].min():.1f} ~ {basket[2025].max():.1f} "
          f"(배수 {basket[2025].max()/basket[2025].min():.1f}) → 지역 편차 {'큼' if basket[2025].max()/basket[2025].min()>1.5 else '작음'}")

    # 수도권 vs 비수도권, 서울 거리
    su = sens[sens.index.isin(SUDO)].mean(); no = sens[~sens.index.isin(SUDO)].mean()
    print(f"수도권 수용지수 {su:+.2f} vs 비수도권 {no:+.2f}")
    g = gpd.read_file("skorea_provinces.json").set_crs(4326, allow_override=True).to_crs(5179)
    g["sido"] = g["name"].map(NAME_MAP)
    cent = g.set_geometry(g.geometry.representative_point())
    seoul = cent[cent.sido == "서울"].geometry.iloc[0]
    g["dist"] = cent.geometry.distance(seoul) / 1000
    gg = g[g.sido.isin(sidos)].copy()
    gg["sens"] = gg["sido"].map(sens)
    r, p = pearsonr(gg["dist"], gg["sens"])
    print(f"서울 거리 × 수용지수: r={r:+.2f}, p={p:.3f} (음=수도권 민감)")

    # 유행별 지역 편차(2025 CV): 어떤 유행이 지역색이 강한가
    print("\n유행별 2025 지역 편차(CV=표준편차/평균, 큰=지역적):")
    for kw in sorted(TREND, key=lambda k: -(rate[k][2025].std() / (rate[k][2025].mean() + 1e-9))):
        cv = rate[kw][2025].std() / (rate[kw][2025].mean() + 1e-9)
        top = rate[kw][2025].idxmax()
        print(f"  {kw:5s} CV={cv:.2f}  최고={top}({rate[kw].loc[top,2025]:.1f})")

    # 그림 1: 수용지수 코로플레스
    fig, ax = plt.subplots(figsize=(6.5, 7.5)); fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    gg.plot(column="sens", ax=ax, cmap="YlOrRd", edgecolor="#cdbfa3", linewidth=.4,
            legend=True, legend_kwds={"shrink": .6, "label": "트렌드 수용 지수"})
    for _, rr in gg.iterrows():
        c = rr.geometry.representative_point()
        ax.annotate(rr["sido"], (c.x, c.y), ha="center", va="center", fontsize=8,
                    color="#211d17")
    ax.set_title("사회 음식 트렌드 수용 지수 — 민감(진함) vs 둔감(연함)", fontsize=12, color=INK)
    ax.axis("off")
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/trend_sens_map.png", dpi=200, facecolor=PAPER)

    # 그림 2: 바스켓 궤적(민감 top3·둔감 bottom3 강조)
    fig2, ax2 = plt.subplots(figsize=(9, 5.5)); fig2.patch.set_facecolor(PAPER); ax2.set_facecolor("#fffdf8")
    hi, lo = sens.index[:3], sens.index[-3:]
    for s in sidos:
        if s in hi:
            ax2.plot(YEARS, basket.loc[s], "-o", color=ACC, lw=2.2, ms=4, label=f"민감 {s}")
        elif s in lo:
            ax2.plot(YEARS, basket.loc[s], "-o", color=COOL, lw=2.2, ms=4, label=f"둔감 {s}")
        else:
            ax2.plot(YEARS, basket.loc[s], "-", color="#cdbfa3", lw=1, alpha=.7)
    ax2.set_xticks(YEARS); ax2.set_xlabel("연도"); ax2.set_ylabel("유행 메뉴 바스켓 등장률(천 끼당)")
    ax2.set_title("유행 메뉴(마라·두바이 등) 수용 궤적 — 주황=민감, 청록=둔감", fontsize=12, color=INK)
    ax2.legend(fontsize=8, frameon=False, ncol=2)
    for sp in ["top", "right"]:
        ax2.spines[sp].set_visible(False)
    fig2.tight_layout(); fig2.savefig(f"{FIG_DIR}/trend_sens_traj.png", dpi=200, facecolor=PAPER)

    # 그림 3: 랭킹 바
    fig3, ax3 = plt.subplots(figsize=(7, 7)); fig3.patch.set_facecolor(PAPER); ax3.set_facecolor("#fffdf8")
    yy = np.arange(len(sens))
    ax3.barh(yy, sens.values, color=[COOL if s in SUDO else ACC for s in sens.index])
    ax3.set_yticks(yy); ax3.set_yticklabels(sens.index, fontsize=9); ax3.invert_yaxis()
    ax3.axvline(0, color=INK, lw=.8)
    ax3.set_xlabel("트렌드 수용 지수 (z)"); ax3.set_title("시도별 트렌드 민감도 랭킹 (청록=수도권)", fontsize=12, color=INK)
    for sp in ["top", "right"]:
        ax3.spines[sp].set_visible(False)
    fig3.tight_layout(); fig3.savefig(f"{FIG_DIR}/trend_sens_rank.png", dpi=200, facecolor=PAPER)
    print("\n그림: trend_sens_map.png, trend_sens_traj.png, trend_sens_rank.png")


if __name__ == "__main__":
    main()
