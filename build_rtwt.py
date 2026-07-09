#!/usr/bin/env python3
# Genera Turbology_con_cocina.csv (limpio) y el bloque const D (RTWT/polígonos)
# a partir de la hoja 'Raw' de Turbology.xlsx, e inyecta const D en index.html.
import openpyxl, json, csv, sys, re, datetime

XLSX = sys.argv[1] if len(sys.argv)>1 else 'Turbology.xlsx'
HERE='.'
m = json.load(open('store2cocina.json'))

def to_m(v):
    if v is None or v=='' : return None
    v=float(v)
    return v*1000 if v<50 else v

# La semana 2026-05-11 quedó codificada gruesa en la hoja ({1.0,2.0,3.0}).
# Mapeo fijo para preservar el histórico ya publicado.
MAY11_MAP={1.0:1000.0, 2.0:2400.0, 3.0:3000.0}
def fin_m(dd, v):
    if dd.year==2026 and dd.month==5 and dd.day==11:
        if v is None or v=='' : return None
        return MAY11_MAP.get(float(v), to_m(v))
    return to_m(v)

def wlabel(d):
    if isinstance(d,str):
        d=datetime.datetime.strptime(d,'%d/%m/%Y')
    return d.strftime('%b %-d')

wb=openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
ws=wb['Raw']
rows=[]
weeks_dt=[]
for r in ws.iter_rows(min_row=2, values_only=True):
    if r[0] is None: continue
    d=r[0]
    if isinstance(d,datetime.datetime): dd=d
    else: dd=datetime.datetime.strptime(str(d),'%d/%m/%Y')
    sem='%d/%d/%d'%(dd.day,dd.month,dd.year)
    sid=r[6]; coc=m.get(sid,'')
    rt=r[8]; cur=to_m(r[9]); fin=fin_m(dd, r[13])
    # descartar RTWT inválidos (celdas con seriales de fecha ~46000 en la hoja)
    if rt not in (None,'') and float(rt)>60: rt=None
    rows.append(dict(dt=dd,sem=sem,city=r[3],marca=r[5],sid=sid,sname=r[7],coc=coc,
                     rt=None if rt in (None,'') else float(rt),cur=cur,fin=fin))
    weeks_dt.append(dd)

# 1) CSV limpio (mismo esquema que antes)
with open('Turbology_con_cocina.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f)
    w.writerow(['Semana','Ciudad','Marca','Store ID','Store Name','Cocina','Avg RTWT (limpio)','Current Size (m)','Final Size (m)'])
    for r in rows:
        w.writerow([r['sem'],r['city'],r['marca'],r['sid'],r['sname'],r['coc'],
                    '' if r['rt'] is None else r['rt'], '' if r['cur'] is None else r['cur'],
                    '' if r['fin'] is None else r['fin']])

# 2) const D: pivot por Store ID
uw=sorted(set(weeks_dt))
weeks=[wlabel(d) for d in uw]
widx={d:i for i,d in enumerate(uw)}
def stripbrand(s): return re.sub(r'\s*-\s*Turbo\s*$','',s).strip()
stores={}
for r in rows:
    sid=r['sid']
    if sid not in stores:
        stores[sid]=dict(b=stripbrand(r['marca']),k=r['coc'],c=r['city'],
                         fin=[None]*len(uw), rt=[None]*len(uw))
    i=widx[r['dt']]
    stores[sid]['fin'][i]=r['fin']
    stores[sid]['rt'][i]=r['rt']
D=dict(weeks=weeks, stores=list(stores.values()))
json.dump(D, open('D_data.json','w'), ensure_ascii=False)
print('weeks:',weeks)
print('n stores:',len(D['stores']))

# 3) inyectar const D en index.html
if '--inject' in sys.argv:
    idx=open('index.html',encoding='utf-8').read()
    payload='const D='+json.dumps(D,ensure_ascii=False)+';'
    new=re.sub(r'const D=\{.*?\};', payload, idx, count=1, flags=re.S)
    assert new!=idx and 'const D={' in new, 'no se pudo inyectar const D'
    open('index.html','w',encoding='utf-8').write(new)
    print('const D inyectado en index.html')
