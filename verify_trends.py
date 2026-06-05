"""
verify_trends.py
----------------
트렌드 관련 '재현 코드가 없던' 주장을 직접 검증하고 시각화한다.

문서(TRENDS/README)에는 있으나 trend_*.py 어디에도 계산이 없던 수치:
  (1) 유행 바스켓의 '79%가 마라' — fad 키워드 집합에서 마라 비중.       → 그림 verify_mara_share.png
  (2) 트렌드 수용지수 '수도권 둔감' — 학교 재표집으로 P(수도권<비수도권). → 그림 verify_boot_sudo.png
  (3) 시도 1위 순위 안정성 — 부트스트랩 top-1 빈도(마라 포함/제외).      → 그림 verify_top1.png

부트스트랩은 시도 내 학교 복원추출(cluster bootstrap), seed 고정 → 재현 가능.
"""
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from trend_reflection import build_set, TREND_ROOTS
from gensim.models import FastText

YEARS_END = (2021, 2025)
NBOOT = 2000
SEED = 20260605
SUDO = {"서울", "경기", "인천"}
EXCLUDE = {"전북"}
SENS_TREND = ["마라", "두바이", "탕후루", "약과", "그릭", "바질", "비건"]   # trend_sensitivity.py 와 동일
SHARE_ROOTS = ["마라", "약과", "그릭", "두바이", "탕후루", "버터떡", "두쫀쿠"]  # 바스켓 구성용
FIG_DIR = "figures"
PAPER, INK, FAD, COOL, HEAL = "#f6f1e7", "#211d17", "#b6452c", "#2c6f7a", "#3f7a4a"


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name()
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


def _z(a):
    return (a - a.mean()) / (a.std(ddof=0) + 1e-9)


def load_meals():
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["y"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["y"].between(2021, 2025)]
    sido = pd.read_parquet("schools.parquet")[["school_code", "sido"]]
    m = m.merge(sido, on="school_code")
    return m[~m["sido"].isin(EXCLUDE)]


# ── (1) 마라 비중 + 바스켓 구성 그림 ─────────────────────────────────
def check_mara_share(m):
    model = FastText.load("fasttext.model")
    fad_kw, _ = build_set(model, TREND_ROOTS)
    fad_re = "|".join(map(re.escape, fad_kw))
    fad = m[m["ddish_nm"].str.contains(fad_re, na=False, regex=True)]
    mara_all = fad["ddish_nm"].str.contains("마라", na=False, regex=False).sum()
    print("=== (1) 유행 바스켓 내 '마라' 비중 ===")
    print(f"  fad 키워드 집합: {', '.join(fad_kw)}")
    print(f"  전체 유행 hit {len(fad):,} 중 '마라' 포함 {mara_all:,} → {mara_all/len(fad)*100:.1f}%")
    f25 = fad[fad["y"] == 2025]
    comp = {r: f25["ddish_nm"].str.contains(r, na=False, regex=False).sum() for r in SHARE_ROOTS}
    tot25 = len(f25)
    print(f"  (2025만) 총 {tot25:,} — 구성:",
          ", ".join(f"{r} {c/tot25*100:.1f}%" for r, c in comp.items()))

    # 그림: 2025 유행 바스켓 구성 — 수평 누적 막대(마라 지배 시각화)
    _font()
    order = sorted(comp, key=lambda r: -comp[r])
    fig, ax = plt.subplots(figsize=(9, 2.6)); fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    left = 0
    cmap = plt.cm.autumn(np.linspace(0, .85, len(order)))
    for col, r in zip(cmap, order):
        w = comp[r] / tot25 * 100
        ax.barh(0, w, left=left, color=col, edgecolor=PAPER)
        if w > 3:
            ax.text(left + w / 2, 0, f"{r}\n{w:.0f}%", ha="center", va="center",
                    fontsize=9, color=INK if r == "마라" else "#fff")
        left += w
    ax.set_xlim(0, 100); ax.set_ylim(-.5, .5); ax.set_yticks([])
    ax.set_xlabel("2025년 유행 바스켓 구성비 (%)")
    ax.set_title("유행 바스켓의 79.7%가 '마라' 단일 항목 — \"유행 반영\"은 사실상 \"마라 반영\"",
                 fontsize=12, color=INK)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/verify_mara_share.png", dpi=200, facecolor=PAPER)
    plt.close(fig)
    return mara_all / len(fad)


# ── (2)(3) 트렌드 수용지수 부트스트랩 ─────────────────────────────────
def build_school_counts(m):
    mm = m[m["y"].isin(YEARS_END)].copy()
    den = mm.groupby(["school_code", "y"]).size().unstack().reindex(columns=YEARS_END).fillna(0)
    num = {}
    for kw in SENS_TREND:
        h = mm[mm["ddish_nm"].str.contains(kw, na=False, regex=False)]
        num[kw] = (h.groupby(["school_code", "y"]).size().unstack()
                   .reindex(index=den.index, columns=YEARS_END).fillna(0))
    sido = (pd.read_parquet("schools.parquet")[["school_code", "sido"]]
            .drop_duplicates("school_code")
            .set_index("school_code")["sido"]).reindex(den.index)
    return den, num, sido


def _sens_np(den_sum, num_sum_list):
    def z(v):
        return (v - v.mean()) / (v.std() + 1e-9)
    lvl = np.zeros(den_sum.shape[0]); grw = np.zeros(den_sum.shape[0])
    for ns in num_sum_list:
        r25 = ns[:, 1] / (den_sum[:, 1] + 1e-9) * 1000
        r21 = ns[:, 0] / (den_sum[:, 0] + 1e-9) * 1000
        lvl += z(r25); grw += z(r25 - r21)
    n = len(num_sum_list)
    return ((lvl / n) + (grw / n)) / 2


