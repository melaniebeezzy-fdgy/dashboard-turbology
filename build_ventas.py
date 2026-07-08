#!/usr/bin/env python3
"""
Regenera el bloque de datos de VENTAS embebido en index.html a partir del
Google Sheet "Turbology" (hojas 'Raw' y 'Raw ventas').

Uso:
  python3 build_ventas.py Turbology.xlsx   # produce ventas_data.json e inyecta en index.html

La marca de datos (fecha de ventas usada, etc.) queda en el JSON.
"""
import sys, json, csv, re, unicodedata, datetime, os
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Turbology.xlsx")
STORE2COC = os.path.join(HERE, "store2cocina.json")

# ---- normalización de marcas (une ventas <-> RTWT) ----
def norm(s):
    if s is None: return ""
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode().lower()
    s = s.replace('&',' ').replace('.',' ').replace('-',' ')
    s = re.sub(r'\bby\b.*$', ' ', s)          # "... by maluma/dorito/robegrill"
    toks_drop = {'turbo','fdl','fd','court','sandwiches','pase'}
    s = ' '.join(t for t in re.sub(r'[^a-z0-9 ]',' ',s).split() if t not in toks_drop)
    return s.strip()

ALIAS = {  # norm ventas -> norm RTWT canónico
    'el jefe':'sanduches el jefe',
    'san jeronimo':'helados san jeronimo',
    'almuerzos de la casa':'almuerzos d la casa',
    'cinnabon foodology':'cinnabon',
}
def canon(s):
    n = norm(s); return ALIAS.get(n, n)

# ---- cocina desde kitchen_id de ventas ("69 ARRECIFE" -> "Arrecife") ----
def coc_norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9 ]',' ', s).strip()
def kitchen_to_cocina(kid, cocina_names):
    base = re.sub(r'^\s*\d+\s*', '', str(kid)).strip()       # quita número
    base = base.replace(' CINNABON','')
    nb = coc_norm(base)
    for c in cocina_names:
        cn = coc_norm(c)
        if cn == nb or nb in cn or cn.split(' /')[0]==nb: return c
    return base.title()

def to_float(x):
    try: return float(str(x).replace(',',''))
    except: return None

