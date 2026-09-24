// Función serverless (Vercel) que publica el index.html actualizado commiteándolo al repo.
// Requiere variables de entorno en Vercel:
//   ADMIN_PASSWORD_TURBO  (clave del /admin)
//   GITHUB_TOKEN_TURBO    (PAT con Contents: write)
//   WAREHOUSE_URL         (opcional) cadena de conexión Postgres/Redshift de solo-lectura,
//                         p.ej. postgres://user:pass@host:5439/db  — para autollenar la venta de CO.
export const config = { api: { bodyParser: { sizeLimit: '12mb' } } };

const OWNER = 'melaniebeezzy-fdgy';
const REPO  = 'dashboard-turbology';
const BRANCH = 'main';
const MI = { Jan:0,Feb:1,Mar:2,Apr:3,May:4,Jun:5,Jul:6,Aug:7,Sep:8,Oct:9,Nov:10,Dec:11 };

function extractD(H) {
  const a = H.indexOf('let D=') + 6;
  let i = a, depth = 0, started = false, end = -1;
  for (; i < H.length; i++) { const c = H[i]; if (c === '{') { depth++; started = true; } else if (c === '}') { depth--; if (started && depth === 0) { end = i + 1; break; } } }
  return { start: a - 6, end, json: H.slice(a, end) };
}
// domingo "Sep 20" -> lunes de order_week (YYYY-MM-DD), año 2026
function orderWeekMonday(label) {
  const m = String(label).trim().match(/([A-Za-z]{3})\s+(\d{1,2})/); if (!m) return null;
  const sun = Date.UTC(2026, MI[m[1]], +m[2]); const mon = new Date(sun - 6 * 86400000);
  return mon.toISOString().slice(0, 10);
}

async function fillCoSales(html, weekLabel, log) {
  const url = process.env.WAREHOUSE_URL;
  if (!url) { log.push('ventas: WAREHOUSE_URL no configurado — semana queda en 0'); return html; }
  const ow = orderWeekMonday(weekLabel);
  if (!ow) { log.push('ventas: no pude derivar order_week de ' + weekLabel); return html; }
  let pg;
  try { pg = await import('pg'); } catch (e) { log.push('ventas: falta dependencia pg'); return html; }
  const Client = pg.default ? pg.default.Client : pg.Client;
  const client = new Client({ connectionString: url, ssl: { rejectUnauthorized: false }, connectionTimeoutMillis: 8000, query_timeout: 20000 });
  try {
    await client.connect();
    const q = `SELECT store_id, COUNT(*)::int q, ROUND(SUM(gmv))::float g
               FROM fdgy_views.orders_consolidado
               WHERE country='COL' AND provider_new_name='Rappi' AND brand ILIKE '%Turbo%'
                 AND order_state='Finalized' AND order_week=$1 GROUP BY store_id`;
    const r = await client.query(q, [ow]);
    const ven = {}; r.rows.forEach(x => { ven[String(x.store_id)] = [x.q | 0, Math.round(x.g) | 0]; });
    const ex = extractD(html); const D = JSON.parse(ex.json); const wi = D.weeks.indexOf(weekLabel);
    if (wi < 0) { log.push('ventas: la semana ' + weekLabel + ' no está en D'); return html; }
    let m = 0, to = 0, tg = 0;
    D.stores.forEach(s => {
      for (const k of ['ow', 'gw']) { if (!Array.isArray(s[k])) s[k] = []; while (s[k].length <= wi) s[k].push(0); }
      const v = ven[String(s.sid)]; if (v) { s.ow[wi] = v[0]; s.gw[wi] = v[1]; m++; to += v[0]; tg += v[1]; }
    });
    log.push('ventas ' + ow + ': ' + m + ' tiendas, ' + to + ' órdenes, gmv ' + tg.toLocaleString('es'));
    return html.slice(0, ex.start) + 'let D=' + JSON.stringify(D) + html.slice(ex.end);
  } catch (e) {
    log.push('ventas: error consultando warehouse — ' + String(e.message || e).slice(0, 160) + ' (se publica con venta 0)');
    return html;
  } finally { try { await client.end(); } catch (e) {} }
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Método no permitido' });
  const log = [];
  try {
    let body = req.body;
    if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = {}; } }
    const { password, country, week } = body || {};
    let { html } = body || {};
    const ADMIN = process.env.ADMIN_PASSWORD_TURBO || process.env.ADMIN_PASSWORD;
    if (!ADMIN) return res.status(500).json({ error: 'Falta ADMIN_PASSWORD_TURBO en el servidor.' });
    if (!password || password !== ADMIN) return res.status(401).json({ error: 'Clave incorrecta.' });
    const token = process.env.GITHUB_TOKEN_TURBO || process.env.GITHUB_TOKEN;
    if (!token) return res.status(500).json({ error: 'Falta GITHUB_TOKEN_TURBO en el servidor.' });
    if (!html || typeof html !== 'string' || html.length < 200000) return res.status(400).json({ error: 'HTML inválido o incompleto.' });

    if (country === 'CO' && week) { html = await fillCoSales(html, week, log); }

    const b64 = Buffer.from(html, 'utf8').toString('base64');
    const hdr = { Authorization: 'Bearer ' + token, 'User-Agent': 'fdgy-admin', Accept: 'application/vnd.github+json' };
    async function commit(path) {
      let sha;
      const g = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/contents/${encodeURIComponent(path)}?ref=${BRANCH}`, { headers: hdr });
      if (g.status === 200) sha = (await g.json()).sha;
      const r = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/contents/${encodeURIComponent(path)}`, {
        method: 'PUT', headers: { ...hdr, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'admin: actualización de datos ' + new Date().toISOString(), content: b64, sha, branch: BRANCH })
      });
      if (!(r.status === 200 || r.status === 201)) throw new Error(`${path}: ${r.status} ${(await r.text()).slice(0, 300)}`);
    }
    await commit('index.html');
    await commit('index_co.html');
    return res.status(200).json({ ok: true, message: 'Publicado. Vercel redepliega en ~1 min.', detail: log });
  } catch (e) {
    return res.status(500).json({ error: String((e && e.message) || e), detail: log });
  }
}
