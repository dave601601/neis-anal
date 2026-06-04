"""
spatial_sigungu.py
------------------
시군구(~250) 단위 공간 자기상관 — 시도(17)보다 고해상.

기존 학교 벡터·임베딩을 그대로 재사용(재수집·재임베딩 불필요).
1. 학교 주소 -> 시군구 매핑 (2013 geojson과 현재 행정구역 차이 보정).
2. 학교 속성·임베딩 대비점수를 시군구로 집계(최소 MIN_SCH개교).
3. 시군구 경계 geojson에 붙여 W(Queen+섬 보정) -> Global Moran's I + LISA.
4. figures/sigungu_*.png 생성 + 콘솔 표.
"""
import json
import os

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
from libpysal.weights import Queen, KNN, W, lag_spatial
from esda.moran import Moran, Moran_Local
from gensim.models import FastText
from menu_attributes import FEATURE_COLUMNS
from region_metrics import CONTRASTS, keyword_vector

SEED, PERM = 0, 999
MIN_SCH = 3                  # 시군구당 최소 학교수(미만은 노이즈 -> 제외)
FIG_DIR = "figures"
PROTEIN_COLS = [c for c in FEATURE_COLUMNS if c.startswith("protein_")]

NAME_MAP = {"서울특별시":"서울","부산광역시":"부산","대구광역시":"대구","인천광역시":"인천",
 "광주광역시":"광주","대전광역시":"대전","울산광역시":"울산","세종특별자치시":"세종",
 "경기도":"경기","강원도":"강원","충청북도":"충북","충청남도":"충남","전라북도":"전북",
 "전라남도":"전남","경상북도":"경북","경상남도":"경남","제주특별자치도":"제주"}

# 행정구역 변경 보정
RENAME = {("인천", "미추홀구"): "남구"}        # 2018 개명
SIDO_FIX = {"군위군": "경북"}                  # geojson(2013)은 군위를 경북에 둠
DISSOLVE = ("부천시", "청주시")                # 구 분할 불일치 -> 시로 합침

METRICS = {
    "rice": "밥 점유율", "bread": "빵 점유율", "noodle": "면 점유율",
    "seafood_share": "해산물 사용도", "protein_index": "단백질 사용도",
    "con_sea_meat": "해산물↔육류", "con_noodle_rice": "면↔밥",
    "con_spicy_mild": "매운↔순한", "con_west_korean": "양식↔한식",
}
Q_COLOR = {0: "#e8e2d5", 1: "#c0392b", 2: "#a9cce3", 3: "#2c6f9b", 4: "#f1948a"}
Q_LABEL = {0: "유의하지 않음", 1: "HH 다같이 높음", 2: "LH 외딴(낮은 섬)",
           3: "LL 다같이 낮음", 4: "HL 외딴(높은 섬)"}


def _font():
    for f in fm.findSystemFonts():
        if "NotoSansCJK" in f:
            fm.fontManager.addfont(f)
            matplotlib.rcParams["font.family"] = fm.FontProperties(fname=f).get_name()
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


def _join_name(sido, name):
    """dissolve 대상 시는 시 단위로 합침."""
    for d in DISSOLVE:
        if name.startswith(d):
            return d
    return name


def load_municipalities():
    muni = gpd.read_file("skorea_municipalities.json").set_crs(4326, allow_override=True)
    prov = gpd.read_file("skorea_provinces.json").set_crs(4326, allow_override=True)
    prov["sido"] = prov["name"].map(NAME_MAP)
    cent = muni.copy(); cent = cent.set_geometry(cent.geometry.representative_point())
    muni["sido"] = gpd.sjoin(cent, prov[["sido", "geometry"]], how="left",
                             predicate="within")["sido"].values
    muni["jname"] = [_join_name(s, n) for s, n in zip(muni["sido"], muni["name"])]
    g = muni.dissolve(by=["sido", "jname"], as_index=False)
    return g[["sido", "jname", "geometry"]], set(zip(g["sido"], g["jname"])), prov


