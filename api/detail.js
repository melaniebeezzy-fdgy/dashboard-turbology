// GET /api/detail  — Detalle orden-por-orden (reemplazo futuro de FDGYD).
// Devuelve solo las columnas que usa el dashboard (sin PII). RTWT con la lógica actual.
// Params: country=CO|MX|PE  from=YYYY-MM-DD  to=YYYY-MM-DD  [kitchen=] [brand=] [limit=] [offset=]
// Paginación por bloques: el cliente pide bloques (limit) con offset creciente hasta que
// un bloque devuelve < limit (hasMore=false). Evita descargar todo el período de una vez.
// Shape de salida (compatible con FDGYD[pais]):
//   { from, to, K:[cocinas], B:[marcas], days:[ISO...], O:[[ki,bi,di,hr,oid,cook,rt],...], n, offset, hasMore }
import { guard, parseCountry, parseRange, cleanStr, clampLimit, getClient, setCache, sendJson, httpError, serverError, BASE_WHERE, RTWT_EXPR } from './_db.js';

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
      ROUND(o.minutes_cooking_time,1)::float AS cook,
      CASE WHEN oi.provider_delivered_to_domiciliary IS NULL OR o.domiciliary_in_store IS NULL
           THEN NULL ELSE ROUND((${RTWT_EXPR})::numeric,2)::float END AS rt,
      ROUND(o.minutes_received_to_destination,1)::float AS ot,
      CASE WHEN o.order_state_waiting_for_delivery IS NULL OR o.domiciliary_in_store IS NULL THEN NULL
           WHEN o.domiciliary_in_store > o.order_state_waiting_for_delivery THEN 'RT'
           ELSE 'COCINA' END AS resp
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
        x.cook == null ? null : x.cook, x.rt == null ? null : x.rt, x.ot == null ? null : x.ot, x.resp || null]);
    }
    setCache(res, 3600);
    sendJson(res, { from: r.from, to: r.to, K, B, days, O, n: O.length, offset, hasMore: O.length >= limit });
  } catch (e) {
    return serverError(res, e, 'detail');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
