# 진행 로그 인덱스

"현재 어디까지 왔는가"의 단일 출처. git 히스토리(*무엇이* 바뀜)·CLAUDE.md(*규칙*)와는 별개.
주제별 상세는 아래 파일, 새 항목은 각 주제 파일 **맨 위**(최신 먼저).

**▶ 이어가기 한 번에: [`RESUME.md`](RESUME.md)** — 이 문서 하나로 전체 상태 + 다음 작업을 resume(복사용).

## 산출물 (발표용 정리본)
- [README.md](../README.md) — 주요 발견 **Top 7**(각 대표 그림). 공간구조·절기캘린더·트렌드·동질화·날씨·트렌드 민감도·유행 반영.
- [METHODS.md](../METHODS.md) — 프로세스 4종(공간자기상관·동질화 robust·날씨통제·트렌드 민감도), 과정 그림.
- [TREND_REFLECTION.md](../TREND_REFLECTION.md) — '유행이 급식에 반영되는가' 상세 보고서(그림 6장 + 5라운드 검증).
- [DYNAMICS.md](../DYNAMICS.md) — **왜 그런가(역학)**. 패턴①②③의 원인을 급식 제도·정책·세대로 추적(외부 다중출처·근거강도 표기).
- [PRESENTATION_RANKING.md](PRESENTATION_RANKING.md) — 발견 발표 적합성 순위.

## 주제 로그
- [pipeline](progress/pipeline.md) — 수집·속성·임베딩 (dotenv·병렬화·전체수집·64G캡)
- [spatial-analysis](progress/spatial-analysis.md) — 공간 자기상관 (Moran's I·LISA), 시도·시군구
- [poster](progress/poster.md) — A1 HTML 포스터
- [temporal-analysis](progress/temporal-analysis.md) — 계절·트렌드·트렌드민감도·유행반영
- [hypothesis-tests](progress/hypothesis-tests.md) — 동질화·날씨·확산·회피규칙 (검증 완료)
- [why-dynamics](progress/why-dynamics.md) — '왜 그런가' 외부 리서치(제도·정책·세대), DYNAMICS.md

## Open (현재 미결 / 다음 할 일)
- [ ] 최종 발표 방향·포스터 확정(공간 vs 시간 vs 결합). `poster.html` 은 시도(17) 데이터 하드코딩 상태.
- [ ] (선택) DYNAMICS.md 적대검증 루프 — '왜' 주장들의 상관↔인과 과장·반례 누락 재점검(원하면).
- [x] **"Why / main dynamics" 리서치 완료** → [DYNAMICS.md](../DYNAMICS.md). 3패턴을 제도 필터①·재정
  인센티브②·세대입맛+잔반③으로 설명(외부 다중출처·근거강도 표기). 통합축="제도가 미리 짠 캘린더".
- [x] 트렌드/유행/동질화/공간/시간 분석 + **5라운드 적대검증 수렴**(구멍 0) — 상세는 위 산출물·주제 파일.

## 작성 규칙
- 항목은 *무엇*과 *왜*(SHA 불요). 최신이 위로. 코드 변경과 같은 커밋에 로그 함께. 인덱스는 50줄 이내.
