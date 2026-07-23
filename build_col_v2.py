#!/usr/bin/env python3
# Pipeline Colombia v2: histórico (fuente vieja) + ventana móvil de 4 semanas
# (data nueva del stakeholder: rt_data_v2.csv). Polígono = coverageCurrent.
# Genera const D (11 semanas) con: b,k,c,storeId,cc,fin[],rt[]  e inyecta en index.html.
#
# Lógica del stakeholder (evaluada en JS al render):
#   avg4w = promedio RTWT de las últimas 4 semanas (con dato).
#   coverageResult = coverageCurrent  si avg4w<=8  else 0  (pierde cobertura + penalización).
#   estados por avg4w: 🟢<2  🟡2-5  🟠5-8  🔴>8 (pierde)  ⚪ sin datos.
import openpyxl, csv, json, sys, re, datetime
from collections import defaultdict

NEW = sys.argv[1] if len(sys.argv) > 1 else 'rt_data_v2.csv'
OLD = 'Turbology.xlsx'

# ---- semanas ----
HIST = ['May 4','May 11','May 18','May 25','Jun 1','Jun 8','Jun 15']   # de la fuente vieja
HIST_DATES = ['2026-05-04','2026-05-11','2026-05-18','2026-05-25','2026-06-01','2026-06-08','2026-06-15']
NEW_WEEKS = ['Jun 22','Jun 29','Jul 6','Jul 13']                       # w1..w4 del stakeholder
WEEKS = HIST + NEW_WEEKS                                               # 11 semanas
NW = len(WEEKS)

def to_m(v):
    if v in (None, ''): return None
    v = float(v)
    return v*1000 if v < 50 else v          # km -> m (1.0, 2.4 ...)
MAY11 = {1.0:1000.0, 2.0:2400.0, 3.0:3000.0}
def fin_m(dd, v):
    if dd == '2026-05-11':
        if v in (None, ''): return None
        return MAY11.get(float(v), to_m(v))
    return to_m(v)
def rtclean(v):
    if v in (None, ''): return None
    v = float(v)
    return None if v > 60 else v            # descarta seriales de fecha / basura

# ---- 1) historia (weeks 0..6) + ciudad, desde la fuente vieja ----
s2c = json.load(open('store2cocina.json'))            # 'CO...' -> cocina
wb = openpyxl.load_workbook(OLD, read_only=True, data_only=True)
ws = wb['Raw']
H = {c:i for i,c in enumerate(next(ws.iter_rows(min_row=1,max_row=1,values_only=True)))}
hist_rt = defaultdict(lambda: [None]*NW)
hist_fin = defaultdict(lambda: [None]*NW)
city_of = {}
for r in ws.iter_rows(min_row=2, values_only=True):
    sid = r[H['Store ID']]
    if not sid: continue
    d = r[H['Semana']]
    dd = (d if isinstance(d,datetime.datetime) else datetime.datetime.strptime(str(d),'%d/%m/%Y')).strftime('%Y-%m-%d')
    key = re.sub(r'\D','',str(sid))             # id numérico
    if r[H['City Name']]: city_of[key] = r[H['City Name']]   # ciudad de cualquier semana
    if dd not in HIST_DATES: continue           # rt/fin solo de semanas históricas
    w = HIST_DATES.index(dd)
    hist_rt[key][w] = rtclean(r[H['Avg. RTWT']])
    hist_fin[key][w] = fin_m(dd, r[H['Final Size']])

# ---- 2) data nueva (weeks 7..10) ----
def numf(x):
    try: return float(x)
    except: return None
stores = {}
with open(NEW, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        key = re.sub(r'\D','',str(row['storeId']))
        cc = row.get('coverageCurrent')
        cc = to_m(cc) if cc not in (None,'') else None
        b = re.sub(r'\s*-\s*Turbo\s*$','', row['brand'] or '').strip()
        coc = s2c.get('CO'+key) or s2c.get(key) or '—'
        rt = list(hist_rt[key])                 # copia historia (0..6)
        fin = list(hist_fin[key])
        for i,wk in enumerate(['w1','w2','w3','w4']):
            v = rtclean(row.get(wk))
            rt[7+i] = v
            fin[7+i] = cc                        # polígono nuevo = coverageCurrent (fijo)
        stores[key] = dict(b=b, k=coc, c=city_of.get(key,'—'), sid=key, cc=cc, fin=fin, rt=rt)

D = dict(weeks=WEEKS, n4=len(NEW_WEEKS), stores=list(stores.values()))
json.dump(D, open('D_v2.json','w'), ensure_ascii=False)

# ---- reporte rápido ----
def avg(a):
    a=[x for x in a if x is not None]; return sum(a)/len(a) if a else None
last4 = lambda s: avg(s['rt'][7:11])
allavg = avg([last4(s) for s in stores.values() if last4(s) is not None])
lose = sum(1 for s in stores.values() if (last4(s) or 0) > 8)
covres = [0 if (last4(s) or 0) > 8 else s['cc'] for s in stores.values() if s['cc'] is not None]
print('CO v2 | semanas:', NW, WEEKS)
print('tiendas:', len(stores))
print('Avg RTWT 4 sem (red):', round(allavg,2))
print('tiendas que pierden cobertura (>8):', lose)
print('cobertura red (prom coverageResult/3000):', round(100*avg(covres)/3000,1),'%')
from collections import Counter
print('coverageCurrent dist:', Counter(s['cc'] for s in stores.values()))

if '--inject' in sys.argv:
    idx = open('index.html', encoding='utf-8').read()
    payload = 'const D=' + json.dumps(D, ensure_ascii=False) + ';'
    new = re.sub(r'const D=\{.*?\};', lambda m: payload, idx, count=1, flags=re.S)
    assert new != idx and 'const D={' in new
    open('index.html','w',encoding='utf-8').write(new)
    print('const D (v2) inyectado en index.html')
