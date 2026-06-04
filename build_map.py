"""
build_map.py
------------
skorea_provinces.json + region_metrics.json -> map.html (자립형 인터랙티브 지도).

- D3(cdnjs)로 시도 코로플레스. 외부 타일/베이스맵 불필요.
- 지표 선택: 밥/빵/면 점유율, 해산물·단백질 사용도(속성), 키워드 유사도(z), 우세 군집.
- 호버 시 지역 상세 + 군집 구성 표시.
geojson과 지표를 HTML에 인라인 임베드하므로 파일 하나로 동작한다.
"""
import json

NAME_MAP = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전라북도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주",
}

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>전국 고등학교 중식 식단 지도</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Sans+KR:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
:root{
  --paper:#f6f1e7; --ink:#211d17; --muted:#6f6657; --line:#d8cdb8;
  --accent:#b6452c; --card:#fffdf8;
}
*{box-sizing:border-box}
body{margin:0;background:
   radial-gradient(1200px 600px at 80% -10%, #efe7d6 0%, transparent 60%),
   var(--paper);
  color:var(--ink);font-family:"IBM Plex Sans KR",sans-serif;}
.wrap{max-width:1120px;margin:0 auto;padding:38px 26px 60px;}
header{border-bottom:2px solid var(--ink);padding-bottom:18px;margin-bottom:8px;}
.kicker{font-size:12px;letter-spacing:.32em;text-transform:uppercase;color:var(--accent);font-weight:600;}
h1{font-family:"Gowun Batang",serif;font-weight:700;font-size:40px;line-height:1.1;margin:.18em 0 .1em;}
.sub{color:var(--muted);font-size:14px;font-weight:300;max-width:60ch;}
.controls{display:flex;flex-wrap:wrap;gap:7px;margin:22px 0 6px;}
.controls button{font-family:inherit;font-size:13px;border:1px solid var(--line);
  background:var(--card);color:var(--muted);padding:7px 13px;border-radius:999px;cursor:pointer;transition:.15s;}
.controls button:hover{border-color:var(--ink);color:var(--ink);}
.controls button.active{background:var(--ink);color:var(--paper);border-color:var(--ink);}
.stage{display:grid;grid-template-columns:1fr 320px;gap:8px;align-items:start;}
@media(max-width:820px){.stage{grid-template-columns:1fr}}
svg{width:100%;height:auto;display:block;}
.region{stroke:var(--paper);stroke-width:.8;cursor:pointer;transition:fill .25s,opacity .15s;}
.region:hover{opacity:.82;stroke:var(--ink);stroke-width:1.4;}
.rlabel{font-size:9.5px;fill:#2b2620;pointer-events:none;font-weight:500;text-anchor:middle;
  paint-order:stroke;stroke:var(--paper);stroke-width:2.4px;}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 18px 20px;
  position:sticky;top:20px;}
.panel h2{font-family:"Gowun Batang",serif;font-size:22px;margin:0 0 2px;}
.panel .n{color:var(--muted);font-size:12px;margin-bottom:14px;}
.metric-row{display:flex;justify-content:space-between;font-size:13px;padding:5px 0;border-bottom:1px dashed var(--line);}
.metric-row span:first-child{color:var(--muted);}
.metric-row b{font-weight:600;font-variant-numeric:tabular-nums;}
.clbars{margin-top:14px;}
.clbars .lab{font-size:11px;color:var(--muted);margin-bottom:5px;letter-spacing:.04em;}
.chips{display:flex;flex-wrap:wrap;gap:5px;}
.chip{font-size:11.5px;background:var(--paper);border:1px solid var(--line);border-radius:999px;
  padding:3px 9px;color:var(--ink);white-space:nowrap;}
