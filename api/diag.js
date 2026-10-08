// TEMPORAL — diagnóstico de conexión. NO expone secretos: solo booleanos y el código
// de error (categoría), nunca el valor de WAREHOUSE_URL, host, usuario ni contraseña.
// Se elimina apenas se identifique la causa del fallo de conexión.
import { getClient } from './_db.js';

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET' });
  if ((req.query && req.query.k) !== 'diag1') return res.status(404).json({ error: 'not found' });

  const url = process.env.WAREHOUSE_URL || '';
  const info = { hasUrl: !!url };
  try {
    const u = new URL(url);
    info.protocol = u.protocol;        // p.ej. "postgres:" (no secreto)
    info.port = u.port || null;        // p.ej. "5439"
    info.hasHost = !!u.hostname;        // booleano, sin revelar el host
    info.hasUser = !!u.username;        // booleano
    info.hasPassword = !!u.password;    // booleano
    info.sslmode = u.searchParams.get('sslmode') || null;
  } catch (e) { info.urlParse = url ? 'invalid' : 'empty'; }

  let client;
  try {
    const t0 = Date.now();
    client = await getClient();
    const r = await client.query('SELECT current_user AS u, current_database() AS d');
    info.connect = 'ok';
    info.ms = Date.now() - t0;
    info.dbUser = r.rows[0].u;
    info.db = r.rows[0].d;
  } catch (e) {
    info.connect = 'fail';
    info.errName = e && e.name;   // categoría, no secreto
    info.errCode = e && e.code;   // p.ej. ETIMEDOUT / ENOTFOUND / 28P01 / ECONNREFUSED
  } finally { try { if (client) await client.end(); } catch (_) {} }

  res.status(200).json(info);
}
