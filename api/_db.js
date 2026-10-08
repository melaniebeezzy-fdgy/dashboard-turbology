// Módulo compartido para los endpoints de LECTURA del dashboard (Fase 1).
// NO expone secretos al frontend: la conexión a Redshift ocurre solo aquí (serverless).
// Requiere env vars en Vercel:
//   WAREHOUSE_URL        cadena de conexión Postgres/Redshift de SOLO LECTURA
//   API_READ_TOKEN       (opcional) si está seteado, los endpoints exigen este token
//                        (header 'x-api-token' o '?token='). Ver nota de seguridad abajo.
//
// NOTA DE SEGURIDAD (limitación documentada):
//   Si el dashboard (navegador) consume estos endpoints directamente, cualquier token
//   enviado desde el front queda visible en el código/el tráfico. Por eso la defensa
//   principal NO es el token sino: método GET, validación estricta de parámetros,
//   whitelist de país, fechas obligatorias con rango máximo, LIMIT tope, columnas
//   explícitas (nunca SELECT *), sin PII, parámetros SQL ($1,$2...) y caché.
//   API_READ_TOKEN sirve como capa extra para uso servidor-a-servidor o mientras el
//   endpoint no se expone al navegador. Cuando se migre el front se puede sustituir por
//   validación de Origin/Referer + rate-limit a nivel de Vercel.

export const CMAP = { CO: 'COL', MX: 'MEX', PE: 'PER' };

// Expresión RTWT — EXACTAMENTE la misma lógica que api/orders-detail.js y los bloques
// embebidos: minutos entre provider_delivered_to_domiciliary y el máximo de
// (domiciliary_in_store, recepción + 5 min), con piso en 0. Requiere alias o=orders,
// oi=ontime_infull_order.
export const RTWT_EXPR =
  "GREATEST(0, EXTRACT(EPOCH FROM (oi.provider_delivered_to_domiciliary - " +
  "GREATEST(o.domiciliary_in_store, o.order_date_local + interval '5 minute')))/60.0)";

export const BASE_WHERE =
  "o.company_id='fdgy' AND o.country=$1 AND o.provider_new_name='Rappi' " +
  "AND o.brand ILIKE '%Turbo%' AND o.order_day BETWEEN $2 AND $3";

const MAX_SPAN_DAYS = 95;   // rango máximo de fechas permitido por consulta
const DEFAULT_LIMIT = 5000;
const MAX_LIMIT = 50000;

export function httpError(res, code, msg) {
  res.status(code).json({ error: msg });
  return null;
}

// Error interno: loguea el detalle SOLO en el servidor (Vercel logs) y devuelve un
// mensaje genérico. Nunca expone el error de pg/Redshift ni WAREHOUSE_URL al cliente.
export function serverError(res, e, tag) {
  // Log mínimo y seguro: solo nombre + SQLSTATE/code. Nunca el mensaje/stack (que podría
  // contener usuario o host), ni variables de entorno.
  try { console.error('[' + (tag || 'api') + '] name=' + (e && e.name) + ' code=' + (e && e.code)); } catch (_) {}
  res.status(500).json({ error: 'Error interno al consultar los datos.' });
  return null;
}

// Verifica método GET y (si aplica) token. Devuelve true si debe continuar.
export function guard(req, res) {
  if (req.method !== 'GET') { httpError(res, 405, 'Método no permitido (usa GET).'); return false; }
  const need = process.env.API_READ_TOKEN;
  if (need) {
    const got = req.headers['x-api-token'] || (req.query && req.query.token);
    if (!got || got !== need) { httpError(res, 401, 'Token inválido o ausente.'); return false; }
  }
  return true;
}

// País -> código ISO3, validado contra whitelist.
export function parseCountry(q) {
  const raw = String(q.country || q.c || '').toUpperCase();
  const code = CMAP[raw] || (Object.values(CMAP).includes(raw) ? raw : null);
  return code; // null si inválido
}

const ISO = /^\d{4}-\d{2}-\d{2}$/;
export function parseDate(v) {
  if (!ISO.test(String(v || ''))) return null;
  const d = new Date(v + 'T00:00:00Z');
  return isNaN(d.getTime()) ? null : v;
}

// Valida from/to obligatorios, formato ISO, orden y rango máximo.
export function parseRange(q) {
  const from = parseDate(q.from), to = parseDate(q.to);
  if (!from || !to) return { err: 'Parámetros from/to obligatorios en formato YYYY-MM-DD.' };
  if (from > to) return { err: 'from no puede ser mayor que to.' };
  const span = (new Date(to) - new Date(from)) / 86400000;
  if (span > MAX_SPAN_DAYS) return { err: `Rango máximo ${MAX_SPAN_DAYS} días (pediste ${Math.round(span)}).` };
  return { from, to };
}

export function clampLimit(v) {
  let n = parseInt(v, 10);
  if (!Number.isFinite(n) || n <= 0) n = DEFAULT_LIMIT;
  return Math.min(n, MAX_LIMIT);
}

// Texto corto y seguro para filtros opcionales (cocina / marca / op).
export function cleanStr(v, max = 80) {
  if (v == null) return null;
  const s = String(v).trim();
  if (!s || s.length > max) return null;
  return s;
}

// Devuelve un cliente pg conectado. Lanza si falta WAREHOUSE_URL o pg.
export async function getClient() {
  const pg = await import('pg');
  const Client = pg.default ? pg.default.Client : pg.Client;
  const common = { ssl: { rejectUnauthorized: false }, connectionTimeoutMillis: 8000, query_timeout: 45000 };

  // Prioridad: variables separadas (evita problemas de URL-encoding en la contraseña).
  const host = process.env.WAREHOUSE_HOST;
  let cfg;
  if (host) {
    cfg = {
      host,
      port: parseInt(process.env.WAREHOUSE_PORT || '5439', 10),
      database: process.env.WAREHOUSE_DATABASE,
      user: process.env.WAREHOUSE_USER,
      password: process.env.WAREHOUSE_PASSWORD,
      ...common,
    };
  } else if (process.env.WAREHOUSE_URL) {
    // Fallback temporal a connection string.
    cfg = { connectionString: process.env.WAREHOUSE_URL, ...common };
  } else {
    throw new Error('Falta configuración de conexión al warehouse.');
  }
  const client = new Client(cfg);
  await client.connect();
  return client;
}

// Caché: la vista refresca D-1, así que es seguro cachear ~1h en el edge/CDN.
export function setCache(res, seconds = 3600) {
  res.setHeader('Cache-Control', `public, s-maxage=${seconds}, stale-while-revalidate=86400`);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
}

export function sendJson(res, obj) {
  res.status(200).send(JSON.stringify(obj)); // JSON compacto (sin espacios)
}
