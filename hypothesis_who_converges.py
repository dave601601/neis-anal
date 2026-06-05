"""
hypothesis_who_converges.py
---------------------------
'누가 누구로 수렴하나' — robust하게 동질화된 전통 축(발효·찌개·김치·나물)에서
어느 지역이 향토색을 잃고 어디로 끌려오는가.

- 4개 축을 z-표준화해 합친 '전통 손맛 지수'(sido×year).
- 시도 궤적 fan-in + 지역 간 표준편차(분산) 축소.
- β-수렴: 2021년 평균에서 먼(향토 강한/약한) 지역일수록 변화가 큰가(평균 회귀)?
  x=2021 편차, y=2021→2025 변화, 기울기<0 = 수렴. 학교 부트스트랩으로 CI.
- 수도권 vs 비수도권 궤적으로 '어디로' 끌려오는지.
"""
import os
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from menu_attributes import parse_menu_string, meal_feature_vector, FEATURE_COLUMNS

YEARS = [2021, 2022, 2023, 2024, 2025]
AXES = ["flag_fermented", "form_stew", "flag_kimchi", "method_seasoned"]
MIN_YEAR_MEALS = 30
EXCLUDE = {"전북"}
SUDO = {"서울", "경기", "인천"}
NBOOT, SEED = 300, 0
FIG_DIR = "figures"
PAPER, INK, ACC, COOL = "#f6f1e7", "#211d17", "#b6452c", "#2c6f7a"


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name(); break
    matplotlib.rcParams["axes.unicode_minus"] = False


def _vec(d):
    ds = parse_menu_string(d)
    if not ds:
        return None
    v = meal_feature_vector(ds, normalize=True)
    return [v[c] for c in AXES]


def trad_matrix(sy, sido_of, sb, rng=None):
    """sy: dict[(school,year)]=4벡터. → sido×year '전통지수'(z합) DataFrame."""
    reg = {}
    for sido, schs in sb.items():
        for y in YEARS:
            use = rng.choice(schs, len(schs), replace=True) if rng is not None else schs
            vs = [sy[(s, y)] for s in use if (s, y) in sy]
            if vs:
                reg[(sido, y)] = np.mean(vs, axis=0)
    M = pd.DataFrame({k: v for k, v in reg.items()}).T          # (sido,year) × 4
    Z = (M - M.mean()) / (M.std() + 1e-9)                       # 축별 z
    trad = Z.mean(axis=1)                                       # 전통 손맛 지수
    return trad.unstack()                                       # sido × year


def beta_conv(T):
    dev0 = T[2021] - T[2021].mean()
    chg = T[2025] - T[2021]
    b = np.polyfit(dev0.values, chg.values, 1)[0]
    return b, dev0, chg


