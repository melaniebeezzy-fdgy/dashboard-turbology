#!/usr/bin/env python3
import re, json

# ----- Venta mensual por ciudad (Abr-Sep 2026), del warehouse orders_consolidado -----
# (gmv, q) por ciudad y mes
CITY_ORDER=['Bogotá','Medellín','Cali','Barranquilla','Bucaramanga','Cartagena']
data={
 'Abr':{'Bogotá':(568183600,12390),'Medellín':(423614300,8734),'Bucaramanga':(92824300,2109),'Cali':(50914400,1128),'Cartagena':(40886800,866),'Barranquilla':(31771600,824)},
 'May':{'Bogotá':(773943800,16383),'Medellín':(391912000,8080),'Bucaramanga':(96630600,2198),'Barranquilla':(71141200,1666),'Cali':(64383600,1427),'Cartagena':(38235900,821)},
 'Jun':{'Bogotá':(888165600,18449),'Medellín':(392778300,8015),'Cali':(106256100,2375),'Barranquilla':(100829200,2437),'Bucaramanga':(98055400,2246),'Cartagena':(46314500,1035)},
 'Jul':{'Bogotá':(881257700,18281),'Medellín':(366460900,7527),'Cali':(113080100,2536),'Barranquilla':(107256800,2577),'Bucaramanga':(102257700,2353),'Cartagena':(46050700,993)},
 'Ago':{'Bogotá':(980722400,20273),'Medellín':(431885600,8834),'Barranquilla':(120989700,2917),'Bucaramanga':(102702600,2352),'Cali':(100743600,2191),'Cartagena':(38028900,814)},
 'Sep':{'Bogotá':(298063600,6222),'Medellín':(122146800,2538),'Barranquilla':(38323000,921),'Bucaramanga':(26759900,638),'Cali':(24061300,543),'Cartagena':(12774000,276)},
}
MV=['Abr','May','Jun','Jul','Ago','Sep']
gmv={'ALL':[]}; ord_={'ALL':[]}
for c in CITY_ORDER: gmv[c]=[]; ord_[c]=[]
for mo in MV:
    tot_g=tot_o=0
    for c in CITY_ORDER:
        g,q=data[mo].get(c,(0,0))
        gmv[c].append(g); ord_[c].append(q); tot_g+=g; tot_o+=q
    gmv['ALL'].append(tot_g); ord_['ALL'].append(tot_o)

# ----- Venta mensual por marca (Top 5 por GMV total, Abr-Sep) -----
# gmv por marca y mes
brand_m={
 'Abr':{'AVOCALIA':210993400,'Burritos & Co':212282000,'La Cuadra':154977600,'Brunch & Munch':67340200,'Green House':53092000},
 'May':{'AVOCALIA':243536700,'Burritos & Co':179801300,'La Cuadra':153801700,'Brunch & Munch':151577400,'Green House':76070600},
 'Jun':{'AVOCALIA':254099600,'Burritos & Co':178086800,'La Cuadra':158361400,'Brunch & Munch':161744600,'Green House':110608300},
 'Jul':{'AVOCALIA':269801100,'Burritos & Co':182090300,'La Cuadra':134276900,'Brunch & Munch':159594100,'Green House':118166400},
 'Ago':{'AVOCALIA':350893600,'Burritos & Co':192340700,'La Cuadra':162680800,'Brunch & Munch':191091800,'Green House':122464800},
 'Sep':{'AVOCALIA':119075300,'Burritos & Co':62438400,'La Cuadra':50033800,'Brunch & Munch':57203000,'Green House':39191100},
}
# label -> matcher (substring lower) + exclusion for coverage from D
brands=[
 {'name':'Avocalia','m':'avocalia','ex':''},
 {'name':'Burritos & Co','m':'burritos & co','ex':''},
 {'name':'La Cuadra','m':'la cuadra','ex':'desayuno'},
 {'name':'Brunch & Munch','m':'brunch','ex':''},
 {'name':'Green House','m':'green house','ex':''},
]
key={'Avocalia':'AVOCALIA','Burritos & Co':'Burritos & Co','La Cuadra':'La Cuadra','Brunch & Munch':'Brunch & Munch','Green House':'Green House'}
for b in brands:
    b['gmv']=[brand_m[mo][key[b['name']]] for mo in MV]

MO={
 'mv':MV,
 'cities':CITY_ORDER,
 'partialIdx':len(MV)-1,      # Sep parcial
 'gmv':gmv,'ord':ord_,
 'brands':brands,
 # meses con histórico de RTWT/cobertura/polígonos (desde mayo). Se derivan de W en JS,
 # pero fijamos las etiquetas visibles:
 'rm':['May','Jun','Jul','Ago','Sep'],
 'rmPartialIdx':4,            # Sep parcial (1 semana)
}
js='const MO='+json.dumps(MO,ensure_ascii=False)+';\n'

h=open('index_co.html',encoding='utf-8').read()
# quitar inyección previa si existe
h=re.sub(r'/\*MONTHLY_START\*/.*?/\*MONTHLY_END\*/','',h,flags=re.S)
anchor='const W=D.weeks'
assert anchor in h
h=h.replace(anchor,'/*MONTHLY_START*/'+js+'/*MONTHLY_END*/\n'+anchor,1)
open('index_co.html','w',encoding='utf-8').write(h)
print('MO inyectado. venta ALL:',gmv['ALL'])
print('brands:',[b['name'] for b in brands])
