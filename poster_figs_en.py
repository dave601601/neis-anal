"""
poster_figs_en.py
-----------------
A1 포스터용 4개 figure를 **영어 라벨**로 생성한다(assets/en/). 한글 산출물은 건드리지 않는다
(문서용 한글 그림 유지). 로제 등 제외 항목은 라벨에서도 뺀다.

  1) en_mara_share.png  — 마라가 유행 바스켓의 ~80% (가로 누적 막대)
  2) en_compete.png     — 학생 유행식 vs 어른 건강식 (2 선)
  3) en_trend.png       — 2021→2025 트렌드 배수 (로그 slopegraph, 로제 제외)
  4) en_mara_lisa.png   — 시군구 마라 LISA 핫스팟 (GIS hero)
"""
import os
import re
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from gensim.models import FastText
from esda.moran import Moran

from trend_reflection import build_set, TREND_ROOTS, HEALTH_ROOTS, NAME_MAP
from trend_spatial import load_municipalities, sigungu_trend_rate, build_weights, lisa_cat
from spatial_sigungu import Q_COLOR

OUT = "assets/en"
YEARS = [2021, 2022, 2023, 2024, 2025]
EXCLUDE = {"전북"}
PAPER, INK, FAD, HEAL, COOL = "#f6f1e7", "#211d17", "#b6452c", "#3f7a4a", "#2c6f7a"
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False


def load_meals():
    m = pd.read_parquet("meals_lunch.parquet", columns=["school_code", "date", "ddish_nm"])
    m["y"] = pd.to_datetime(m["date"], format="%Y%m%d").dt.year
    m = m[m["y"].isin(YEARS)]
    sido = pd.read_parquet("schools.parquet")[["school_code", "sido"]]
    return m.merge(sido, on="school_code").pipe(lambda d: d[~d["sido"].isin(EXCLUDE)])


def natrate(m, kws):
    pat = "|".join(map(re.escape, kws))
    hit = m["ddish_nm"].str.contains(pat, na=False, regex=True)
    return (m[hit].groupby("y").size() / m.groupby("y").size() * 1000).reindex(YEARS).fillna(0.0)


def _save(fig, name):
    fig.savefig(f"{OUT}/{name}", dpi=200, facecolor=PAPER); plt.close(fig)
    print("  ✓", name)


# 1) mara share -------------------------------------------------------------
def fig_mara_share(m, fad_kw):
    f25 = m[(m["y"] == 2025) & m["ddish_nm"].str.contains("|".join(map(re.escape, fad_kw)),
                                                          na=False, regex=True)]
    roots = [("Mala", "마라"), ("Yakgwa", "약과"), ("Greek", "그릭"), ("Dubai choc.", "두바이"),
             ("Tanghulu", "탕후루"), ("Butter cake", "버터떡"), ("Dujjonku", "두쫀쿠")]
    tot = len(f25)
    comp = [(en, f25["ddish_nm"].str.contains(ko, na=False, regex=False).sum() / tot * 100)
            for en, ko in roots]
    comp = sorted([(en, v) for en, v in comp if v >= 0.5], key=lambda x: x[1])  # asc -> biggest on top
    labels = [e for e, _ in comp]; vals = [v for _, v in comp]
    palette = {"Mala": "#b6452c", "Yakgwa": "#2c6f7a", "Greek": "#3f7a4a", "Dubai choc.": "#9c6b30",
               "Tanghulu": "#8a4a6f", "Butter cake": "#6f6657", "Dujjonku": "#a0894f"}
    colors = [palette.get(e, "#999") for e in labels]
    fig, ax = plt.subplots(figsize=(5.6, 3.0)); fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    y = np.arange(len(labels))
    ax.barh(y, vals, color=colors, edgecolor="white", height=.74)
    for yi, v in zip(y, vals):
        ax.text(v + 1.6, yi, f"{v:.0f}%", va="center", fontsize=15, color=INK)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=15)
    ax.set_xlim(0, 92); ax.set_xlabel("Share of the 2025 trend basket (%)", fontsize=12)
    ax.set_title("Mala alone is about 80% of all trend food", fontsize=14, color=INK)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); _save(fig, "en_mara_share.png")


# 2) competition ------------------------------------------------------------
def fig_compete(m, fad_kw, heal_kw):
    fad = natrate(m, fad_kw); heal = natrate(m, heal_kw)
    fig, ax = plt.subplots(figsize=(5.6, 4.2)); fig.patch.set_facecolor(PAPER); ax.set_facecolor("#fffdf8")
    ax.plot(YEARS, fad.values, "-o", color=FAD, lw=2.6, ms=6, label="Trend food (mala, yakgwa, ...)")
    ax.plot(YEARS, heal.values, "-o", color=HEAL, lw=2.6, ms=6, label="Health food (vegan, plant-based, ...)")
    ax.set_xticks(YEARS); ax.set_xlabel("Year"); ax.set_ylabel("Appearances per 1,000 meals")
    ax.set_title("Trend food vs health food, 2021 to 2025", fontsize=13, color=INK)
    ax.legend(fontsize=10, frameon=False, loc="upper left")
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); _save(fig, "en_compete.png")


