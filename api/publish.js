// Función serverless (Vercel) que publica el index.html actualizado commiteándolo al repo.
// Requiere variables de entorno en Vercel:  ADMIN_PASSWORD  y  GITHUB_TOKEN (PAT con Contents: write).
export const config = { api: { bodyParser: { sizeLimit: '12mb' } } };

const OWNER = 'melaniebeezzy-fdgy';
const REPO  = 'dashboard-turbology';
const BRANCH = 'main';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Método no permitido' });
  try {
    let body = req.body;
    if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = {}; } }
    const { password, html } = body || {};
    const ADMIN = process.env.ADMIN_PASSWORD_TURBO || process.env.ADMIN_PASSWORD;
    if (!ADMIN) {
      const seen = Object.keys(process.env).filter(k => /ADMIN|GITHUB|TURBO|PASSWORD|TOKEN/i.test(k));
      return res.status(500).json({ error: 'Falta ADMIN_PASSWORD_TURBO. El servidor ve estas variables: ' + (seen.join(', ') || 'ninguna relacionada') + '. Si no aparece, haz Redeploy en Vercel DESPUÉS de crearla.' });
    }
    if (!password || password !== ADMIN) return res.status(401).json({ error: 'Clave incorrecta.' });
    const token = process.env.GITHUB_TOKEN_TURBO || process.env.GITHUB_TOKEN;
    if (!token) return res.status(500).json({ error: 'Falta GITHUB_TOKEN_TURBO en el servidor.' });
    if (!html || typeof html !== 'string' || html.length < 200000) return res.status(400).json({ error: 'HTML inválido o incompleto.' });

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
    return res.status(200).json({ ok: true, message: 'Publicado. Vercel redepliega en ~1 min.' });
  } catch (e) {
    return res.status(500).json({ error: String((e && e.message) || e) });
  }
}
