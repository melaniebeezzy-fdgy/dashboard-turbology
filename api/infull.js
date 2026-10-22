// GET /api/infull  — InFull por tienda (órdenes y quejas) Turbo en vivo desde Redshift.
// InFull% = (órdenes - quejas)/órdenes. Agrega en SQL por store_id.
// Params: country=CO|MX|PE  from=YYYY-MM-DD  to=YYYY-MM-DD
// Shape: { country, from, to, rows:[[store_id, n, nq], ...] }   // n = órdenes, nq = quejas
import { guard, parseCountry, parseDate, getClient, setCache, sendJson, httpError, serverError, BASE_WHERE } from './_db.js';

const MAX_SPAN_DAYS = 400;   // igual que /api/sales: permite el período completo del dashboard

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
    SELECT o.store_id AS sid,
      COUNT(*)::int AS n,
      SUM(CASE WHEN o.is_complaint=1 THEN 1 ELSE 0 END)::int AS nq
    FROM fdgy_views.orders_consolidado o
    WHERE ${BASE_WHERE}
    GROUP BY o.store_id`;

  let client;
  try {
    client = await getClient();
    const rows = (await client.query(sql, [country, from, to])).rows
      .map(x => [x.sid == null ? '' : String(x.sid), x.n | 0, x.nq | 0]);
    setCache(res, 3600);
    sendJson(res, { country, from, to, rows });
  } catch (e) {
    return serverError(res, e, 'infull');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