# 3) trend slopegraph (no 로제) --------------------------------------------
def fig_trend(m):
    items = [("Mala", "마라"), ("Mala-tang", "마라탕"), ("Dubai choc.", "두바이"),
             ("Tanghulu", "탕후루"), ("Carbonara", "까르보")]
    rows = []
    for en, ko in items:
        r = natrate(m, [ko])
        a, b = max(float(r[2021]), 0.05), max(float(r[2025]), 0.05)
        rows.append((en, a, b))
    rows.sort(key=lambda x: x[2] / x[1])
    fig, ax = plt.subplots(figsize=(5.6, 5.2)); fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    for en, a, b in rows:
        col = FAD if b >= a else COOL
        ax.plot([0, 1], [a, b], "-o", color=col, lw=2.2, ms=5, alpha=.9)
        ax.annotate(f"{en}  x{b/a:.1f}", (1, b), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=10, color=col)
        ax.annotate(f"{a:.1f}", (0, a), xytext=(-6, 0), textcoords="offset points",
                    va="center", ha="right", fontsize=9, color="#6f6657")
    ax.set_yscale("log"); ax.set_xlim(-.3, 1.9); ax.set_xticks([0, 1])
    ax.set_xticklabels(["2021", "2025"], fontsize=12); ax.set_ylabel("Per 1,000 meals (log)")
    ax.set_title("How school lunch trends grew, 2021 to 2025", fontsize=13, color=INK)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.tight_layout(); _save(fig, "en_trend.png")


# 4) mala LISA (GIS hero) ---------------------------------------------------
def fig_lisa():
    gall, gkeys, prov = load_municipalities()
    df = sigungu_trend_rate(gkeys); g = gall.merge(df, on=["sido", "jname"], how="inner")
    w = build_weights(g)
    np.random.seed(0); mi = Moran(g["mara"].values.astype(float), w, permutations=999)
    cat = lisa_cat(g["mara"].values, w)
    lab = {0: "Not significant", 1: "High-High (hotspot)", 2: "Low-High outlier",
           3: "Low-Low (cold)", 4: "High-Low outlier"}
    fig, ax = plt.subplots(figsize=(7.0, 8.2)); fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    gall.plot(ax=ax, color="#efe8d8", edgecolor="#d8cdb8", linewidth=0.25)
    g.plot(ax=ax, color=[Q_COLOR[c] for c in cat], edgecolor="#b8ab92", linewidth=0.25)
    prov.boundary.plot(ax=ax, color="#6f6657", linewidth=0.9)
    ax.set_title(f"Mala clusters (LISA): Moran's I = {mi.I:.2f}, p = {mi.p_sim:.3f}",
                 fontsize=13, color=INK); ax.axis("off")
    keys = [k for k in lab if k in set(cat)]
    handles = [plt.Rectangle((0, 0), 1, 1, fc=Q_COLOR[k], ec="#9a8f78") for k in keys]
    ax.legend(handles, [lab[k] for k in keys], loc="lower left", fontsize=10, frameon=False)
    # annotate hotspot cities
    ax.text(0.62, 0.30, "Busan", transform=ax.transAxes, fontsize=11, color=FAD, fontweight="bold")
    ax.text(0.58, 0.45, "Daegu", transform=ax.transAxes, fontsize=11, color=FAD, fontweight="bold")
    fig.tight_layout(); _save(fig, "en_mara_lisa.png")


# 5) trend-food index vs health-food index — Korea choropleth (by province) ---
def fig_index_maps(m, fad_kw, heal_kw):
    m25 = m[m["y"] == 2025]
    den = m25.groupby("sido").size()

    def zidx(kws):
        h = m25[m25["ddish_nm"].str.contains("|".join(map(re.escape, kws)), na=False, regex=True)]
        r = (h.groupby("sido").size() / den * 1000).reindex(den.index).fillna(0.0)
        return (r - r.mean()) / (r.std(ddof=0) + 1e-9)

    fad_idx, heal_idx = zidx(fad_kw), zidx(heal_kw)
    g = gpd.read_file("skorea_provinces.json").set_crs(4326, allow_override=True)
    g["sido"] = g["name"].map(NAME_MAP)
    g["Trend"] = g["sido"].map(fad_idx); g["Health"] = g["sido"].map(heal_idx)
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 5.4)); fig.patch.set_facecolor(PAPER)
    for ax, col, ttl, cm in [(axes[0], "Trend", "Trend-food index", "Oranges"),
                             (axes[1], "Health", "Health-food index", "Greens")]:
        g.plot(column=col, ax=ax, cmap=cm, edgecolor="#cdbfa3", linewidth=.4, legend=True,
               legend_kwds={"shrink": .5}, missing_kwds={"color": "#e8e2d5"})
        ax.set_title(ttl, fontsize=13, color=INK); ax.axis("off"); ax.set_facecolor(PAPER)
    fig.suptitle("Where each is high, by province (z-score, 2025)", fontsize=13, color=INK)
    fig.tight_layout(); _save(fig, "en_index_maps.png")


def main():
    os.makedirs(OUT, exist_ok=True)
    print("loading model + meals ...")
    model = FastText.load("fasttext.model")
    fad_kw, _ = build_set(model, TREND_ROOTS)
    heal_kw, _ = build_set(model, HEALTH_ROOTS)
    m = load_meals()
    fig_mara_share(m, fad_kw)
    fig_compete(m, fad_kw, heal_kw)
    fig_trend(m)
    fig_index_maps(m, fad_kw, heal_kw)
    fig_lisa()
    print(f"done -> {OUT}/")


if __name__ == "__main__":
    main()
