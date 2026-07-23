# Dashboard Turbo México (snapshot)

`index_mx.html` es la versión México, adaptada del de Colombia. La data de México es un
**snapshot** (un corte con comparación vs. semana pasada), no una serie semanal, así que
**no** tiene las gráficas de tendencia semanal ni el heatmap. Sí tiene: KPIs (RTWT actual
vs. semana pasada, cobertura, distribución de polígonos), tablas por ciudad y por cocina,
y análisis de órdenes (Pareto, top 5, top por cocina, "dónde flojean").

## Actualizar

1. Baja el archivo de México como `FOODOLOGY.xlsx` en esta carpeta (hoja `DETALLE`).
2. Corre: `python3 build_mx.py FOODOLOGY.xlsx --inject`
   - Extrae la **cocina** de cada tienda (Queue ID + nombre de tienda) → `store2cocina_mx.json`.
   - Calcula KPIs, cobertura, distribución, tablas y Pareto por ciudad e inyecta el bloque
     `const MX` en `index_mx.html` (entre `/*MX_DATA_START*/ … /*MX_DATA_END*/`).
   - Deja también `mx_data.json`.

## Notas de la data de México
- Tamaños (`FINAL SIZE` / `Current Size`) vienen mezclados: `1.0` = 1 km. Se normaliza a metros.
- `Avg. RTWT` = RTWT actual; `LW_RTWT` = semana pasada (para el Δ). No hay cobertura de la
  semana pasada, así que la cobertura solo se muestra actual.
- Órdenes están en la misma hoja (no hay hoja de ventas aparte).
- **Cocina** se deriva del nombre; el `City Name` del origen tiene algunos errores puntuales
  (ej. una tienda de Azcapotzalco marcada como Monterrey) que se reflejan tal cual.
