#!/usr/bin/env python3
# Pipeline dashboard MÉXICO (snapshot). Lee FOODOLOGY.xlsx (hoja DETALLE),
# extrae cocina (Queue ID + Store Name), calcula KPIs, cobertura, distribución
# de polígonos, tablas por ciudad y cocina (RTWT actual vs semana pasada) y
# Pareto de marcas por órdenes. Inyecta el bloque MX en index_mx.html.
import openpyxl, re, json, sys, unicodedata
from collections import Counter, defaultdict

XLSX = sys.argv[1] if len(sys.argv) > 1 else 'FOODOLOGY.xlsx'
LV = [1000, 2100, 2400, 2700, 3000]
IDEAL = 3000

wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
ws = wb['DETALLE']
H = {c: i for i, c in enumerate(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))}
def col(r, name):
    i = H.get(name);
    return r[i] if i is not None and i < len(r) else None

rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if col(r, 'Store ID')]

# ---------- marcas ----------
bset = set()
for br in wb['BRANDS'].iter_rows(min_row=1, values_only=True):
    if br[1]: bset.add(str(br[1]))
for r in rows:
    if col(r, 'Brand Name'): bset.add(str(col(r, 'Brand Name')))
brand_frag = sorted({re.sub(r'\s*[-–]?\s*Turbo.*$', '', b, flags=re.I).strip(' .-') for b in bset if b}, key=len, reverse=True)
brand_frag = [b for b in brand_frag if b]
def stripbrand(s):
    return re.sub(r'\s*[-–]?\s*Turbo.*$', '', s or '', flags=re.I).strip()

def sac(s): return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
def rm_brands(s):
    for b in brand_frag: s = re.sub(re.escape(b), '', s, flags=re.I)
    return s
def extract_loc(name):
    s = name
    m = re.search(r'\(([^)]*)\)', s)
    if m and m.group(1).strip():
        s = m.group(1)
    else:
        s = re.sub(r'\s*[-–]?\s*Turbo.*$', '', s, flags=re.I)
        s = rm_brands(s)
        s = re.split(r'(Blvd|Av\.|Avenida|Cra|Calle|Carrera|Cl\.|#|Rest\b)', s, flags=re.I)[0]
        parts = [p.strip() for p in re.split(r'[-–]', s) if p.strip()]
        s = parts[-1] if parts else s
    s = rm_brands(s)
    s = re.sub(r'[().]', ' ', s); s = re.sub(r'\s+', ' ', s).strip(' .-')
    return s.title()

# ---------- cocina por tienda ----------
q = defaultdict(list)
for r in rows: q[col(r, 'Queue ID')].append(r)
raw = {col(r, 'Store ID'): extract_loc(col(r, 'Store Name')) for r in rows}
for qid, grp in q.items():
    if qid is None: continue
    locs = [raw[col(g, 'Store ID')] for g in grp]
    mode = Counter(sac(l).lower() for l in locs).most_common(1)[0][0]
    disp = Counter(l for l in locs if sac(l).lower() == mode).most_common(1)[0][0]
    for g in grp: raw[col(g, 'Store ID')] = disp
# unificar acentos
keydisp = defaultdict(Counter)
for sid, loc in raw.items(): keydisp[sac(loc).lower()][loc] += 1
canon = {k: c.most_common(1)[0][0] for k, c in keydisp.items()}
s2c = {sid: canon[sac(loc).lower()] for sid, loc in raw.items()}
# merge por sufijo: etiquetas con marca pegada -> cocina establecida
cnt = Counter(s2c.values())
established = {c for c, n in cnt.items() if n >= 2}
def merge_suffix(lbl):
    if lbl in established: return lbl
    for e in sorted(established, key=len, reverse=True):
        if lbl.lower().endswith(e.lower()): return e
    return lbl
s2c = {sid: merge_suffix(lbl) for sid, lbl in s2c.items()}
json.dump(s2c, open('store2cocina_mx.json', 'w'), ensure_ascii=False)

CITY_SHORT = {'Ciudad de México': 'CDMX'}
def short_city(c): return CITY_SHORT.get(c, c)

# ---------- registros por tienda ----------
def num(x):
    return float(x) if isinstance(x, (int, float)) else None
def to_m(x):
    # normaliza tamaños a metros: valores en km (<50) -> x1000
    v = num(x)
    if v is None: return None
    return v * 1000 if v < 50 else v
stores = []
for r in rows:
    sid = col(r, 'Store ID')
    stores.append(dict(
        sid=sid, b=stripbrand(col(r, 'Brand Name')), coc=s2c.get(sid, '—'),
        c=short_city(col(r, 'City Name') or '—'), kam=col(r, 'KAM'),
        orders=num(col(r, 'Orders')) or 0,
        rt=num(col(r, 'Avg. RTWT')), lwrt=num(col(r, 'LW_RTWT')),
        fin=to_m(col(r, 'FINAL SIZE')), cur=to_m(col(r, 'Current Size')),
    ))

