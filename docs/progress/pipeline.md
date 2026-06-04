# pipeline — 수집·속성·임베딩

NEIS 전국 고교 중식 → 속성벡터(43) + FastText 임베딩(128) → 군집·지표. 환경은 uv(`.venv`).

## 2026-06-05 전체 수집 + 64G 메모리 캡
`NEIS_SCHOOLS_PER_OFFICE=0` 으로 전국 고교 전수 수집: 2,407교 · 약 220만 끼(샘플 502교의 4.8배).
파이프라인은 사용자 요청으로 `systemd-run --user --scope -p MemoryMax=64G -p MemorySwapMax=0` 아래 실행(전체 프로세스 트리 RSS를 64GiB로 캡, 초과 시 종료). 실사용은 10G 안팎이라 안전 여유.
임베딩 학습이 긴 구간(~18분)이라 백그라운드로 돌림. 산출: 어휘 23.8만, 학교 임베딩 2,395개, 분석 학교 2,355개(≥100끼).

## 2026-06-05 build_vectors 병렬화
끼→속성벡터 변환이 `iterrows` 단일코어 루프라 47만 끼에서 1m37s 병목. CPU 바운드 순수 파이썬이라
`ProcessPoolExecutor`(16워커)로 분산 → 9.5s(약 10배). `executor.map`이 입력 순서를 보존하고 변환 함수가
순수 함수라 **출력은 워커 수와 무관하게 비트동일**(직렬 baseline과 `pandas.equals()=True`, maxabsdiff=0 검증).
`VEC_WORKERS` 환경변수로 조절.

## 2026-06-05 NEIS 키 dotenv 로딩
`.env` 에는 `NEIS_API_KEY` 로 적혀 있으나 코드가 `NEIS_KEY` 를 읽고 dotenv 로딩도 없어 키가 무시됐다.
`python-dotenv` 로 repo 루트 `.env` 를 자동 로딩하고 변수명을 `NEIS_API_KEY` 로 통일.
