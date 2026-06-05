"""
hypothesis_weather.py
---------------------
H-날씨 검정: 급식은 (계절 말고) '그날의 날씨'에 반응하는가? 아니면 미리 짠 식단표라 무반응인가?

H0: 계절을 제거하면 그날 기온과 메뉴 구성은 무관(식단은 캘린더에 고정).
H1: 추운 날(기온 음의 이상치)일수록 국물요리↑ / 더운 날일수록 냉면↑.

설계
- 계절 제거: 각 값(기온·국물비중·냉면비중)을 day-of-year 기후값(±7일 순환 평활)으로 빼 '이상치'를 만든다.
- 검정: corr(기온 이상치, 국물 이상치) < 0 ?  corr(기온 이상치, 냉면 이상치) > 0 ?
- 학교일만(평일 + 끼수 충분). 블록 부트스트랩(2주 블록)으로 CI.
- 기온: Open-Meteo 아카이브(무료) 7개 도시 일평균 평균.
"""
import io
import numpy as np
import pandas as pd
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

FIG_DIR = "figures"
PAPER, INK, ACC, COOL = "#f6f1e7", "#211d17", "#b6452c", "#2c6f7a"
MIN_MEALS_DAY = 500
SEED = 0

CITIES = {  # 전국 대표 7개 (위도, 경도)
    "서울": (37.57, 126.98), "부산": (35.18, 129.08), "대구": (35.87, 128.60),
    "광주": (35.16, 126.85), "대전": (36.35, 127.38), "춘천": (37.88, 127.73),
    "제주": (33.50, 126.53),
}
WARM = r"된장국|미역국|북어|뭇국|무국|콩나물국|시래기|육개장|김치찌개|된장찌개|순두부|부대찌개|동태|매운탕|갈비탕|곰탕|설렁탕|삼계탕|국밥|떡국|만둣국|감자탕|추어탕|우거지|어묵국|전골|찌개"
COLD = r"냉면|물냉|비빔냉면|콩국수|메밀국수|밀면|초계국수|열무국수|냉모밀"


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name(); break
    matplotlib.rcParams["axes.unicode_minus"] = False


def fetch_temp():
    frames = []
    for name, (lat, lon) in CITIES.items():
        u = ("https://archive-api.open-meteo.com/v1/archive?"
             f"latitude={lat}&longitude={lon}&start_date=2021-01-01&end_date=2025-12-31"
             "&daily=temperature_2m_mean&timezone=Asia%2FSeoul")
        js = requests.get(u, timeout=60).json()["daily"]
        frames.append(pd.Series(js["temperature_2m_mean"], index=pd.to_datetime(js["time"]), name=name))
    T = pd.concat(frames, axis=1)
    return T.mean(axis=1).rename("temp")          # 전국 평균 일평균기온


