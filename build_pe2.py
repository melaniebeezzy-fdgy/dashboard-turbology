#!/usr/bin/env python3
# Actualiza SOLO la cobertura de Perú con un nuevo snapshot (Foodology Coberturas.xlsx, 5 sep).
#  - Actual = 5 sep (archivo nuevo); Anterior = cobertura vigente (Jul 26, la que estaba de 'Actual').
#  - RTWT y ventas se conservan de pe_data.json (no hay fuente nueva).
#  - Agrega marca-zona nuevas del archivo (RTWT vacío).
import openpyxl, json, sys, re, unicodedata, datetime, os, warnings
from collections import Counter, defaultdict
warnings.filterwarnings('ignore')

# Uso:  python3 build_pe2.py [ruta_al_xlsx_de_coberturas] [--inject]
#   - Si no se pasa ruta, usa el último "Foodology Coberturas*.xlsx" en ../uploads.
#   - La etiqueta del corte (p.ej. "Sep 5") se saca sola de la columna Coverage Day.
import glob
_args = [a for a in sys.argv[1:] if not a.startswith('--')]
if _args:
    NEWCOB = _args[0]
else:
    _cands = sorted(glob.glob('../uploads/*obertura*.xlsx') + glob.glob('../uploads/*overage*.xlsx'), key=os.path.getmtime)
    NEWCOB = _cands[-1] if _cands else '../uploads/Foodology Coberturas.xlsx'
KDS = 'KDS_ventas_pe.xlsx'
LV = [1000, 2100, 2400, 2700, 3000]
IDEAL = 3000
NEW_LABEL = None             # se deriva de la fecha del archivo (Coverage Day)

def num(x): return float(x) if isinstance(x, (int, float)) else None
def to_m(x):
    v = num(x)
    return None if v is None else (v*1000 if v < 50 else v)
def sac(s): return ''.join(c for c in unicodedata.normalize('NFD', str(s or '')) if unicodedata.category(c) != 'Mn')
def avg(a):
    a = [x for x in a if x is not None]; return sum(a)/len(a) if a else None
def lvl(m): return min(LV, key=lambda l: abs(l-m)) if m is not None else None
def zona(name):
    n = sac(name).lower()
    if 'san isidro' in n: return 'San Isidro'
    if 'surquillo' in n: return 'Surquillo'
    if 'molina' in n: return 'La Molina'
    if 'gonzalez prada' in n or 'manuel gonzalez' in n or 'gonzales prada' in n: return 'Gonzáles Prada'
    return 'Otra'
def bkey(b):
    n = sac(b).lower(); n = re.sub(r'\bturbo\b', ' ', n).replace('&', ' ').replace('-', ' ')
    t = re.sub(r'[^a-z0-9 ]', ' ', n).split(); return ' '.join(t[:2])
def bdisp(b):
    return re.sub(r'\s*-\s*Turbo.*$', '', str(b or ''), flags=re.I).replace(' Turbo', '').strip()

# ---- PE actual (RTWT/ventas/estructura) ----
h = open('index_pe.html', encoding='utf-8').read()
PEold = json.loads(h[h.index('const PE=')+9:h.index(';/*PE_DATA_END*/')])
WEEKS = PEold['weeks']; NW = len(WEEKS)
PREV_LABEL = PEold['week']    # 'Jul 26' -> pasa a Anterior
rtw_by = {}; disp_by = {}
for s in PEold['stores']:
    key = (bkey(s['b']), s['k'])
    rtw_by[key] = (s.get('rtw') or [None]*NW, s.get('rt'), s.get('rtlw'))
    disp_by[key] = s['b']
old_cc = {(bkey(s['b']), s['k']): s['cc'] for s in PEold['stores']}   # Jul 26 -> Anterior

# ---- snapshot nuevo (5 sep) ----
wb = openpyxl.load_workbook(NEWCOB, data_only=True)
ws = wb[wb.sheetnames[0]]
newcov = defaultdict(list); newdisp = {}; _days = []
for r in ws.iter_rows(min_row=2, values_only=True):
    if r[0] is None: continue
    if isinstance(r[4], datetime.datetime): _days.append(r[4])
    z = zona(r[1])
    if z == 'Otra': continue
    k = (bkey(r[2]), z)
    m = to_m(r[5])
    if m is not None: newcov[k].append((sac(r[1]), m))   # (nombre_tienda, distancia)
    newdisp.setdefault(k, bdisp(r[2]))
