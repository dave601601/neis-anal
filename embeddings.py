"""
embeddings.py
-------------
명시 속성(43차원)에 더해, 데이터에서 학습한 의미 임베딩 블록을 만든다.

방식
- 한 끼 = 메뉴 토큰들의 '문장'. FastText skip-gram으로 학습.
  -> 같은 끼에 자주 함께 나오는 메뉴(맥락) + 한국어 부분단어(char n-gram, OOV 대응)
     양쪽을 모두 반영한 메뉴 벡터를 얻는다.
- 메뉴 벡터를 IDF 가중 평균 -> 끼 벡터, 끼 벡터 평균 -> 학교 학습형 벡터.

명시 속성 축이 '무엇이 나오는가'(해석축)라면, 이 블록은 규칙으로 못 잡는
'어떤 메뉴들이 함께/비슷하게 나오는가'(잠재 구조)를 채운다.

성능 개선 포인트
- IDF 가중 집계: 쌀밥·배추김치처럼 거의 모든 끼에 나오는 보편 메뉴는 변별력이
  없으므로 가중을 낮추고, 고등어구이·크림파스타처럼 드물고 특징적인 메뉴에
  가중을 높인다. 학교/지역 간 구별력이 살아난다(군집 쏠림 완화).
- 빈출어 서브샘플링(sample)·negative·차원 확대(128)·epochs 증대로 표현력 강화.
"""
import re
import math
from collections import Counter

import numpy as np
import pandas as pd
from gensim.models import FastText
from menu_attributes import parse_menu_string

EMB_DIM = 128
MIN_COUNT = 5          # 실데이터 5 권장(희소 노이즈 억제). 합성/소량은 1~3
WINDOW = 8             # 한 끼 메뉴 수가 보통 5~8개라 끼 전체를 맥락으로
EPOCHS = 30
SAMPLE = 1e-4          # 빈출 메뉴 다운샘플링(보편어가 학습을 지배하지 않게)
NEGATIVE = 10
_SPACE = re.compile(r"\s+")


def _tokenize_meal(ddish_nm: str) -> list[str]:
    # 부분단어 학습을 위해 메뉴명 내부 공백 제거 -> 단일 토큰
    return [_SPACE.sub("", d) for d in parse_menu_string(ddish_nm)]


def train_fasttext(meals_df: pd.DataFrame) -> FastText:
    sentences = [t for t in (_tokenize_meal(s) for s in meals_df["ddish_nm"]) if t]
    model = FastText(vector_size=EMB_DIM, window=WINDOW, min_count=MIN_COUNT,
                     sg=1, min_n=2, max_n=4, epochs=EPOCHS, workers=4, seed=0,
                     sample=SAMPLE, negative=NEGATIVE)
    model.build_vocab(corpus_iterable=sentences)
    model.train(corpus_iterable=sentences,
                total_examples=len(sentences), epochs=EPOCHS)
    return model


def compute_idf(meals_df: pd.DataFrame) -> dict:
    """끼(=문서) 단위 IDF. 거의 모든 끼에 나오는 메뉴일수록 가중치가 낮다."""
    doc_freq = Counter()
    n_docs = 0
    for s in meals_df["ddish_nm"]:
        toks = {t for t in _tokenize_meal(s) if t}
        if not toks:
            continue
        n_docs += 1
        doc_freq.update(toks)
    # smoothed idf (>=1): 흔한 토큰은 1 근처, 드문 토큰은 크게
    return {t: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0
            for t, df in doc_freq.items()}


def school_embeddings(meals_df: pd.DataFrame, model: FastText,
                      idf: dict) -> pd.DataFrame:
    """학교별 학습형 임베딩 (IDF 가중 끼 평균의 학교 평균)."""
    rows = []
    for school_code, grp in meals_df.groupby("school_code"):
        meal_vecs = []
        for s in grp["ddish_nm"]:
            toks = [t for t in _tokenize_meal(s) if t]
            if not toks:
                continue
            num = np.zeros(EMB_DIM, dtype=np.float64)
            wsum = 0.0
            for t in toks:
                w = idf.get(t, 1.0)                  # OOV는 기본 가중 1
                num += w * model.wv[t]               # FastText는 OOV도 부분단어 처리
                wsum += w
            if wsum > 0:
                meal_vecs.append(num / wsum)
        if meal_vecs:
            v = np.mean(meal_vecs, axis=0)
            rows.append({"school_code": school_code,
                         **{f"emb_{i}": float(v[i]) for i in range(EMB_DIM)}})
    return pd.DataFrame(rows)


EMB_COLUMNS = [f"emb_{i}" for i in range(EMB_DIM)]


def main():
    meals_df = pd.read_parquet("meals_lunch.parquet")
    model = train_fasttext(meals_df)
    print(f"FastText 학습 완료: 어휘 {len(model.wv)}개, {EMB_DIM}차원")
    model.save("fasttext.model")               # 키워드 유사도용으로 보관
    idf = compute_idf(meals_df)
    print(f"IDF 계산: 토큰 {len(idf)}개 (끼=문서 기준)")
    emb = school_embeddings(meals_df, model, idf)
    emb.to_parquet("school_embeddings.parquet", index=False)
    print(f"학교 임베딩 {len(emb)}개 저장 -> school_embeddings.parquet")
    # 유사 메뉴 점검
    for probe in ["제육볶음", "고등어구이", "크림파스타"]:
        if probe in model.wv:
            sims = ", ".join(w for w, _ in model.wv.most_similar(probe, topn=4))
            print(f"  {probe} ~ {sims}")


if __name__ == "__main__":
    main()
