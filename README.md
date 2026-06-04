# NEIS 고등학교 중식 식단 군집 · 지도 시각화 파이프라인

전국 고등학교 **중식**(2021~현재)을 **107차원**(속성 43 + 임베딩 64) 벡터로 표현해
학교별 군집을 만들고, 시도별 지표를 한국 지도(코로플레스)로 시각화한다.

## 파일

| 파일 | 역할 |
|------|------|
| `collect_neis.py` | NEIS API 수집 → `schools.parquet`, `meals_lunch.parquet` |
| `menu_attributes.py` | 파싱 + 43차원 속성 태깅 (**핵심 — 계속 보강**) |
| `embeddings.py` | FastText 학습 → 학교 64차원 임베딩 + `fasttext.model` 저장 |
| `build_vectors.py` | 끼→학교 속성벡터 (표본필터 + 수축 + CLR) |
| `cluster_schools.py` | 블록 결합 → PCA → KMeans(실루엣 k) → 군집·지역 분석 |
| `region_metrics.py` | 시도별 지표(점유율·사용도·키워드 유사도·군집구성) → `region_metrics.json` |
| `build_map.py` | geojson + 지표 → **`map.html`** (자립형 인터랙티브 지도) |
| `skorea_provinces.json` | 17개 시도 경계 GeoJSON |
| `_test_synthetic.py` | NEIS 없이 검증용 합성 데이터 |

## 실행 순서

```bash
export NEIS_KEY="발급키"          # https://open.neis.go.kr (수집 단계만 외부망 필요)
python collect_neis.py            # 1) 수집
python build_vectors.py           # 2) 속성 블록(43)
python embeddings.py              # 3) 임베딩 블록(64) + 모델 저장
python cluster_schools.py         # 4) 결합·군집·지역분석
python region_metrics.py          # 5) 시도별 지표
python build_map.py               # 6) map.html
```

NEIS 없이 동작 확인:
```bash
python _test_synthetic.py && python build_vectors.py && python embeddings.py \
 && python cluster_schools.py && python region_metrics.py && python build_map.py
```

## 지도에서 보는 지표

- **점유율(속성)**: 밥 / 빵 / 면 — 한 끼 메뉴 중 형태 비율의 시도 평균.
- **사용도(속성)**: 해산물(어패 단백질 비율), 단백질(전체 단백질 속성 합).
- **유사도(임베딩, z)**: 학교 임베딩과 키워드('해산물','단백질','밥','빵','면') 벡터의
  코사인 유사도를 지역 비교용으로 z-표준화. 규칙 태깅이 못 잡는 잠재 경향을 포착.
- **우세 군집**: 시도별 최빈 KMeans 군집. 호버 시 군집 구성 막대 표시.

`map.html`은 geojson·지표를 인라인 임베드한 단일 파일이라 브라우저로 바로 열린다
(d3·폰트만 CDN에서 로드). 실데이터로 다시 돌리면 `region_metrics.json`이 갱신되고
`build_map.py`만 재실행하면 지도가 업데이트된다.

## 차원·표현 확장 레버

- `embeddings.py`: `EMB_DIM`(64→128/256), `WINDOW`, `EPOCHS`.
- `menu_attributes.py`: 키워드/축 추가.
- `cluster_schools.py`: `EMB_WEIGHT`(블록 균형), `K_RANGE`.
- `region_metrics.py`: `KEYWORDS`에 유사도 항목 추가(예: '튀김','매운맛','양식').
- 더: 영양 API 축, 끼 다양성 엔트로피, 연도별 임베딩(시계열), 시군구 단위 지도.

## 설계 결정

- 중식 한정 + 고등학교 고정 → 끼니·학교급 교란 제거.
- 속성 블록(조성)엔 CLR, 임베딩 블록엔 표준화. 결합 시 블록별 스케일.
- 수축으로 끼 적은 학교 노이즈 억제. k는 실루엣 자동 선택.

---

## 설치

```bash
pip install -r requirements.txt
```

## 데이터 / 생성물 안내

`*.parquet`, `fasttext.model`, `region_metrics.json`, `map.html` 은 파이프라인
실행으로 재생성되는 산출물이라 `.gitignore` 처리되어 있다. 입력 경계 파일
`skorea_provinces.json` 만 레포에 포함된다.

GeoJSON 출처: southkorea/southkorea-maps (시도 간소화 경계).
