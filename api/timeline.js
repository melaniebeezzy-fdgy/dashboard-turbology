// GET /api/timeline  — Timeline de UNA orden (reemplazo futuro de FDGYT).
// Se consulta on-demand al hacer clic en una orden; evita embeber ~45k timelines.
// Params: oid=<provider_order_id>  (obligatorio).  [country=CO|MX|PE] opcional (acota).
// Shape: { oid, t:[recv,oq,oc,op,ow,oh,od,late,wait,dis] }
//   recv = minuto del día de recepción; oq..ow,oh,dis = minutos desde recepción a cada estado;
//   oh = provider_delivered_to_domiciliary (nodo "Entregado"); od = minutes_received_to_destination;
//   late = display_info_is_late (0/1); wait = display_info_waiting_time.
// Nota: no lleva fechas obligatorias porque es un lookup por clave única de 1 orden.
import { guard, parseCountry, cleanStr, getClient, setCache, sendJson, httpError, serverError } from './_db.js';

export default async function handler(req, res) {
  if (!guard(req, res)) return;
  const q = req.query || {};
  const oid = cleanStr(q.oid, 40);
  if (!oid || !/^\d{1,25}$/.test(oid)) return httpError(res, 400, 'Parámetro oid obligatorio (numérico).');
  const country = parseCountry(q); // opcional

  const params = [oid];
  let where = "o.company_id='fdgy' AND o.provider_new_name='Rappi' AND o.brand ILIKE '%Turbo%' AND o.provider_order_id=$1";
  if (country) { params.push(country); where += ` AND o.country=$${params.length}`; }

  const sql = `
    SELECT
      FLOOR(EXTRACT(EPOCH FROM (o.order_date_local - date_trunc('day', o.order_date_local)))/60)::int AS recv,
      ROUND(EXTRACT(EPOCH FROM (o.order_state_queued - o.order_date_local))/60)::int AS oq,
      ROUND(EXTRACT(EPOCH FROM (o.order_state_cooking - o.order_date_local))/60)::int AS oc,
      ROUND(EXTRACT(EPOCH FROM (o.order_state_packing - o.order_date_local))/60)::int AS op,
      ROUND(EXTRACT(EPOCH FROM (o.order_state_waiting_for_delivery - o.order_date_local))/60)::int AS ow,
      ROUND(EXTRACT(EPOCH FROM (oi.provider_delivered_to_domiciliary - o.order_date_local))/60)::int AS oh,
      ROUND(o.minutes_received_to_destination)::int AS od,
      CASE WHEN o.display_info_is_late THEN 1 ELSE 0 END AS late,
      ROUND(o.display_info_waiting_time)::int AS wait,
      ROUND(EXTRACT(EPOCH FROM (o.domiciliary_in_store - o.order_date_local))/60)::int AS dis
    FROM fdgy_views.orders_consolidado o
    LEFT JOIN fdgy_views.ontime_infull_order oi ON oi.order_id = o.id
    WHERE ${where}
    LIMIT 1`;

  let client;
  try {
    client = await getClient();
    const rows = (await client.query(sql, params)).rows;
    if (!rows.length) return httpError(res, 404, 'Orden no encontrada.');
    const x = rows[0];
    const t = [x.recv, x.oq, x.oc, x.op, x.ow, x.oh, x.od, x.late, x.wait, x.dis]
      .map(v => (v == null ? null : (v | 0)));
    setCache(res, 86400); // una orden pasada no cambia: cache largo
    sendJson(res, { oid, t });
  } catch (e) {
    return serverError(res, e, 'timeline');
  } finally { try { if (client) await client.end(); } catch (e) {} }
}