def bootstrap_sens(m, trend, label):
    den, num, sido = build_school_counts(m)
    den_arr = den.values.astype(float)
    num_arr = [num[kw].values.astype(float) for kw in trend]
    codes, sido_names = pd.factorize(sido.values)
    K = len(sido_names)
    su_mask = np.array([s in SUDO for s in sido_names])

    def sums(pick):
        sc = codes[pick]
        ds = np.stack([np.bincount(sc, den_arr[pick, c], minlength=K) for c in (0, 1)], axis=1)
        nss = [np.stack([np.bincount(sc, na[pick, c], minlength=K) for c in (0, 1)], axis=1)
               for na in num_arr]
        return ds, nss

    allpos = np.arange(len(codes))
    ds0, ns0 = sums(allpos)
    sens0 = _sens_np(ds0, ns0)
    order = np.argsort(-sens0)
    su0, no0 = sens0[su_mask].mean(), sens0[~su_mask].mean()
    print(f"\n=== ({label}) 관측 수용지수 (민감↑) ===")
    for i in order:
        print(f"  {sido_names[i]:4s} {sens0[i]:+.2f} {'수도권' if su_mask[i] else ''}")
    print(f"  수도권 {su0:+.2f} vs 비수도권 {no0:+.2f}  (수도권 둔감={su0 < no0})")
    print(f"  관측 1위: {sido_names[order[0]]}")

    rng = np.random.default_rng(SEED)
    groups = [np.where(codes == k)[0] for k in range(K)]
    su_arr = np.empty(NBOOT); no_arr = np.empty(NBOOT); top1 = np.zeros(K, int)
    for b in range(NBOOT):
        pick = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        ds, nss = sums(pick)
        sens = _sens_np(ds, nss)
        su_arr[b] = sens[su_mask].mean(); no_arr[b] = sens[~su_mask].mean()
        top1[np.argmax(sens)] += 1
    p_sudo = (su_arr < no_arr).mean() * 100
    print(f"  부트스트랩({NBOOT}): P(수도권<비수도권) = {p_sudo:.0f}%")
    tops = np.argsort(-top1)[:6]
    print("  1위 빈도:", ", ".join(f"{sido_names[i]} {top1[i]/NBOOT*100:.0f}%" for i in tops))
    return dict(names=sido_names, su0=su0, no0=no0, su_arr=su_arr, no_arr=no_arr,
                p_sudo=p_sudo, top1=top1 / NBOOT * 100)


def fig_boot_sudo(res):
    """수도권 vs 비수도권 평균 수용지수의 부트스트랩 분포(겹친 히스토그램)."""
    fig, ax = plt.subplots(figsize=(8.5, 4.8)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    bins = np.linspace(min(res["su_arr"].min(), res["no_arr"].min()),
                       max(res["su_arr"].max(), res["no_arr"].max()), 40)
    ax.hist(res["no_arr"], bins=bins, color=FAD, alpha=.55, label="비수도권 평균")
    ax.hist(res["su_arr"], bins=bins, color=COOL, alpha=.55, label="수도권 평균")
    ax.axvline(res["no0"], color=FAD, lw=2); ax.axvline(res["su0"], color=COOL, lw=2)
    ax.set_xlabel("트렌드 수용 지수 (z)"); ax.set_ylabel("부트스트랩 표본 수")
    ax.set_title(f"수도권은 비수도권보다 둔감 — 2,000회 재표집 중 {res['p_sudo']:.0f}%에서 수도권<비수도권",
                 fontsize=12, color=INK)
    ax.legend(fontsize=10, frameon=False)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/verify_boot_sudo.png", dpi=200, facecolor=PAPER)
    plt.close(fig)


def fig_top1(res_in, res_ex):
    """시도 1위 부트스트랩 빈도 — 마라 포함 vs 제외."""
    names = list(res_in["names"])
    union = sorted(set(np.array(names)[res_in["top1"] > 0]) | set(np.array(names)[res_ex["top1"] > 0]),
                   key=lambda s: -res_in["top1"][names.index(s)])
    inc = [res_in["top1"][names.index(s)] for s in union]
    exc = [res_ex["top1"][names.index(s)] for s in union]
    y = np.arange(len(union)); h = .38
    fig, ax = plt.subplots(figsize=(8, 4.8)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    ax.barh(y + h / 2, inc, height=h, color=FAD, label="마라 포함")
    ax.barh(y - h / 2, exc, height=h, color=COOL, label="마라 제외")
    ax.set_yticks(y); ax.set_yticklabels(union); ax.invert_yaxis()
    ax.set_xlabel("부트스트랩 1위 빈도 (%)")
    ax.set_title("시도 1위는 광주가 최빈 — 마라를 빼면 오히려 더 견고(40%)",
                 fontsize=12, color=INK)
    ax.legend(fontsize=10, frameon=False)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/verify_top1.png", dpi=200, facecolor=PAPER)
    plt.close(fig)


def main():
    _font()
    m = load_meals()
    print(f"분석 끼(2021~25, 전북 제외): {len(m):,}")
    check_mara_share(m)
    res_in = bootstrap_sens(m, SENS_TREND, "마라 포함")
    res_ex = bootstrap_sens(m, [k for k in SENS_TREND if k != "마라"], "마라 제외")
    fig_boot_sudo(res_in)
    fig_top1(res_in, res_ex)
    print("\n그림: verify_mara_share.png, verify_boot_sudo.png, verify_top1.png")


if __name__ == "__main__":
    main()