def lvl(m):
    return min(LV, key=lambda l: abs(l - m)) if m is not None else None
def avg(a):
    a = [x for x in a if x is not None]
    return sum(a) / len(a) if a else None

CITIES = sorted({s['c'] for s in stores})

def compute(subset):
    st = subset
    fins = [s['fin'] for s in st if s['fin'] is not None]
    rts = [s['rt'] for s in st if s['rt'] is not None]
    lwrts = [(s['rt'], s['lwrt']) for s in st if s['rt'] is not None and s['lwrt'] is not None]
    rtwt = avg(rts)
    rtwt_lw = avg([s['lwrt'] for s in st if s['lwrt'] is not None])
    cov = 100 * avg(fins) / IDEAL if fins else None
    dist = Counter(lvl(f) for f in fins)
    tot = len(fins)
    orders = sum(s['orders'] for s in st)
    brands = {s['b'] for s in st if s['orders'] > 0} or {s['b'] for s in st}
    cocs = {s['coc'] for s in st}
    alerts = dict(rt3=sum(1 for x in rts if x > 3), poly1=dist.get(1000, 0))

    # ----- distribución apilada (por cocina si hay pocas; por ciudad si es ALL) -----
    if len({s['c'] for s in st}) > 1:
        gkey = lambda s: s['c']
    else:
        gkey = lambda s: s['coc']
    gg = defaultdict(list)
    for s in st:
        if s['fin'] is not None: gg[gkey(s)].append(s)
    # ordenar por cobertura asc (peor primero)
    def gcov(v):
        f = [x['fin'] for x in v]; return 100 * avg(f) / IDEAL
    glabels = sorted(gg.keys(), key=lambda k: gcov(gg[k]))
    stack = {str(l): [] for l in LV}
    stack_tot = []
    for lab in glabels:
        d = Counter(lvl(x['fin']) for x in gg[lab])
        for l in LV: stack[str(l)].append(d.get(l, 0))
        stack_tot.append(sum(d.values()))

    # ----- tabla por cocina -----
    bycoc = defaultdict(list)
    for s in st: bycoc[s['coc']].append(s)
    cocinas = []
    for coc, v in bycoc.items():
        f = [x['fin'] for x in v if x['fin'] is not None]
        rr = [x['rt'] for x in v if x['rt'] is not None]
        lr = [x['lwrt'] for x in v if x['lwrt'] is not None]
        rtc = avg(rr); rtl = avg(lr)
        cocinas.append(dict(coc=coc, city=Counter(x['c'] for x in v).most_common(1)[0][0],
            n=len(v), nb=len({x['b'] for x in v}), orders=round(sum(x['orders'] for x in v)),
            rtwt=None if rtc is None else round(rtc, 2),
            drt=None if (rtc is None or rtl is None) else round(rtc - rtl, 2),
            cov=None if not f else round(100 * avg(f) / IDEAL, 1)))
    cocinas.sort(key=lambda x: (x['cov'] if x['cov'] is not None else 999))

    # ----- tabla por ciudad (solo aplica en ALL) -----
    bycity = defaultdict(list)
    for s in st: bycity[s['c']].append(s)
    cities = []
    for cc, v in bycity.items():
        f = [x['fin'] for x in v if x['fin'] is not None]
        rr = [x['rt'] for x in v if x['rt'] is not None]
        lr = [x['lwrt'] for x in v if x['lwrt'] is not None]
        rtc = avg(rr); rtl = avg(lr)
        cities.append(dict(city=cc, n=len(v), nb=len({x['b'] for x in v}),
            orders=round(sum(x['orders'] for x in v)),
            rtwt=None if rtc is None else round(rtc, 2),
            drt=None if (rtc is None or rtl is None) else round(rtc - rtl, 2),
            cov=None if not f else round(100 * avg(f) / IDEAL, 1)))
    cities.sort(key=lambda x: (x['cov'] if x['cov'] is not None else 999))

    # ----- Pareto de marcas por órdenes -----
    bo = defaultdict(float)
    for s in st: bo[s['b']] += s['orders']
    bo = {b: o for b, o in bo.items() if o > 0}
    tot_o = sum(bo.values()) or 1
    pareto = []
    cum = 0
    for b, o in sorted(bo.items(), key=lambda x: -x[1]):
        cum += o
        pareto.append(dict(brand=b, orders=round(o), pct=round(100 * o / tot_o, 1), cum=round(100 * cum / tot_o, 1)))
    top5 = [p['brand'] for p in pareto[:5]]

    # ----- detalle top5: cobertura & RTWT + mejor/peor cocina -----
    top5_detail = []
    for b in top5:
        sb = [s for s in st if s['b'] == b]
        f = [x['fin'] for x in sb if x['fin'] is not None]
        rr = [x['rt'] for x in sb if x['rt'] is not None]
        # por cocina
        bc = defaultdict(list)
        for s in sb: bc[s['coc']].append(s)
        rowlist = []
        for coc, v in bc.items():
            fv = [x['fin'] for x in v if x['fin'] is not None]
            rv = avg([x['rt'] for x in v if x['rt'] is not None])
            sz = lvl(avg(fv)) if fv else None
            cv = round(100 * avg(fv) / IDEAL) if fv else None
            # rank de la marca dentro de la cocina por órdenes
            allb = defaultdict(float)
            for s in st:
                if s['coc'] == coc: allb[s['b']] += s['orders']
            ranked = [x for x, _ in sorted(allb.items(), key=lambda x: -x[1]) if allb[x] > 0]
            rank = (ranked.index(b) + 1) if b in ranked else None
            ob = round(sum(x['orders'] for x in v))
            sev = 'bad' if (rv is not None and rv > 3) or (sz is not None and sz <= 1000) else ('warn' if (rv is not None and rv > 2) or (sz is not None and sz <= 2100) else 'ok')
            rowlist.append(dict(coc=coc, orders=ob, rank=rank, nbrands=len(ranked),
                rt=None if rv is None else round(rv, 2), size=sz, cov=cv, sev=sev))
        rowlist.sort(key=lambda x: -x['orders'])
        rr_by_coc = [(coc, avg([x['rt'] for x in v if x['rt'] is not None])) for coc, v in bc.items()]
        rr_by_coc = [(c, r) for c, r in rr_by_coc if r is not None]
        best = min(rr_by_coc, key=lambda x: x[1])[0] if rr_by_coc else None
        worst = max(rr_by_coc, key=lambda x: x[1])[0] if rr_by_coc else None
        top5_detail.append(dict(brand=b, orders=round(sum(x['orders'] for x in sb)),
            avg_cov=None if not f else round(100 * avg(f) / IDEAL, 1),
            avg_rt=None if not rr else round(avg(rr), 2),
            best=best, worst=worst, rows=rowlist))

    # ----- top marcas por cocina -----
    per_cocina = {}
    for coc, v in bycoc.items():
        bb = defaultdict(float)
        for s in v: bb[s['b']] += s['orders']
        tt = sum(bb.values()) or 1
        lst = [dict(brand=b, orders=round(o), pct=round(100 * o / tt, 1)) for b, o in sorted(bb.items(), key=lambda x: -x[1]) if o > 0][:5]
        if lst: per_cocina[coc] = lst
    coc_list = sorted(per_cocina.keys())

    return dict(
        kpi=dict(rtwt=None if rtwt is None else round(rtwt, 2),
                 rtwt_lw=None if rtwt_lw is None else round(rtwt_lw, 2),
                 drt=None if (rtwt is None or rtwt_lw is None) else round(rtwt - rtwt_lw, 2),
                 cov=None if cov is None else round(cov, 1),
                 n_stores=len(st), n_orders=round(orders), n_brands=len(brands), n_cocinas=len(cocs),
                 dist={str(l): dist.get(l, 0) for l in LV}, tot=tot, alerts=alerts),
        stack=dict(labels=glabels, series=stack, tot=stack_tot),
        cities=cities, cocinas=cocinas,
        pareto=pareto, top5=top5, top5_detail=top5_detail,
        per_cocina=per_cocina, coc_list=coc_list)