def school_sigungu(geo_keys):
    """학교 -> (sido, jname). geojson에 있는 키로 안착시킨다."""
    sch = pd.read_parquet("schools.parquet")[["school_code", "sido", "addr"]]

    def key(row):
        sido, t = row["sido"], str(row["addr"]).split()
        if sido == "세종":
            return (sido, "세종시")
        base = t[1] if len(t) > 1 else None
        cand = (t[1] + t[2]) if (len(t) >= 3 and t[1].endswith("시")
                                 and t[2].endswith("구")) else base
        cand = RENAME.get((sido, cand), cand)
        sido = SIDO_FIX.get(cand, sido)
        for k in (cand, base):                       # 시+구 우선, 안 되면 시
            if k and _join_name(sido, k) and (sido, _join_name(sido, k)) in geo_keys:
                return (sido, _join_name(sido, k))
        return (sido, None)

    keys = sch.apply(key, axis=1)
    sch["sido"] = [k[0] for k in keys]
    sch["jname"] = [k[1] for k in keys]
    return sch.dropna(subset=["jname"])[["school_code", "sido", "jname"]]


def build_school_metrics():
    """학교별 명시 속성 + 임베딩 대비점수(원시, z 이전)."""
    raw = pd.read_parquet("school_vectors_raw.parquet")
    emb = pd.read_parquet("school_embeddings.parquet")
    emb_cols = [c for c in emb.columns if c.startswith("emb_")]
    model = FastText.load("fasttext.model")
    df = raw.merge(emb, on="school_code")

    out = pd.DataFrame({"school_code": df["school_code"]})
    out["rice"] = df["form_rice"]; out["bread"] = df["form_bread"]
    out["noodle"] = df["form_noodle"]; out["seafood_share"] = df["protein_seafood"]
    out["protein_index"] = df[PROTEIN_COLS].sum(axis=1)

    E = df[emb_cols].values
    En = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
    for name, (a, b) in CONTRASTS.items():
        out[name] = En @ keyword_vector(model, a) - En @ keyword_vector(model, b)
    return out


def _zscore(s):
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd > 1e-9 else s * 0.0


def aggregate(gkeys):
    sm = build_school_metrics()
    sg = school_sigungu(gkeys)
    df = sm.merge(sg, on="school_code")
    grp = df.groupby(["sido", "jname"])
    agg = grp[list(METRICS)].mean()
    agg["n_sch"] = grp.size()
    agg = agg[agg["n_sch"] >= MIN_SCH].reset_index()
    # 대비점수는 시군구 비교용 z-표준화
    for c in CONTRASTS:
        agg[c] = _zscore(agg[c])
    return agg, len(df), int(df["school_code"].nunique())


def build_weights(g):
    w = Queen.from_dataframe(g, use_index=True)
    if w.islands:
        knn = KNN.from_dataframe(g, k=2)
        neigh = {i: list(w.neighbors[i]) for i in w.id_order}
        wts = {i: list(w.weights[i]) for i in w.id_order}
        for isl in w.islands:
            for j in knn.neighbors[isl]:
                for a, b in [(isl, j), (j, isl)]:
                    if b not in neigh[a]:
                        neigh[a].append(b); wts[a].append(1.0)
        w = W(neigh, wts)
        print(f"  섬 {len(w.islands) if hasattr(w,'islands') else 0}곳 최근접 연결")
    w.transform = "r"
    return w


def global_moran(g, w):
    rows = []
    for m, label in METRICS.items():
        np.random.seed(SEED)
        mi = Moran(g[m].values.astype(float), w, permutations=PERM)
        sig = "유의" if mi.p_sim <= 0.05 else ("경향" if mi.p_sim <= 0.1 else "무작위")
        rows.append({"지표": label, "MoranI": round(mi.I, 3), "p": round(mi.p_sim, 3),
                     "판정": ("끼리끼리" if mi.I > 0 else "흩어짐") + "·" + sig})
    return pd.DataFrame(rows).sort_values("MoranI", ascending=False).reset_index(drop=True)


def lisa(g, w, m):
    np.random.seed(SEED)
    loc = Moran_Local(g[m].values.astype(float), w, permutations=PERM, seed=SEED)
    cat = np.where(loc.p_sim <= 0.05, loc.q, 0)
    return loc, cat