def deseason(s, doy):
    """day-of-year 기후값(±7일 순환 평활)을 빼 이상치 반환."""
    clim = s.groupby(doy).mean().reindex(range(1, 367))
    clim = clim.interpolate().bfill().ffill()
    v = clim.values
    k = 15
    sm = np.array([np.nanmean(np.take(v, range(i - k // 2, i + k // 2 + 1), mode="wrap"))
                   for i in range(len(v))])
    clim_sm = pd.Series(sm, index=clim.index)
    return s - doy.map(clim_sm).values


def block_boot_corr(x, y, block=14, n=1000, rng=None):
    rng = rng or np.random.default_rng(SEED)
    N = len(x); nb = N // block
    out = []
    for _ in range(n):
        starts = rng.integers(0, N - block, size=nb)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])
        out.append(np.corrcoef(x[idx], y[idx])[0, 1])
    return np.percentile(out, [2.5, 97.5])


def main():
    _font()
    m = pd.read_parquet("meals_lunch.parquet", columns=["date", "ddish_nm"])
    d = pd.to_datetime(m["date"], format="%Y%m%d")
    m["d"] = d
    daily = m.groupby("d").agg(
        n=("ddish_nm", "size"),
        warm=("ddish_nm", lambda s: s.str.contains(WARM, regex=True, na=False).mean()),
        cold=("ddish_nm", lambda s: s.str.contains(COLD, regex=True, na=False).mean()),
    )
    daily = daily[(daily["n"] >= MIN_MEALS_DAY) & (daily.index.dayofweek < 5)]   # 평일·학교일
    daily = daily[(daily.index.year >= 2021) & (daily.index.year <= 2025)]

    print("기온 수집(Open-Meteo 7개 도시)...")
    temp = fetch_temp()
    df = daily.join(temp, how="inner").dropna()
    df["doy"] = df.index.dayofyear
    print(f"분석 학교일: {len(df)}  (평일·끼수>= {MIN_MEALS_DAY})")

    df["t_a"] = deseason(df["temp"], df["doy"])
    df["w_a"] = deseason(df["warm"], df["doy"])
    df["c_a"] = deseason(df["cold"], df["doy"])

    rng = np.random.default_rng(SEED)
    print("\n=== 계절 제거 후 기온 이상치 vs 메뉴 이상치 ===")
    for lab, col, exp in [("국물요리", "w_a", "음(-)"), ("냉면류", "c_a", "양(+)")]:
        r = np.corrcoef(df["t_a"], df[col])[0, 1]
        lo, hi = block_boot_corr(df["t_a"].values, df[col].values, n=1000, rng=rng)
        sig = "유의" if (lo > 0) == (hi > 0) else "비유의(0 포함)"
        print(f"  기온이상치 × {lab} 이상치: r={r:+.3f}  95%CI[{lo:+.3f},{hi:+.3f}]  ({sig}, 예상 {exp})")

    # 참고: 계절 제거 전(raw) 상관 — 계절 교란이 얼마나 큰지 대비
    r_raw_w = np.corrcoef(df["temp"], df["warm"])[0, 1]
    r_raw_c = np.corrcoef(df["temp"], df["cold"])[0, 1]
    print(f"\n(참고) 계절 제거 전 raw 상관: 기온×국물 {r_raw_w:+.3f}, 기온×냉면 {r_raw_c:+.3f}")

    rw = np.corrcoef(df["t_a"], df["w_a"])[0, 1]
    rc = np.corrcoef(df["t_a"], df["c_a"])[0, 1]
    lo_w, hi_w = block_boot_corr(df["t_a"].values, df["w_a"].values, n=1000, rng=rng)
    strong = (abs(rw) > 0.2 and (lo_w > 0) == (hi_w > 0))
    print(f"\n>>> {'강한 신호: 급식이 날씨에 반응' if strong else '약함/귀무 못 기각: 식단은 캘린더에 고정(날씨 무반응)'}")

    # 그림: 두 산점도
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4)); fig.patch.set_facecolor(PAPER)
    for ax, col, lab, col_c, r in [(axes[0], "w_a", "국물요리 비중 이상치", ACC, rw),
                                    (axes[1], "c_a", "냉면류 비중 이상치", COOL, rc)]:
        ax.set_facecolor("#fffdf8")
        ax.scatter(df["t_a"], df[col], s=8, color=col_c, alpha=.25, edgecolor="none")
        z = np.polyfit(df["t_a"], df[col], 1)
        xs = np.array([df["t_a"].min(), df["t_a"].max()])
        ax.plot(xs, np.poly1d(z)(xs), color=INK, lw=1.8, label=f"r={r:+.3f}")
        ax.axhline(0, color="#b0a890", lw=.6); ax.axvline(0, color="#b0a890", lw=.6)
        ax.set_xlabel("기온 이상치 (℃, 계절 제거)"); ax.set_ylabel(lab)
        ax.legend(fontsize=11, frameon=False)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
    fig.suptitle("H-날씨: 계절을 제거하면 급식이 그날 기온에 반응하는가?", fontsize=14, color=INK)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/hyp_weather.png", dpi=200, facecolor=PAPER)
    print(f"\n그림: {FIG_DIR}/hyp_weather.png")


if __name__ == "__main__":
    main()