data = {'ALL': compute(stores)}
for c in CITIES:
    data[c] = compute([s for s in stores if s['c'] == c])

updated = None
for r in rows:
    u = col(r, 'UPDATED_AT_UTC')
    if u: updated = str(u)[:10]; break

MX = dict(updated=updated, ideal=IDEAL, LV=LV, cities=CITIES, data=data)
json.dump(MX, open('mx_data.json', 'w'), ensure_ascii=False)
print('MX listo | actualizado', updated, '| ciudades', CITIES)
print('cocinas:', len(set(s2c.values())), '| tiendas', len(stores))
k = data['ALL']['kpi']
print('ALL: RTWT', k['rtwt'], 'vs LW', k['rtwt_lw'], '| cobertura', k['cov'], '% | órdenes', k['n_orders'], '| dist', k['dist'])

if '--inject' in sys.argv:
    idx = open('index_mx.html', encoding='utf-8').read()
    payload = '/*MX_DATA_START*/const MX=' + json.dumps(MX, ensure_ascii=False) + ';/*MX_DATA_END*/'
    new = re.sub(r'/\*MX_DATA_START\*/.*?/\*MX_DATA_END\*/', lambda m: payload, idx, count=1, flags=re.S)
    assert new != idx, 'no se pudo inyectar MX'
    open('index_mx.html', 'w', encoding='utf-8').write(new)
    print('MX inyectado en index_mx.html')
