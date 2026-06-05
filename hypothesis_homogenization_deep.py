"""
hypothesis_homogenization_deep.py
---------------------------------
H-동질화 심화: 시도 간 급식 차이가 줄어드는가? — 5개 연(年) 점 대신 월(月) 해상도로 검정력 확보.

NEIS는 2021+만 제공(뒤로 확장 불가) → 같은 창에서 시간 점을 늘린다: 월별 ~60점.

설계
- 월별 시도 속성 프로파일(CLR) 간 평균 쌍거리 = '지역 분산'(월 시계열).
- 표본 구성 통제: 5년(2021~2025) balanced panel 학교만(연 30끼+ 모두).
- 계절성 제거: 분산 시계열에서 월-of-year 평균을 빼 추세만 본다.
- 추세 검정: 탈계절 분산에 OLS 기울기 + Mann-Kendall + 학교 블록 부트스트랩 p/CI.
- 보강: 연도별 지역 프로파일 MDS 궤적(수렴 시각화), 속성별 동질화 분해.
"""
import os
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from sklearn.manifold import MDS
from menu_attributes import parse_menu_string, meal_feature_vector, FEATURE_COLUMNS

PANEL_YEARS = [2021, 2022, 2023, 2024, 2025]
MIN_YEAR_MEALS = 30
# 전북은 NEIS 중식 데이터가 2024년부터만 존재(2021~23 학교 2개) → 커버리지 변화가
# 가짜 동질화를 만든다. 시간 분석에서 제외.
EXCLUDE = {"전북"}
MIN_SCH_REGION_MONTH = 5      # 그 달 그 시도에 panel 학교 최소
MIN_REGIONS = 15             # 그 달 분산 계산에 최소 시도 수
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


def clr(X):
    L = np.log(X + 1e-6)
    return L - L.mean(axis=1, keepdims=True)


def mann_kendall(v):
    v = np.asarray(v, float); n = len(v)
    s = sum(np.sign(v[j] - v[i]) for i in range(n) for j in range(i + 1, n))
    var = n * (n - 1) * (2 * n + 5) / 18.0
    z = (s - np.sign(s)) / np.sqrt(var) if var > 0 else 0.0
    return s, z


def pair_disp(profiles):
    """region×43 (원 비율) → CLR 후 평균 쌍거리."""
    R = clr(np.asarray(profiles)); n = len(R)
    d = [np.linalg.norm(R[i] - R[j]) for i in range(n) for j in range(i + 1, n)]
    return float(np.mean(d))


def monthly_dispersion(prof_sm, sido_of, panel, months, rng=None):
    """prof_sm: dict[(school,ym)] = 43벡터. 월별 지역 분산 시계열."""
    by_region_month = {}
    for ym in months:
        reg = {}
        for s in panel:
            if (s, ym) in prof_sm:
                reg.setdefault(sido_of[s], []).append(s)
        profs = []
        for sido, schs in reg.items():
            if len(schs) < MIN_SCH_REGION_MONTH:
                continue
            use = rng.choice(schs, len(schs), replace=True) if rng is not None else schs
            profs.append(np.mean([prof_sm[(s, ym)] for s in use], axis=0))
        by_region_month[ym] = pair_disp(profs) if len(profs) >= MIN_REGIONS else np.nan
    return np.array([by_region_month[ym] for ym in months])


def deseason(series, months):
    mo = np.array([ym % 100 for ym in months])
    s = pd.Series(series, index=mo)
    clim = s.groupby(level=0).transform("mean")
    return series - clim.values + np.nanmean(series)


