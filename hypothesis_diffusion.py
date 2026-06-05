"""
hypothesis_diffusion.py
-----------------------
H-확산 검정: 신메뉴(마라)는 수도권/도시에서 시작해 지방으로 퍼지는가(공간 확산), 전국 동시발생인가?

H0: 마라 채택은 서울로부터의 거리·도시성과 무관(전국 동시).
H1: 먼 지역일수록 늦게/적게 채택(수도권→지방 확산).

설계
- 시도×연도 마라 등장률(천 끼당). '조기 채택' = 2021~2022 평균률.
- 서울 중심으로부터 거리(시도 중심, EPSG:5179) · 수도권 더미와 상관/대비.
- viz: 연도별 마라 코로플레스(소다중) + 거리 vs 조기채택 산점도.
"""
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from scipy.stats import pearsonr

YEARS = [2021, 2022, 2023, 2024, 2025]
KW = "마라"
FIG_DIR = "figures"
PAPER, INK, ACC = "#f6f1e7", "#211d17", "#b6452c"
NAME_MAP = {"서울특별시":"서울","부산광역시":"부산","대구광역시":"대구","인천광역시":"인천",
 "광주광역시":"광주","대전광역시":"대전","울산광역시":"울산","세종특별자치시":"세종",
 "경기도":"경기","강원도":"강원","충청북도":"충북","충청남도":"충남","전라북도":"전북",
 "전라남도":"전남","경상북도":"경북","경상남도":"경남","제주특별자치도":"제주"}
SUDO = {"서울", "경기", "인천"}


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name(); break
    matplotlib.rcParams["axes.unicode_minus"] = False


def main():
    _font()
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["y"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["y"].between(2021, 2025)]
    m["hit"] = m["ddish_nm"].str.contains(KW, na=False, regex=False)
    sido = pd.read_parquet("schools.parquet")[["school_code", "sido"]]
    m = m.merge(sido, on="school_code", how="left")

    rate = (m.groupby(["sido", "y"])["hit"].mean().unstack() * 1000).reindex(columns=YEARS)
    rate["early"] = rate[[2021, 2022]].mean(axis=1)
    rate["late"] = rate[[2024, 2025]].mean(axis=1)

    # 거리: 시도 중심 ~ 서울 중심
    gdf = gpd.read_file("skorea_provinces.json").set_crs(4326, allow_override=True).to_crs(5179)
    gdf["sido"] = gdf["name"].map(NAME_MAP)
    cent = gdf.set_geometry(gdf.geometry.representative_point())
    seoul = cent.loc[cent["sido"] == "서울"].geometry.iloc[0]
    gdf["dist"] = cent.geometry.distance(seoul) / 1000.0      # km
    R = gdf[["sido", "dist", "geometry"]].merge(rate.reset_index(), on="sido")

    print(f"=== H-확산: '{KW}' 시도별 채택 ===")
    print("시도별 연도 등장률(천 끼당):")
    print(rate[YEARS].round(1).to_string())

    r_e, p_e = pearsonr(R["dist"], R["early"])
    r_l, p_l = pearsonr(R["dist"], R["late"])
    print(f"\n거리(서울→) × 조기채택(2021-22): r={r_e:+.3f}, p={p_e:.3f}")
    print(f"거리(서울→) × 후기채택(2024-25): r={r_l:+.3f}, p={p_l:.3f}")
    su = R[R["sido"].isin(SUDO)]["early"].mean()
    no = R[~R["sido"].isin(SUDO)]["early"].mean()
    print(f"조기채택 평균: 수도권 {su:.2f} vs 비수도권 {no:.2f} (배수 {su/max(no,1e-9):.2f})")
    strong = (p_e < 0.05) and (r_e < -0.3)
    print(f"\n>>> {'강한 신호: 수도권→지방 확산' if strong else '약함: 거리와 무관(전국 동시발생에 가까움)'}")

    # 그림: 연도별 코로플레스 + 거리 산점도
    fig = plt.figure(figsize=(15, 5.6)); fig.patch.set_facecolor(PAPER)
    vmax = float(np.nanmax(R[YEARS].values))
    for i, y in enumerate(YEARS):
        ax = fig.add_subplot(1, 6, i + 1)
        R.plot(column=y, ax=ax, cmap="YlOrRd", vmin=0, vmax=vmax,
               edgecolor="#cdbfa3", linewidth=.3)
        ax.set_title(f"{y}", fontsize=12, color=INK); ax.axis("off"); ax.set_facecolor(PAPER)
    ax = fig.add_subplot(1, 6, 6); ax.set_facecolor("#fffdf8")
    ax.scatter(R["dist"], R["early"], s=40, color=ACC, edgecolor=INK, zorder=3)
    for _, r in R.iterrows():
        ax.annotate(r["sido"], (r["dist"], r["early"]), fontsize=7, xytext=(3, 2),
                    textcoords="offset points", color="#3a342a")
    z = np.polyfit(R["dist"], R["early"], 1)
    xs = np.array([R["dist"].min(), R["dist"].max()])
    ax.plot(xs, np.poly1d(z)(xs), "--", color=INK, lw=1.2, label=f"r={r_e:+.2f}")
    ax.set_xlabel("서울로부터 거리(km)"); ax.set_ylabel("조기채택률 2021-22")
    ax.legend(fontsize=9, frameon=False)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.suptitle(f"H-확산: '{KW}'의 시도별 확산 (연도별 등장률 + 거리 상관)", fontsize=14, color=INK)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/hyp_diffusion.png", dpi=200, facecolor=PAPER)
    print(f"\n그림: {FIG_DIR}/hyp_diffusion.png")


if __name__ == "__main__":
    main()
