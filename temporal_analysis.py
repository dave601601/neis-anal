"""
temporal_analysis.py
--------------------
급식의 시간 차원: A 계절·명절 캘린더 + B 연도 트렌드.

데이터: meals_lunch.parquet (date=MLSV_YMD, ddish_nm). 완전한 해 2021~2025만 사용
(2026은 1~6월만 있어 계절·트렌드 왜곡 방지).

A 캘린더: 키워드 월별 등장률 -> 계절 히트맵(행 z) + 극좌표 '달력'. 데이터 주도로
  전체 메뉴를 분해해 '가장 계절 타는' 메뉴도 발굴.
B 트렌드: 키워드 연도별 등장률 -> 기울기·CAGR·Mann-Kendall, slopegraph. 데이터 주도로
  급상승/급하락 메뉴 발굴.

산출: figures/temporal_*.png + 콘솔 표.
"""
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

YEARS = list(range(2021, 2026))          # 완전한 해만
MONTHS = list(range(1, 13))
FIG_DIR = "figures"
MONTH_KO = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]

# A 계절 히트맵 행 (변이형 묶으려 부분문자열)
SEASONAL = ["떡국","송편","팥죽","삼계탕","냉면","콩국수","수박","참외","빙수",
            "추어탕","보양","호박죽","호빵","찐빵","어묵","오곡","부럼","미역국"]
# A 극좌표 달력에 쓸 상징 메뉴
ICONIC = [("떡국","떡국 · 설"),("송편","송편 · 추석"),("팥죽","팥죽 · 동지"),
          ("삼계탕","삼계탕 · 삼복"),("수박","수박 · 여름"),("냉면","냉면 · 여름")]
# B 트렌드 후보 (상승 의심 + 비교)
TREND = ["마라","마라탕","로제","그릭","비건","리조또","탕후루","약과","두바이",
         "크림","까르보","흑임자","바질","쌀국수"]

PAPER, INK, ACC = "#f6f1e7", "#211d17", "#b6452c"


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name()
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


def load():
    m = pd.read_parquet("meals_lunch.parquet", columns=["date", "ddish_nm"])
    d = pd.to_datetime(m["date"], format="%Y%m%d")
    m["y"], m["mon"] = d.dt.year, d.dt.month
    return m[m["y"].between(2021, 2025)].reset_index(drop=True)


# ── 부분문자열 등장률 (끼 단위) ───────────────────────────────────────
def rate_by_month(m, kw):
    hit = m["ddish_nm"].str.contains(kw, na=False, regex=False)
    num = m[hit].groupby("mon").size().reindex(MONTHS, fill_value=0)
    den = m.groupby("mon").size().reindex(MONTHS, fill_value=0)
    return (num / den * 1000)           # 천 끼당


def rate_by_year(m, kw):
    hit = m["ddish_nm"].str.contains(kw, na=False, regex=False)
    num = m[hit].groupby("y").size().reindex(YEARS, fill_value=0)
    den = m.groupby("y").size().reindex(YEARS, fill_value=0)
    return (num / den * 1000)


def mann_kendall(v):
    v = np.asarray(v, float); n = len(v)
    s = sum(np.sign(v[j] - v[i]) for i in range(n) for j in range(i + 1, n))
    return int(s)                       # >0 상승, <0 하락


# ── 데이터 주도 발견 (전체 메뉴 분해) ────────────────────────────────
_PAREN = re.compile(r"[\(\[][0-9.\s]*[\)\]]")
_TAIL = re.compile(r"[\d.]+\s*$")
_ECO = re.compile(r"[*★]|친환경")


def discover(m, min_n=3000):
    parts = m["ddish_nm"].str.split(r"<br\s*/?>", regex=True)
    ex = m[["y", "mon"]].join(parts.rename("dish")).explode("dish")
    ex["dish"] = (ex["dish"].str.replace(_PAREN, "", regex=True)
                  .str.replace(_ECO, "", regex=True)
                  .str.replace(_TAIL, "", regex=True).str.strip())
    ex = ex[ex["dish"].str.len() >= 2]
    freq = ex["dish"].value_counts()
    cand = freq[freq >= min_n].index
    exc = ex[ex["dish"].isin(cand)]
    tot_m = m.groupby("mon").size().reindex(MONTHS); tot_y = m.groupby("y").size().reindex(YEARS)

    mon = (exc.groupby(["dish", "mon"]).size().unstack(fill_value=0).reindex(columns=MONTHS, fill_value=0))
    monr = mon.div(tot_m.values, axis=1) * 1000
    seas = (monr.max(axis=1) - monr.min(axis=1)) / (monr.mean(axis=1) + 1e-9)   # 계절 강도
    peak = monr.idxmax(axis=1)

    yr = (exc.groupby(["dish", "y"]).size().unstack(fill_value=0).reindex(columns=YEARS, fill_value=0))
    yrr = yr.div(tot_y.values, axis=1) * 1000
    slope = yrr.apply(lambda r: np.polyfit(YEARS, r.values, 1)[0], axis=1)
    growth = (yrr[2025] + 1e-9) / (yrr[2021] + 1e-9)
    return seas, peak, slope, growth, yrr, freq


# ── 그림 ──────────────────────────────────────────────────────────────
def fig_heatmap(m, fname):
    rows = [kw for kw in SEASONAL]
    Z = np.array([rate_by_month(m, kw).values for kw in rows])
    Zz = (Z - Z.mean(1, keepdims=True)) / (Z.std(1, keepdims=True) + 1e-9)
    order = np.argsort([np.argmax(z) for z in Zz])         # 피크월 순 정렬
    rows = [rows[i] for i in order]; Zz = Zz[order]
    fig, ax = plt.subplots(figsize=(9, 7))
    fig.patch.set_facecolor(PAPER)
    im = ax.imshow(Zz, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(12)); ax.set_xticklabels(MONTH_KO)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows)
    ax.set_title("계절 캘린더 — 메뉴 × 월 (행별 z, 빨강=그 달에 몰림)", fontsize=14, color=INK)
    fig.colorbar(im, ax=ax, shrink=.7, label="월별 등장(행 z)")
    fig.tight_layout(); fig.savefig(fname, dpi=200, facecolor=PAPER); plt.close(fig)


