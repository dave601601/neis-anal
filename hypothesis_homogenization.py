"""
hypothesis_homogenization.py
----------------------------
H-동질화 검정: 전국 표준화 시대에 시도 간 급식 차이가 줄어드는가(동질화) 늘어나는가(향토 강화)?

H0: 지역 간 식단 거리는 연도에 따라 변하지 않는다(기울기=0).
H1: 줄어든다(동질화, 기울기<0) 또는 늘어난다(다양화, >0).

설계
- 연도별 시도 속성 프로파일(43차원, CLR) → 17개 시도 간 평균 쌍거리(Aitchison) = '지역 분산'.
- 교란 통제: **5년(2021~2025) 모두 연 MIN_MEALS 이상인 학교만**(balanced panel) → 표본 구성 변화 배제.
- 유의성: 학교를 시도 내에서 재표집하는 부트스트랩으로 연도별 분산 CI + 기울기 분포·p.
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
MIN_MEALS_PER_YEAR = 30
NBOOT = 400
SEED = 0
FIG_DIR = "figures"
PAPER, INK, ACC = "#f6f1e7", "#211d17", "#b6452c"


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


def per_meal(m):
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(_vec, m["ddish_nm"].tolist(), chunksize=4000))
    keep = np.array([r is not None for r in res])
    arr = np.array([r for r in res if r is not None], dtype=np.float64)
    return arr, m["school_code"].values[keep], m["year"].values[keep]


def clr(X):
    L = np.log(X + 1e-6)
    return L - L.mean(axis=1, keepdims=True)


def dispersion(region_clr):
    """17×43 CLR 행렬 → 평균 쌍거리(Aitchison)."""
    n = len(region_clr)
    d = 0.0; cnt = 0
    for i in range(n):
        for j in range(i + 1, n):
            d += np.linalg.norm(region_clr[i] - region_clr[j]); cnt += 1
    return d / cnt


def region_dispersion_by_year(sy, sido_of, schools_by_sido, rng=None):
    """school-year 프로파일(sy: dict[(school,year)] = 43벡터) → 연도별 지역 분산.
    rng 주면 시도 내 학교를 복원추출(부트스트랩)."""
    out = []
    for y in YEARS:
        regvecs = []
        for sido, schs in schools_by_sido.items():
            use = rng.choice(schs, size=len(schs), replace=True) if rng is not None else schs
            vs = [sy[(s, y)] for s in use if (s, y) in sy]
            if vs:
                regvecs.append(np.mean(vs, axis=0))
        R = clr(np.array(regvecs))
        out.append(dispersion(R))
    return np.array(out)


def main():
    _font()
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["year"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["year"].between(2021, 2025)].reset_index(drop=True)
    schools = pd.read_parquet("schools.parquet")[["school_code", "sido"]]

    print(f"끼 {len(m)} 벡터화...")
    arr, sc, yr = per_meal(m)
    df = pd.DataFrame(arr, columns=FEATURE_COLUMNS)
    df["school"] = sc; df["year"] = yr

    # 학교×연도 끼수 → balanced panel
    cnt = df.groupby(["school", "year"]).size().unstack().reindex(columns=YEARS)
    panel = cnt[(cnt >= MIN_MEALS_PER_YEAR).all(axis=1)].index
    print(f"balanced panel 학교: {len(panel)} / {df['school'].nunique()} "
          f"(5년 모두 연 {MIN_MEALS_PER_YEAR}끼 이상)")

    dfp = df[df["school"].isin(panel)]
    prof = dfp.groupby(["school", "year"])[FEATURE_COLUMNS].mean()
    sy = {idx: row.values for idx, row in prof.iterrows()}

    sido_of = dict(zip(schools["school_code"], schools["sido"]))
    sb = {}
    for s in panel:
        sb.setdefault(sido_of.get(s), []).append(s)
    sb = {k: np.array(v) for k, v in sb.items() if k is not None}
    print("시도별 panel 학교수:", {k: len(v) for k, v in sorted(sb.items())})

    # 관측 분산
    obs = region_dispersion_by_year(sy, sido_of, sb)
    slope_obs = np.polyfit(YEARS, obs, 1)[0]
    print("\n=== 연도별 지역 간 분산(평균 쌍거리, CLR) ===")
    for y, d in zip(YEARS, obs):
        print(f"  {y}: {d:.4f}")
    print(f"기울기(관측): {slope_obs:+.5f}/년  ({'동질화' if slope_obs<0 else '다양화'} 방향)")

    # 부트스트랩
    rng = np.random.default_rng(SEED)
    boots = np.array([region_dispersion_by_year(sy, sido_of, sb, rng) for _ in range(NBOOT)])
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    slopes = np.array([np.polyfit(YEARS, b, 1)[0] for b in boots])
    p_two = 2 * min((slopes >= 0).mean(), (slopes <= 0).mean())
    pct = (obs[-1] / obs[0] - 1) * 100
    print(f"\n부트스트랩({NBOOT}): 기울기 95% CI [{np.percentile(slopes,2.5):+.5f}, "
          f"{np.percentile(slopes,97.5):+.5f}], p≈{p_two:.3f}")
    print(f"2021→2025 분산 변화: {pct:+.1f}%")
    strong = (p_two < 0.05) and (np.sign(np.percentile(slopes,2.5)) == np.sign(np.percentile(slopes,97.5)))
    print(f"\n>>> {'강한 신호' if strong else '약함/불명확'}: "
          f"{'동질화' if slope_obs<0 else '다양화'} {'유의' if p_two<0.05 else '비유의'} (p={p_two:.3f})")

    # 그림
    fig, ax = plt.subplots(figsize=(8, 6)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    ax.fill_between(YEARS, lo, hi, color=ACC, alpha=.18, label="95% CI (부트스트랩)")
    ax.plot(YEARS, obs, "-o", color=ACC, lw=2.2, label="지역 간 분산(평균 쌍거리)")
    tl = np.poly1d(np.polyfit(YEARS, obs, 1))
    ax.plot(YEARS, tl(YEARS), "--", color=INK, lw=1.3,
            label=f"추세 {slope_obs:+.4f}/년, p≈{p_two:.3f}")
    ax.set_xticks(YEARS); ax.set_xlabel("연도"); ax.set_ylabel("시도 간 평균 식단 거리 (Aitchison)")
    ax.set_title(f"H-동질화: 지역 식단 차이의 추이 ({pct:+.1f}%, 2021→25)", fontsize=13, color=INK)
    ax.legend(fontsize=9, frameon=False)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/hyp_homogenization.png", dpi=200, facecolor=PAPER)
    print(f"\n그림: {FIG_DIR}/hyp_homogenization.png")


if __name__ == "__main__":
    main()
