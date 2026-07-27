# Cómo se arma el dashboard (Colombia + México en un solo `index.html`)

El link que se comparte es **`index.html`**, que es un archivo **combinado** con pestañas
🇨🇴 Colombia / 🇲🇽 México. Se genera a partir de dos fuentes que NO se editan a mano:

- `index_co.html` — dashboard de Colombia (lógica de 4 semanas móviles, cobertura
  coverageCurrent/Result, penalización, filtro de ciudad + ops, ventas KDS).
- `index_mx.html` — dashboard de México (comparativo de 2 semanas: RTWT actual vs semana
  pasada, cobertura actual vs propuesta, ventas KDS con WoW, filtro de ciudad + ops).

## Flujo de actualización

### Colombia
1. `rt_data_v2.csv` (hoja `Tiendas` del Sheet foodology_rt_data_v2) + `KDS_ventas.xlsx` (ventas CO).
2. `python3 build_col_v2.py rt_data_v2.csv --inject`  → inyecta `const D` en **index_co.html**.
3. `python3 build_ventas.py KDS_ventas.xlsx`          → inyecta `const VENTAS` en **index_co.html**.

### México
1. `FOODOLOGY.xlsx` (RTWT actual+LW, polígono actual), `mx_polygon_proposal.xlsx`
   (Size Proposal), `KDS_ventas_mx.xlsx` (ventas MX con ops).
2. `python3 build_mx.py FOODOLOGY.xlsx --inject`       → inyecta `const MX` en **index_mx.html**.

### Perú
1. `PE_rtwt.xlsx` (RTWT por tienda/semana, hoja Resumen) y `PE_cobertura.xlsx` (polígono por tienda).
2. `python3 build_pe.py --inject`  → inyecta `const PE` en **index_pe.html**.
   - Usa la **última semana** (29-jun) vs anterior (22-jun); estados 4 niveles y penalización
     (>8 min → 0% cobertura), igual que Colombia pero sin promedio de 4 semanas.
   - Perú no trae ventas ni ops todavía (el KDS recibido era de Colombia).

### Combinar (siempre al final)
`python3 merge_mx.py`  → genera **index.html** (CO + MX + PE con pestañas).
`cp index.html Dashboard_Turbo_Foodology.html`

Luego: `git add -A && git commit -m "..." && git push` (Vercel redepliega).

## Notas
- México mantiene su lógica snapshot (2 semanas), sin el histórico largo de Colombia.
- Mapeos cocina→ops: `cocina2ops.json` (CO), `cocina2ops_mx.json` (MX).
- El filtro de ops y el de ciudad son excluyentes (elegir uno limpia el otro), en ambos países.
- `merge_mx.py` prefija los IDs de México con `mx-` y encapsula su JS en un IIFE para que no
  choque con Colombia. Si cambias el HTML/JS de un país, edita su archivo fuente y vuelve a
  correr `merge_mx.py`.