def fig_polar(m, fname):
    fig, axes = plt.subplots(2, 3, figsize=(11, 8), subplot_kw={"projection": "polar"})
    fig.patch.set_facecolor(PAPER)
    th = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    for ax, (kw, lab) in zip(axes.ravel(), ICONIC):
        r = rate_by_month(m, kw).values
        ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
        ax.set_facecolor("#fffdf8")
        ax.fill(np.append(th, th[0]), np.append(r, r[0]), color=ACC, alpha=.25)
        ax.plot(np.append(th, th[0]), np.append(r, r[0]), color=ACC, lw=2)
        ax.set_xticks(th); ax.set_xticklabels(MONTH_KO, fontsize=8)
        ax.set_yticklabels([]); ax.set_title(lab, fontsize=12, color=INK, pad=12)
    fig.suptitle("급식의 달력 — 상징 메뉴의 월별 리듬 (천 끼당)", fontsize=15, color=INK)
    fig.tight_layout(); fig.savefig(fname, dpi=200, facecolor=PAPER); plt.close(fig)


def fig_slopegraph(m, items, fname):
    """로그 스케일 slopegraph: 세로 거리 = 배수. 트렌드(곱셈 변화)에 적합."""
    fig, ax = plt.subplots(figsize=(8.5, 9)); fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    rows = []
    for kw in items:
        r = rate_by_year(m, kw)
        a, b = max(float(r[2021]), 0.05), max(float(r[2025]), 0.05)   # 로그용 바닥
        rows.append((kw, a, b))
    rows.sort(key=lambda x: x[2] / x[1])
    for kw, a, b in rows:
        col = ACC if b >= a else "#2c6f7a"
        ax.plot([0, 1], [a, b], color=col, lw=2, marker="o", alpha=.85)
        ax.annotate(f"{kw}  ×{b/a:.1f}  ({b:.1f})", (1, b), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=10, color=col)
        ax.annotate(f"{a:.1f}", (0, a), xytext=(-6, 0), textcoords="offset points",
                    va="center", ha="right", fontsize=9, color="#6f6657")
    ax.set_yscale("log")
    ax.set_xlim(-.32, 1.85); ax.set_xticks([0, 1]); ax.set_xticklabels(["2021", "2025"], fontsize=12)
    ax.set_ylabel("천 끼당 등장 (로그)")
    ax.set_title("급식 트렌드 — 상승(주황)·하락(청록), 라벨=2021→25 배수", fontsize=13, color=INK)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(fname, dpi=200, facecolor=PAPER); plt.close(fig)


def main():
    _font()
    m = load()
    print(f"분석 끼: {len(m)} (2021~2025), 날짜 {m['date'].nunique()}일")

    # B 트렌드 표 (부분문자열)
    print("\n=== B 트렌드 (천 끼당, 2021->2025) ===")
    tr = []
    for kw in TREND:
        r = rate_by_year(m, kw)
        cagr = (r[2025] / r[2021]) ** (1 / 4) - 1 if r[2021] > 0.05 else np.nan
        tr.append((kw, r[2021], r[2025], r[2025] / max(r[2021], .05), mann_kendall(r.values), cagr))
    trdf = pd.DataFrame(tr, columns=["메뉴", "2021", "2025", "배수", "MK", "CAGR"]).sort_values("배수", ascending=False)
    print(trdf.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # 데이터 주도 발견
    print("\n=== 데이터 주도 발견 (분해 중...) ===")
    seas, peak, slope, growth, yrr, freq = discover(m)
    topseas = seas.sort_values(ascending=False).head(15)
    print("[가장 계절 타는 메뉴] (계절강도 · 피크월)")
    for d, s in topseas.items():
        print(f"  {d:12s} 강도{s:5.1f}  피크 {int(peak[d]):2d}월  (n={int(freq[d])})")
    common = freq[freq >= 8000].index
    up = slope[slope.index.isin(common)].sort_values(ascending=False).head(10)
    dn = slope[slope.index.isin(common)].sort_values().head(8)
    print("\n[급상승 메뉴] (연 기울기, 천 끼당/년)")
    for d, sl in up.items():
        print(f"  {d:12s} +{sl:.2f}/년  ({yrr.loc[d,2021]:.1f}->{yrr.loc[d,2025]:.1f})")
    print("[급하락 메뉴]")
    for d, sl in dn.items():
        print(f"  {d:12s} {sl:.2f}/년  ({yrr.loc[d,2021]:.1f}->{yrr.loc[d,2025]:.1f})")

    fig_heatmap(m, f"{FIG_DIR}/temporal_heatmap.png")
    fig_polar(m, f"{FIG_DIR}/temporal_polar.png")
    # slopegraph: 트렌드 서사 항목만 큐레이션(고정 스테이플 크림·흑임자·쌀국수 제외)
    viz = ["마라", "마라탕", "두바이", "탕후루", "약과", "바질", "그릭", "비건", "로제", "까르보", "리조또"]
    fig_slopegraph(m, viz, f"{FIG_DIR}/temporal_slopegraph.png")
    print("\n그림: temporal_heatmap.png, temporal_polar.png, temporal_slopegraph.png")


if __name__ == "__main__":
    main()
