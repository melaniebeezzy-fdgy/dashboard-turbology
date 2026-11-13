// GET /api/batching — Batching de RT: comandas que un mismo repartidor recoge en lote
// (misma cocina, mismo día, con ≤15 min entre recepciones). Sesionización igual al query de Ops.
// Solo órdenes con RT identificado (domiciliary no nulo) — es un piso (~53% de cobertura del RT).
// Params: country=CO|MX|PE  from=YYYY-MM-DD  to=YYYY-MM-DD  (rango inclusivo; máx 62 días)
// Shape: { country, from, to, rows:[[kitchen, total, n1, n2, n3, n4plus], ...] }
//   total = órdenes con RT; n1 = en lote de 1 (sola); n2/n3/n4plus = órdenes en lotes de ese tamaño.
import { guard, parseCountry, parseDate, getClient, setCache, sendJson, httpError, serverError } from './_db.js';

const MAX_SPAN_DAYS = 62;

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
          ORDER BY o.received_at_local, o._id) AS prev_t
      FROM fdgy_views.orders o
      INNER JOIN consolidated a ON a.id=o._id AND a.country=o.country AND a.rn=1
      WHERE o.country=$1 AND o.provider_name='Rappi' AND o.domiciliary IS NOT NULL
        AND o.received_at_local >= $2 AND o.received_at_local < (CAST($3 AS date) + 1)
    ),
    marked AS (
      SELECT *, CASE WHEN prev_t IS NULL OR DATEDIFF(second, prev_t, t) > 900 THEN 1 ELSE 0 END AS newg FROM base
    ),
    numbered AS (
      SELECT *, SUM(newg) OVER (
        PARTITION BY kitchen_id, domiciliary, DATE_TRUNC('day', t)
        ORDER BY t, oid ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS gnum FROM marked
    ),
    grp AS (
      SELECT *, DENSE_RANK() OVER (ORDER BY kitchen_id, domiciliary, DATE_TRUNC('day', t), gnum) AS batch_id FROM numbered
    ),
    gs AS (SELECT batch_id, COUNT(*) AS sz FROM grp GROUP BY batch_id)
    SELECT g.kitchen,
      COUNT(*)::int AS total,
      SUM(CASE WHEN gs.sz=1 THEN 1 ELSE 0 END)::int AS n1,
      SUM(CASE WHEN gs.sz=2 THEN 1 ELSE 0 END)::int AS n2,
      SUM(CASE WHEN gs.sz=3 THEN 1 ELSE 0 END)::int AS n3,
      SUM(CASE WHEN gs.sz>=4 THEN 1 ELSE 0 END)::int AS n4
    FROM grp g JOIN gs ON gs.batch_id=g.batch_id
    GROUP BY g.kitchen
    ORDER BY total DESC`;

  let client;
  try {
    client = await getClient();
    const rows = (await client.query(sql, [country, from, to])).rows
      .map(x => [x.kitchen == null ? '—' : String(x.kitchen), x.total | 0, x.n1 | 0, x.n2 | 0, x.n3 | 0, x.n4 | 0]);
    setCache(res, 3600);
    sendJson(res, { country, from, to, rows });
  } catch (e) {
    return serverError(res, e, 'batching');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
