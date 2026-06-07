"""
poster_figs_en.py
-----------------
A1 포스터용 영어 figure 5종 (assets/en/). 한글 산출물은 건드리지 않는다.
스타일: 흰 배경, 차분한 팔레트(terracotta / teal / slate — 신호등 색 금지),
큰 제목, 잘 보이는 범례. 그림 제목이 곧 설명이라 HTML 캡션은 뺀다.
"""
import os
import re
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from gensim.models import FastText
from esda.moran import Moran

from trend_reflection import build_set, TREND_ROOTS, HEALTH_ROOTS, NAME_MAP
from trend_spatial import load_municipalities, sigungu_trend_rate, build_weights, lisa_cat

OUT = "assets/en"
YEARS = [2021, 2022, 2023, 2024, 2025]
EXCLUDE = {"전북"}
WHITE, INK, MUTE = "#ffffff", "#1b1b1b", "#666666"
T, H, G = "#b5654a", "#2f6d74", "#44476a"          # terracotta / teal / slate
CMAP_T = LinearSegmentedColormap.from_list("t", ["#f4ece7", "#b5654a"])
CMAP_H = LinearSegmentedColormap.from_list("h", ["#e6eeee", "#2f6d74"])
# LISA cluster colours (no red/green/blue traffic lights)
LCOL = {0: "#ededed", 1: T, 2: "#a9c5c8", 3: H, 4: "#d8b3a6"}
LLAB = {0: "Not significant", 1: "Hotspot (high, high)", 2: "Low among highs",
        3: "Cold spot (low, low)", 4: "High among lows"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.unicode_minus": False,
    "font.size": 14, "axes.titlesize": 19, "axes.titleweight": "bold",
    "axes.labelsize": 14, "legend.fontsize": 15, "xtick.labelsize": 13, "ytick.labelsize": 13,
    "figure.facecolor": WHITE, "axes.facecolor": WHITE, "savefig.facecolor": WHITE,
})


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


def _legend(ax):
    ax.legend(fontsize=15, frameon=True, facecolor="white", edgecolor="#cccccc",
              framealpha=1, loc="upper left")


def _save(fig, name):
    fig.tight_layout(); fig.savefig(f"{OUT}/{name}", dpi=200); plt.close(fig)
    print("  saved", name)


# 1) mala share -------------------------------------------------------------
def fig_mara_share(m, fad_kw):
    f25 = m[(m["y"] == 2025) & m["ddish_nm"].str.contains("|".join(map(re.escape, fad_kw)),
                                                          na=False, regex=True)]
    roots = [("Mala", "마라"), ("Yakgwa", "약과"), ("Greek", "그릭"), ("Dubai choc.", "두바이"),
             ("Tanghulu", "탕후루")]
    tot = len(f25)
    comp = [(en, f25["ddish_nm"].str.contains(ko, na=False, regex=False).sum() / tot * 100)
            for en, ko in roots]
    comp = sorted([(en, v) for en, v in comp if v >= 0.5], key=lambda x: x[1])
    labels = [e for e, _ in comp]; vals = [v for _, v in comp]
    pal = {"Mala": T, "Yakgwa": H, "Greek": "#b08a3a", "Dubai choc.": "#8a5a3c", "Tanghulu": "#6d5577"}
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    y = np.arange(len(labels))
    ax.barh(y, vals, color=[pal.get(e, "#999") for e in labels], edgecolor="white", height=.74)
    for yi, v in zip(y, vals):
        ax.text(v + 1.6, yi, f"{v:.0f}%", va="center", fontsize=17, color=INK, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=16)
    ax.set_xlim(0, 95); ax.set_xlabel("Share of the 2025 trend basket (%)")
    ax.set_title("Mala is ~80% of trend food", fontsize=18)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    _save(fig, "en_mara_share.png")


# 2) competition ------------------------------------------------------------
def fig_compete(m, fad_kw, heal_kw):
    fad = natrate(m, fad_kw); heal = natrate(m, heal_kw)
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    ax.plot(YEARS, fad.values, "-o", color=T, lw=3, ms=7)
    ax.plot(YEARS, heal.values, "-s", color=H, lw=3, ms=7)
    # label lines directly at their right end (no legend box to cover the curve)
    ax.annotate("Trend food", (2025, fad[2025]), xytext=(7, 0), textcoords="offset points",
                va="center", fontsize=16, color=T, fontweight="bold")
    ax.annotate("Health food", (2025, heal[2025]), xytext=(7, 0), textcoords="offset points",
                va="center", fontsize=16, color=H, fontweight="bold")
    ax.set_xticks(YEARS); ax.set_xlim(2020.8, 2026.7); ax.set_ylim(bottom=0)
    ax.set_xlabel("Year"); ax.set_ylabel("Appearances per 1,000 meals")
    ax.set_title("Trend food climbs, health stays flat", fontsize=17)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    _save(fig, "en_compete.png")


