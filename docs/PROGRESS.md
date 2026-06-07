# 진행 로그 인덱스

"현재 어디까지 왔는가"의 단일 출처. git 히스토리(*무엇이* 바뀜)·CLAUDE.md(*규칙*)와는 별개.
주제별 상세는 아래 파일, 새 항목은 각 주제 파일 **맨 위**(최신 먼저).

**▶ 이어가기 한 번에: [`RESUME.md`](RESUME.md)** — 이 문서 하나로 전체 상태 + 다음 작업을 resume(복사용).

## 산출물 (발표용 정리본)
- [README.md](../README.md) — 주요 발견 **Top 7**(각 대표 그림). 공간구조·절기캘린더·트렌드·동질화·날씨·트렌드 민감도·유행 반영.
- [METHODS.md](../METHODS.md) — 프로세스 4종(공간자기상관·동질화 robust·날씨통제·트렌드 민감도), 과정 그림.
- [TRENDS.md](../TRENDS.md) — **트렌드 종합 보고서**(질문·방법·발견3·역학·검증). 데이터 재현·부트스트랩(`verify_trends.py`)·외부출처 적대감사 통과.
- [DYNAMICS.md](../DYNAMICS.md) — **왜 그런가(역학)**. 패턴①②③의 원인을 급식 제도·정책·세대로 추적(외부 다중출처·근거강도 표기).
- [poster_outline.html](../poster_outline.html) — **트렌드 발표 영어 A1 포스터**(3단, FastText·LISA·Moran's I 공식). 그림 `poster_figs_en.py`→`assets/en/`, 변환 `md_to_pdf.py`.
- [PRESENTATION_RANKING.md](PRESENTATION_RANKING.md) — 발견 발표 적합성 순위.

## 주제 로그
- [pipeline](progress/pipeline.md) — 수집·속성·임베딩 (dotenv·병렬화·전체수집·64G캡)
- [spatial-analysis](progress/spatial-analysis.md) — 공간 자기상관 (Moran's I·LISA), 시도·시군구
- [poster](progress/poster.md) — A1 발표 포스터 (영어 트렌드 + 한글 공간)
- [temporal-analysis](progress/temporal-analysis.md) — 계절·트렌드·트렌드민감도·유행반영
- [hypothesis-tests](progress/hypothesis-tests.md) — 동질화·날씨·확산·회피규칙 (검증 완료)
- [why-dynamics](progress/why-dynamics.md) — '왜 그런가' 외부 리서치(제도·정책·세대), DYNAMICS.md

## Open (현재 미결 / 다음 할 일)
- [ ] **포스터 팀명/멤버 placeholder를 실제 이름으로** (poster_outline.html 헤더).
- [ ] (선택) DYNAMICS ③(전통 후퇴·마라=영남) 적대검증 — ①②④는 트렌드 종합검증서 감사 완료.
- [x] **트렌드 발표 영어 A1 포스터 완성** → [poster_outline.html](../poster_outline.html) (3단·1페이지, 그림 `poster_figs_en.py`→assets/en/ 5장, Moran's I 공식·핫스팟 이유 포함). 공대생 청중 평이체.
- [x] **트렌드 종합검증 + TRENDS.md 통합 완료** → 데이터 재현·부트스트랩(`verify_trends.py`)·외부 적대감사.
  교정: 89%→90%, '대구 1위 53%'→광주 33%(stale), 정체 '48→50'→유행28→30·건강11.8→10.3. → [TRENDS.md](../TRENDS.md).
- [x] **"Why / main dynamics" 리서치 완료** → [DYNAMICS.md](../DYNAMICS.md). 3패턴을 제도 필터①·재정
  인센티브②·세대입맛+잔반③으로 설명(외부 다중출처·근거강도 표기). 통합축="제도가 미리 짠 캘린더".
- [x] 트렌드/유행/동질화/공간/시간 분석 + **5라운드 적대검증 수렴**(구멍 0) — 상세는 위 산출물·주제 파일.

## 작성 규칙
- 항목은 *무엇*과 *왜*(SHA 불요). 최신이 위로. 코드 변경과 같은 커밋에 로그 함께. 인덱스는 50줄 이내.
