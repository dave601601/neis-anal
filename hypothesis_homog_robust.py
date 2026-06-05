"""
hypothesis_homog_robust.py
--------------------------
H-동질화 분해의 robust화: '어떤 속성이 진짜 유의하게 수렴/발산하나?'

앞선 분해는 끝점(2021 vs 2025) 분산비라 노이즈가 컸다. 여기서는
- 속성별 '지역 간 분산'을 월 해상도(~60점) 시계열로,
- 계절 제거 후 추세 기울기를 상대화(% / 전체창),
- Mann-Kendall(단조성) + 학교 재표집 부트스트랩(300)으로 CI·p,
- forest plot으로 유의 수렴/발산만 가린다.
전북 제외(2024부터라 가짜). balanced panel(5년 연 30끼+).
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

PANEL_YEARS = [2021, 2022, 2023, 2024, 2025]
MIN_YEAR_MEALS, MIN_SCH, MIN_REGIONS = 30, 5, 15
EXCLUDE = {"전북"}
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
    return [v[c] for c in FEATURE_COLUMNS]


def mann_kendall_z(v):
    v = np.asarray(v, float); n = len(v)
    s = sum(np.sign(v[j] - v[i]) for i in range(n) for j in range(i + 1, n))
    var = n * (n - 1) * (2 * n + 5) / 18.0
    return (s - np.sign(s)) / np.sqrt(var) if var > 0 else 0.0


def deseason(series, mo):
    s = pd.Series(series, index=mo)
    return series - s.groupby(level=0).transform("mean").values + np.nanmean(series)


def main():
    _font(); os.makedirs(FIG_DIR, exist_ok=True)
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    dt = pd.to_datetime(m["date"], format="%Y%m%d")
    m["year"] = dt.dt.year; m["ym"] = dt.dt.year * 100 + dt.dt.month
    m = m[m["year"].between(2021, 2026)].reset_index(drop=True)
    sido_of = dict(pd.read_parquet("schools.parquet")[["school_code", "sido"]].values)

    print(f"끼 {len(m)} 벡터화...")
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(_vec, m["ddish_nm"].tolist(), chunksize=4000))
    keep = np.array([r is not None for r in res])
    arr = np.array([r for r in res if r is not None], float)
    df = pd.DataFrame(arr, columns=FEATURE_COLUMNS)
    df["school"] = m["school_code"].values[keep]
    df["year"] = m["year"].values[keep]; df["ym"] = m["ym"].values[keep]

    cy = df[df.year.isin(PANEL_YEARS)].groupby(["school", "year"]).size().unstack().reindex(columns=PANEL_YEARS)
    panel = set(cy[(cy >= MIN_YEAR_MEALS).all(axis=1)].index)
    panel = {s for s in panel if sido_of.get(s) not in (None, *EXCLUDE)}
    dfp = df[df.school.isin(panel)]
    prof = dfp.groupby(["school", "ym"])[FEATURE_COLUMNS].mean()
    print(f"panel 학교 {len(panel)}")

    # ym -> region -> (k×43) 학교 월프로파일
    prof = prof.reset_index()
    prof["sido"] = prof["school"].map(sido_of)
    ymreg = {}
    for ym, g in prof.groupby("ym"):
        reg = {}
        for sido, gg in g.groupby("sido"):
            if len(gg) >= MIN_SCH:
                reg[sido] = gg[FEATURE_COLUMNS].values
        if len(reg) >= MIN_REGIONS:
            ymreg[ym] = reg
    months = sorted(ymreg)
    mo = np.array([y % 100 for y in months])
    t = np.arange(len(months))
    print(f"유효 월 {len(months)}")

    NA = len(FEATURE_COLUMNS)

    def var_matrix(rng=None):
        V = np.empty((len(months), NA))
        for i, ym in enumerate(months):
            rm = []
            for M in ymreg[ym].values():
                if rng is not None:
                    M = M[rng.integers(0, len(M), len(M))]
                rm.append(M.mean(axis=0))
            V[i] = np.var(np.array(rm), axis=0)
        return V

    def rel_slopes(V):
        out = np.empty(NA)
        for c in range(NA):
            s = deseason(V[:, c], mo)
            out[c] = np.polyfit(t, s, 1)[0] * (len(t) - 1) / (V[:, c].mean() + 1e-9) * 100
        return out

    Vobs = var_matrix()
    obs = rel_slopes(Vobs)
    mk = np.array([mann_kendall_z(deseason(Vobs[:, c], mo)) for c in range(NA)])

    rng = np.random.default_rng(SEED)
    boots = np.array([rel_slopes(var_matrix(rng)) for _ in range(NBOOT)])
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    p = 2 * np.minimum((boots >= 0).mean(axis=0), (boots <= 0).mean(axis=0))

    res = pd.DataFrame({"attr": FEATURE_COLUMNS, "rel%": obs.round(1), "lo": lo.round(1),
                        "hi": hi.round(1), "MKz": mk.round(2), "p": p.round(3)})
    res["robust"] = (res["p"] < 0.05) & (np.sign(res["lo"]) == np.sign(res["hi"])) & (res["MKz"].abs() > 1.96)
    res = res.sort_values("rel%")
    pd.set_option("display.width", 120)
    print("\n=== 속성별 지역분산 추세(월, 계절제거) — 음=수렴, 양=발산 ===")
    print("[robust 수렴]"); print(res[(res.robust) & (res["rel%"] < 0)].to_string(index=False))
    print("\n[robust 발산]"); print(res[(res.robust) & (res["rel%"] > 0)].to_string(index=False))
    print(f"\nrobust 유의 속성: {int(res.robust.sum())}/{NA}")

    # forest plot
    rr = res.copy()
    fig, ax = plt.subplots(figsize=(9, 11)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    yy = np.arange(len(rr))
    for k, (_, r) in enumerate(rr.iterrows()):
        col = COOL if r["rel%"] < 0 else ACC
        sig = r["robust"]
        ax.plot([r["lo"], r["hi"]], [k, k], color=col, lw=2 if sig else 1, alpha=1 if sig else .35)
        ax.scatter([r["rel%"]], [k], color=col, s=42 if sig else 16, zorder=3, alpha=1 if sig else .4,
                   edgecolor=INK if sig else "none", linewidth=.6)
    ax.axvline(0, color=INK, lw=.9)
    ax.set_yticks(yy); ax.set_yticklabels(
        [f"{r['attr']}{'  ★' if r['robust'] else ''}" for _, r in rr.iterrows()], fontsize=8)
    ax.set_xlabel("지역 간 분산 추세 (% / 전체창, 계절제거)")
    ax.set_title("동질화 분해 robust화 — ★=유의(부트스트랩 CI·MK)\n청록=수렴(동질화), 주황=발산(향토 강화)", fontsize=12, color=INK)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/hyp_homog_forest.png", dpi=200, facecolor=PAPER)
    print(f"\n그림: {FIG_DIR}/hyp_homog_forest.png")


if __name__ == "__main__":
    main()
