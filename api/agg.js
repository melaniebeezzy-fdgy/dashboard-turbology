// GET /api/agg  — Agregados por cocina·marca·día (reemplazo futuro de FDGY2).
// Toda la agregación ocurre en SQL (GROUP BY). No trae órdenes crudas al navegador.
// Params:  country=CO|MX|PE  from=YYYY-MM-DD  to=YYYY-MM-DD  [kitchen=...] [op=...(no-op por ahora)]
// Shape de salida (compatible con FDGY2[pais]):
//   { country, from, to, days:[ISO...], K:[cocinas], B:[marcas],
//     R:[[ki,bi,di,n,c7,c79,c9,cavg,rtsum,rtcnt], ...] }
import { guard, parseCountry, parseRange, cleanStr, getClient, setCache, sendJson, httpError, serverError, BASE_WHERE, RTWT_EXPR } from './_db.js';

export default async function handler(req, res) {
  if (!guard(req, res)) return;
  const q = req.query || {};
  const country = parseCountry(q);
  if (!country) return httpError(res, 400, 'Parámetro country inválido (usa CO, MX o PE).');
  const r = parseRange(q);
  if (r.err) return httpError(res, 400, r.err);
  const kitchen = cleanStr(q.kitchen);

  const params = [country, r.from, r.to];
  let where = BASE_WHERE;
  if (kitchen) { params.push(kitchen); where += ` AND o.kitchen=$${params.length}`; }

  // Buckets de cocción (≤7 / 7–9 / >9), promedio de cocción, y RTWT (suma + conteo).
  const sql = `
    SELECT o.kitchen AS k, o.brand AS b, o.order_day::text AS d,
      COUNT(*)::int AS n,
      SUM(CASE WHEN o.minutes_cooking_time<=7 THEN 1 ELSE 0 END)::int AS c7,
      SUM(CASE WHEN o.minutes_cooking_time>7 AND o.minutes_cooking_time<=9 THEN 1 ELSE 0 END)::int AS c79,
      SUM(CASE WHEN o.minutes_cooking_time>9 THEN 1 ELSE 0 END)::int AS c9,
      ROUND(AVG(o.minutes_cooking_time),1)::float AS cavg,
      ROUND(SUM(${RTWT_EXPR}),1)::float AS rtsum,
      COUNT(${RTWT_EXPR})::int AS rtcnt
    FROM fdgy_views.orders_consolidado o
    LEFT JOIN fdgy_views.ontime_infull_order oi ON oi.order_id = o.id
    WHERE ${where}
    GROUP BY o.kitchen, o.brand, o.order_day`;

  let client;
  try {
    client = await getClient();
    const rows = (await client.query(sql, params)).rows;

    // Índices compactos. days = lista continua from..to (di = offset de día).
    const days = [];
    for (let d = new Date(r.from + 'T00:00:00Z'); d <= new Date(r.to + 'T00:00:00Z'); d = new Date(d.getTime() + 86400000)) {
      days.push(d.toISOString().slice(0, 10));
    }
    const dIx = new Map(days.map((d, i) => [d, i]));
    const K = [], Ki = new Map(), B = [], Bi = new Map(), R = [];
    for (const x of rows) {
      let ki = Ki.get(x.k); if (ki === undefined) { ki = K.push(x.k) - 1; Ki.set(x.k, ki); }
      let bi = Bi.get(x.b); if (bi === undefined) { bi = B.push(x.b) - 1; Bi.set(x.b, bi); }
      const di = dIx.get(String(x.d).slice(0, 10));
      if (di === undefined) continue;
      R.push([ki, bi, di, x.n | 0, x.c7 | 0, x.c79 | 0, x.c9 | 0,
        x.cavg == null ? null : x.cavg, x.rtsum == null ? 0 : x.rtsum, x.rtcnt | 0]);
    }
    setCache(res, 3600);
    sendJson(res, { country, from: r.from, to: r.to, days, K, B, R });
  } catch (e) {
    return serverError(res, e, 'agg');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