.chip em{font-style:normal;color:var(--accent);font-weight:600;font-variant-numeric:tabular-nums;}
.bar{height:16px;border-radius:4px;display:flex;overflow:hidden;border:1px solid var(--line);}
.bar i{display:block;height:100%;}
.legend{margin-top:18px;display:flex;align-items:center;gap:10px;font-size:11px;color:var(--muted);}
.legend .grad{height:11px;flex:1;border-radius:6px;border:1px solid var(--line);}
.hint{font-size:11px;color:var(--muted);margin-top:6px;}
.foot{margin-top:26px;font-size:11px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px;line-height:1.6;}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="kicker">NEIS · 고등학교 중식 · 2021–현재</div>
    <h1>지역별 급식 식단 경향 지도</h1>
    <p class="sub">밥·빵·면 점유율, 해산물·단백질 사용도, 그리고 FastText 임베딩 키워드 유사도와 군집 구성으로 본 전국 17개 시도의 학교 중식 특성.</p>
  </header>

  <div class="controls" id="controls"></div>
  <div class="hint" id="hint"></div>

  <div class="stage">
    <div>
      <svg id="map" viewBox="0 0 640 720" preserveAspectRatio="xMidYMid meet"></svg>
      <div class="legend"><span id="lmin"></span><div class="grad" id="grad"></div><span id="lmax"></span></div>
    </div>
    <aside class="panel" id="panel"></aside>
  </div>

  <div class="foot">
    수치는 시도별 학교 평균. 점유율은 한 끼 메뉴 중 해당 형태 비율, 사용도는 단백질 속성 합. 대비 유사도는 반대 개념 키워드(예 해산물↔육류) 임베딩 투영의 차를 지역 비교용으로 z-표준화한 값(0=전국평균, 단일 키워드 유사도의 지역 편향을 상쇄). 특색 메뉴는 전국 대비 그 지역 학교가 유독 자주 내는 메뉴(학교 단위 lift). 군집은 KMeans 결과.
  </div>
</div>

<script>
const GEO = __GEOJSON__;
const M = __METRICS__;
const NAME = __NAMEMAP__;

const METRICS = [
  {key:'rice',          label:'밥 점유율',        type:'seq', fmt:'pct'},
  {key:'bread',         label:'빵 점유율',        type:'seq', fmt:'pct'},
  {key:'noodle',        label:'면 점유율',        type:'seq', fmt:'pct'},
  {key:'seafood_share', label:'해산물 사용도',     type:'seq', fmt:'pct'},
  {key:'protein_index', label:'단백질 사용도',     type:'seq', fmt:'num'},
  {key:'con_sea_meat',    label:'해산물↔육류',  type:'div'},
  {key:'con_noodle_rice', label:'면↔밥',        type:'div'},
  {key:'con_spicy_mild',  label:'매운↔순한',    type:'div'},
  {key:'con_west_korean', label:'양식↔한식',    type:'div'},
  {key:'dominant_cluster', label:'우세 군집',      type:'cat'},
];
const CL_COLORS = ['#b6452c','#2f6f7a','#c79a36','#5a7b4a','#8c5a86','#3f6196','#a8643f','#6b6f57'];

const svg = d3.select('#map');
const W=640, H=720;
const proj = d3.geoMercator().fitExtent([[24,24],[W-24,H-24]], GEO);
const path = d3.geoPath(proj);
let current = METRICS[0];

function shortName(f){ return NAME[f.properties.name] || f.properties.name; }
function val(f){ const s=shortName(f); return M[s] ? M[s][current.key] : null; }

function colorScale(){
  const vals = GEO.features.map(val).filter(v=>v!=null);
  if(current.type==='cat'){
    return c => CL_COLORS[c % CL_COLORS.length];
  }
  if(current.type==='div'){
    const m = d3.max(vals.map(Math.abs)) || 1;
    return d3.scaleDiverging(t=>d3.interpolateRdBu(1-t)).domain([-m,0,m]);
  }
  return d3.scaleSequential(d3.interpolateYlOrRd).domain([d3.min(vals), d3.max(vals)]);
}

function fmt(v){
  if(v==null) return '–';
  if(current.fmt==='pct') return (v*100).toFixed(1)+'%';
  if(current.fmt==='num') return v.toFixed(2);
  return (typeof v==='number'? v.toFixed(2): v);
}

function drawLegend(){
  const g=document.getElementById('grad');
  const lmin=document.getElementById('lmin'), lmax=document.getElementById('lmax');
  if(current.type==='cat'){
    const ncl=Object.values(M)[0].cluster_share?Object.keys(Object.values(M)[0].cluster_share).length:CL_COLORS.length;
    const stops=[...Array(ncl).keys()].map((c,i)=>`${CL_COLORS[c%CL_COLORS.length]} ${i/ncl*100}% ${ (i+1)/ncl*100}%`);
    g.style.background=`linear-gradient(90deg,${stops.join(',')})`;
    lmin.textContent='군집0'; lmax.textContent='군집'+(ncl-1);
    return;
  }
  const vals=GEO.features.map(val).filter(v=>v!=null);
  const sc=colorScale();
  const n=24, stops=[];
  if(current.type==='div'){
    const m=d3.max(vals.map(Math.abs))||1;
    for(let i=0;i<=n;i++){const v=-m+2*m*i/n; stops.push(sc(v));}
    lmin.textContent='낮음(−)'; lmax.textContent='높음(+)';
  } else {
    const mn=d3.min(vals), mx=d3.max(vals);
    for(let i=0;i<=n;i++){stops.push(sc(mn+(mx-mn)*i/n));}
    lmin.textContent=fmt(mn); lmax.textContent=fmt(mx);
  }
  if(current.type==='div'){
    if(current.label && current.label.includes('↔')){
      const parts=current.label.split('↔');
      lmin.textContent=parts[1]+' 우세(−)'; lmax.textContent=parts[0]+' 우세(+)';
    } else { lmin.textContent='낮음(−)'; lmax.textContent='높음(+)'; }
  }
  g.style.background=`linear-gradient(90deg,${stops.join(',')})`;
}

