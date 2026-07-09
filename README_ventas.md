# Actualizar el dashboard con nuevos datos (RTWT / polígonos / ventas)

1. (Claude) vuelve a bajar la hoja "Turbology" de Drive como `Turbology.xlsx` en esta carpeta
   (tiene las hojas `Raw` = RTWT/polígonos y `Raw ventas` = órdenes).
2. Corre, en este orden:
   - `python3 build_rtwt.py Turbology.xlsx --inject`
     - Regenera `Turbology_con_cocina.csv` (Raw depurado: metros + cocina) y el bloque
       `const D=…` (RTWT/polígonos por semana) **inyectándolo** en `index.html`.
     - Anexa automáticamente la última semana disponible en `Raw`.
   - `python3 build_ventas.py Turbology.xlsx`
     - Recalcula Pareto y rankings de la última semana de ventas e **inyecta los datos**
       en `index.html` (entre `/*VENTAS_DATA_START*/ … /*VENTAS_DATA_END*/`).
     - Deja también `ventas_data.json`.
3. Actualiza a mano las etiquetas de fecha en el texto de `index.html` si cambió la semana
   de cierre (busca la fecha vieja y reemplázala, p. ej. `29 jun` → nueva; `22 jun` → anterior).
4. `cp index.html Dashboard_Turbo_Foodology.html`
5. `git add -A && git commit -m "datos <fecha>" && git push`  → Vercel redepliega solo.

Notas:
- `build_rtwt.py` normaliza tamaños a metros (×1000 si viene en km), mapea tienda→cocina con
  `store2cocina.json`, descarta RTWT inválidos (>60, celdas con seriales de fecha) y aplica el
  mapeo fijo de la semana 2026-05-11 (que quedó codificada gruesa {1,2,3} km → 1000/2400/3000).
- El UI (secciones/menú) se insertó una sola vez con `_inject_ventas_ui.py`; no hay que volver a correrlo.
