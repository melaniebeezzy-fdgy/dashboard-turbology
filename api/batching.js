// GET /api/batching — Agrupamiento de órdenes a un mismo RT (misma cocina, mismo día).
// Sesionización: órdenes consecutivas del mismo repartidor con ≤15 min entre recepciones = un grupo (lote).
// Dentro del lote, cada orden se clasifica por el gap al vecino más cercano del mismo grupo:
//   BUNDLE   = gap ≤ 60 s  (dos órdenes que entran casi juntas y salen en el mismo viaje)
//   BATCHING = 60 s < gap ≤ 15 min  (se unen al viaje pero con más de 1 min de diferencia)
// Solo órdenes con RT identificado (domiciliary no nulo) — es un piso (~53% de cobertura del RT).
// Params: country=CO|MX|PE  from=YYYY-MM-DD  to=YYYY-MM-DD  (rango inclusivo; máx 62 días)
// Shape: { country, from, to, bundleSec, rows:[[kitchen, total, b2,b3,b4, t2,t3,t4], ...] }
//   total = órdenes con RT; b* = órdenes en BUNDLE por tamaño de lote (2/3/4+); t* = órdenes en BATCHING por tamaño.
import { guard, parseCountry, parseDate, getClient, setCache, sendJson, httpError, serverError } from './_db.js';

const MAX_SPAN_DAYS = 62;
const BUNDLE_SEC = 60;   // ≤ 60 s entre órdenes = bundle; por encima (hasta 900 s) = batching

export default async function handler(req, res) {
  if (!guard(req, res)) return;
  const q = req.query || {};
  const country = parseCountry(q);
  if (!country) return httpError(res, 400, 'Parámetro country inválido (usa CO, MX o PE).');
  const from = parseDate(q.from), to = parseDate(q.to);
  if (!from || !to) return httpError(res, 400, 'Parámetros from/to obligatorios en formato YYYY-MM-DD.');
  if (from > to) return httpError(res, 400, 'from no puede ser mayor que to.');
  if ((new Date(to) - new Date(from)) / 86400000 > MAX_SPAN_DAYS) return httpError(res, 400, `Rango máximo ${MAX_SPAN_DAYS} días.`);

  const sql = `
    WITH consolidated AS (
      SELECT id, country, kitchen,
        ROW_NUMBER() OVER (PARTITION BY country, id ORDER BY order_date_local DESC) AS rn
      FROM fdgy_views.orders_consolidado
      WHERE country=$1 AND brand ILIKE '%Turbo%'
    ),
    base AS (
      SELECT o._id AS oid, o.kitchen_id, COALESCE(a.kitchen,'—') AS kitchen, o.domiciliary, o.received_at_local AS t,
        LAG(o.received_at_local) OVER (
          PARTITION BY o.country, o.kitchen_id, o.domiciliary, DATE_TRUNC('day', o.received_at_local)
          ORDER BY o.received_at_local, o._id) AS prev_t,
        LEAD(o.received_at_local) OVER (
          PARTITION BY o.country, o.kitchen_id, o.domiciliary, DATE_TRUNC('day', o.received_at_local)
          ORDER BY o.received_at_local, o._id) AS next_t
      FROM fdgy_views.orders o
      INNER JOIN consolidated a ON a.id=o._id AND a.country=o.country AND a.rn=1
      WHERE o.country=$1 AND o.provider_name='Rappi' AND o.domiciliary IS NOT NULL
        AND o.received_at_local >= $2 AND o.received_at_local < (CAST($3 AS date) + 1)
    ),
    marked AS (
      SELECT *,
        CASE WHEN prev_t IS NULL OR DATEDIFF(second, prev_t, t) > 900 THEN 1 ELSE 0 END AS newg,
        CASE WHEN prev_t IS NOT NULL AND DATEDIFF(second, prev_t, t) <= 900 THEN DATEDIFF(second, prev_t, t) END AS gprev,
        CASE WHEN next_t IS NOT NULL AND DATEDIFF(second, t, next_t) <= 900 THEN DATEDIFF(second, t, next_t) END AS gnext
      FROM base
    ),
    numbered AS (
      SELECT *, SUM(newg) OVER (
        PARTITION BY kitchen_id, domiciliary, DATE_TRUNC('day', t)
        ORDER BY t, oid ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS gnum FROM marked
    ),
    grp AS (
      SELECT *, DENSE_RANK() OVER (ORDER BY kitchen_id, domiciliary, DATE_TRUNC('day', t), gnum) AS batch_id FROM numbered
    ),
    gs AS (SELECT batch_id, COUNT(*) AS sz FROM grp GROUP BY batch_id),
    classified AS (
      SELECT g.kitchen, gs.sz,
        LEAST(COALESCE(g.gprev, 1000000), COALESCE(g.gnext, 1000000)) AS join_gap
      FROM grp g JOIN gs ON gs.batch_id=g.batch_id
    )
    SELECT kitchen,
      COUNT(*)::int AS total,
      SUM(CASE WHEN sz=2  AND join_gap<=${BUNDLE_SEC} THEN 1 ELSE 0 END)::int AS b2,
      SUM(CASE WHEN sz=3  AND join_gap<=${BUNDLE_SEC} THEN 1 ELSE 0 END)::int AS b3,
      SUM(CASE WHEN sz>=4 AND join_gap<=${BUNDLE_SEC} THEN 1 ELSE 0 END)::int AS b4,
      SUM(CASE WHEN sz=2  AND join_gap>${BUNDLE_SEC} AND join_gap<=900 THEN 1 ELSE 0 END)::int AS t2,
      SUM(CASE WHEN sz=3  AND join_gap>${BUNDLE_SEC} AND join_gap<=900 THEN 1 ELSE 0 END)::int AS t3,
      SUM(CASE WHEN sz>=4 AND join_gap>${BUNDLE_SEC} AND join_gap<=900 THEN 1 ELSE 0 END)::int AS t4
    FROM classified
    GROUP BY kitchen
    ORDER BY total DESC`;

  let client;
  try {
    client = await getClient();
    const rows = (await client.query(sql, [country, from, to])).rows
      .map(x => [x.kitchen == null ? '—' : String(x.kitchen), x.total | 0, x.b2 | 0, x.b3 | 0, x.b4 | 0, x.t2 | 0, x.t3 | 0, x.t4 | 0]);
    setCache(res, 3600);
    sendJson(res, { country, from, to, bundleSec: BUNDLE_SEC, rows });
  } catch (e) {
    return serverError(res, e, 'batching');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
