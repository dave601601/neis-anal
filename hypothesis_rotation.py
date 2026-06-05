"""
hypothesis_rotation.py
----------------------
H-회피규칙 검정: 학교는 같은 '유형'의 끼니를 단기 반복 회피하고 주기(순환)로 도나?

H0: 끼니 배치는 시간 구조 없음 — 잔차(그 학교 평균 대비 편차)가 lag와 무관(ACF=0).
H1: 단기엔 회피(lag1 음의 자기상관) + 순환 주기에서 되돌아옴(특정 lag 양의 봉우리).

측정: 정확한 메뉴명 Jaccard는 '기장밥≠흑미밥'이라 유형을 못 잡는다(바닥 유사도). 대신 끼니를
43차원 속성벡터로 보고, **학교 평균을 뺀 잔차 벡터의 코사인 자기상관**을 lag별로 계산.
귀무: 같은 학교 끼니 순서를 무작위로 섞어 시간 구조만 파괴(빈도·구성 동일) → ACF≈0.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from menu_attributes import parse_menu_string, meal_feature_vector, FEATURE_COLUMNS

N_SCHOOLS, MIN_DAYS, N_NULL, SEED = 500, 250, 1, 0
LAGS = list(range(1, 46))
FIG_DIR = "figures"
PAPER, INK, ACC, NUL = "#f6f1e7", "#211d17", "#b6452c", "#9a8f78"


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name(); break
    matplotlib.rcParams["axes.unicode_minus"] = False


def meal_vec(ddish):
    ds = parse_menu_string(ddish)
    if not ds:
        return None
    v = meal_feature_vector(ds, normalize=True)
    return np.array([v[c] for c in FEATURE_COLUMNS], dtype=np.float64)


def cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na > 1e-9 and nb > 1e-9 else np.nan


def acf(V):
    n = len(V); out = np.full(len(LAGS), np.nan)
    for i, L in enumerate(LAGS):
        v = [cos(V[t], V[t + L]) for t in range(n - L)]
        v = [x for x in v if not np.isnan(x)]
        if v:
            out[i] = np.mean(v)
    return out


def main():
    _font()
    rng = np.random.default_rng(SEED)
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    cnt = m.groupby("school_code").size()
    elig = cnt[cnt >= MIN_DAYS].index.to_numpy()
    sample = rng.choice(elig, size=min(N_SCHOOLS, len(elig)), replace=False)
    sm = m[m["school_code"].isin(sample)].copy()
    print(f"표본 학교 {len(sample)} (각 ≥{MIN_DAYS} 학교일) 벡터화...")
    sm["vec"] = sm["ddish_nm"].map(meal_vec)
    sm = sm.dropna(subset=["vec"])

    real, null = [], []
    for sc, g in sm.groupby("school_code"):
        g = g.sort_values("date")
        byday = g.groupby("date")["vec"].apply(lambda s: np.mean(np.stack(s.values), axis=0))
        V = np.stack(byday.values)
        if len(V) <= max(LAGS) + 5:
            continue
        Vc = V - V.mean(axis=0, keepdims=True)            # 학교 평균(전형적 끼니) 제거 → 잔차
        real.append(acf(Vc))
        for _ in range(N_NULL):
            null.append(acf(rng.permutation(Vc)))
    real = np.nanmean(real, axis=0); null = np.nanmean(null, axis=0)

    print("\n=== 잔차 속성벡터 코사인 자기상관 (학교일 lag) ===")
    print("lag   실측    귀무")
    for i, L in enumerate(LAGS):
        if L <= 8 or L % 5 == 0:
            print(f"  {L:2d}  {real[i]:+.3f}  {null[i]:+.3f}")

    lag1 = real[0]
    far = np.array(LAGS) >= 12
    peak_lag = int(np.array(LAGS)[far][np.argmax(real[far])])
    peak_amp = float(real[far].max())
    print(f"\nlag1 자기상관(회피): {lag1:+.3f}  (음수=어제와 반대 유형, 귀무≈{null[0]:+.3f})")
    print(f"순환 봉우리: lag {peak_lag} 학교일(≈{peak_lag/5:.0f}주)에서 {peak_amp:+.3f}")
    strong = (lag1 < -0.05) or (peak_amp > 0.05)
    print(f"\n>>> {'강한 신호: 단기 회피 + 순환 주기 구조' if strong else '약함'}")

    fig, ax = plt.subplots(figsize=(9, 5.6)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    ax.axhline(0, color="#b0a890", lw=.8)
    ax.plot(LAGS, null, "--", color=NUL, lw=2, label="귀무(순서 무작위)")
    ax.plot(LAGS, real, "-o", color=ACC, lw=2, ms=3, label="실측 식단(잔차)")
    ax.axvline(peak_lag, color=INK, lw=.8, ls=":")
    ax.annotate(f"순환 봉우리 lag {peak_lag}\n(≈{peak_lag/5:.0f}주)",
                (peak_lag, peak_amp), xytext=(8, 8), textcoords="offset points", fontsize=9, color=INK)
    ax.annotate(f"단기 회피\nlag1 {lag1:+.3f}", (1, lag1), xytext=(12, -2),
                textcoords="offset points", fontsize=9, color=ACC)
    ax.set_xlabel("lag (학교일)"); ax.set_ylabel("잔차 메뉴 유형 자기상관 (코사인)")
    ax.set_title("H-회피규칙: 끼니 유형의 자기상관 — 단기 회피 + 순환", fontsize=13, color=INK)
    ax.legend(fontsize=10, frameon=False)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/hyp_rotation.png", dpi=200, facecolor=PAPER)
    print(f"\n그림: {FIG_DIR}/hyp_rotation.png")


if __name__ == "__main__":
    main()