def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    store2coc = json.load(open(STORE2COC, encoding='utf-8')) if os.path.exists(STORE2COC) else {}

    # ---------- RTWT / cobertura (CSV ya limpio, en metros, mapeado a cocina) ----------
    # Se usa Turbology_con_cocina.csv (misma data de la hoja Raw ya depurada:
    # RTWT sin códigos de error y Final Size en metros). Última semana disponible.
    rtc_path = os.path.join(HERE, 'Turbology_con_cocina.csv')
    rtc = list(csv.DictReader(open(rtc_path, encoding='utf-8-sig')))
    def rget(row,*names):
        for n in names:
            if n in row: return row[n]
        return None
    def parse_wk(s):
        try: return datetime.datetime.strptime(s.strip(),'%d/%m/%Y')
        except: return None
    wk_of={r.get('Semana') or list(r.values())[0]: parse_wk(r.get('Semana') or list(r.values())[0]) for r in rtc}
    maxd=max((d for d in wk_of.values() if d), default=None)
    rt_rows=[]
    for r in rtc:
        wk=r.get('Semana') or list(r.values())[0]
        if wk_of.get(wk)!=maxd: continue
        brand=rget(r,'Marca'); coc=rget(r,'Cocina') or 'Otra'
        rtv=to_float(rget(r,'Avg RTWT (limpio)')); fin=to_float(rget(r,'Final Size (m)'))
        rt_rows.append(dict(cb=canon(brand), coc=coc, city=rget(r,'Ciudad'), rt=rtv, fin=fin))
    rtwt_week = maxd.strftime('%d/%m/%Y') if maxd else '—'

    # filas RTWT semana actual y anterior (con ciudad); se indexan por ciudad en compute()
    prevd=max((d for d in wk_of.values() if d and d<maxd), default=None)
    rt_prev_rows=[]
    if prevd is not None:
        for r in rtc:
            wk=r.get('Semana') or list(r.values())[0]
            if wk_of.get(wk)!=prevd: continue
            rt_prev_rows.append(dict(cb=canon(rget(r,'Marca')), coc=rget(r,'Cocina') or 'Otra',
                                     city=rget(r,'Ciudad'),
                                     rt=to_float(rget(r,'Avg RTWT (limpio)')),
                                     fin=to_float(rget(r,'Final Size (m)'))))

    # ---------- VENTAS (hoja Raw ventas) ----------
    v = list(wb['Raw ventas'].iter_rows(values_only=True))
    vh = [str(h).strip() if h else '' for h in v[0]]
    vi = {h:i for i,h in enumerate(vh)}
    def vcol(row,name):
        i=vi.get(name); return row[i] if (i is not None and i<len(row)) else None
    recs=[]; days=set()
    for r in v[1:]:
        d=vcol(r,'date')
        if not isinstance(d, datetime.datetime):
            try: d=datetime.datetime.fromisoformat(str(d))
            except: continue
        days.add(d.date())
        recs.append((d.date(), vcol(r,'city'), vcol(r,'kitchen_id'), vcol(r,'brand'), to_float(vcol(r,'Total orders')) or 0))
    lastday=max(days); firstlw=lastday-datetime.timedelta(days=6)
    sales_week=f"{firstlw.strftime('%d/%m')}–{lastday.strftime('%d/%m/%Y')}"
    pfirst=firstlw-datetime.timedelta(days=7); plast=firstlw-datetime.timedelta(days=1)
    lw_all=[x for x in recs if firstlw<=x[0]<=lastday]
    pw_all=[x for x in recs if pfirst<=x[0]<=plast]

    cocina_names=sorted(set(x['coc'] for x in rt_rows))
    def pretty(name): return name.title() if name.isupper() else name
    disp={}
    for _,_,_,b,_ in lw_all: disp.setdefault(canon(b), pretty(b.strip()))

    def indexrt(rows):
        bc={}
        for x in rows:
            d=bc.setdefault((x['cb'],x['coc']), {'rt':[], 'fin':[]})
            if x['rt'] is not None: d['rt'].append(x['rt'])
            if x['fin'] is not None: d['fin'].append(x['fin'])
        return bc
    def aggf(bc,key):
        d=bc.get(key)
        if not d: return (None,None)
        rt=sum(d['rt'])/len(d['rt']) if d['rt'] else None
        fin=sum(d['fin'])/len(d['fin']) if d['fin'] else None
        return (rt,fin)

    def compute(city):
        inc=lambda rc: (city is None or rc==city)
        lw=[x for x in lw_all if inc(x[1])]
        if not lw: return None
        pw=[x for x in pw_all if inc(x[1])]
        bc=indexrt([r for r in rt_rows if inc(r['city'])])
        bcp=indexrt([r for r in rt_prev_rows if inc(r['city'])])
        agg=lambda k: aggf(bc,k); agg_prev=lambda k: aggf(bcp,k)
        bt={}
        for _,_,_,b,o in lw: bt[canon(b)]=bt.get(canon(b),0)+o
        tot=sum(bt.values()) or 1
        bt_prev={}
        for _,_,_,b,o in pw: bt_prev[canon(b)]=bt_prev.get(canon(b),0)+o
        pareto=[]; cum=0
        for cb,o in sorted(bt.items(), key=lambda x:-x[1]):
            cum+=o
            pareto.append(dict(brand=disp.get(cb,cb), cb=cb, orders=round(o),
                               pct=round(100*o/tot,1), cum=round(100*cum/tot,1)))
        top5=[p['cb'] for p in pareto[:5]]
        cbk={}
        for _,_,kid,b,o in lw:
            coc=kitchen_to_cocina(kid, cocina_names)
            cbk[(coc,canon(b))]=cbk.get((coc,canon(b)),0)+o
        cocinas=sorted(set(k[0] for k in cbk))
        per_cocina={}; rank_in={}
        for coc in cocinas:
            items=sorted([(cb,o) for (c,cb),o in cbk.items() if c==coc], key=lambda x:-x[1])
            tt=sum(o for _,o in items) or 1
            per_cocina[coc]=[dict(brand=disp.get(cb,cb), cb=cb, orders=round(o), pct=round(100*o/tt,1)) for cb,o in items[:5]]
            for i,(cb,o) in enumerate(items): rank_in[(coc,cb)]=(i+1,round(o),len(items))
        top5_detail=[]
        for cb in top5:
            rows=[]
            for coc in cocinas:
                o=cbk.get((coc,cb))
                if not o: continue
                rk,orders,ncb=rank_in[(coc,cb)]
                rt,fin=agg((cb,coc))
                covpct=None if fin is None else round(100*fin/3000,1)
                sev='ok'
                if (rt is not None and rt>3) or (fin is not None and fin<=1000): sev='bad'
                elif (rt is not None and rt>2) or (fin is not None and fin<=2100): sev='warn'
                rows.append(dict(coc=coc, orders=orders, rank=rk, nbrands=ncb,
                                 rt=None if rt is None else round(rt,2),
                                 size=None if fin is None else round(fin),
                                 cov=covpct, sev=sev))
            rows.sort(key=lambda x:-x['orders'])
            wr=[r for r in rows if r['rt'] is not None]
            best=min(wr,key=lambda x:x['rt'])['coc'] if wr else None
            worst=max(wr,key=lambda x:x['rt'])['coc'] if wr else None
            ar=[r['rt'] for r in rows if r['rt'] is not None]
            ac=[r['cov'] for r in rows if r['cov'] is not None]
            avg_rt=round(sum(ar)/len(ar),2) if ar else None
            avg_cov=round(sum(ac)/len(ac),1) if ac else None
            pr=[]; pc=[]
            for r in rows:
                rtp,finp=agg_prev((cb,r['coc']))
                if rtp is not None: pr.append(rtp)
                if finp is not None: pc.append(100*finp/3000)
            avg_rt_prev=sum(pr)/len(pr) if pr else None
            avg_cov_prev=sum(pc)/len(pc) if pc else None
            drt=None if (avg_rt is None or avg_rt_prev is None) else round(avg_rt-avg_rt_prev,2)
            dcov=None if (avg_cov is None or avg_cov_prev is None) else round(avg_cov-avg_cov_prev,1)
            oprev=bt_prev.get(cb,0)
            wow=None if not oprev else round(100*(bt[cb]-oprev)/oprev,1)
            top5_detail.append(dict(brand=disp.get(cb,cb), cb=cb, orders=round(bt[cb]),
                wow=wow, orders_prev=round(oprev), avg_rt=avg_rt, avg_cov=avg_cov,
                drt=drt, dcov=dcov, best=best, worst=worst, rows=rows))
        return dict(meta=dict(total_orders=round(tot), n_brands=len(pareto),
                    top5_share=round(sum(bt[c] for c in top5)/tot*100,1)),
                    pareto=pareto, top5=top5, top5_detail=top5_detail,
                    per_cocina=per_cocina, cocinas=cocinas)

    cities=sorted(set(x[1] for x in lw_all if x[1]))
    data={'ALL':compute(None)}
    for c in cities:
        rc=compute(c)
        if rc: data[c]=rc
    payload=dict(sales_week=sales_week, rtwt_week=rtwt_week,
                 generated=datetime.date.today().isoformat(),
                 cities=['ALL']+cities, data=data)

    json.dump(payload, open(os.path.join(HERE,'ventas_data.json'),'w'), ensure_ascii=False, indent=1)

    # ---- inyecta el bloque de datos en index.html (entre marcadores) ----
    idx=os.path.join(HERE,'index.html')
    if os.path.exists(idx):
        html=open(idx,encoding='utf-8').read()
        A='/*VENTAS_DATA_START*/'; B='/*VENTAS_DATA_END*/'
        block=A+'const VENTAS='+json.dumps(payload,ensure_ascii=False)+';'+B
        if A in html and B in html:
            html=re.sub(re.escape(A)+'.*?'+re.escape(B), lambda m: block, html, flags=re.S)
            open(idx,'w',encoding='utf-8').write(html)
            print('index.html: bloque VENTAS actualizado')
        else:
            print('index.html: marcadores no encontrados (aún no inyectado el HTML de Ventas)')

    # resumen validación
    A=payload['data']['ALL']
    print("VENTAS", sales_week, "| RTWT", rtwt_week, "| ciudades:", payload['cities'])
    for ck in payload['cities']:
        D=payload['data'].get(ck)
        if not D: continue
        n80=next((i+1 for i,p in enumerate(D['pareto']) if p['cum']>=80), len(D['pareto']))
        print(f"  [{ck:12}] orders={D['meta']['total_orders']:5} marcas={D['meta']['n_brands']:2} top5={D['meta']['top5_share']:5.1f}% n80={n80} top5={[t['brand'] for t in D['top5_detail']]}")
    return payload

if __name__=='__main__':
    main()
