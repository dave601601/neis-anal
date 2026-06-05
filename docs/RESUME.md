# RESUME — 한국 급식 GIS 프로젝트 이어가기

> 이 문서 하나만 읽으면 작업을 이어갈 수 있다. 더 깊이는 아래 "읽기 순서" 참조.
> (작성: 2026-06-05, 세션 핸드오프용. 복사해서 새 세션 컨텍스트로 붙여넣어도 됨.)

---

## 0. 이 프로젝트가 뭔가
대한민국 **고교 급식(중식)** 을 주제로 한 **GIS 포스터 발표** 프로젝트. 과목/전시 테마 = **"Geography of Spirit"**.
팀메이트 minseok shin이 NEIS 수집→메뉴 토큰화→FastText 임베딩→KMeans→지도 파이프라인을 만들었고,
사용자(Dongha Gwak)가 research 방향을 잡는다. 핵심 가치: **수학·수치·참신성·예쁜 시각화·단계적 설명·정직성**.
청중은 (교수 가정) 고등학생 → 수식은 유지하되 쉬운 풀이를 곁들인다.

## 1. 읽기 순서 (resume 시)
1. **이 문서(RESUME.md)** — 전체 상태 + 다음 작업
2. [`../README.md`](../README.md) — 주요 발견 **Top 7**(각 대표 그림)
3. [`../METHODS.md`](../METHODS.md) — 프로세스 4종 상세(수식 + 쉬운 말)
4. [`../TREND_REFLECTION.md`](../TREND_REFLECTION.md) — '유행 반영' 상세 보고서(그림 6 + 5라운드 검증)
5. [`PROGRESS.md`](PROGRESS.md) + [`progress/*.md`](progress/) — 주제별 시간순 로그
6. [`PRESENTATION_RANKING.md`](PRESENTATION_RANKING.md) — 발견 발표 적합성 순위

## 2. 환경 · 규칙 (반드시 지킬 것)
- 위치: `/home/rlrl/gis_final/neis-school-lunch-map/` (git repo). 상위 `/home/rlrl/gis_final/` 는 git 아님.
- Python: **uv** (`.venv/bin/python ...`). 의존성 `requirements.txt`.
- 무거운 작업(벡터화·부트스트랩)은 **64G 메모리 캡** 아래:
  `systemd-run --user --scope -p MemoryMax=64G -p MemorySwapMax=0 --quiet .venv/bin/python <script>`
- **NEIS는 2021년부터만** 제공(과거 확장 불가, 확인됨). 전북은 중식이 2024부터라 시계열 분석서 제외.
- 기온 등 외부데이터는 **Open-Meteo 아카이브**(무료·키 불필요).
- CLAUDE.md 규칙: **"고" 신호 전엔 구현 보류**(계획만); 산출물 한국어; Conventional Commits 자동커밋(AI 트레일러 금지);
  진행로그를 코드와 같은 커밋에. **figures/ 는 .gitignore** → 그림을 문서에 박을 땐 `assets/` 로 복사해 참조.

## 3. 데이터
- `meals_lunch.parquet` (약 220만 끼, 2021–2026): `school_code·date(YYYYMMDD)·ddish_nm`
- `schools.parquet`: `school_code·sido·school_name·addr·office` (2,407교 수집, 분석은 ≥100끼 2,355교)
- `fasttext.model` (gensim FastText, 메뉴 토큰 임베딩), `skorea_provinces.json`(17 시도)·`skorea_municipalities.json`(251 시군구)
- 생성물(parquet·model·json·html)은 .gitignore — 파이프라인 재실행으로 재생성.