# Al promediar, si varias tiendas caen en (marca,zona), usar solo las cuyo NOMBRE
# corresponde a la marca (evita mezclar marcas mal etiquetadas, p.ej. Cacerola como Avocalia).
newcc = {}
for k, rows in newcov.items():
    tok = k[0].split()[0] if k[0] else ''
    match = [d for (nm, d) in rows if tok and tok in nm]
    use = match if match else [d for (_, d) in rows]
    if use: newcc[k] = round(avg(use))
if NEW_LABEL is None:
    NEW_LABEL = max(_days).strftime('%b %-d') if _days else 'Nuevo'

# ---- construir lista de tiendas (union) ----
ST = []
keys = set(rtw_by) | set(newcc)
for k in keys:
    rtw, rt, rtlw = rtw_by.get(k, ([None]*NW, None, None))
    cc_prev = old_cc.get(k)                 # Anterior = Jul 26
    cc = newcc.get(k, cc_prev)              # Actual = 5 sep (si no vino, deja el anterior)
    b = disp_by.get(k) or newdisp.get(k) or k[0]
    ST.append(dict(b=b, k=k[1], c='Lima', cc=cc, cc_prev=cc_prev, rtw=rtw, rt=rt, rtlw=rtlw))
ZONAS = sorted({s['k'] for s in ST})
HEAT_COLS = [PREV_LABEL, NEW_LABEL]

# ---- ventas KDS (igual que build_pe) ----
def bnorm(b):
    n = sac(b).lower().replace('&', ' ').replace('-', ' ')
    drop = {'turbo', 'fdl', 'fd', 'court', 'sandwiches'}
    return ' '.join(t for t in re.sub(r'[^a-z0-9 ]', ' ', n).split() if t not in drop).strip()
def bshow(b):
    s = re.sub(r'\s*-?\s*turbo\b.*$', '', str(b or ''), flags=re.I).strip()
    return (s.title() if s.isupper() else s) or str(b)
vrecs = []
if os.path.exists(KDS):
    wv = openpyxl.load_workbook(KDS, read_only=True, data_only=True)
    for r in wv['Export'].iter_rows(min_row=2, values_only=True):
        r = list(r) + [None]*(6-len(list(r)))
        if not isinstance(r[0], datetime.datetime): continue
        vrecs.append((r[0].date(), zona(r[2]), str(r[3] or ''), num(r[4]) or 0))
days = [x[0] for x in vrecs]
sales_week = prev_week = None; lw_all = pw_all = []; vdisp = {}
if days:
    lastday = max(days); firstlw = lastday - datetime.timedelta(days=6)
    pfirst = firstlw - datetime.timedelta(days=7); plast = firstlw - datetime.timedelta(days=1)
    sales_week = f"{firstlw.strftime('%d/%m')}–{lastday.strftime('%d/%m/%Y')}"
    prev_week = f"{pfirst.strftime('%d/%m')}–{plast.strftime('%d/%m')}"
    lw_all = [x for x in vrecs if firstlw <= x[0] <= lastday]
    pw_all = [x for x in vrecs if pfirst <= x[0] <= plast]
    for x in lw_all + pw_all: vdisp.setdefault(bnorm(x[2]), bshow(x[2]))

def covResult(s): return s['cc']   # Perú no penaliza
def ftok(b):
    t = bnorm(b).split(); return t[0] if t else ''
sidx = {}
for s in ST:
    sidx[(ftok(s['b']), s['k'])] = (s['rt'], s['cc'], covResult(s))

