#!/usr/bin/env python3
# Combina Colombia (index_co.html), México (index_mx.html) y Perú (index_pe.html)
# en un solo index.html con pestañas de país. Cada país va aislado (México con IDs
# prefijados 'mx-'; Perú ya usa 'pe-') y su JS en un IIFE, para no chocar entre sí.
import re

co = open('index_co.html', encoding='utf-8').read()
mx = open('index_mx.html', encoding='utf-8').read()
pe = open('index_pe.html', encoding='utf-8').read()

def extract(html):
    main = re.search(r'<main id="main">(.*?)</main>', html, re.S).group(1)
    js = max(re.findall(r'<script>(.*?)</script>', html, re.S), key=len)
    return main, js

# ---- México: prefijar ids 'mx-' + IIFE ----
mx_main, mx_js = extract(mx)
ids = set(re.findall(r'id="([^"]+)"', mx_main)) | {'selCity', 'selOps'}
for x in ids:
    mx_main = mx_main.replace(f'id="{x}"', f'id="mx-{x}"').replace(f'href="#{x}"', f'href="#mx-{x}"')
    mx_js = mx_js.replace(f"getElementById('{x}')", f"getElementById('mx-{x}')").replace(f'getElementById("{x}")', f'getElementById("mx-{x}")')
mx_js = re.sub(r"document\.querySelectorAll\('#side a'\)\.forEach\([^\n]*\n", "", mx_js)
mx_js = "(function(){\n" + mx_js + "\nwindow.__mxRender=render;\n})();"

# ---- Perú: ids ya 'pe-'; solo IIFE ----
pe_main, pe_js = extract(pe)
pe_js = "(function(){\n" + pe_js + "\nwindow.__peRender=render;\n})();"

h = co
# 1) CSS de tabs + kpis MX/PE en una línea
css = '''
.tabs{display:flex;gap:8px;margin-bottom:16px}
.tab{background:#fff;border:1px solid var(--bd);border-radius:10px;padding:8px 18px;font-family:Poppins;font-size:13px;font-weight:600;color:var(--mut);cursor:pointer}
.tab:hover{color:var(--primary)}
.tab.active{background:var(--primary);color:#fff;border-color:var(--primary)}
#mx-kpis,#pe-kpis{grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);grid-template-columns:none}
#kpis .kpi,#mx-kpis .kpi,#pe-kpis .kpi{min-height:118px}
#pe-trend .card,#pe-poligonos .card{height:400px}#pe-trend .card .chartbox,#pe-poligonos .card .chartbox{flex:1}#pe-poligonos .card .scroll{max-height:none}
#pe-alertas .card,#pe-alertas2 .card{height:420px}#pe-alertas .card .scroll,#pe-alertas2 .card .scroll{flex:1;max-height:none}
#mx-trend .card{height:400px}#mx-trend .card .chartbox{flex:1}
@media(max-width:600px){#mx-kpis,#pe-kpis{grid-auto-flow:row;grid-auto-columns:auto;grid-template-columns:1fr 1fr}}
'''
h = h.replace('</style>', css + '</style>', 1)

# 2) filtros MX + PE en el topbar (ocultos por defecto)
h = h.replace('<select id="selOps" title="Filtro global por ops"></select>',
              '<select id="selOps" title="Filtro global por ops"></select>'
              '\n  <select id="mx-selCity" title="Filtro por ciudad (México)" style="display:none"></select>'
              '\n  <select id="mx-selOps" title="Filtro por ops (México)" style="display:none"></select>'
              '\n  <select id="selZona" title="Filtro por zona (Perú)" style="display:none"></select>', 1)

# 3) nav CO envuelto + nav MX + nav PE
h = h.replace('<nav id="side">', '<nav id="side"><div id="nav-co">', 1)
nav_extra = '''</div><div id="nav-mx" style="display:none">
  <div class="sec">Reporte · México</div>
  <a href="#mx-resumen">Resumen ejecutivo</a>
  <a href="#mx-poligonos">Polígonos & ciudades</a>
  <a href="#mx-cocinas">Cocinas</a>
  <a href="#mx-heat">Mapa de calor</a>
  <div class="sec">Órdenes</div>
  <a href="#mx-vpareto">Pareto de marcas</a>
  <a href="#mx-vtop5">Top 5 · cobertura & RTWT</a>
  <a href="#mx-vcocina">Top marcas por cocina</a>
</div><div id="nav-pe" style="display:none">
  <div class="sec">Reporte · Perú</div>
  <a href="#pe-resumen">Resumen ejecutivo</a>
  <a href="#pe-poligonos">Polígonos & zonas</a>
  <a href="#pe-zonas">Fuera de cobertura</a>
</div>'''
h = h.replace('</nav>', nav_extra + '</nav>', 1)

# 4) tabs + apertura view-co
tabs = '''<div id="main">
<div class="tabs"><button class="tab active" onclick="showCountry('co')">🇨🇴 Colombia</button><button class="tab" onclick="showCountry('mx')">🇲🇽 México</button><button class="tab" onclick="showCountry('pe')">🇵🇪 Perú</button></div>
<div id="view-co">'''
h = h.replace('<div id="main">', tabs, 1)

# 5) cerrar view-co + insertar view-mx y view-pe
anchor = 'se excluyen de todo el análisis.</div>\n</div>'
assert anchor in h, 'no se encontró el cierre de #main'
h = h.replace(anchor,
    'se excluyen de todo el análisis.</div>\n</div><!--/view-co-->\n'
    '<div id="view-mx" style="display:none">\n' + mx_main + '\n</div>\n'
    '<div id="view-pe" style="display:none">\n' + pe_main + '\n</div>', 1)

# 6) scripts MX + PE + switch de país
switch = '''
<script>
function showCountry(c){
  var v={co:'view-co',mx:'view-mx',pe:'view-pe'}, n={co:'nav-co',mx:'nav-mx',pe:'nav-pe'};
  for(var kk in v){document.getElementById(v[kk]).style.display=(kk===c?'':'none');document.getElementById(n[kk]).style.display=(kk===c?'':'none');}
  document.getElementById('selCity').style.display=c==='co'?'':'none';
  document.getElementById('selOps').style.display=c==='co'?'':'none';
  document.getElementById('mx-selCity').style.display=c==='mx'?'':'none';
  document.getElementById('mx-selOps').style.display=c==='mx'?'':'none';
  document.getElementById('selZona').style.display=c==='pe'?'':'none';
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',(c==='co'&&i===0)||(c==='mx'&&i===1)||(c==='pe'&&i===2)));
  var lbl={co:'Colombia',mx:'México',pe:'Perú'};
  var t=document.querySelector('#topbar .t'); if(t) t.innerHTML='Foodology <span>· Turbo '+lbl[c]+'</span> — RTWT & Polígonos';
  if(c==='mx' && window.__mxRender){ try{window.__mxRender();}catch(e){console.error(e);} }
  if(c==='pe' && window.__peRender){ try{window.__peRender();}catch(e){console.error(e);} }
  setTimeout(function(){window.dispatchEvent(new Event('resize'));},80);
}
</script>
<script>
''' + mx_js + '''
</script>
<script>
''' + pe_js + '''
</script>
'''
h = h.replace('</body>', switch + '</body>', 1)

open('index.html', 'w', encoding='utf-8').write(h)
print('index.html combinado (CO+MX+PE):', len(h), 'chars')