def main():
    _font(); os.makedirs(FIG_DIR, exist_ok=True)
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    d = pd.to_datetime(m["date"], format="%Y%m%d")
    m["year"] = d.dt.year; m["ym"] = d.dt.year * 100 + d.dt.month
    m = m[m["year"].between(2021, 2026)].reset_index(drop=True)
    schools = pd.read_parquet("schools.parquet")[["school_code", "sido"]]

    print(f"끼 {len(m)} 벡터화...")
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(_vec, m["ddish_nm"].tolist(), chunksize=4000))
    keep = np.array([r is not None for r in res])
    arr = np.array([r for r in res if r is not None], float)
    df = pd.DataFrame(arr, columns=FEATURE_COLUMNS)
    df["school"] = m["school_code"].values[keep]
    df["year"] = m["year"].values[keep]; df["ym"] = m["ym"].values[keep]

    # balanced panel (5년 모두 연 30끼+)
    cy = df[df["year"].isin(PANEL_YEARS)].groupby(["school", "year"]).size().unstack().reindex(columns=PANEL_YEARS)
    panel = cy[(cy >= MIN_YEAR_MEALS).all(axis=1)].index.to_numpy()
    sido_of = dict(zip(schools["school_code"], schools["sido"]))
    panel = np.array([s for s in panel if sido_of.get(s) not in (None, *EXCLUDE)])
    print(f"balanced panel 학교: {len(panel)} (제외 시도: {EXCLUDE})")

    dfp = df[df["school"].isin(panel)]
    prof_sm = {idx: row.values for idx, row in dfp.groupby(["school", "ym"])[FEATURE_COLUMNS].mean().iterrows()}
    months = sorted(set(ym for (_, ym) in prof_sm))

    obs = monthly_dispersion(prof_sm, sido_of, panel, months)
    valid = ~np.isnan(obs)
    months_v = [ym for ym, ok in zip(months, valid) if ok]
    obs_v = obs[valid]
    t = np.arange(len(months_v))
    des = deseason(obs_v, months_v)
    slope = np.polyfit(t, des, 1)[0]
    mk_s, mk_z = mann_kendall(des)
    print(f"\n유효 월 점: {len(months_v)} ({months_v[0]}~{months_v[-1]})")
    print(f"탈계절 분산 추세: 기울기 {slope:+.5f}/월, Mann-Kendall z={mk_z:+.2f} "
          f"(|z|>1.96 유의)  방향 {'동질화' if slope<0 else '다양화'}")
    pct = (np.nanmean(obs_v[-6:]) / np.nanmean(obs_v[:6]) - 1) * 100
    print(f"분산 변화(첫6월 평균 대비 마지막6월): {pct:+.1f}%")

    # 부트스트랩 (학교 재표집 → 전체 시계열 재계산 → 기울기 분포)
    rng = np.random.default_rng(SEED)
    slopes = []
    for _ in range(NBOOT):
        bo = monthly_dispersion(prof_sm, sido_of, panel, months_v, rng)
        if np.isnan(bo).any():
            continue
        slopes.append(np.polyfit(t, deseason(bo, months_v), 1)[0])
    slopes = np.array(slopes)
    lo, hi = np.percentile(slopes, [2.5, 97.5])
    p_two = 2 * min((slopes >= 0).mean(), (slopes <= 0).mean())
    strong = (p_two < 0.05) and (np.sign(lo) == np.sign(hi)) and abs(mk_z) > 1.96
    print(f"부트스트랩({len(slopes)}): 기울기 95%CI [{lo:+.5f},{hi:+.5f}], p≈{p_two:.3f}")
    print(f"\n>>> {'강한 신호: ' + ('동질화' if slope<0 else '다양화') + ' 유의' if strong else '약함/불명확'}")

    # 그림 1: 월별 분산 + 탈계절 + 추세
    fig, ax = plt.subplots(figsize=(11, 5)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    xt = np.arange(len(months_v))
    ax.plot(xt, obs_v, color="#cdbfa3", lw=1, label="월별 지역 분산(원)")
    ax.plot(xt, des, "-o", color=ACC, ms=3, lw=1.8, label="탈계절")
    ax.plot(xt, np.poly1d(np.polyfit(xt, des, 1))(xt), "--", color=INK, lw=1.4,
            label=f"추세 {slope:+.4f}/월, MK z={mk_z:+.1f}, p≈{p_two:.3f}")
    tick = [i for i, ym in enumerate(months_v) if ym % 100 == 3]
    ax.set_xticks(tick); ax.set_xticklabels([months_v[i] // 100 for i in tick])
    ax.set_xlabel("연도(월별 점 ~%d개)" % len(months_v)); ax.set_ylabel("시도 간 평균 식단 거리")
    ax.set_title(f"H-동질화 심화(월 해상도): {pct:+.1f}% (2021→2026)", fontsize=13, color=INK)
    ax.legend(fontsize=9, frameon=False, ncol=3)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/hyp_homog_monthly.png", dpi=200, facecolor=PAPER)

    # 그림 2: 연도별 지역 프로파일 MDS 궤적 (수렴?)
    regyear = {}
    for y in PANEL_YEARS:
        for sido in set(sido_of[s] for s in panel):
            schs = [s for s in panel if sido_of[s] == sido]
            vs = [dfp[(dfp.school == s) & (dfp.year == y)][FEATURE_COLUMNS].mean().values for s in schs]
            vs = [v for v in vs if not np.isnan(v).any()]
            if vs:
                regyear[(sido, y)] = np.mean(vs, axis=0)
    keys = list(regyear); X = clr(np.array([regyear[k] for k in keys]))
    emb = MDS(n_components=2, random_state=SEED, normalized_stress="auto").fit_transform(X)
    pos = {k: emb[i] for i, k in enumerate(keys)}
    fig2, ax2 = plt.subplots(figsize=(8, 8)); fig2.patch.set_facecolor(PAPER); ax2.set_facecolor("#fffdf8")
    sidos = sorted(set(s for s, _ in keys))
    cmap = plt.cm.tab20(np.linspace(0, 1, len(sidos)))
    for c, sido in zip(cmap, sidos):
        pts = np.array([pos[(sido, y)] for y in PANEL_YEARS if (sido, y) in pos])
        ax2.plot(pts[:, 0], pts[:, 1], "-", color=c, lw=1, alpha=.6)
        ax2.scatter(pts[:, 0], pts[:, 1], color=c, s=18)
        ax2.annotate(sido, pts[-1], fontsize=8, color=INK)
    ax2.set_title("지역 프로파일 MDS 궤적 (2021→2025, 안쪽 모이면 동질화)", fontsize=12, color=INK)
    ax2.axis("off")
    fig2.tight_layout(); fig2.savefig(f"{FIG_DIR}/hyp_homog_mds.png", dpi=200, facecolor=PAPER)

    # 속성별 동질화 분해: 연도별 지역 간 분산의 변화 (음=수렴/동질화, 양=발산/차별화)
    av = {}
    for ci, c in enumerate(FEATURE_COLUMNS):
        av[c] = [np.var([regyear[(s, y)][ci] for s in sidos if (s, y) in regyear]) for y in PANEL_YEARS]
    rows = [(c, (v[-1] / v[0] - 1) * 100) for c, v in av.items() if v[0] > 1e-7]
    rows.sort(key=lambda r: r[1])
    print("\n=== 속성별 지역 간 분산 변화 2021→2025 (%, 음수=수렴) ===")
    print("[가장 수렴(동질화)] " + ", ".join(f"{c} {p:+.0f}%" for c, p in rows[:8]))
    print("[가장 발산(차별화)] " + ", ".join(f"{c} {p:+.0f}%" for c, p in rows[-6:]))
    sel = rows[:11] + rows[-8:]
    fig3, ax3 = plt.subplots(figsize=(8.5, 8)); fig3.patch.set_facecolor(PAPER); ax3.set_facecolor("#fffdf8")
    yy = np.arange(len(sel))
    ax3.barh(yy, [p for _, p in sel], color=[COOL if p < 0 else ACC for _, p in sel])
    ax3.set_yticks(yy); ax3.set_yticklabels([c for c, _ in sel], fontsize=8)
    ax3.axvline(0, color=INK, lw=.8); ax3.invert_yaxis()
    ax3.set_xlabel("지역 간 분산 변화 2021→2025 (%)")
    ax3.set_title("속성별: 수렴(청록, 동질화) vs 발산(주황, 향토 강화)", fontsize=12, color=INK)
    for s in ["top", "right"]:
        ax3.spines[s].set_visible(False)
    fig3.tight_layout(); fig3.savefig(f"{FIG_DIR}/hyp_homog_attrs.png", dpi=200, facecolor=PAPER)
    print(f"그림: hyp_homog_monthly.png, hyp_homog_mds.png, hyp_homog_attrs.png")


if __name__ == "__main__":
    main()
