// GET /api/detail  — Detalle orden-por-orden (reemplazo futuro de FDGYD).
// Devuelve solo las columnas que usa el dashboard (sin PII). RTWT con la lógica actual.
// Params: country=CO|MX|PE  from=YYYY-MM-DD  to=YYYY-MM-DD  [kitchen=] [brand=] [limit=] [offset=]
// Paginación por bloques: el cliente pide bloques (limit) con offset creciente hasta que
// un bloque devuelve < limit (hasMore=false). Evita descargar todo el período de una vez.
// Shape de salida (compatible con FDGYD[pais]):
//   { from, to, K:[cocinas], B:[marcas], days:[ISO...], O:[[ki,bi,di,hr,oid,cook,rt],...], n, offset, hasMore }
import { guard, parseCountry, parseRange, cleanStr, clampLimit, getClient, setCache, sendJson, httpError, serverError, BASE_WHERE, RTWT_EXPR, COOK_EXPR } from './_db.js';

export default async function handler(req, res) {
  if (!guard(req, res)) return;
  const q = req.query || {};
  const country = parseCountry(q);
  if (!country) return httpError(res, 400, 'Parámetro country inválido (usa CO, MX o PE).');
  const r = parseRange(q);
  if (r.err) return httpError(res, 400, r.err);
  const kitchen = cleanStr(q.kitchen), brand = cleanStr(q.brand);
  const limit = clampLimit(q.limit);
  const offset = Math.max(0, Math.min(5000000, parseInt(q.offset, 10) || 0));

  const params = [country, r.from, r.to];
  let where = BASE_WHERE;
  if (kitchen) { params.push(kitchen); where += ` AND o.kitchen=$${params.length}`; }
  if (brand) { params.push(brand); where += ` AND o.brand=$${params.length}`; }
  params.push(limit); const limIx = params.length;
  params.push(offset); const offIx = params.length;

  // Orden estable (incluye provider_order_id) para que la paginación por offset sea determinista.
  const sql = `
    SELECT o.kitchen AS k, o.brand AS b, o.order_day::text AS d,
      FLOOR(o.order_hour)::int AS hr,
      o.provider_order_id AS oid,
      ROUND((${COOK_EXPR})::numeric,2)::float AS cook,
      CASE WHEN oi.provider_delivered_to_domiciliary IS NULL OR o.domiciliary_in_store IS NULL
           THEN NULL ELSE ROUND((${RTWT_EXPR})::numeric,2)::float END AS rt,
      ROUND(o.minutes_received_to_destination,1)::float AS ot,
      -- responsable demora: clasifica la demora con timestamps reales.
      -- InicioPenalizacion = MAX(order_date_local+5min, domiciliary_in_store) (igual que RTWT; in_store NULL -> solo recv+5).
      -- Kitchen_Wait = MAX(order_state_waiting_for_delivery - InicioPenalizacion, 0)
      -- RT_Wait      = MAX(domiciliary_did_take - order_state_waiting_for_delivery, 0)
      -- Los NULL se tratan explícitamente (no se convierten a 0): sin waiting -> SIN DATOS;
      -- waiting pero sin NINGÚN evento del RT (in_store y did_take null) -> SIN TRACKING (no hay cómo asignar responsabilidad);
      -- waiting, RT llegó a tienda (in_store) pero no tomó (did_take null) -> LISTO_SIN_TOMA_RT.
      CASE
        WHEN o.order_state_waiting_for_delivery IS NULL THEN 'SIN DATOS'
        WHEN o.domiciliary_did_take IS NULL AND o.domiciliary_in_store IS NULL THEN 'SIN TRACKING'
        WHEN o.domiciliary_did_take IS NULL THEN 'LISTO_SIN_TOMA_RT'
        WHEN GREATEST(0, EXTRACT(EPOCH FROM (o.order_state_waiting_for_delivery - GREATEST(o.order_date_local + interval '5 minute', o.domiciliary_in_store)))/60.0) > 0
         AND GREATEST(0, EXTRACT(EPOCH FROM (o.domiciliary_did_take - o.order_state_waiting_for_delivery))/60.0) > 0 THEN 'MIXTO'
        WHEN GREATEST(0, EXTRACT(EPOCH FROM (o.order_state_waiting_for_delivery - GREATEST(o.order_date_local + interval '5 minute', o.domiciliary_in_store)))/60.0) > 0 THEN 'COCINA'
        WHEN GREATEST(0, EXTRACT(EPOCH FROM (o.domiciliary_did_take - o.order_state_waiting_for_delivery))/60.0) > 0 THEN 'RT'
        ELSE 'SIN ESPERA' END AS resp,
      CASE WHEN o.is_complaint=1 THEN 1 ELSE 0 END AS q   -- 1 = la orden tuvo queja (InFull)
    FROM fdgy_views.orders_consolidado o
    LEFT JOIN fdgy_views.ontime_infull_order oi ON oi.order_id = o.id
    WHERE ${where}
    ORDER BY o.order_day, o.order_date_local, o.provider_order_id
    LIMIT $${limIx} OFFSET $${offIx}`;

  let client;
  try {
    client = await getClient();
    const rows = (await client.query(sql, params)).rows;

    const K = [], Ki = new Map(), B = [], Bi = new Map(), days = [], Di = new Map(), O = [];
    for (const x of rows) {
      let ki = Ki.get(x.k); if (ki === undefined) { ki = K.push(x.k) - 1; Ki.set(x.k, ki); }
      let bi = Bi.get(x.b); if (bi === undefined) { bi = B.push(x.b) - 1; Bi.set(x.b, bi); }
      const ds = String(x.d).slice(0, 10);
      let di = Di.get(ds); if (di === undefined) { di = days.push(ds) - 1; Di.set(ds, di); }
      O.push([ki, bi, di, x.hr == null ? null : (x.hr | 0), String(x.oid),
        x.cook == null ? null : x.cook, x.rt == null ? null : x.rt, x.ot == null ? null : x.ot, x.resp || null, x.q | 0]);
    }
    setCache(res, 3600);
    sendJson(res, { from: r.from, to: r.to, K, B, days, O, n: O.length, offset, hasMore: O.length >= limit });
  } catch (e) {
    return serverError(res, e, 'detail');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