def fig_lisa(gall, prov, g, cat, m, fname):
    """전체 시군구 경계 위에 분석대상만 색칠. 라벨 대신 시도 경계로 오리엔테이션."""
    fig, ax = plt.subplots(figsize=(7.2, 8.4))
    fig.patch.set_facecolor("#f6f1e7"); ax.set_facecolor("#f6f1e7")
    gall.plot(ax=ax, color="#efe8d8", edgecolor="#d8cdb8", linewidth=0.25)
    g.assign(_c=cat).plot(ax=ax, color=[Q_COLOR[c] for c in cat],
                          edgecolor="#b8ab92", linewidth=0.25)
    prov.boundary.plot(ax=ax, color="#6f6657", linewidth=0.9)      # 시도 경계
    ax.set_title(f"시군구 LISA: {METRICS[m]}  (n={len(g)})", fontsize=13); ax.axis("off")
    handles = [plt.Rectangle((0, 0), 1, 1, fc=Q_COLOR[k], ec="#9a8f78") for k in [1, 3, 4, 2, 0]]
    ax.legend(handles, [Q_LABEL[k] for k in [1, 3, 4, 2, 0]], loc="lower left", fontsize=9, frameon=False)
    fig.tight_layout(); fig.savefig(fname, dpi=200, facecolor="#f6f1e7"); plt.close(fig)


def fig_scatter(g, w, m, I, fname):
    y = g[m].values.astype(float); z = (y - y.mean()) / y.std()
    wz = lag_spatial(w, z)
    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor("#f6f1e7"); ax.set_facecolor("#fffdf8")
    ax.axhline(0, color="#b0a890", lw=.8); ax.axvline(0, color="#b0a890", lw=.8)
    ax.scatter(z, wz, s=26, color="#b6452c", edgecolor="#211d17", linewidth=.4, alpha=.8, zorder=3)
    xs = np.array([z.min() - .2, z.max() + .2])
    ax.plot(xs, I * xs, color="#211d17", lw=1.8, label=f"기울기 = Moran's I = {I:.2f}")
    ax.set_xlabel("우리 시군구 값 (z)"); ax.set_ylabel("이웃 평균 (Wz)")
    ax.set_title(f"시군구 Moran 산점도: {METRICS[m]} (n={len(g)})", fontsize=12)
    ax.legend(loc="upper left", fontsize=10, frameon=False)
    fig.tight_layout(); fig.savefig(fname, dpi=200, facecolor="#f6f1e7"); plt.close(fig)


def main():
    _font(); os.makedirs(FIG_DIR, exist_ok=True)
    gall, gkeys, prov = load_municipalities()
    agg, n_match, n_sch = aggregate(gkeys)
    print(f"학교 {n_sch}개 매칭 -> 시군구 {len(agg)}개 (>= {MIN_SCH}교)")

    g = gall.merge(agg, on=["sido", "jname"], how="inner")
    print(f"분석 단위(geometry+지표): {len(g)}개 시군구")
    w = build_weights(g)

    print("\n=== 시군구 Global Moran's I ===")
    tbl = global_moran(g, w)
    print(tbl.to_string(index=False))

    # 큐레이션한 4개 축 지도화 (서로 다른 식문화 지리)
    LISA_AXES = ["rice", "seafood_share", "con_spicy_mild", "con_west_korean"]
    for m in LISA_AXES:
        I = float(tbl[tbl["지표"] == METRICS[m]]["MoranI"].iloc[0])
        loc, cat = lisa(g, w, m)
        hh = [(g.iloc[i]["sido"], g.iloc[i]["jname"]) for i in range(len(g)) if cat[i] == 1]
        ll = [(g.iloc[i]["sido"], g.iloc[i]["jname"]) for i in range(len(g)) if cat[i] == 3]
        print(f"\n[{METRICS[m]}] I={I:.3f} | HH {len(hh)}곳, LL {len(ll)}곳")
        print("  HH:", ", ".join(f"{s}{n}" for s, n in hh[:14]))
        print("  LL:", ", ".join(f"{s}{n}" for s, n in ll[:14]))
        fig_lisa(gall, prov, g, cat, m, f"{FIG_DIR}/sigungu_lisa_{m}.png")
    # 산점도는 최강 축(밥 점유율) 하나로 방법 예시
    Ir = float(tbl[tbl["지표"] == METRICS["rice"]]["MoranI"].iloc[0])
    fig_scatter(g, w, "rice", Ir, f"{FIG_DIR}/sigungu_scatter_rice.png")
    print(f"\n그림: figures/sigungu_lisa_{{{','.join(LISA_AXES)}}}.png + sigungu_scatter_rice.png")


if __name__ == "__main__":
    main()