## 4. 지금까지의 발견 (전부 5라운드 적대검증 통과)
| # | 발견 | 스크립트 |
|---|---|---|
| 공간 | 시군구 237 LISA, 9축 p=0.001, 밥 I=0.54, **수도권↔지방**(매운=영남·양식=수도권). | `spatial_sigungu.py`·`spatial_autocorr.py` |
| 동질화 | robust 신호 = **전통 손맛(발효−72%·찌개−64%·김치·나물) 수렴**, 단 정체는 '지역 수렴'이 아닌 **전국 후퇴**(시간추세). | `hypothesis_homog_robust.py`·`hypothesis_who_converges.py` |
| 시간 | 절기 캘린더(설 떡국·동지 팥죽·삼복 삼계탕·제철 과일), 트렌드(마라 ×6.9). | `temporal_analysis.py` |
| 날씨 | 계절 제거 시 무반응(귀무; raw 기온×냉면 0.585 → 탈계절 ≈0). 식단은 미리 짠 캘린더. | `hypothesis_weather.py` |
| 트렌드 민감 | **광주·경북 민감·서울 둔감**, "도시=리더" 기각(수도권 둔감 부트스트랩 89% 견고). 1위 순위는 마라 의존. | `trend_sensitivity.py` |
| 유행 반영 | 어른은 **'메뉴화 가능한' 유행(마라, 바스켓 79%)만** 반영, 탕후루·두바이 간식형 미반영; 유행:건강 2.9배(둘 다 2023 정체). | `trend_reflection.py` |

방법론 메타: **표본의 함정**(샘플 502교→전체 2,355교서 해안성 0.42→0.04 붕괴) · **robust화**(부트스트랩·MK·Bonferroni로
false signal 제거) · **임베딩 키워드 centroid 표류 → 5라운드 적대검증**(유행:건강 10배→2.9배, 트렌드리더 대구→광주로 정직화).
이 "보이는 게 다가 아니다" 자기검증 서사 자체가 발표의 강점.

## 5. 핵심 스크립트 맵
- 파이프라인: `collect_neis.py`(.env NEIS_API_KEY)→`build_vectors.py`(VEC_WORKERS 병렬)→`embeddings.py`→`cluster_schools.py`→`region_metrics.py`→`build_map.py`(map.html)
- 공간: `spatial_autocorr.py`(시도), `spatial_sigungu.py`(시군구)
- 시간/트렌드: `temporal_analysis.py`, `trend_sensitivity.py`, `trend_reflection.py`
- 가설: `hypothesis_homogenization*.py`, `hypothesis_homog_robust.py`, `hypothesis_who_converges.py`, `hypothesis_weather.py`, `hypothesis_diffusion.py`, `hypothesis_rotation.py`
- 포스터: `build_poster.py`(A1 poster.html — 단, 시도 데이터 하드코딩 상태)

## 6. "Why / main dynamics" 리서치 — 완료 (2026-06-05)
발견의 **왜(역학)** 를 외부 다중출처(정부 법령·교육청·학술·언론)로 설명 → **[`../DYNAMICS.md`](../DYNAMICS.md)**.
3패턴 병렬 리서치 에이전트 + 근거강도(강/중/약/추측) + 출처. 통합축 = **"급식은 학생 문화의 거울이 아니라 제도가 미리 짠 캘린더"**.
- **① 제도 필터(강)**: 급식법 별표3 단순당류 제한·영양기준 + 월단위 조달(매월 27일 계약) + 어린이 식생활안전관리 특별법(캔디·초콜릿류) → 간식형 배제. 날씨 무반응과 같은 뿌리.
- **② 재정 인센티브(강)**: 친환경·로컬푸드 추가지원 경북1084·전남803 vs 서울0원 → 지방 민감. 미해소 반례=경남 둔감.
- **③ 세대입맛+잔반(A강·B추측)**: 청소년 채소−50%·김치 반토막 → 잔반 1위(채소57%·찌개23%) → 기호도 편성. 마라=영남은 실증 비교 부재.

## 7. ▶ 다음 작업 (NEXT) — 발표 방향·포스터 확정
- 최종 발표 방향 결정: **공간 vs 시간 vs 결합** (또는 what→why 서사 = DYNAMICS 축으로 통합).
- `poster.html` 은 시도(17) 데이터 하드코딩 → 시군구/시간/why 데이터로 갱신할지 미정.
- (선택) **DYNAMICS.md 적대검증 루프** — '왜' 주장의 상관↔인과 과장·반례 누락 재점검(원하면).

---
*git 클린 상태에서 작성. 모든 수치는 코드 재실행으로 재현 가능.*
