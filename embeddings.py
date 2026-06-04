"""
embeddings.py
-------------
명시 속성(43차원)에 더해, 데이터에서 학습한 의미 임베딩 블록을 만든다.

방식
- 한 끼 = 메뉴 토큰들의 '문장'. FastText skip-gram으로 학습.
  -> 같은 끼에 자주 함께 나오는 메뉴(맥락) + 한국어 부분단어(char n-gram, OOV 대응)
     양쪽을 모두 반영한 메뉴 벡터를 얻는다.
- 메뉴 벡터 평균 -> 끼 벡터, 끼 벡터 평균 -> 학교 학습형 벡터.

명시 속성 축이 '무엇이 나오는가'(해석축)라면, 이 블록은 규칙으로 못 잡는
'어떤 메뉴들이 함께/비슷하게 나오는가'(잠재 구조)를 채운다.
"""
import re
import numpy as np
import pandas as pd
from gensim.models import FastText
from menu_attributes import parse_menu_string

EMB_DIM = 64
MIN_COUNT = 3          # 실데이터 5 권장, 합성/소량은 1~3
WINDOW = 8             # 한 끼 메뉴 수가 보통 5~8개라 끼 전체를 맥락으로
EPOCHS = 20
_SPACE = re.compile(r"\s+")


def _tokenize_meal(ddish_nm: str) -> list[str]:
    # 부분단어 학습을 위해 메뉴명 내부 공백 제거 -> 단일 토큰
    return [_SPACE.sub("", d) for d in parse_menu_string(ddish_nm)]


def train_fasttext(meals_df: pd.DataFrame) -> FastText:
    sentences = [t for t in (_tokenize_meal(s) for s in meals_df["ddish_nm"]) if t]
    model = FastText(vector_size=EMB_DIM, window=WINDOW, min_count=MIN_COUNT,
                     sg=1, min_n=2, max_n=4, epochs=EPOCHS, workers=4, seed=0)
    model.build_vocab(corpus_iterable=sentences)
    model.train(corpus_iterable=sentences,
                total_examples=len(sentences), epochs=EPOCHS)
    return model


def school_embeddings(meals_df: pd.DataFrame, model: FastText) -> pd.DataFrame:
    """학교별 학습형 임베딩 (끼 평균의 학교 평균)."""
    rows = []
    for school_code, grp in meals_df.groupby("school_code"):
        meal_vecs = []
        for s in grp["ddish_nm"]:
            toks = _tokenize_meal(s)
            vs = [model.wv[t] for t in toks if t]      # FastText는 OOV도 부분단어로 처리
            if vs:
                meal_vecs.append(np.mean(vs, axis=0))
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
    emb = school_embeddings(meals_df, model)
    emb.to_parquet("school_embeddings.parquet", index=False)
    print(f"학교 임베딩 {len(emb)}개 저장 -> school_embeddings.parquet")
    # 유사 메뉴 점검
    for probe in ["제육볶음", "고등어구이", "크림파스타"]:
        if probe in model.wv:
            sims = ", ".join(w for w, _ in model.wv.most_similar(probe, topn=4))
            print(f"  {probe} ~ {sims}")


if __name__ == "__main__":
    main()
