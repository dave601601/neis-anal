"""
verify_trends.py
----------------
트렌드 관련 '재현 코드가 없던' 주장을 직접 검증한다.

문서(TREND_REFLECTION/README)에는 있으나 trend_*.py 어디에도 계산이 없던 수치:
  (1) 유행 바스켓의 '79%가 마라' — fad 키워드 집합에서 마라 비중.
  (2) 트렌드 수용지수 '수도권 둔감 부트스트랩 89%' — 학교 재표집으로
      P(수도권 평균 < 비수도권 평균).
  (3) 시도 1위 순위 안정성 'top-1 ~12%(마라 빼면)/~53%(마라 포함 전)' — 부트스트랩
      top-1 빈도, 그리고 마라 단일 유행 제외 시 1위가 바뀌는지.

부트스트랩은 시도 내 학교 복원추출(cluster bootstrap). 결과는 콘솔 출력만(그림 없음).
"""
import numpy as np
import pandas as pd

from trend_reflection import build_set, TREND_ROOTS
from gensim.models import FastText

YEARS_END = (2021, 2025)
NBOOT = 2000
SEED = 20260605
SUDO = {"서울", "경기", "인천"}
EXCLUDE = {"전북"}
# trend_sensitivity.py 와 동일한 바스켓
SENS_TREND = ["마라", "두바이", "탕후루", "약과", "그릭", "바질", "비건"]


def _z(a):
    return (a - a.mean()) / (a.std(ddof=0) + 1e-9)


def load_meals():
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["y"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["y"].between(2021, 2025)]
    sido = pd.read_parquet("schools.parquet")[["school_code", "sido"]]
    m = m.merge(sido, on="school_code")
    return m[~m["sido"].isin(EXCLUDE)]


# ── (1) 마라 비중 ─────────────────────────────────────────────────────
def check_mara_share(m):
    model = FastText.load("fasttext.model")
    fad_kw, _ = build_set(model, TREND_ROOTS)
    fad_re = "|".join(map(__import__("re").escape, fad_kw))
    hit = m["ddish_nm"].str.contains(fad_re, na=False, regex=True)
    fad = m[hit]
    mara = fad["ddish_nm"].str.contains("마라", na=False, regex=False).sum()
    total = len(fad)
    print("=== (1) 유행 바스켓 내 '마라' 비중 ===")
    print(f"  fad 키워드 집합: {', '.join(fad_kw)}")
    print(f"  전체 유행 hit {total:,} 중 '마라' 포함 {mara:,} → {mara/total*100:.1f}%")
    # 2025만
    f25 = fad[fad["y"] == 2025]
    m25 = f25["ddish_nm"].str.contains("마라", na=False, regex=False).sum()
    print(f"  (2025만) {len(f25):,} 중 마라 {m25:,} → {m25/max(len(f25),1)*100:.1f}%")
    return fad_kw


# ── (2)(3) 트렌드 수용지수 부트스트랩 ─────────────────────────────────
def build_school_counts(m):
    """학교×연도(2021,2025) 분모 + 키워드별 분자 테이블."""
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
    """den_sum:(K,2), num_sum_list:[(K,2)…] 시도합 → 수용지수 (K,) numpy."""
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
    # numpy 변환
    den_arr = den.values.astype(float)                       # (n,2) [2021,2025]
    num_arr = [num[kw].values.astype(float) for kw in trend]  # list of (n,2)
    codes, sido_names = pd.factorize(sido.values)             # (n,), names
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
    su_lt_no = 0; top1 = np.zeros(K, int)
    for _ in range(NBOOT):
        pick = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        ds, nss = sums(pick)
        sens = _sens_np(ds, nss)
        su_lt_no += int(sens[su_mask].mean() < sens[~su_mask].mean())
        top1[np.argmax(sens)] += 1
    print(f"  부트스트랩({NBOOT}): P(수도권<비수도권) = {su_lt_no/NBOOT*100:.0f}%")
    tops = np.argsort(-top1)[:5]
    print("  1위 빈도:", ", ".join(f"{sido_names[i]} {top1[i]/NBOOT*100:.0f}%" for i in tops))


def main():
    m = load_meals()
    print(f"분석 끼(2021~25, 전북 제외): {len(m):,}")
    check_mara_share(m)
    bootstrap_sens(m, SENS_TREND, "마라 포함")
    bootstrap_sens(m, [k for k in SENS_TREND if k != "마라"], "마라 제외")


if __name__ == "__main__":
    main()
