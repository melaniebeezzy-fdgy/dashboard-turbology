#!/usr/bin/env python3
# Inserción única del UI de Ventas en index.html (nav + secciones + JS de render).
# Los DATOS se llenan aparte con build_ventas.py (entre /*VENTAS_DATA_START*/ .. END).
import os,sys
HERE=os.path.dirname(os.path.abspath(__file__))
idx=os.path.join(HERE,'index.html')
html=open(idx,encoding='utf-8').read()

if 'VENTAS_HTML_START' in html:
    print('Ya inyectado. Nada que hacer.'); sys.exit(0)

# 1) NAV
nav_anchor='<a href="#alertas">Alertas de polígono</a>'
nav_add='''
  <div class="sec">Ventas · última semana</div>
  <a href="#vpareto">Pareto de marcas</a>
  <a href="#vtop5">Top 5 · cobertura & RTWT</a>
  <a href="#vcocina">Top marcas por cocina</a>
  <a href="#vproblemas">Top 5 Foodology por cocina</a>
'''+nav_anchor
assert html.count(nav_anchor)==1, 'nav anchor'
html=html.replace(nav_anchor,nav_add)

# 2) SECCIONES (antes del modal)
sec='''<!--VENTAS_HTML_START-->
<h1 id="vpareto" style="scroll-margin-top:70px">Ventas <span>· última semana</span> <span id="vWk" style="font-size:14px;color:var(--mut)"></span></h1>
<div class="sub">Órdenes totales por marca y cocina de la última semana (hoja <b>Raw ventas</b>). Se aplica el <b>filtro de ciudad</b> de la barra superior. RTWT y polígonos son del cierre más reciente.</div>
<div class="kpis" id="vKpis"></div>

<div class="card" style="margin-bottom:14px">
  <h2>Pareto de marcas — órdenes última semana</h2>
  <div class="hint">Barras = órdenes por marca (desc); línea = % acumulado. Las <b>5 marcas top</b> van resaltadas; la línea punteada marca el 80%.</div>
  <div class="chartbox" style="height:360px"><canvas id="chPareto"></canvas></div>
</div>

<div class="card" style="margin-bottom:14px" id="vtop5"><h2>Top 5 marcas — cobertura & RTWT</h2>
  <div class="hint">Semáforo RTWT: <span style="color:#1e8e5a;font-weight:700">&lt;2</span> · <span style="color:#d99a1b;font-weight:700">2–3</span> · <span style="color:#c0392b;font-weight:700">&gt;3</span>. «Mejor/peor cocina» por RTWT. Cobertura = polígono final vs. 3.0 km.</div>
  <div class="vgrid" id="vTop5Cards"></div>
</div>

<div class="grid" id="vcocina" style="grid-template-columns:.9fr 1.1fr">
  <div class="card"><h2>Top 5 marcas por cocina</h2>
    <div class="hint">Elige una cocina para ver sus 5 marcas más vendidas (última semana).</div>
    <div style="margin:8px 0"><select id="vCocinaSel" class="vsel"></select></div>
    <div class="scroll"><table id="vCocinaTable" class="dense"></table></div>
  </div>
  <div class="card"><h2>¿Dónde flojean las marcas top?</h2>
    <div class="hint">Para cada una de las 5 marcas top del alcance seleccionado: en qué puesto va dentro de cada cocina y cómo está su RTWT y polígono. Filas <span style="color:#c0392b;font-weight:700">rojas</span> = RTWT&gt;3 o polígono ≤1 km; <span style="color:#d99a1b;font-weight:700">ámbar</span> = alerta.</div>
    <div style="margin:8px 0"><select id="vBrandSel" class="vsel"></select> <span id="vBrandSum" style="font-size:12px;color:var(--mut)"></span></div>
    <div class="scroll" id="vProblemas"></div>
  </div>
</div>
<div id="vproblemas" style="scroll-margin-top:70px"></div>
<!--VENTAS_HTML_END-->
'''
modal='<div class="grid" id="alertas">'
assert html.count(modal)==1,'alertas anchor'
html=html.replace(modal, sec+modal, 1)

# 3) estilos mínimos (reusa el resto). Insertar antes de </style>
css='''
.vgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.vcard{border:1px solid var(--line,#e4e8ef);border-radius:12px;padding:12px 14px;background:#fff}
.vcard .vb{font-weight:700;color:var(--navy2,#242F42);font-size:14px;margin-bottom:2px}
.vcard .vo{font-size:22px;font-weight:700;color:#156082}
.vcard .vm{font-size:11px;color:var(--mut,#7a869a);margin-top:4px;line-height:1.5}
.vsel{padding:6px 10px;border:1px solid #cfd6e0;border-radius:8px;font-family:Poppins;font-size:13px;background:#fff}
tr.sev-bad td{background:rgba(192,57,43,.10)} tr.sev-warn td{background:rgba(217,154,27,.10)}
.rk{display:inline-block;min-width:20px;font-weight:700}
'''
html=html.replace('</style>', css+'</style>',1)

