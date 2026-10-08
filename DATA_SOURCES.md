# Fuentes de datos del dashboard (Fase 0A — inventario de generadores de snapshots)

> Objetivo: documentar qué proceso genera cada bloque embebido, para dejar de depender de
> ellos y poder usar los snapshots actuales como rollback. **No se borra nada todavía.**
> No hay cron ni GitHub Actions: toda la generación es **manual** (CLI, /admin o MCP).

## Bloques que se reemplazarán por API (Fase 2)

| Bloque | Marcador | Generador actual | Archivos que modifica | Cómo se ejecuta | Fuente de datos |
|---|---|---|---|---|---|
| **FDGY2** | `/*FDGY_START*/const FDGY2=` | **Ninguno en el repo** — se construyó **manualmente vía Claude/MCP** extrayendo de Redshift | `index.html`, `index_co.html` | Manual (sesión Claude + MCP) | Redshift: `fdgy_views.orders_consolidado` + `fdgy_views.ontime_infull_order` (agregado cocina·marca·día) |
| **FDGYD** | `/*FDGYD_START*/const FDGYD=` | **`api/orders-detail.js`** (serverless) + en la práctica también extracción manual MCP | `index.html`, `index_co.html` (commit a GitHub) | Botón "Cargar detalle" en **/admin** → POST a `api/orders-detail.js` | Redshift: `orders_consolidado` (+ join `ontime_infull_order` para RTWT) |
| **FDGYT** | `/*FDGYT_START*/const FDGYT=` | **Ninguno en el repo** — construido **manualmente vía Claude/MCP** | `index.html`, `index_co.html` | Manual (sesión Claude + MCP) | Redshift: `orders_consolidado` + `ontime_infull_order` (timeline por orden) |

**Procesos a detener para estos 3 bloques:** la extracción manual por Claude/MCP (FDGY2, FDGYT) y el flujo `/admin → orders-detail.js` (FDGYD). No hay jobs programados que desactivar.

## Otros bloques embebidos (fuera del alcance de Fase 2, documentados para referencia)

| Bloque | Marcador / const | Generador | Fuente |
|---|---|---|---|
| **D** (RTWT/polígonos/cobertura semanal CO) | `let D=` | `build_co_update.py` (lee un HTML "RT dashboard" subido) · `build_col_v2.py`/`build_rtwt.py` (de `Turbology.xlsx` / Google Sheet `foodology_rt_data_v2`) · ventas de la semana rellenadas por `api/publish.js` desde Redshift | **Mixto**: Excel/Sheets (polígono `cc`, ops `op`, RTWT) + Redshift (ventas por `order_week`). Config auxiliar: `store2cocina.json`, `cocina2ops.json` |
| **SALESWK / VENTAS_DATA** (venta semanal CO) | `/*SALESWK_*/` · `/*VENTAS_DATA_*/` | `build_ventas.py` | Excel `KDS_ventas.xlsx` (hoja Export) + `D_v2.json` + `store2cocina.json`/`cocina2ops.json` |
| **MONTHLY** (venta mensual CO) | `/*MONTHLY_START*/` | `inject_monthly.py` | **Valores hardcodeados** en el script (copiados de una consulta manual a `orders_consolidado`) |
| **MXDATA / const MX** | `/*MXDATA_*/` | `build_mx.py` y `build_mx_update.py`; `merge_mx.py` combina en `index.html` | Excel: `FOODOLOGY.xlsx`, `MX_rtwt.xlsx`, `mx_polygon_proposal.xlsx`, `KDS_ventas_mx.xlsx` (+ ventas opcional por SQL manual) |
| **PEDATA / const PE** | `/*PEDATA_*/` | `build_pe.py` | Excel: `PE_rtwt_v2.xlsx`, `PE_cobertura_v2.xlsx`, `PE_cobertura.xlsx`, `KDS_ventas_pe.xlsx` |

## Rollback
Los snapshots vigentes quedan embebidos en `index.html`, `index_co.html` y la copia
`Dashboard_Turbo_Foodology.html`. Mientras `USE_API_DATA=false`, el dashboard sigue
sirviéndolos tal cual.