# 3) trend slopegraph -------------------------------------------------------
def fig_trend(m):
    items = [("Mala", "마라"), ("Mala-tang", "마라탕"), ("Dubai choc.", "두바이"),
             ("Tanghulu", "탕후루"), ("Carbonara", "까르보")]
    rows = []
    for en, ko in items:
        r = natrate(m, [ko])
        a, b = max(float(r[2021]), 0.05), max(float(r[2025]), 0.05)
        rows.append((en, a, b))
    rows.sort(key=lambda x: x[2] / x[1])
    fig, ax = plt.subplots(figsize=(5.6, 5.0))
    for en, a, b in rows:
        col = T if b >= a else H
        ax.plot([0, 1], [a, b], "-o", color=col, lw=2.6, ms=6)
        ax.annotate(f"{en}  x{b/a:.1f}", (1, b), xytext=(9, 0), textcoords="offset points",
                    va="center", fontsize=15, color=col, fontweight="bold")
        ax.annotate(f"{a:.1f}", (0, a), xytext=(-6, 0), textcoords="offset points",
                    va="center", ha="right", fontsize=13, color=MUTE)
    ax.set_yscale("log"); ax.set_xlim(-.3, 1.95); ax.set_xticks([0, 1])
    ax.set_xticklabels(["2021", "2025"]); ax.set_ylabel("Per 1,000 meals (log)")
    ax.set_title("Mala soars; snack fads stay flat", fontsize=19)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    _save(fig, "en_trend.png")


# 4) trend vs health index maps --------------------------------------------
def fig_index_maps(m, fad_kw, heal_kw):
    m25 = m[m["y"] == 2025]; den = m25.groupby("sido").size()

    def zidx(kws):
        h = m25[m25["ddish_nm"].str.contains("|".join(map(re.escape, kws)), na=False, regex=True)]
        r = (h.groupby("sido").size() / den * 1000).reindex(den.index).fillna(0.0)
        return (r - r.mean()) / (r.std(ddof=0) + 1e-9)

    g = gpd.read_file("skorea_provinces.json").set_crs(4326, allow_override=True)
    g["sido"] = g["name"].map(NAME_MAP)
    g["Trend"] = g["sido"].map(zidx(fad_kw)); g["Health"] = g["sido"].map(zidx(heal_kw))
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 5.4))
    for ax, col, ttl, cm in [(axes[0], "Trend", "Trend food", CMAP_T),
                             (axes[1], "Health", "Health food", CMAP_H)]:
        g.plot(column=col, ax=ax, cmap=cm, edgecolor="#bbbbbb", linewidth=.4, legend=True,
               legend_kwds={"shrink": .55}, missing_kwds={"color": "#ededed"})
        ax.set_title(ttl, fontsize=18); ax.axis("off")
    fig.suptitle("Where each runs high, by province (2025)", fontsize=18, fontweight="bold")
    _save(fig, "en_index_maps.png")


# 5) mala LISA (GIS hero) ---------------------------------------------------
def fig_lisa():
    gall, gkeys, prov = load_municipalities()
    df = sigungu_trend_rate(gkeys); g = gall.merge(df, on=["sido", "jname"], how="inner")
    w = build_weights(g)
    np.random.seed(0); mi = Moran(g["mara"].values.astype(float), w, permutations=999)
    cat = lisa_cat(g["mara"].values, w)
    fig, ax = plt.subplots(figsize=(7.0, 8.2))
    gall.plot(ax=ax, color="#f2f2f2", edgecolor="#dddddd", linewidth=0.25)
    g.plot(ax=ax, color=[LCOL[c] for c in cat], edgecolor="#bbbbbb", linewidth=0.25)
    prov.boundary.plot(ax=ax, color="#888888", linewidth=0.9)
    ax.set_title("Mala clusters in Busan and Daegu", fontsize=19); ax.axis("off")
    keys = [k for k in LLAB if k in set(cat)]
    handles = [plt.Rectangle((0, 0), 1, 1, fc=LCOL[k], ec="#888888") for k in keys]
    ax.legend(handles, [LLAB[k] for k in keys], loc="lower left", fontsize=15,
              frameon=True, facecolor="white", edgecolor="#cccccc", framealpha=1)
    ax.text(0.62, 0.30, "Busan", transform=ax.transAxes, fontsize=15, color=T, fontweight="bold")
    ax.text(0.57, 0.46, "Daegu", transform=ax.transAxes, fontsize=15, color=T, fontweight="bold")
    _save(fig, "en_mara_lisa.png")


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
