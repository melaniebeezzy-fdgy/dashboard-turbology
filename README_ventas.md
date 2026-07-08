# Actualizar el dashboard con nuevos datos de ventas / RTWT

1. (Claude) vuelve a bajar la hoja "Turbology" de Drive como `Turbology.xlsx` en esta carpeta.
2. Corre:  `python3 build_ventas.py Turbology.xlsx`
   - Recalcula el Pareto y rankings de la última semana e **inyecta los datos** en `index.html`
     (entre los marcadores `/*VENTAS_DATA_START*/ … /*VENTAS_DATA_END*/`).
   - Deja también `ventas_data.json` con el detalle.
3. `git add -A && git commit -m "ventas <fecha>" && git push`  → Vercel redepliega solo.

Notas:
- RTWT y cobertura salen de `Turbology_con_cocina.csv` (hoja Raw ya depurada, en metros y mapeada a cocina).
- El UI (secciones/menú) se insertó una sola vez con `_inject_ventas_ui.py`; no hay que volver a correrlo.
