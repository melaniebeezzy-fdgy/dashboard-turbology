// GET /api/trend — Serie SEMANAL por cocina y por marca (histórico para §12: tendencias y deterioros).
// Agrega en SQL por semana. Para cada semana: órdenes, cocción promedio, RTWT promedio,
// quejas (para tasa /100) y % de pedidos con cocción > 9 min (cola).
// Params: country=CO|MX|PE  from=YYYY-MM-DD  to=YYYY-MM-DD   (rango máx. 95 días ≈ 13 semanas)
// Shape: { country, from, to, weeks:[ISO...],
//          K:[cocinas], KR:[[ki, wi, n, cook, rtwt, nq, slow9], ...],
//          B:[marcas],  BR:[[bi, wi, n, cook, rtwt, nq, slow9], ...] }
import { guard, parseCountry, parseRange, getClient, setCache, sendJson, httpError, serverError, RTWT_EXPR, COOK_EXPR } from './_db.js';

export default async function handler(req, res) {
  if (!guard(req, res)) return;
  const q = req.query || {};
  const country = parseCountry(q);
  if (!country) return httpError(res, 400, 'Parámetro country inválido (usa CO, MX o PE).');
  const r = parseRange(q);
  if (r.err) return httpError(res, 400, r.err);

  const WHERE = `o.company_id='fdgy' AND o.country=$1 AND o.provider_new_name='Rappi'
      AND o.brand ILIKE '%Turbo%' AND o.order_state='Finalized' AND o.order_day BETWEEN $2 AND $3`;
  const metrics = `
      COUNT(*)::int AS n,
      ROUND(AVG(${COOK_EXPR})::numeric,2)::float AS cook,
      ROUND(AVG(${RTWT_EXPR})::numeric,2)::float AS rtwt,
      SUM(CASE WHEN o.is_complaint=1 THEN 1 ELSE 0 END)::int AS nq,
      ROUND(100.0*SUM(CASE WHEN (${COOK_EXPR})>9 THEN 1 ELSE 0 END)/NULLIF(COUNT(${COOK_EXPR}),0),1)::float AS slow9`;
  const FROMJOIN = `FROM fdgy_views.orders_consolidado o
      LEFT JOIN fdgy_views.ontime_infull_order oi ON oi.order_id = o.id`;

  const sqlK = `SELECT o.kitchen AS g, o.order_week::text AS wk, ${metrics} ${FROMJOIN}
      WHERE ${WHERE} GROUP BY o.kitchen, o.order_week`;
  const sqlB = `SELECT o.brand AS g, o.order_week::text AS wk, ${metrics} ${FROMJOIN}
      WHERE ${WHERE} GROUP BY o.brand, o.order_week`;

  let client;
  try {
    client = await getClient();
    const params = [country, r.from, r.to];
    const [rk, rb] = await Promise.all([client.query(sqlK, params), client.query(sqlB, params)]);

    // Semanas ordenadas (ISO) de ambas consultas
    const wset = new Set();
    rk.rows.forEach(x => wset.add(String(x.wk).slice(0, 10)));
    rb.rows.forEach(x => wset.add(String(x.wk).slice(0, 10)));
    const weeks = Array.from(wset).sort();
    const wIx = new Map(weeks.map((w, i) => [w, i]));

    function pack(rows) {
      const G = [], Gi = new Map(), R = [];
      for (const x of rows) {
        const gl = x.g == null ? '—' : String(x.g);
        let gi = Gi.get(gl); if (gi === undefined) { gi = G.push(gl) - 1; Gi.set(gl, gi); }
        const wi = wIx.get(String(x.wk).slice(0, 10)); if (wi === undefined) continue;
        R.push([gi, wi, x.n | 0, x.cook == null ? null : x.cook, x.rtwt == null ? null : x.rtwt, x.nq | 0, x.slow9 == null ? null : x.slow9]);
      }
      return { G, R };
    }
    const K = pack(rk.rows), B = pack(rb.rows);
    setCache(res, 3600);
    sendJson(res, { country, from: r.from, to: r.to, weeks, K: K.G, KR: K.R, B: B.G, BR: B.R });
  } catch (e) {
    return serverError(res, e, 'trend');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