function render(){
  const sc=colorScale();
  svg.selectAll('path').data(GEO.features).join('path')
    .attr('class','region').attr('d',path)
    .attr('fill',f=>{const v=val(f); return v==null?'#ddd':sc(v);})
    .on('mouseenter',(e,f)=>showPanel(shortName(f)))
    .on('click',(e,f)=>showPanel(shortName(f)));
  svg.selectAll('text.rlabel').data(GEO.features).join('text')
    .attr('class','rlabel')
    .attr('transform',f=>`translate(${path.centroid(f)})`)
    .text(f=>shortName(f));
  drawLegend();
}

function showPanel(sido){
  const d=M[sido]; const p=document.getElementById('panel');
  if(!d){p.innerHTML=`<h2>${sido}</h2><div class="n">데이터 없음</div>`;return;}
  const z=v=>(v>=0?'+':'')+v.toFixed(2);
  const rows=[
    ['밥 점유율',(d.rice*100).toFixed(1)+'%'],
    ['빵 점유율',(d.bread*100).toFixed(1)+'%'],
    ['면 점유율',(d.noodle*100).toFixed(1)+'%'],
    ['해산물 사용도',(d.seafood_share*100).toFixed(1)+'%'],
    ['단백질 사용도',d.protein_index.toFixed(2)],
    ['해산물↔육류(z)',z(d.con_sea_meat)],
    ['면↔밥(z)',z(d.con_noodle_rice)],
    ['매운↔순한(z)',z(d.con_spicy_mild)],
    ['양식↔한식(z)',z(d.con_west_korean)],
  ];
  const cs=d.cluster_share||{};
  const bars=Object.keys(cs).map(c=>`<i style="width:${cs[c]*100}%;background:${CL_COLORS[c%CL_COLORS.length]}" title="군집${c}: ${(cs[c]*100).toFixed(0)}%"></i>`).join('');
  const sig=(d.signature||[]);
  const sigHtml = sig.length
    ? `<div class="clbars"><div class="lab">특색 메뉴 (전국 대비 자주 등장)</div>`
      + `<div class="chips">` + sig.map(s=>`<span class="chip" title="${(s.rate*100).toFixed(0)}% 학교가 제공 · 전국 대비 ${s.lift}배">${s.item} <em>×${s.lift}</em></span>`).join('') + `</div></div>`
    : '';
  p.innerHTML=`<h2>${sido}</h2><div class="n">학교 ${d.n_schools}개 · 우세 군집 ${d.dominant_cluster}</div>`
    + rows.map(r=>`<div class="metric-row"><span>${r[0]}</span><b>${r[1]}</b></div>`).join('')
    + `<div class="clbars"><div class="lab">군집 구성</div><div class="bar">${bars}</div></div>`
    + sigHtml;
}

const cbox=document.getElementById('controls');
METRICS.forEach((m,i)=>{
  const b=document.createElement('button');
  b.textContent=m.label; if(i===0)b.classList.add('active');
  b.onclick=()=>{current=m;[...cbox.children].forEach(c=>c.classList.remove('active'));b.classList.add('active');
    document.getElementById('hint').textContent = m.type==='div'?'대비 임베딩 유사도 · z-표준화(+ 왼쪽/− 오른쪽 개념이 상대적으로 우세, 0=전국평균)':(m.type==='cat'?'시도별 우세 군집(KMeans)':'한 끼 메뉴 중 비율(시도 평균)');
    render();};
  cbox.appendChild(b);
});
document.getElementById('hint').textContent='한 끼 메뉴 중 비율(시도 평균)';
render();
showPanel(Object.keys(M)[0]);
</script>
</body>
</html>
"""


def main():
    geo = json.load(open("skorea_provinces.json", encoding="utf-8"))
    metrics = json.load(open("region_metrics.json", encoding="utf-8"))
    html = (TEMPLATE
            .replace("__GEOJSON__", json.dumps(geo, ensure_ascii=False))
            .replace("__METRICS__", json.dumps(metrics, ensure_ascii=False))
            .replace("__NAMEMAP__", json.dumps(NAME_MAP, ensure_ascii=False)))
    with open("map.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"map.html 생성 ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
