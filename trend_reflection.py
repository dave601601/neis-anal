"""
trend_reflection.py  (교정판)
-----------------------------
"새 음식 유행이 실제로 급식에 반영되는가 — 식단 짜는 어른들이 학생 유행을 따라가는가?"

[교정 사유] 초판은 시드 임베딩의 '중심 벡터'로 확장했는데, 마라(매운)+탕후루(디저트)+
요거트(유제품)를 평균한 centroid가 "유행"이 아니라 "디저트 일반"을 가리켜 아이스크림·
마카롱·도넛 같은 상시 디저트가 유행식 카운트를 지배했다(아이스크림 단독 3.7만 건).

[교정] (1) 구체적 트렌드 단어를 root로 큐레이션, (2) 임베딩은 root별 최근접 변형만 보강
(blended centroid 금지), (3) 스테이플(아이스크림·마카롱·도넛·요거트·우유 등) stopword 제외.
이러면 root substring이 본질적으로 깨끗하고, 임베딩은 두쫀쿠 같은 비(非)root 변형만 보탠다.

산출: figures/refl_*.png + 콘솔(최종 키워드·제외어 포함).
"""
import re
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from scipy.stats import pearsonr
from gensim.models import FastText

YEARS = [2021, 2022, 2023, 2024, 2025]
FIG_DIR = "figures"
PAPER, INK, FAD, HEAL = "#f6f1e7", "#211d17", "#b6452c", "#3f7a4a"
SUDO = {"서울", "경기", "인천"}
EXCLUDE = {"전북"}
NAME_MAP = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
 "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
 "경기도": "경기", "강원도": "강원", "충청북도": "충북", "충청남도": "충남", "전라북도": "전북",
 "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주"}

# 구체적 2021~25 트렌드 root (이 단어가 들어간 메뉴는 진짜 그 유행)
TREND_ROOTS = ["마라", "로제", "탕후루", "두바이", "약과", "그릭", "흑당", "버블티", "두쫀쿠", "버터떡"]
# 헬시 플레저/대체식품 root (식물성·비건·콩 계열)
HEALTH_ROOTS = ["비건", "채식", "식물성", "콩고기", "콩불고기", "곡물불고기", "대체", "두유", "두부까스", "두부텐더"]
# 스테이플(상시 메뉴) — root를 포함하지 않으면 제외
STOP = ["아이스크림", "마카롱", "도넛", "케잌", "케이크", "사탕", "요거트", "요구르트", "만주",
        "다쿠아즈", "오란다", "쿠키", "젤리", "우유", "프리첼", "파이", "푸딩", "빙수"]
# 개별 라인용 대표 유행(부분문자열)
FAD_ITEMS = ["마라", "로제", "탕후루", "두바이", "약과", "그릭"]


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name(); break
    matplotlib.rcParams["axes.unicode_minus"] = False


def build_set(model, roots, sim_thr=0.6, min_count=30):
    """root별 임베딩 최근접 변형만 보강(blended centroid 금지) + 스테이플 제외."""
    cand = set(roots)
    for r in roots:
        try:
            for w, sc in model.wv.most_similar(r, topn=25):
                # 임베딩 변형은 트렌드 root를 포함하는 것만(약과→송편 같은 의미표류 차단)
                if (sc >= sim_thr and model.wv.get_vecattr(w, "count") >= min_count
                        and any(rt in w for rt in roots)):
                    cand.add(w)
        except KeyError:
            pass

    def is_staple(t):
        return any(s in t for s in STOP) and not any(r in t for r in roots)
    keep = sorted(t for t in cand if not is_staple(t))
    dropped = sorted(t for t in cand if is_staple(t))
    return keep, dropped


def rate_year(m, regex, by_region=False):
    hit = m["ddish_nm"].str.contains(regex, na=False, regex=True)
    if by_region:
        return (m[hit].groupby(["sido", "y"]).size() / m.groupby(["sido", "y"]).size() * 1000)
    return (m[hit].groupby("y").size() / m.groupby("y").size() * 1000).reindex(YEARS)


