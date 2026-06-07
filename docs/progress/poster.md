# poster — A1 발표 포스터

두 종류: (구) `build_poster.py`→`poster.html`(시도 공간분석 한글), (신) `poster_outline.html`(트렌드 발표 **영어** A1).

## 2026-06-07 트렌드 발표 영어 A1 포스터 (poster_outline.html + poster_figs_en.py)

새 트렌드 발표용 A1 포스터를 별도 제작(외국인 학생 포함이라 전부 영어). TRENDS.md 내용을 포스터로 가지치기.
- 레이아웃(594×841mm, 3단, 1페이지): 제목+thesis → 데이터 한 줄 + **FastText 방법 강조박스**(root→변형 다이어그램, 7/8 root 칩) → 발견 3열(FORM=슬로프+마라비중 / INSTITUTION=경쟁선+유행식·건강식 한반도 choropleth / SPACE=마라 LISA + **Moran's I 공식·해설 박스** + 핫스팟 이유) → 역학 3열 → 결론 → 한계/방법.
- 프레임: "상식 3개 뒤집기" = 인기·학생수요·도시 통념을 **form·institution·space**(맛·인기·도시가 아니라 형태·제도·예산)로 뒤집음. form/institution/space는 단일 쿨톤(steel-blue #345b7a).
- figure: `poster_figs_en.py` → `assets/en/` 5장(영어 라벨·흰 배경·차분한 팔레트 terracotta/teal/slate, 신호등 색 폐기). 마라 LISA(Moran's I=0.25, p<0.001)가 GIS hero. 경쟁선은 범례 대신 선 끝 직접 라벨(곡선 가림 방지).
- 사용자 피드백 반영: 공대생 평이체로 humanize(대시·따옴표·이탤릭 절제), 데이터 타일 슬림·방법론 강조, 빅넘버 축소, 마라 막대 색 구분, 범례 가독성, Moran's I 공식+핫스팟 이유 추가, 상단 라인·[GIS core] 제거, 팀명 placeholder.
- 변환: `md_to_pdf.py`(마크다운 문서→PDF), 포스터는 weasyprint→PDF→pdftoppm→PNG. 산출 `pdf/`·`assets/en/`은 재생성 가능. 미결: 팀명/멤버 placeholder를 실제 이름으로.

## 2026-06-05 포스터 v1 (시도 데이터 · 한글)

## 2026-06-05 포스터 v1 (시도 데이터)
구조: 연구질문 → 데이터 → 4단계 방법(W·Moran's I·LISA 수식 + "쉬운 말" 풀이) → 전역 결과(Moran 산점도+표) →
국지 LISA 2지도(매운맛·양식) → 대조 패널(군집 vs 무작위) → 핵심 발견 → 결론·한계.
사용자 의도 명확화: 수식을 *없애라*가 아니라 교수 앞 설명용으로 **표현을 알아먹기 쉽게**(수식 유지 + 쉬운 풀이).
헤드라인은 매운맛 LISA(경북 HH·수도권 LL) + 양식 LISA. 수치는 전체 데이터(2,355교·220만 끼) 하드코딩.
포스터용으로 그림 200dpi·라벨 흰 테두리, 헤드라인 축을 해석 쉬운 것으로 선정.

미결: `poster.html` 수치는 시도(17) 결과 하드코딩 → 시군구로 갱신할지 미정. (현재 방향은 시간 분석으로 전환)
