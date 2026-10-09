// GET /api/sales  — Venta (órdenes + GMV) Turbo en vivo desde Redshift. Solo order_state='Finalized'.
// Agrega en SQL. Cubre los consumidores de venta del dashboard (semanal/mensual por ciudad/cocina/marca/tienda).
// Params:
//   country=CO|MX|PE  (oblig.)
//   from=YYYY-MM-DD  to=YYYY-MM-DD  (oblig.; rango máx. 400 días para permitir vistas mensuales)
//   group = city | kitchen | brand | store   (default city)
//   period = day | week | month              (default week)
// Shape (compacto, indexado):
//   { country, from, to, group, period, G:[etiquetas de grupo], P:[periodos ISO],
//     rows:[[gi, pi, q, gmv], ...] }           // q = órdenes, gmv = suma de gmv
import { guard, parseCountry, parseDate, getClient, setCache, sendJson, httpError, serverError } from './_db.js';

const GROUP_COL = { city: 'o.city', kitchen: 'o.kitchen', brand: 'o.brand', store: 'o.store_id' };
const PERIOD_COL = { day: 'o.order_day', week: 'o.order_week', month: 'o.order_month' };
const MAX_SPAN_DAYS = 400;

export default async function handler(req, res) {
  if (!guard(req, res)) return;
  const q = req.query || {};
  const country = parseCountry(q);
  if (!country) return httpError(res, 400, 'Parámetro country inválido (usa CO, MX o PE).');

  const from = parseDate(q.from), to = parseDate(q.to);
  if (!from || !to) return httpError(res, 400, 'Parámetros from/to obligatorios en formato YYYY-MM-DD.');
  if (from > to) return httpError(res, 400, 'from no puede ser mayor que to.');
  if ((new Date(to) - new Date(from)) / 86400000 > MAX_SPAN_DAYS) return httpError(res, 400, `Rango máximo ${MAX_SPAN_DAYS} días.`);

  const group = String(q.group || 'city').toLowerCase();
  const period = String(q.period || 'week').toLowerCase();
  const gcol = GROUP_COL[group], pcol = PERIOD_COL[period];
  if (!gcol) return httpError(res, 400, 'group inválido (city, kitchen, brand o store).');
  if (!pcol) return httpError(res, 400, 'period inválido (week o month).');

  const sql = `
    SELECT ${gcol} AS g, ${pcol}::text AS p,
      COUNT(*)::int AS q, ROUND(SUM(o.gmv))::float AS gmv
    FROM fdgy_views.orders_consolidado o
    WHERE o.company_id='fdgy' AND o.country=$1 AND o.provider_new_name='Rappi'
      AND o.brand ILIKE '%Turbo%' AND o.order_state='Finalized'
      AND o.order_day BETWEEN $2 AND $3
    GROUP BY ${gcol}, ${pcol}`;

  let client;
  try {
    client = await getClient();
    const rows = (await client.query(sql, [country, from, to])).rows;
    const G = [], Gi = new Map(), pset = new Set(), tmp = [];
    for (const x of rows) {
      const gl = x.g == null ? '—' : String(x.g);
      let gi = Gi.get(gl); if (gi === undefined) { gi = G.push(gl) - 1; Gi.set(gl, gi); }
      const pl = String(x.p).slice(0, 10); pset.add(pl);
      tmp.push([gi, pl, x.q | 0, x.gmv == null ? 0 : x.gmv]);
    }
    const P = Array.from(pset).sort();               // periodos en orden cronológico (ISO)
    const Pi = new Map(P.map((d, i) => [d, i]));
    const out = tmp.map(r => [r[0], Pi.get(r[1]), r[2], r[3]]);
    setCache(res, 3600);
    sendJson(res, { country, from, to, group, period, G, P, rows: out });
  } catch (e) {
    return serverError(res, e, 'sales');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
