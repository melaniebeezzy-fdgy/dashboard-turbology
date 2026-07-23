# Colombia v2 — lógica de 4 semanas móviles (stakeholder)

Desde jul-2026 la evaluación de Colombia sigue la lógica del dashboard del stakeholder:

- Se mira el **promedio móvil de RTWT de las últimas 4 semanas** (no solo la última).
- La **cobertura** de cada tienda = su **polígono asignado** (`coverageCurrent`), que **no cambia**
  salvo penalización.
- Si el **promedio de 4 semanas supera 8 min** → la tienda queda en **0% de cobertura** y recibe
  penalización durante 4 semanas (estado 🔴 Crítico). Para recuperarla: plan de acción + seguimiento.
- Estados por promedio de 4 semanas: 🟢 Saludable `<2` · 🟡 Atención `2–5` · 🟠 Riesgo `5–8` ·
  🔴 Crítico `>8` · ⚪ Sin datos. Meta operativa RT ≤ 2 min.

## Fuente de datos
Google Sheet **foodology_rt_data_v2** (hoja `Tiendas`), columnas:
`brand, storeId, storeName, avg4w, weeksData, coverageCurrent, coverageResult, diffGoal, devPct,
status, losesCoverage, trend, w1, w2, w3, w4` (w1..w4 = 22-jun, 29-jun, 06-jul, 13-jul).

## Actualizar
1. Descarga la hoja `Tiendas` como `rt_data_v2.csv` en esta carpeta (File ▸ Download ▸ CSV).
2. Corre: `python3 build_col_v2.py rt_data_v2.csv --inject`
   - Fusiona el histórico viejo (may–jun 15, de `Turbology.xlsx`) con la ventana de 4 semanas nueva.
   - Polígono de las últimas 4 semanas = `coverageCurrent`; el resto de la lógica (promedio 4 sem,
     estados, penalización) la calcula el dashboard al vuelo.
   - Inyecta `const D` (11 semanas, con `cc`=coverageCurrent por tienda) en `index.html`.
3. `cp index.html Dashboard_Turbo_Foodology.html`
4. Publica (git add/commit/push).

Notas:
- `store2cocina.json` mapea Store ID → cocina; la ciudad sale de `Turbology.xlsx`.
- Tamaños en km (`1.0`, `2.4`…) se normalizan a metros; RTWT > 60 min se descarta (basura).

## Ventas + filtro de ops (KDS)
La data de ventas ahora viene del archivo **KDS** (hoja `Export`: `date, city, kitchen_id,
brand, Total orders, ops`). Trae la columna **ops** (responsable de operación).

1. Guarda el KDS como `KDS_ventas.xlsx` en esta carpeta.
2. Corre: `python3 build_col_v2.py rt_data_v2.csv --inject` (esto usa `cocina2ops.json` para
   poner el `op` de cada tienda en `const D`). El mapeo cocina→ops se genera del KDS; si cambian
   las cocinas/ops, regenéralo (ver más abajo).
3. Corre: `python3 build_ventas.py KDS_ventas.xlsx` → recalcula el Pareto/rankings de la última
   semana **por ciudad y por ops** e inyecta el bloque VENTAS.

El **filtro de ops** (barra superior) aplica a todo el dashboard. Al elegir un ops se limpia el
filtro de ciudad (y viceversa). Ops actuales: Leidy Pinzón, Laura Hernández, Diana Florez,
Álvaro Pulgarín, Juan Sebastián Bernal (Bogotá); Juan Pablo Gómez (costa/Cali/Bmga); Jose Luis
Rodriguez (Medellín).

Regenerar `cocina2ops.json` (si cambian kitchens/ops): mapea cada `kitchen_id` del KDS a la
cocina del dashboard (quitando el número y normalizando acentos) y le asigna su `ops`.