def main():
    _font()
    model = FastText.load("fasttext.model")
    fad_kw, fad_drop = build_set(model, TREND_ROOTS)
    heal_kw, heal_drop = build_set(model, HEALTH_ROOTS)
    print("=== 유행식 키워드(교정) ===\n  " + ", ".join(fad_kw))
    print("  [스테이플 제외]:", ", ".join(fad_drop) or "(없음)")
    print("=== 건강식 키워드(교정) ===\n  " + ", ".join(heal_kw))
    print("  [스테이플 제외]:", ", ".join(heal_drop) or "(없음)")

    fad_re = "|".join(map(re.escape, fad_kw))
    heal_re = "|".join(map(re.escape, heal_kw))

    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["y"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["y"].isin(YEARS)]
    sido = pd.read_parquet("schools.parquet")[["school_code", "sido"]]
    m = m.merge(sido, on="school_code")
    m = m[~m["sido"].isin(EXCLUDE)]

    fad_nat = rate_year(m, fad_re)
    heal_nat = rate_year(m, heal_re)
    print("\n=== 전국 등장률(천 끼당, 연도) ===")
    print("유행식:", {y: round(fad_nat[y], 1) for y in YEARS}, f"({fad_nat[2025]/max(fad_nat[2021],.01):.1f}배)")
    print("건강식:", {y: round(heal_nat[y], 1) for y in YEARS}, f"({heal_nat[2025]/max(heal_nat[2021],.01):.1f}배)")
    print(f"유행:건강 비 = {fad_nat[2025]/max(heal_nat[2025],.01):.1f}배")

    fr = rate_year(m, fad_re, by_region=True).unstack().reindex(columns=YEARS).fillna(0)
    hr = rate_year(m, heal_re, by_region=True).unstack().reindex(columns=YEARS).fillna(0)
    sidos = fr.index.tolist()
    fad_idx = (fr[2025] - fr[2025].mean()) / fr[2025].std()
    heal_idx = (hr[2025] - hr[2025].mean()) / hr[2025].std()

    print("\n=== 단기 유행식 지역 (2025 천끼당, 높은순) ===")
    for s in fr[2025].sort_values(ascending=False).index:
        print(f"  {s:4s} {fr.loc[s,2025]:5.1f} {'수도권' if s in SUDO else ''}")
    su = fr.loc[fr.index.isin(SUDO), 2025].mean(); no = fr.loc[~fr.index.isin(SUDO), 2025].mean()
    print(f"수도권 {su:.1f} vs 비수도권 {no:.1f} → 가설(수도권 우세) {'성립' if su>no else '기각'}")

    g = gpd.read_file("skorea_provinces.json").set_crs(4326, allow_override=True).to_crs(5179)
    g["sido"] = g["name"].map(NAME_MAP)
    cent = g.set_geometry(g.geometry.representative_point())
    seoul = cent[cent.sido == "서울"].geometry.iloc[0]
    g["dist"] = cent.geometry.distance(seoul) / 1000
    gg = g[g.sido.isin(sidos)].copy()
    gg["fad"] = gg["sido"].map(fad_idx); gg["heal"] = gg["sido"].map(heal_idx)
    r, p = pearsonr(gg["dist"], gg["fad"])
    print(f"서울거리 × 유행식: r={r:+.2f} p={p:.3f} (음=수도권 우세)")

    # 그림 1: 개별 유행 시계열
    fig, ax = plt.subplots(figsize=(9, 5.5)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    cmap = plt.cm.autumn(np.linspace(0, .8, len(FAD_ITEMS)))
    for c, kw in zip(cmap, FAD_ITEMS):
        ax.plot(YEARS, rate_year(m, re.escape(kw)).values, "-o", color=c, lw=2, ms=4, label=kw)
    ax.set_xticks(YEARS); ax.set_xlabel("연도"); ax.set_ylabel("천 끼당 등장")
    ax.set_title("단기 유행식의 급식 반영 — 마라·로제만 크게, 간식형은 미미", fontsize=12, color=INK)
    ax.legend(fontsize=9, frameon=False, ncol=2)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{FIG_DIR}/refl_fad_lines.png", dpi=200, facecolor=PAPER)

    # 그림 2: 경쟁(전국)
    fig2, ax2 = plt.subplots(figsize=(8.5, 5)); fig2.patch.set_facecolor(PAPER); ax2.set_facecolor("#fffdf8")
    ax2.plot(YEARS, fad_nat.values, "-o", color=FAD, lw=2.4, ms=5, label="유행식(마라·로제·약과…)")
    ax2.plot(YEARS, heal_nat.values, "-o", color=HEAL, lw=2.4, ms=5, label="건강식(비건·채식·콩…)")
    ax2.set_xticks(YEARS); ax2.set_xlabel("연도"); ax2.set_ylabel("천 끼당 등장")
    ax2.set_title("급식 속 경쟁구도 — 학생 유행식 vs 어른 건강식 (교정)", fontsize=13, color=INK)
    ax2.legend(fontsize=10, frameon=False)
    for s in ["top", "right"]:
        ax2.spines[s].set_visible(False)
    fig2.tight_layout(); fig2.savefig(f"{FIG_DIR}/refl_compete_nat.png", dpi=200, facecolor=PAPER)

    # 그림 3: 지도 2장
    fig3, axes = plt.subplots(1, 2, figsize=(11, 6.5)); fig3.patch.set_facecolor(PAPER)
    for ax3, col, ttl, cm in [(axes[0], "fad", "단기 유행식 지수", "Oranges"),
                              (axes[1], "heal", "건강식 지수", "Greens")]:
        gg.plot(column=col, ax=ax3, cmap=cm, edgecolor="#cdbfa3", linewidth=.4, legend=True,
                legend_kwds={"shrink": .55})
        for _, rr in gg.iterrows():
            c = rr.geometry.representative_point()
            ax3.annotate(rr["sido"], (c.x, c.y), ha="center", va="center", fontsize=7, color=INK)
        ax3.set_title(ttl, fontsize=12, color=INK); ax3.axis("off"); ax3.set_facecolor(PAPER)
    fig3.suptitle("지역 분포 — 유행식(좌) vs 건강식(우)", fontsize=13, color=INK)
    fig3.tight_layout(); fig3.savefig(f"{FIG_DIR}/refl_maps.png", dpi=200, facecolor=PAPER)

    # 그림 4: 경쟁 산점도
    fig4, ax4 = plt.subplots(figsize=(7.5, 6)); fig4.patch.set_facecolor(PAPER); ax4.set_facecolor("#fffdf8")
    for s in sidos:
        c = "#2c6f7a" if s in SUDO else FAD
        ax4.scatter(heal_idx[s], fad_idx[s], s=55, color=c, edgecolor=INK, zorder=3)
        ax4.annotate(s, (heal_idx[s], fad_idx[s]), fontsize=8, xytext=(4, 3), textcoords="offset points")
    rr2, pp2 = pearsonr(heal_idx.values, fad_idx.values)
    xs = np.array([heal_idx.min(), heal_idx.max()])
    ax4.plot(xs, np.poly1d(np.polyfit(heal_idx, fad_idx, 1))(xs), "--", color=INK, lw=1.2,
             label=f"r={rr2:+.2f} (p={pp2:.2f})")
    ax4.axhline(0, color="#b0a890", lw=.6); ax4.axvline(0, color="#b0a890", lw=.6)
    ax4.set_xlabel("건강식 지수 (z)"); ax4.set_ylabel("유행식 지수 (z)")
    ax4.set_title("지역별 경쟁구도 — 건강식 강한 곳이 유행식도 강한가?", fontsize=12, color=INK)
    ax4.legend(fontsize=10, frameon=False)
    for s in ["top", "right"]:
        ax4.spines[s].set_visible(False)
    fig4.tight_layout(); fig4.savefig(f"{FIG_DIR}/refl_compete_scatter.png", dpi=200, facecolor=PAPER)
    print(f"\n건강식 × 유행식 지역 상관: r={rr2:+.2f} p={pp2:.2f}")
    print("그림: refl_fad_lines.png, refl_compete_nat.png, refl_maps.png, refl_compete_scatter.png")


if __name__ == "__main__":
    main()