def compute(kind, name):
    st = [s for s in ST if kind == 'all' or s['k'] == name]
    fins = [s['cc'] for s in st if s['cc'] is not None]
    rts = [s['rt'] for s in st if s['rt'] is not None]
    rtwt = avg(rts); rtwt_lw = avg([s['rtlw'] for s in st if s['rtlw'] is not None])
    crs = [covResult(s) for s in st if covResult(s) is not None]
    cov = 100*avg(crs)/IDEAL if crs else None
    cov_asg = 100*avg(fins)/IDEAL if fins else None
    dist = Counter(lvl(f) for f in fins); tot = len(fins)
    lose = sum(1 for s in st if s['rt'] is not None and s['rt'] > 8)
    alerts = dict(rt3=sum(1 for x in rts if x > 3), poly1=dist.get(1000, 0))
    weekly = [ (lambda a: round(a, 2) if a is not None else None)(avg([s['rtw'][w] for s in st if s.get('rtw') and w < len(s['rtw'])])) for w in range(NW) ]
    pv_g = [s['cc_prev'] for s in st if s.get('cc_prev') is not None]
    cov_prev = round(100*avg(pv_g)/IDEAL, 1) if pv_g else None
    cov_series = [cov_prev, None if cov is None else round(cov, 1)]
    heat_cols = HEAT_COLS
    zheat = sorted({s['k'] for s in st})
    heat_cov = []; heat_detail = []
    for z in zheat:
        zs = [s for s in st if s['k'] == z]
        pv = [s['cc_prev'] for s in zs if s.get('cc_prev') is not None]
        cov_a = round(100*avg(pv)/IDEAL, 1) if pv else None
        det_a = []
        for s in zs:
            if s.get('cc_prev') is None: continue
            szl = lvl(s['cc_prev'])
            if szl != 3000: det_a.append(dict(b=s['b'], sz=szl, rt=None if s['rt'] is None else round(s['rt'], 2), drop=None))
        det_a.sort(key=lambda x: (x['sz'], x['b']))
        cv = [covResult(s) for s in zs if covResult(s) is not None]
        cov_c = round(100*avg(cv)/IDEAL, 1) if cv else None
        det_c = []
        for s in zs:
            cr = covResult(s)
            if cr is None: continue
            szl = 0 if cr == 0 else lvl(cr)
            cp = s.get('cc_prev'); dr = None
            if cp is not None and szl not in (0, None) and lvl(cp) is not None and szl < lvl(cp): dr = [lvl(cp), szl]
            if szl != 3000: det_c.append(dict(b=s['b'], sz=szl, rt=None if s['rt'] is None else round(s['rt'], 2), drop=dr))
        det_c.sort(key=lambda x: (x['sz'], x['b']))
        heat_cov.append([cov_a, cov_c]); heat_detail.append([det_a, det_c])
    heat = dict(zonas=zheat, cols=heat_cols, cov=heat_cov, detail=heat_detail)
    gg = defaultdict(list)
    for s in st:
        if s['cc'] is not None: gg[s['k']].append(s)
    glabels = sorted(gg.keys(), key=lambda k: 100*avg([x['cc'] for x in gg[k]])/IDEAL)
    stack = {str(l): [] for l in LV}; stack_tot = []
    for lab in glabels:
        d = Counter(lvl(x['cc']) for x in gg[lab])
        for l in LV: stack[str(l)].append(d.get(l, 0))
        stack_tot.append(sum(d.values()))
    by = defaultdict(list)
    for s in st: by[s['k']].append(s)
    cocinas = []
    for k, v in by.items():
        rr = avg([x['rt'] for x in v if x['rt'] is not None]); rl = avg([x['rtlw'] for x in v if x['rtlw'] is not None])
        cr = [covResult(x) for x in v if covResult(x) is not None]
        cocinas.append(dict(k=k, city='Lima', n=len(v),
            rtwt=None if rr is None else round(rr, 2),
            drt=None if (rr is None or rl is None) else round(rr-rl, 2),
            cov=None if not cr else round(100*avg(cr)/IDEAL, 1),
            lose=sum(1 for x in v if x['rt'] is not None and x['rt'] > 8)))
    cocinas.sort(key=lambda x: x['cov'] if x['cov'] is not None else 999)
    lc = sorted([dict(b=s['b'], k=s['k'], rt=s['rt'], cc=s['cc'], res=covResult(s)) for s in st if s['rt'] is not None and s['rt'] > 8],
                key=lambda x: -x['rt'])
    rising = []
    L = NW - 1
    for s in st:
        w = s.get('rtw') or []
        if len(w) < 2 or w[L] is None or w[L-1] is None or not (w[L] > w[L-1]): continue
        i = L; path = [w[L]]; inc = 0
        while i-1 >= 0 and w[i-1] is not None and w[i] > w[i-1]:
            path.insert(0, round(w[i-1], 2)); inc += 1; i -= 1
        if inc >= 2: rising.append(dict(b=s['b'], k=s['k'], inc=inc, path=[round(x, 2) for x in path], last=round(w[L], 2)))
    rising.sort(key=lambda x: -x['last'])
    min1 = sorted([dict(b=s['b'], k=s['k'], rt=None if s['rt'] is None else round(s['rt'], 2)) for s in st if covResult(s) == 1000],
                  key=lambda x: -(x['rt'] or 0))
    byb = defaultdict(list)
    for s in st:
        if s['rt'] is not None: byb[s['b']].append(s['rt'])
    brand_worst = sorted([dict(brand=b, rt=round(avg(v), 2), n=len(v)) for b, v in byb.items()], key=lambda x: -x['rt'])[:15]
    gbz = defaultdict(list)
    for s in st: gbz[(s['b'], s['k'])].append(s)
    brand_zona = []
    for (b, kz), g in gbz.items():
        rr = avg([x['rt'] for x in g if x['rt'] is not None])
        if rr is None or rr <= 3: continue
        rl = avg([x['rtlw'] for x in g if x['rtlw'] is not None])
        cr = [covResult(x) for x in g if covResult(x) is not None]
        brand_zona.append(dict(b=b, k=kz, rt=round(rr, 2),
                               rtlw=None if rl is None else round(rl, 2),
                               res=round(avg(cr)) if cr else None, rt_last=round(rr, 2)))
    brand_zona.sort(key=lambda x: -x['rt'])
    vinc = lambda x: kind == 'all' or (kind == 'zona' and x[1] == name)
    lw = [x for x in lw_all if vinc(x)]; pw = [x for x in pw_all if vinc(x)]
    bt = defaultdict(float); btp = defaultdict(float)
    for x in lw: bt[bnorm(x[2])] += x[3]
    for x in pw: btp[bnorm(x[2])] += x[3]
    tot_o = sum(bt.values()) or 1
    pareto = []; cum = 0
    for cb, o in sorted(bt.items(), key=lambda x: -x[1]):
        cum += o; pareto.append(dict(brand=vdisp.get(cb, cb), orders=round(o), pct=round(100*o/tot_o, 1), cum=round(100*cum/tot_o, 1)))
    top5c = [p for p in sorted(bt, key=lambda c: -bt[c])[:5]]
    cbz = defaultdict(float)
    for x in lw: cbz[(x[1], bnorm(x[2]))] += x[3]
    zonas_v = sorted({k[0] for k in cbz})
    per_zona = {}; rankz = {}
    for z in zonas_v:
        items = sorted([(cb, o) for (zz, cb), o in cbz.items() if zz == z], key=lambda x: -x[1])
        tt = sum(o for _, o in items) or 1
        per_zona[z] = []
        for cb, o in items[:5]:
            rtv, cc_, cr = sidx.get((cb.split()[0] if cb else '', z), (None, None, None))
            per_zona[z].append(dict(brand=vdisp.get(cb, cb), orders=round(o), pct=round(100*o/tt, 1),
                                    rt=None if rtv is None else round(rtv, 2), size=cr))
        for i, (cb, o) in enumerate(items): rankz[(z, cb)] = (i+1, round(o), len(items))
    top5_detail = []
    for cb in top5c:
        rr = []
        for z in zonas_v:
            o = cbz.get((z, cb))
            if not o: continue
            rk, orders, nb = rankz[(z, cb)]
            rtv, cc, cr = sidx.get((cb.split()[0] if cb else '', z), (None, None, None))
            cv = None if cr is None else round(100*cr/IDEAL)
            sz = lvl(cr) if cr else None
            sev = 'bad' if (rtv is not None and rtv > 3) or (sz is not None and sz <= 1000) else ('warn' if (rtv is not None and rtv > 2) or (sz is not None and sz <= 2100) else 'ok')
            rr.append(dict(coc=z, orders=orders, rank=rk, nbrands=nb, rt=None if rtv is None else round(rtv, 2), size=sz, cov=cv, sev=sev))
        rr.sort(key=lambda x: -x['orders'])
        wr = [r for r in rr if r['rt'] is not None]
        best = min(wr, key=lambda x: x['rt'])['coc'] if wr else None
        worst = max(wr, key=lambda x: x['rt'])['coc'] if wr else None
        ar = [r['rt'] for r in rr if r['rt'] is not None]; ac = [r['cov'] for r in rr if r['cov'] is not None]
        oprev = btp.get(cb, 0); wow = None if not oprev else round(100*(bt[cb]-oprev)/oprev, 1)
        top5_detail.append(dict(brand=vdisp.get(cb, cb), orders=round(bt[cb]), wow=wow,
            avg_rt=round(avg(ar), 2) if ar else None, avg_cov=round(avg(ac), 1) if ac else None,
            best=best, worst=worst, rows=rr))
    top5_share = round(100*sum(bt[c] for c in top5c)/tot_o, 1) if bt else 0
    n80 = next((i+1 for i, p in enumerate(pareto) if p['cum'] >= 80), len(pareto))
    ventas = dict(pareto=pareto, top5=[vdisp.get(c, c) for c in top5c], top5_detail=top5_detail,
                  per_zona=per_zona, zonas_v=zonas_v, total_orders=round(sum(bt.values())),
                  n_brands=len(pareto), top5_share=top5_share, n80=n80)
    return dict(
        kpi=dict(rtwt=None if rtwt is None else round(rtwt, 2),
                 rtwt_lw=None if rtwt_lw is None else round(rtwt_lw, 2),
                 drt=None if (rtwt is None or rtwt_lw is None) else round(rtwt-rtwt_lw, 2),
                 cov=None if cov is None else round(cov, 1),
                 cov_asg=None if cov_asg is None else round(cov_asg, 1),
                 n_stores=len(st), n_cocinas=len({s['k'] for s in st}),
                 dist={str(l): dist.get(l, 0) for l in LV}, tot=tot, lose=lose, alerts=alerts),
        stack=dict(labels=glabels, series=stack, tot=stack_tot),
        weekly=weekly, cov_series=cov_series, heat=heat,
        cocinas=cocinas, lost=lc, rising=rising, min1=min1, brand_worst=brand_worst, brand_zona=brand_zona, ventas=ventas)

