"""
build_poster.py
---------------
공간 자기상관 분석 결과를 A1(594x841mm) 인쇄용 HTML 포스터로 조립한다.

- figures/*.png 를 base64로 내장 -> 단일 파일(poster.html)로 어디서나 열림.
- 테마는 map.html과 통일(paper 팔레트, Gowun Batang + IBM Plex Sans KR).
- 본문 기준 16pt. 수식은 유지하되 '쉬운 말' 풀이를 곁들인다(가독성).

수치는 spatial_autocorr.py 출력 기준(시도 표본 502교·47만 끼).
데이터를 다시 돌리면 값이 바뀔 수 있으니 헤드라인 수치는 함께 갱신할 것.
"""
import base64
import json

FIGS = {
    "__IMG_SCATTER__": "figures/moran_scatter_con_spicy_mild.png",
    "__IMG_LISA_SPICY__": "figures/lisa_con_spicy_mild.png",
    "__IMG_LISA_WEST__": "figures/lisa_con_west_korean.png",
    "__IMG_PANEL__": "figures/lisa_panel.png",
}

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<title>급식에도 '동네'가 있다 — GIS 포스터</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Sans+KR:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#f6f1e7; --ink:#211d17; --muted:#6f6657; --line:#d8cdb8;
  --accent:#b6452c; --card:#fffdf8; --hh:#c0392b; --ll:#2c6f9b; --soft:#efe7d6;
}
@page{ size:594mm 841mm; margin:0; }
*{ box-sizing:border-box; }
html,body{ margin:0; background:#cfc8b9; }
.poster{
  width:594mm; min-height:841mm; margin:0 auto; padding:15mm 15mm 11mm;
  background:
    radial-gradient(1400px 700px at 88% -8%, #efe7d6 0%, transparent 55%),
    var(--paper);
  color:var(--ink); font-family:"IBM Plex Sans KR",sans-serif;
  font-size:16pt; line-height:1.5;
}
header{ border-bottom:3px solid var(--ink); padding-bottom:6mm; }
.kicker{ font-size:13pt; letter-spacing:.3em; color:var(--accent); font-weight:600; }
.title{ font-family:"Gowun Batang",serif; font-weight:700; font-size:62pt; line-height:1.04; margin:2mm 0 2mm; }
.sub{ font-size:21pt; color:#3a342a; font-weight:300; max-width:46em; }
.byline{ margin-top:4mm; font-size:14pt; color:var(--muted); display:flex; justify-content:space-between; }
.byline b{ color:var(--ink); font-weight:600; }

.row{ display:flex; gap:9mm; margin-top:8mm; align-items:stretch; }
.card{ background:var(--card); border:1px solid var(--line); border-radius:11px;
  padding:6mm 7mm 6.5mm; flex:1; }
.card.plain{ background:transparent; border:none; padding:0 1mm; }
h2{ font-family:"Gowun Batang",serif; font-size:23pt; margin:0 0 4mm; }
h2 .num{ color:var(--accent); margin-right:.4em; }
h2.line{ border-bottom:2px solid var(--accent); padding-bottom:2mm; }
p{ margin:0 0 3mm; }
.lead{ font-size:18pt; }
.muted{ color:var(--muted); }
.small{ font-size:13pt; line-height:1.45; }
em.k{ font-style:normal; color:var(--accent); font-weight:600; }
b.k{ color:var(--accent); }

.tobler{ font-family:"Gowun Batang",serif; font-size:20pt; color:var(--ink);
  border-left:4px solid var(--accent); padding:1mm 0 1mm 5mm; margin:4mm 0 0; }

.facts{ list-style:none; margin:0; padding:0; }
.facts li{ display:flex; justify-content:space-between; padding:2.4mm 0; border-bottom:1px dashed var(--line); }
.facts li span{ color:var(--muted); }
.facts li b{ font-variant-numeric:tabular-nums; }
.big{ font-family:"Gowun Batang",serif; font-size:34pt; color:var(--accent); line-height:1; }

.steps{ display:flex; gap:6mm; }
.step{ flex:1; background:var(--soft); border-radius:9px; padding:5mm 5mm; }
.step .n{ font-family:"Gowun Batang",serif; font-size:26pt; color:var(--accent); }
.step h3{ font-size:16.5pt; margin:1mm 0 2mm; }
.step p{ font-size:14pt; line-height:1.42; color:#3a342a; margin:0; }

.formula{ background:#2a251e; color:#f3ecdd; border-radius:10px; padding:5mm 6mm; margin-top:5mm; }
.formula .eq{ font-size:21pt; text-align:center; margin:1mm 0 2mm; font-family:"IBM Plex Sans KR"; }
.frac{ display:inline-flex; flex-direction:column; text-align:center; vertical-align:middle; margin:0 .25em; }
.frac .nu{ border-bottom:1.6px solid #f3ecdd; padding:0 .4em 1px; }
.frac .de{ padding:1px .4em 0; }
.formula .gloss{ font-size:14pt; color:#d8cdb8; line-height:1.45; }
.formula .gloss b{ color:#f0b8a6; }
.formula .sym{ font-size:12.5pt; color:#b3a892; margin-top:2mm; border-top:1px solid #4a443a; padding-top:2mm; }

.fig{ width:100%; display:block; border-radius:8px; }
.cap{ font-size:13pt; color:var(--muted); margin-top:2mm; line-height:1.4; }

.mtable{ width:100%; border-collapse:collapse; font-size:15pt; }
.mtable th,.mtable td{ text-align:left; padding:2.4mm 2mm; border-bottom:1px solid var(--line); }
.mtable th{ color:var(--muted); font-weight:500; font-size:13pt; }
.mtable td.n{ text-align:right; font-variant-numeric:tabular-nums; }
.tag{ font-size:12.5pt; padding:.5mm 2.4mm; border-radius:999px; font-weight:600; }
.tag.yes{ background:#e7f0ea; color:#2e6e4e; }
.tag.maybe{ background:#f3ecd6; color:#9a7b1f; }
.tag.no{ background:#efe2dd; color:#9a4a36; }

.legend{ display:flex; flex-wrap:wrap; gap:3mm 7mm; font-size:13.5pt; margin:3mm 0 1mm; }
.legend span{ display:flex; align-items:center; gap:2mm; }
.sw{ width:5mm; height:5mm; border-radius:3px; border:1px solid var(--line); display:inline-block; }

.headline{ font-family:"Gowun Batang",serif; font-size:30pt; line-height:1.12; margin:0 0 1mm; }
.headline .accent{ color:var(--accent); }

.find{ display:flex; gap:9mm; }
.find .one{ flex:1; }
.find h3{ font-size:18pt; margin:0 0 2mm; }
.badge{ display:inline-block; font-size:12.5pt; font-weight:700; color:#fff; background:var(--accent);
  border-radius:999px; padding:.6mm 3mm; margin-right:2mm; }

.foot{ margin-top:8mm; border-top:2px solid var(--ink); padding-top:4mm;
  font-size:12.5pt; color:var(--muted); line-height:1.5; display:flex; justify-content:space-between; gap:8mm; }
</style>
</head>
<body>
<div class="poster">

  <header>
    <div class="kicker">GEOGRAPHY OF SPIRIT · 공간통계 (MORAN'S I · LISA)</div>
    <div class="title">급식에도 ‘동네’가 있다</div>
    <div class="sub">전국 고등학교 점심 <b>약 220만 끼</b>로 본 식문화의 공간 구조 — 옆 지역끼리 정말 닮을까?</div>
    <div class="byline">
      <span>곽동하 · 신민석 &nbsp;|&nbsp; KAIST</span>
      <span><b>데이터</b> NEIS 학교급식 오픈API · 2021–2026 · 2,355개교 17개 시도</span>
    </div>
  </header>

  <!-- 연구질문 + 데이터 -->
  <div class="row">
    <div class="card" style="flex:2.1">
      <h2 class="line"><span class="num">Q</span>연구 질문</h2>
      <p class="lead">급식은 전국 영양 기준으로 <em class="k">표준화</em>돼 있다. 그렇다면 식단은 어디나 비슷할까?
      우리는 거꾸로 물었다 — 지역색이 남아 있다면, 그것이 <em class="k">공간적으로 구조화</em>돼 있을까?
      즉 <b>가까운 지역끼리 서로 닮아 ‘식문화 권역’을 이룰까?</b></p>
      <div class="tobler">“가까운 것은 먼 것보다 더 닮는다.”<br><span class="muted" style="font-size:14pt">— 토블러의 지리학 제1법칙. 이 한 문장을 급식 데이터로 검증한다.</span></div>
    </div>
    <div class="card">
      <h2 class="line"><span class="num">D</span>데이터</h2>
      <ul class="facts">
        <li><span>출처</span><b>NEIS 오픈API</b></li>
        <li><span>대상</span><b>전국 고교 점심(중식)</b></li>
        <li><span>기간</span><b>2021 – 2026</b></li>
        <li><span>규모</span><b>2,355개교 · 220만 끼</b></li>
        <li><span>공간 단위</span><b>17개 시도</b></li>
      </ul>
    </div>
  </div>

  <!-- 방법 -->
  <div class="row">
    <div class="card">
      <h2 class="line"><span class="num">M</span>어떻게 쟀나 — 4단계</h2>
      <div class="steps">
        <div class="step"><div class="n">1</div><h3>메뉴 → 숫자</h3>
          <p>메뉴 글자를 토큰화해 <b>43개 속성</b>(밥·면·해산물·매운…)으로. 동시에 FastText로 <b>128차원 의미 임베딩</b>. <span class="muted">(파이프라인: 신민석)</span></p></div>
        <div class="step"><div class="n">2</div><h3>지역 점수</h3>
          <p>학교 벡터를 시도별로 평균 → <b>9개 식문화 지표</b>(해산물·면·양식화 등).</p></div>
        <div class="step"><div class="n">3</div><h3>이웃 정의 (W)</h3>
          <p>경계를 맞댄 시도를 <b>이웃(=1)</b>으로. <b>제주는 섬</b>이라 가장 가까운 전남과 연결.</p></div>
        <div class="step"><div class="n">4</div><h3>공간통계</h3>
          <p><b>Moran’s I</b>로 “얼마나 끼리끼리인가”, <b>LISA</b>로 “어디가 뭉치고 튀나”. 999번 섞어 우연 여부 확인.</p></div>
      </div>

      <div class="formula">
        <div class="eq">전역 Moran’s I&nbsp;=&nbsp;
          <span class="frac"><span class="nu">n</span><span class="de">S<sub>0</sub></span></span> ×
          <span class="frac"><span class="nu">Σ<sub>i</sub> Σ<sub>j</sub> w<sub>ij</sub> z<sub>i</sub> z<sub>j</sub></span><span class="de">Σ<sub>i</sub> z<sub>i</sub><sup>2</sup></span></span>
          &nbsp;&nbsp;·&nbsp;&nbsp; 국지 LISA<sub> i</sub> = z<sub>i</sub> · Σ<sub>j</sub> w<sub>ij</sub> z<sub>j</sub>
        </div>
        <div class="gloss">
          <b>쉬운 말 ▸ 전역:</b> 각 지역과 그 이웃이 같은 방향(둘 다 평균보다 높거나, 둘 다 낮음)이면 +점, 엇갈리면 −점. 전국을 평균내 한 숫자로 →
          <b>+1</b> 완전 끼리끼리 · <b>0</b> 무작위 · <b>−1</b> 체스판처럼 교대.<br>
          <b>쉬운 말 ▸ 국지:</b> 지역 하나만 떼어 본 버전. 나(z<sub>i</sub>)와 이웃 평균이 같은 부호면 <b>뭉침</b>(HH·LL), 반대면 <b>튀는 곳</b>(HL·LH).
          <div class="sym">기호 — z = (지역값 − 전국평균) ÷ 표준편차 · w<sub>ij</sub> = 이웃이면 1 (행 표준화) · S<sub>0</sub> = 가중치 총합 · p값은 무작위 999회 순열검정.</div>
        </div>
      </div>
    </div>
  </div>

  <!-- 결과 전역 -->
  <div class="row">
    <div class="card" style="flex:1.15">
      <h2 class="line"><span class="num">R1</span>전역 — 식문화는 공간을 탄다</h2>
      <img class="fig" src="__IMG_SCATTER__"/>
      <div class="cap">Moran 산점도(매운맛). 가로=우리 지역 값, 세로=이웃 평균. 점들이 <b>우상향</b>이면 “매운 지역은 이웃도 맵다 = 끼리끼리”. <b>기울기가 곧 Moran’s I = 0.30.</b></div>
    </div>
    <div class="card">
      <div class="headline">식문화는 공간을 탄다.<br><span class="accent">단, 전부는 아니다.</span></div>
      <p class="small muted">면·양식·매운맛 성향은 지역끼리 뭉치지만, 단백질·빵은 인접해도 닮지 않는다(오히려 흩어진다).</p>
      <table class="mtable">
        <tr><th>식문화 지표</th><th class="n">Moran’s I</th><th class="n">p</th><th>판정</th></tr>
        <tr><td>면 점유율</td><td class="n">0.35</td><td class="n">.021</td><td><span class="tag yes">끼리끼리</span></td></tr>
        <tr><td>양식 ↔ 한식</td><td class="n">0.31</td><td class="n">.027</td><td><span class="tag yes">끼리끼리</span></td></tr>
        <tr><td>매운 ↔ 순한</td><td class="n">0.30</td><td class="n">.028</td><td><span class="tag yes">끼리끼리</span></td></tr>
        <tr><td>해안성(바다 식문화)</td><td class="n">0.25</td><td class="n">.032</td><td><span class="tag yes">끼리끼리</span></td></tr>
        <tr><td>밥 점유율</td><td class="n">0.15</td><td class="n">ns</td><td><span class="tag no">무작위</span></td></tr>
        <tr><td>단백질 · 빵</td><td class="n">&lt;0</td><td class="n">.06–.10</td><td><span class="tag maybe">흩어짐</span></td></tr>
      </table>
    </div>
  </div>

  <!-- 결과 국지 -->
  <div class="row">
    <div class="card">
      <h2 class="line"><span class="num">R2</span>국지 — 어디가 뭉치고, 어디가 튀나 (LISA)</h2>
      <div class="legend">
        <span><i class="sw" style="background:var(--hh)"></i> HH 다같이 높음(핫스팟)</span>
        <span><i class="sw" style="background:var(--ll)"></i> LL 다같이 낮음(콜드스팟)</span>
        <span><i class="sw" style="background:#f1948a"></i> HL·LH 주변과 다른 ‘튀는 곳’</span>
        <span><i class="sw" style="background:#e8e2d5"></i> 유의하지 않음</span>
      </div>
      <div class="row" style="margin-top:3mm; gap:7mm;">
        <div class="card plain">
          <img class="fig" src="__IMG_LISA_SPICY__"/>
          <div class="cap"><b>매운 ↔ 순한.</b> 🔴 경북 = 영남 매운맛 핫스팟(이웃과 함께 맵다). 🔵 서울·인천·경기(수도권) = 순한맛 콜드스팟. → <b>“매운맛은 영남에 뭉치고, 수도권은 순하다.”</b></div>
        </div>
        <div class="card plain">
          <img class="fig" src="__IMG_LISA_WEST__"/>
          <div class="cap"><b>양식 ↔ 한식.</b> 🔴 서울·인천(수도권) = 양식 핫스팟. 🔵 전남(호남) = 한식 콜드스팟. 🌸 제주 = ‘튀는 곳’(이상치). → <b>“양식화는 수도권에 뭉친다.”</b></div>
        </div>
      </div>
    </div>
  </div>

  <!-- 대조 + 핵심발견 -->
  <div class="row">
    <div class="card" style="flex:1.25">
      <h2 class="line">무엇이 뭉치고, 무엇이 안 뭉치나</h2>
      <img class="fig" src="__IMG_PANEL__"/>
      <div class="cap">왼쪽 둘(매운맛·양식)은 색이 <b>뭉친다</b>(공간 군집). 오른쪽 둘(단백질·빵)은 거의 <b>회색=무작위</b>(오히려 흩어짐). ‘공간을 타는 식문화’와 ‘전국에 흩어진 식문화’가 따로 있다.</div>
    </div>
    <div class="card">
      <h2 class="line"><span class="num">!</span>핵심 발견</h2>
      <div class="find" style="flex-direction:column; gap:5mm;">
        <div class="one">
          <h3><span class="badge">검증</span>표본 크기가 결론을 바꾼다</h3>
          <p class="small">처음의 <b>502개교 표본</b>에선 ‘해안성’이 1위로 보였다(I=0.42). 그러나 전국 <b>2,355개교</b>로 늘리자 그 패턴은 <b class="k">사라졌다</b>(0.25로 약화). 진짜로 남은 구조는 <b>면·양식·매운맛</b>. <b>작은 표본은 가짜 패턴을 만든다</b>는 것을 데이터로 직접 보였다.</p>
        </div>
        <div class="one">
          <h3><span class="badge">발견</span>매운맛의 지리 · 제주라는 섬</h3>
          <p class="small"><b>영남(경북)은 맵고 수도권은 순하다</b> — 매운맛이 공간적으로 뭉친다(전체 데이터에서야 또렷해짐). <b>제주</b>는 양식 축의 통계적 <b>공간 이상치</b>(향토 메뉴 ‘몸국’ 강세) — 전국에서 가장 외딴 식단.</p>
        </div>
      </div>
    </div>
  </div>

  <!-- 결론 + 한계 -->
  <div class="row">
    <div class="card" style="flex:1.5; background:#2a251e; color:#f3ecdd; border:none;">
      <h2 style="color:#f3ecdd; border-bottom:2px solid var(--accent); padding-bottom:2mm;">결론</h2>
      <p class="lead" style="color:#f3ecdd; margin:0;">급식 식문화는 무작위가 아니라 <b style="color:#f0b8a6">‘영남 매운권’·‘수도권 양식권’</b> 같은 <b style="color:#f0b8a6">공간 구조</b>를 갖는다.
      표준화된 제도 안에서도 지역의 <b style="color:#f0b8a6">혼(spirit)</b>은 지도에 남는다 — 단, <b style="color:#f0b8a6">충분한 표본</b>에서만 신뢰할 수 있다.</p>
    </div>
    <div class="card">
      <h2 class="line">한계 &amp; 다음 단계</h2>
      <p class="small">· 학교는 전수에 가깝지만(2,355교) <b>공간 단위가 17개 시도</b>뿐 → 통계적 힘 제한. 다음: <b class="k">시군구(~250)</b> 고해상 지도.<br>
      · 제주 등 섬·이상치는 <b>이웃 정의(W)</b>에 민감.<br>
      · 임베딩 학습은 본래 비결정적이나 <b>seed 고정</b>으로 재현 확보.</p>
    </div>
  </div>

  <div class="foot">
    <span><b>데이터</b> NEIS 학교급식 오픈API · <b>경계</b> southkorea-maps(시도) · <b>도구</b> Python · gensim(FastText) · PySAL(esda·libpysal) · GeoPandas · matplotlib</span>
    <span>곽동하 · 신민석 · KAIST · 2026</span>
  </div>

</div>
</body>
</html>
"""


def main():
    html = TEMPLATE
    for token, path in FIGS.items():
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        html = html.replace(token, f"data:image/png;base64,{b64}")
    with open("poster.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"poster.html 생성 ({len(html)//1024} KB, A1 594x841mm)")


if __name__ == "__main__":
    main()
