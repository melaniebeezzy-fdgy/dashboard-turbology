// Función serverless (Vercel): carga el DETALLE orden-por-orden (Rappi Turbo) desde el warehouse
// y lo escribe en el dashboard (bloque FDGYD) commiteándolo al repo.
// Requiere en Vercel:  ADMIN_PASSWORD_TURBO, GITHUB_TOKEN_TURBO, WAREHOUSE_URL
// Body JSON: { password, country: 'CO'|'MX'|'PE', from: 'YYYY-MM-DD', to: 'YYYY-MM-DD' }
export const config = { api: { bodyParser: { sizeLimit: '2mb' } } };

const OWNER = 'melaniebeezzy-fdgy';
const REPO  = 'dashboard-turbology';
const BRANCH = 'main';
const CMAP = { CO: 'COL', MX: 'MEX', PE: 'PER' };

function replaceFDGYD(html, obj) {
  const S = '/*FDGYD_START*/', E = '/*FDGYD_END*/';
  const a = html.indexOf(S), b = html.indexOf(E);
  if (a < 0 || b < 0 || b < a) throw new Error('No encontré los marcadores FDGYD en el archivo.');
  return html.slice(0, a) + S + 'const FDGYD=' + JSON.stringify(obj) + ';' + html.slice(b);
}
function currentFDGYD(html) {
  const S = '/*FDGYD_START*/const FDGYD=', E = ';/*FDGYD_END*/';
  const a = html.indexOf(S), b = html.indexOf(E);
  if (a < 0 || b < 0) return {};
  try { return JSON.parse(html.slice(a + S.length, b)); } catch (e) { return {}; }
}

async function fetchFile(path, hdr) {
  const g = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/contents/${encodeURIComponent(path)}?ref=${BRANCH}`, { headers: hdr });
  if (g.status !== 200) throw new Error(`${path}: no pude leer (${g.status})`);
  const meta = await g.json();
  let content = meta.content && meta.encoding === 'base64' ? Buffer.from(meta.content, 'base64').toString('utf8') : null;
  if (content == null) { // archivo >1MB: usar blobs
    const bl = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/git/blobs/${meta.sha}`, { headers: hdr });
    const blj = await bl.json();
    content = Buffer.from(blj.content, 'base64').toString('utf8');
  }
  return { sha: meta.sha, content };
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Método no permitido' });
  const log = [];
  try {
    let body = req.body;
    if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = {}; } }
    const { password, country, from, to } = body || {};
    const ADMIN = process.env.ADMIN_PASSWORD_TURBO || process.env.ADMIN_PASSWORD;
    if (!ADMIN) return res.status(500).json({ error: 'Falta ADMIN_PASSWORD_TURBO en el servidor.' });
    if (!password || password !== ADMIN) return res.status(401).json({ error: 'Clave incorrecta.' });
    const token = process.env.GITHUB_TOKEN_TURBO || process.env.GITHUB_TOKEN;
    if (!token) return res.status(500).json({ error: 'Falta GITHUB_TOKEN_TURBO en el servidor.' });
    const wh = process.env.WAREHOUSE_URL;
    if (!wh) return res.status(500).json({ error: 'Falta WAREHOUSE_URL en el servidor.' });
    const cc = CMAP[country]; if (!cc) return res.status(400).json({ error: 'country debe ser CO, MX o PE.' });
    if (!/^\d{4}-\d{2}-\d{2}$/.test(from || '') || !/^\d{4}-\d{2}-\d{2}$/.test(to || '')) return res.status(400).json({ error: 'from/to deben ser YYYY-MM-DD.' });

    // 1) Warehouse: detalle orden-por-orden
    let pg;
    try { pg = await import('pg'); } catch (e) { return res.status(500).json({ error: 'Falta dependencia pg en el servidor.' }); }
    const Client = pg.default ? pg.default.Client : pg.Client;
    const client = new Client({ connectionString: wh, ssl: { rejectUnauthorized: false }, connectionTimeoutMillis: 8000, query_timeout: 45000 });
    let rows;
    try {
      await client.connect();
      const q = `SELECT kitchen, brand, order_day,
                   FLOOR(order_hour)::int AS hr,
                   provider_order_id AS oid,
                   ROUND(minutes_cooking_time,1)::float AS cook,
                   ROUND(GREATEST(0, EXTRACT(EPOCH FROM (order_state_handed_to_delivery - GREATEST(domiciliary_in_store, order_date_local + interval '5 minute')))/60.0)::numeric,2)::float AS rt
                 FROM fdgy_views.orders_consolidado
                 WHERE company_id='fdgy' AND country=$1 AND provider_new_name='Rappi' AND brand ILIKE '%Turbo%'
                   AND order_day BETWEEN $2 AND $3
                 ORDER BY order_day, order_date_local`;
      const r = await client.query(q, [cc, from, to]);
      rows = r.rows;
    } finally { try { await client.end(); } catch (e) {} }
    log.push('warehouse ' + country + ' ' + from + '→' + to + ': ' + rows.length + ' órdenes');

    // 2) Compactar (índices)
    const K = [], Ki = new Map(), B = [], Bi = new Map(), days = [], Di = new Map(), O = [];
    for (const x of rows) {
      let ki = Ki.get(x.kitchen); if (ki === undefined) { ki = K.push(x.kitchen) - 1; Ki.set(x.kitchen, ki); }
      let bi = Bi.get(x.brand); if (bi === undefined) { bi = B.push(x.brand) - 1; Bi.set(x.brand, bi); }
      const dstr = (x.order_day instanceof Date) ? x.order_day.toISOString().slice(0, 10) : String(x.order_day).slice(0, 10);
      let di = Di.get(dstr); if (di === undefined) { di = days.push(dstr) - 1; Di.set(dstr, di); }
      O.push([ki, bi, di, x.hr == null ? null : (x.hr | 0), String(x.oid), x.cook == null ? null : x.cook, x.rt == null ? null : x.rt]);
    }
    const payload = { from, to, K, B, days, O, n: O.length };

    // 3) Escribir en ambos archivos y commitear
    const hdr = { Authorization: 'Bearer ' + token, 'User-Agent': 'fdgy-admin', Accept: 'application/vnd.github+json' };
    async function updateFile(path) {
      const f = await fetchFile(path, hdr);
      const cur = currentFDGYD(f.content);
      cur[country] = payload;
      const nuevo = replaceFDGYD(f.content, cur);
      const b64 = Buffer.from(nuevo, 'utf8').toString('base64');
      const r = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/contents/${encodeURIComponent(path)}`, {
        method: 'PUT', headers: { ...hdr, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'admin: detalle orden-por-orden ' + country + ' ' + from + '→' + to, content: b64, sha: f.sha, branch: BRANCH })
      });
      if (!(r.status === 200 || r.status === 201)) throw new Error(`${path}: ${r.status} ${(await r.text()).slice(0, 300)}`);
    }
    await updateFile('index.html');
    await updateFile('index_co.html');
    log.push('publicado ' + O.length + ' órdenes (' + K.length + ' cocinas, ' + B.length + ' marcas, ' + days.length + ' días)');
    return res.status(200).json({ ok: true, message: 'Detalle ' + country + ' publicado. Vercel redepliega en ~1 min.', detail: log });
  } catch (e) {
    return res.status(500).json({ error: String((e && e.message) || e), detail: log });
  }
}