data = {'ALL': compute('all', None)}
for z in ZONAS: data[z] = compute('zona', z)
PE = dict(ideal=IDEAL, LV=LV, zonas=ZONAS, weeks=WEEKS, cov_labels=HEAT_COLS, week=NEW_LABEL, prev_week=PREV_LABEL,
          sales_week=sales_week, sales_prev=prev_week,
          stores=[dict(b=s['b'], k=s['k'], c=s['c'], cc=s['cc'], cc_prev=s.get('cc_prev'),
                       rt=s['rt'], rtlw=s['rtlw'], rtw=s['rtw']) for s in ST],
          data=data)
json.dump(PE, open('pe_data.json', 'w'), ensure_ascii=False)
k = data['ALL']['kpi']
print('PE | zonas', ZONAS, '| tiendas', len(ST), '(antes', len(PEold['stores']), ')')
print('cortes:', HEAT_COLS)
print('ALL cob efec', k['cov'], '% (antes', PEold['data']['ALL']['kpi']['cov'], ') | asignada', k['cov_asg'], '% | dist', k['dist'])
print('cov por zona (Anterior->Actual):')
for z in ZONAS:
    hc = data[z]['heat']['cov'][0]; print('  ', z, hc)

if '--inject' in sys.argv:
    payload = '/*PE_DATA_START*/const PE=' + json.dumps(PE, ensure_ascii=False) + ';/*PE_DATA_END*/'
    new = re.sub(r'/\*PE_DATA_START\*/.*?/\*PE_DATA_END\*/', lambda m: payload, h, count=1, flags=re.S)
    # actualiza el subtítulo con la fecha del corte de cobertura
    sub = ('<div class="sub">Turbo Perú (Lima) · <b>RTWT</b> por la última semana (%s vs %s). '
           '<b>Cobertura</b> = polígono asignado por tienda, corte del <b>%s</b> (Anterior: %s). '
           'Filtro por zona en la barra superior.</div>') % (WEEKS[-1], WEEKS[-2], NEW_LABEL, PREV_LABEL)
    new = re.sub(r'<div class="sub">Turbo Perú \(Lima\).*?Filtro por zona en la barra superior\.</div>',
                 lambda m: sub, new, count=1, flags=re.S)
    open('index_pe.html', 'w', encoding='utf-8').write(new)
    print('PE inyectado en index_pe.html (corte %s, subtítulo actualizado)' % NEW_LABEL)