# 4) JS + placeholder de datos, antes de la llamada final update();
js='''
/*VENTAS_DATA_START*/const VENTAS={pareto:[],top5:[],top5_detail:[],per_cocina:{},cocinas:[],meta:{}};/*VENTAS_DATA_END*/
(function(){
 if(typeof VENTAS==='undefined'||!VENTAS.data) return;
 const pillSize=s=>s==null?'<span class="pill" style="background:#eee;color:#888">s/d</span>':`<span class="pill" style="background:${scol[s]||'#888'};color:${lcol[s]||'#fff'}">${(s/1000).toFixed(1)} km</span>`;
 const wowTag=v=>v==null?'<span style="font-size:11px;color:var(--mut)">s/d</span>':`<span style="white-space:nowrap;font-size:12px;font-weight:600;color:${v>0?'#1e8e5a':(v<0?'#c0392b':'#7a869a')}">${v>0?'▲':(v<0?'▼':'•')} ${Math.abs(v)}%</span>`;
 const dTag=(v,unit,goodDown)=>{if(v==null)return '';const good=goodDown?v<0:v>0;const col=v==0?'#7a869a':(good?'#1e8e5a':'#c0392b');const ar=v>0?'▲':(v<0?'▼':'•');return `<span style="white-space:nowrap;font-size:10.5px;color:${col}">${ar} ${Math.abs(v)}${unit}</span>`;};
 const sub=()=>VENTAS.data[CITY]||VENTAS.data.ALL;
 let chPar=null;
 function renderCoc(){const D=sub();if(!D)return;const c=document.getElementById('vCocinaSel').value,rows=(D.per_cocina[c]||[]);
   document.getElementById('vCocinaTable').innerHTML='<tr><th>#</th><th>Marca</th><th class="num">Órdenes</th><th class="num">% cocina</th></tr>'+
   rows.map((r,i)=>`<tr><td class="rk">${i+1}</td><td>${r.brand}</td><td class="num">${r.orders}</td><td class="num">${r.pct}%</td></tr>`).join('');}
 let pSort={key:'orders',dir:-1};
 window.vSortProb=function(k){if(pSort.key===k)pSort.dir*=-1;else{pSort.key=k;pSort.dir=(k==='coc')?1:-1;}renderProb();};
 function renderProb(){const D=sub();if(!D)return;const d=D.top5_detail[+document.getElementById('vBrandSel').value];if(!d)return;
   const nb=d.rows.filter(r=>r.sev==='bad').length,nw=d.rows.filter(r=>r.sev==='warn').length;
   document.getElementById('vBrandSum').innerHTML=`${nb} crítica(s) · ${nw} en alerta · ${d.rows.length} cocinas`;
   const cols=[{k:'coc',l:'Cocina'},{k:'orders',l:'Órdenes',num:1},{k:'rank',l:'Puesto',num:1},{k:'rt',l:'RTWT',num:1},{k:'size',l:'Polígono',num:1},{k:'cov',l:'Cobert.',num:1}];
   const ar=k=>pSort.key===k?(pSort.dir===1?' ↑':' ↓'):'';
   const rows=[...d.rows].sort((a,b)=>{const k=pSort.key;let av=a[k],bv=b[k];if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return -1;if(typeof av==='string')return av.localeCompare(bv)*pSort.dir;return (av-bv)*pSort.dir;});
   const head='<tr>'+cols.map(c=>`<th class="${c.num?'num ':''}sortable" onclick="vSortProb('${c.k}')" title="Ordenar">${c.l}${ar(c.k)}</th>`).join('')+'</tr>';
   document.getElementById('vProblemas').innerHTML='<table class="dense">'+head+
   rows.map(r=>`<tr class="sev-${r.sev}"><td>${r.coc}</td><td class="num">${r.orders}</td><td><span class="rk">#${r.rank}</span><span style="color:var(--mut)">/${r.nbrands}</span></td><td class="num">${rtfmt(r.rt)}</td><td class="num">${pillSize(r.size)}</td><td class="num">${r.cov==null?'–':r.cov+'%'}</td></tr>`).join('')+'</table>';}
 function renderV(){
   const D=sub();
   const wk=document.getElementById('vWk'); if(wk) wk.textContent='· '+(VENTAS.sales_week||'')+(CITY!=='ALL'?' · '+CITY:'');
   const vk=document.getElementById('vKpis');
   if(!D){vk.innerHTML='<div class="kpi"><div class="l">Sin ventas</div><div class="v">–</div><div class="d">esta ciudad no tiene datos</div></div>';
     document.getElementById('vTop5Cards').innerHTML='';document.getElementById('vCocinaTable').innerHTML='';document.getElementById('vProblemas').innerHTML='';document.getElementById('vBrandSum').innerHTML='';
     if(chPar){chPar.destroy();chPar=null;} return;}
   const M=D.meta; let n80=D.pareto.findIndex(p=>p.cum>=80)+1; if(n80<=0)n80=D.pareto.length;
   vk.innerHTML=[
     {l:'Órdenes (semana)',v:(M.total_orders||0).toLocaleString('es'),d:VENTAS.sales_week||''},
     {l:'Marcas activas',v:M.n_brands,d:'con ventas en la semana'},
     {l:'Peso del Top 5',v:(M.top5_share||0)+'%',d:'de las órdenes'},
     {l:'Marcas para el 80%',v:n80,d:'según Pareto'},
   ].map(k=>`<div class="kpi"><div class="l">${k.l}</div><div class="v">${k.v}</div><div class="d">${k.d}</div></div>`).join('');
   // Pareto
   const P=D.pareto, top=new Set(D.top5);
   if(chPar) chPar.destroy();
   chPar=new Chart(chPareto,{data:{labels:P.map(p=>p.brand),
     datasets:[
       {type:'bar',order:2,label:'Órdenes',data:P.map(p=>p.orders),yAxisID:'y',
        backgroundColor:P.map(p=>top.has(p.cb)?'#156082':'#c9d3df'),
        borderColor:P.map(p=>top.has(p.cb)?'#0E2841':'#c9d3df'),borderWidth:1},
       {type:'line',order:1,label:'% acumulado',data:P.map(p=>p.cum),yAxisID:'y1',
        borderColor:'#c0392b',backgroundColor:'#c0392b',tension:.25,pointRadius:2,fill:false},
       {type:'line',order:0,label:'80%',data:P.map(()=>80),yAxisID:'y1',
        borderColor:'#d99a1b',borderDash:[6,4],pointRadius:0,borderWidth:1.5,fill:false},
     ]},
    options:{maintainAspectRatio:false,plugins:{legend:{display:false},datalabels:{display:false},
      tooltip:{callbacks:{label:c=>c.dataset.type==='bar'?` ${c.raw} órdenes (${P[c.dataIndex].pct}%)`:(c.datasetIndex===1?` acumulado ${c.raw}%`:'')}}},
     scales:{x:{ticks:{font:{size:9},maxRotation:70,minRotation:55,autoSkip:false}},
       y:{beginAtZero:true,title:{display:true,text:'Órdenes'},ticks:{font:{size:10}}},
       y1:{position:'right',min:0,max:100,grid:{display:false},ticks:{callback:v=>v+'%',font:{size:10}}}}}});
   // Top5 cards
   document.getElementById('vTop5Cards').innerHTML=D.top5_detail.map(d=>{
     const nb=d.rows.filter(r=>r.sev==='bad').length;
     return `<div class="vcard"><div class="vb">${d.brand}</div>
     <div class="vo">${d.orders.toLocaleString('es')} ${wowTag(d.wow)}</div>
     <div class="vm">
     Cobertura <b style="color:#156082;font-size:14px">${d.avg_cov==null?'–':d.avg_cov+'%'}</b> ${dTag(d.dcov,' pts',false)}<br>
     RTWT ${rtfmt(d.avg_rt)} ${dTag(d.drt,'',true)}<br>
     <span style="color:#1e8e5a">▲ mejor: <b>${d.best||'–'}</b></span> · <span style="color:#c0392b">▼ peor: <b>${d.worst||'–'}</b></span>
     ${nb?`<br><span class="warnc">${nb} cocina(s) con RTWT/polígono crítico</span>`:''}</div></div>`;
   }).join('');
   // selects (reconstruir preservando selección)
   const vco=document.getElementById('vCocinaSel'), pc=vco.value;
   vco.innerHTML=D.cocinas.map(c=>`<option>${c}</option>`).join('');
   vco.value=D.cocinas.includes(pc)?pc:(D.cocinas[0]||'');
   const vbr=document.getElementById('vBrandSel'), pb=+vbr.value||0;
   vbr.innerHTML=D.top5_detail.map((d,i)=>`<option value="${i}">${d.brand}</option>`).join('');
   vbr.value=String(pb<D.top5_detail.length?pb:0);
   renderCoc(); renderProb();
 }
 document.getElementById('vCocinaSel').onchange=renderCoc;
 document.getElementById('vBrandSel').onchange=renderProb;
 renderV();
 if(typeof update==='function'){const _u=update; update=function(){_u.apply(this,arguments); try{renderV();}catch(e){console.error(e);}};}
})();
'''
tail='\nupdate();'
assert html.count(tail)>=1,'update() anchor'
# insertar el JS justo antes de la última llamada update();
i=html.rfind(tail)
html=html[:i]+js+html[i:]

open(idx,'w',encoding='utf-8').write(html)
print('UI de Ventas inyectado OK')
