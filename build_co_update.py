#!/usr/bin/env python3
# Actualiza Colombia en el dashboard (index_co.html) con el HTML del "Dashboard RT" de Foodology.
# USO: python3 build_co_update.py [ruta_reporte.html]
#   - Sin argumento usa el más reciente "*rt_dashboard*.html" en ../uploads.
# Qué hace:
#   - Del reporte extrae por tienda: storeId, coverageCurrent (polígono actual) y w4 (RTWT de la semana nueva).
#   - Toma la D actual del dashboard y AGREGA una semana nueva (etiqueta = último domingo de D + 7 días).
#     Las tiendas del reporte reciben rt=w4 y fin=coverageCurrent; el resto rt=null y fin=último polígono.
#     Ciudad/ops/cocina se conservan de D. Ventas de la semana nueva quedan en 0 (el reporte no trae ventas).
import re, json, sys, os, glob, datetime

HTML = 'index_co.html'
report = None
for a in sys.argv[1:]:
    if a.lower().endswith('.html'): report = a
if not report:
    cands = sorted(glob.glob('../uploads/*rt_dashboard*.html') + glob.glob('../uploads/*Dashboard*RT*.html'), key=os.path.getmtime)
    report = cands[-1] if cands else None
if not report or not os.path.exists(report):
    sys.exit('No encontré el HTML del reporte. Pásalo como argumento.')
print('Reporte:', report)

htmlR = open(report, encoding='utf-8').read()
rx = re.compile(r'\{"brand": "(.*?)", "storeId": "(\d+)", "storeName": "(.*?)", "avg4w": (?:[0-9.]+|null), "weeksData": \d+, "coverageCurrent": (\d+), "coverageResult".*?"w4": ([0-9.]+|null)\}')
rep = {}
for brand, sid, sname, cov, w4 in rx.findall(htmlR):
    rep[sid] = dict(brand=brand, sname=sname, cov=float(cov), w4=(None if w4 == 'null' else round(float(w4), 6)))
print('Tiendas en el reporte:', len(rep))

H = open(HTML, encoding='utf-8').read()
a = H.index('let D=') + 6
i, depth, started, end = a, 0, False, -1
while i < len(H):
    c = H[i]
    if c == '{': depth += 1; started = True
    elif c == '}':
        depth -= 1
        if started and depth == 0: end = i + 1; break
    i += 1
D = json.loads(H[a:end])
weeks = D['weeks']; oldLen = len(weeks)

MONTHS = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
MI = {v:k for k,v in MONTHS.items()}
def parse_lbl(l):
    m = re.match(r'([A-Za-z]{3}) (\d{1,2})', l.strip());
    return datetime.date(2026, MI[m.group(1)], int(m.group(2)))
last = parse_lbl(weeks[-1])
new = last + datetime.timedelta(days=7)
newlbl = '%s %d' % (MONTHS[new.month], new.day)
if newlbl in weeks:
    sys.exit('La semana %s ya existe en D. Nada que hacer.' % newlbl)
print('Semana nueva:', newlbl, '(D terminaba en %s)' % weeks[-1])

def strip_brand(b): return re.sub(r'\s*-?\s*Turbo.*$', '', b, flags=re.I).strip()

weeks.append(newlbl)
nrt = 0; npoly = 0
for s in D['stores']:
    sid = str(s['sid'])
    r = rep.get(sid)
    s.setdefault('gw', [0]*oldLen); s.setdefault('ow', [0]*oldLen)
    # asegurar longitudes previas
    for key, fill in (('rt', None), ('fin', None), ('gw', 0), ('ow', 0)):
        while len(s.get(key, [])) < oldLen: s[key].append(fill)
    if r and r['w4'] is not None:
        s['rt'].append(r['w4']); nrt += 1
    else:
        s['rt'].append(None)
    if r:
        s['fin'].append(r['cov']); s['cc'] = r['cov']; npoly += 1
    else:
        s['fin'].append(s['fin'][-1] if s['fin'] else None)
    s['gw'].append(0); s['ow'].append(0)

D['weeks'] = weeks
startD = H.index('let D=')
payload = 'let D=' + json.dumps(D, ensure_ascii=False)  # el ';' original queda en H[end:]
H = H[:startD] + payload + H[end:]
open(HTML, 'w', encoding='utf-8').write(H)
open('index.html', 'w', encoding='utf-8').write(H)
print('CO actualizado: %d semanas | RTWT nueva sem: %d tiendas | polígono actualizado: %d' % (len(weeks), nrt, npoly))
print('Nota: ventas de la semana nueva = 0 (el reporte RT no trae ventas).')