def main():
    _font(); os.makedirs(FIG_DIR, exist_ok=True)
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["year"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["year"].isin(YEARS)].reset_index(drop=True)
    sido_of = dict(pd.read_parquet("schools.parquet")[["school_code", "sido"]].values)

    print(f"끼 {len(m)} 벡터화...")
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(_vec, m["ddish_nm"].tolist(), chunksize=4000))
    keep = np.array([r is not None for r in res])
    df = pd.DataFrame([r for r in res if r is not None], columns=AXES)
    df["school"] = m["school_code"].values[keep]; df["year"] = m["year"].values[keep]

    cy = df.groupby(["school", "year"]).size().unstack().reindex(columns=YEARS)
    panel = [s for s in cy[(cy >= MIN_YEAR_MEALS).all(axis=1)].index
             if sido_of.get(s) not in (None, *EXCLUDE)]
    sy = {idx: row.values for idx, row in df[df.school.isin(panel)].groupby(["school", "year"])[AXES].mean().iterrows()}
    sb = {}
    for s in panel:
        sb.setdefault(sido_of[s], []).append(s)
    sb = {k: np.array(v) for k, v in sb.items()}
    print(f"panel {len(panel)}교 / 시도 {len(sb)}")

    T = trad_matrix(sy, sido_of, sb)[YEARS]
    std_y = T.std()
    print("\n전통 손맛 지수 — 연도별 지역 간 표준편차:")
    print("  " + "  ".join(f"{y}:{std_y[y]:.3f}" for y in YEARS))
    print(f"  수렴 폭: {(std_y[2025]/std_y[2021]-1)*100:+.1f}% (음=수렴)")

    b, dev0, chg = beta_conv(T)
    print(f"\nβ-수렴 기울기: {b:+.3f} (음=평균 회귀=수렴)")
    print("\n2021 향토 강도순 (지수) 와 변화:")
    order = T[2021].sort_values(ascending=False)
    for sido in order.index:
        tag = "수도권" if sido in SUDO else ""
        print(f"  {sido:4s} 2021 {T.loc[sido,2021]:+.2f} → 2025 {T.loc[sido,2025]:+.2f}  Δ{chg[sido]:+.2f} {tag}")
    su = T.loc[T.index.isin(SUDO)].mean(); no = T.loc[~T.index.isin(SUDO)].mean()
    print(f"\n수도권 평균 궤적: {su[2021]:+.2f}→{su[2025]:+.2f} | 비수도권: {no[2021]:+.2f}→{no[2025]:+.2f}")

    # 부트스트랩: 수렴폭·β
    rng = np.random.default_rng(SEED)
    redu, betas = [], []
    for _ in range(NBOOT):
        Tb = trad_matrix(sy, sido_of, sb, rng)[YEARS]
        redu.append(Tb.std()[2025] / Tb.std()[2021] - 1)
        betas.append(beta_conv(Tb)[0])
    redu, betas = np.array(redu) * 100, np.array(betas)
    pr = 2 * min((redu >= 0).mean(), (redu <= 0).mean())
    pb = 2 * min((betas >= 0).mean(), (betas <= 0).mean())
    print(f"\n부트스트랩: 수렴폭 95%CI [{np.percentile(redu,2.5):+.1f}%,{np.percentile(redu,97.5):+.1f}%] p≈{pr:.3f}")
    print(f"           β 95%CI [{np.percentile(betas,2.5):+.2f},{np.percentile(betas,97.5):+.2f}] p≈{pb:.3f}")

    # 그림 1: 궤적 fan-in
    fig, ax = plt.subplots(figsize=(9, 6)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    for sido in T.index:
        c = COOL if sido in SUDO else ACC
        ax.plot(YEARS, T.loc[sido].values, "-o", color=c, ms=3, lw=1.5,
                alpha=.85 if sido in SUDO else .5)
        ax.annotate(sido, (2025, T.loc[sido, 2025]), fontsize=7.5, xytext=(4, 0),
                    textcoords="offset points", color=c, va="center")
    ax.axhline(0, color="#b0a890", lw=.8)
    ax.set_xticks(YEARS); ax.set_xlabel("연도"); ax.set_ylabel("전통 손맛 지수 (발효·찌개·김치·나물 z합)")
    ax.set_title(f"전통 손맛의 지역 수렴 ({(std_y[2025]/std_y[2021]-1)*100:+.0f}%) — 청록=수도권, 주황=지방", fontsize=12, color=INK)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/who_converge_traj.png", dpi=200, facecolor=PAPER)

    # 그림 2: β-수렴 산점도
    fig2, ax2 = plt.subplots(figsize=(8, 6)); fig2.patch.set_facecolor(PAPER); ax2.set_facecolor("#fffdf8")
    for sido in T.index:
        c = COOL if sido in SUDO else ACC
        ax2.scatter(dev0[sido], chg[sido], s=55, color=c, edgecolor=INK, zorder=3)
        ax2.annotate(sido, (dev0[sido], chg[sido]), fontsize=8, xytext=(4, 3), textcoords="offset points")
    xs = np.array([dev0.min(), dev0.max()])
    ax2.plot(xs, np.poly1d(np.polyfit(dev0, chg, 1))(xs), "--", color=INK, lw=1.4,
             label=f"β={b:+.2f} (p≈{pb:.3f})")
    ax2.axhline(0, color="#b0a890", lw=.6); ax2.axvline(0, color="#b0a890", lw=.6)
    ax2.set_xlabel("2021 향토 편차 (평균 대비, +면 전통 강함)"); ax2.set_ylabel("2021→2025 변화")
    ax2.set_title("β-수렴: 향토 강한 지역일수록 더 떨어지나(평균 회귀)?", fontsize=12, color=INK)
    ax2.legend(fontsize=10, frameon=False)
    for s in ["top", "right"]:
        ax2.spines[s].set_visible(False)
    fig2.tight_layout(); fig2.savefig(f"{FIG_DIR}/who_converge_beta.png", dpi=200, facecolor=PAPER)
    print(f"\n그림: who_converge_traj.png, who_converge_beta.png")


if __name__ == "__main__":
    main()
