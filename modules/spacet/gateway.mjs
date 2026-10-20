/**
 * SpaceT public gateway.
 *
 * Cloudflare Tunnel connects from this machine, so God's Eye View sees every
 * internet visitor as a loopback client and would let them reach Provider
 * Settings and the credential-minting endpoints. This gateway is the only
 * thing the tunnel talks to: it forwards the app and refuses those routes.
 * It also lets the hub (and only the hub) frame the full app, gives static
 * files long cache lifetimes so repeat visits load from disk, and adds the
 * Vietnamese UI layer (i18n/) to every HTML page.
 *
 *   cloudflared -> 127.0.0.1:4174 (this file) -> 127.0.0.1:4173 (vite preview)
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import { fileURLToPath } from 'node:url';

const I18N_DIR = fileURLToPath(new URL('./i18n/', import.meta.url));
const I18N_PATH = '/spacet-vi.js';

const LISTEN_HOST = '127.0.0.1';
const LISTEN_PORT = Number(process.env.SPACET_GATEWAY_PORT || 4174);
const TARGET_HOST = '127.0.0.1';
const TARGET_PORT = Number(process.env.SPACET_TARGET_PORT || 4173);

const ALLOWED_METHODS = new Set(['GET', 'HEAD', 'POST', 'OPTIONS']);
// Normalized (decoded, lower-cased) routes that never leave this machine:
// a route matches itself and everything below it.
const BLOCKED_ROUTES = [
  '/api/setup',
  '/api/realtime',
  '/api/openai',
  '/mcp',
  '/node_modules',
];
// Dev-server internals and dotfiles: anything starting with these characters.
const BLOCKED_STARTS = ['/@', '/__', '/.'];

/** Decode and flatten a request path so encoded or dotted variants cannot slip past the list. */
function normalizePath(rawUrl) {
  let path = String(rawUrl || '/').split('?')[0].split('#')[0];
  for (let i = 0; i < 3; i++) {
    try {
      const decoded = decodeURIComponent(path);
      if (decoded === path) break;
      path = decoded;
    } catch {
      return null;
    }
  }
  path = path
    .replace(/\\/g, '/')
    .replace(/;[^/]*/g, '')
    .replace(/\/{2,}/g, '/')
    .toLowerCase();
  if (path.split('/').some((part) => part === '..')) return null;
  // Windows drops trailing dots and spaces from names: "/api/setup." is "/api/setup".
  return path.replace(/[. ]+(?=\/|$)/g, '');
}

function isBlocked(rawUrl) {
  const path = normalizePath(rawUrl);
  if (path === null) return true;
  return (
    BLOCKED_ROUTES.some((route) => path === route || path.startsWith(`${route}/`)) ||
    BLOCKED_STARTS.some((start) => path.startsWith(start))
  );
}

// Only the hub may frame the app (the app itself sends frame-ancestors 'none').
const FRAME_ANCESTORS = process.env.SPACET_FRAME_ANCESTORS || 'https://sonxit.io.vn';
const STATIC_EXTENSIONS = /\.(?:js|css|wasm|glb|gltf|svg|png|jpe?g|webp|gif|ico|woff2?|json|xml)$/;
const ONE_DAY = 'public, max-age=86400';
const ONE_WEEK = 'public, max-age=604800';
const ONE_YEAR = 'public, max-age=31536000, immutable';

// Reuse sockets to the preview server instead of reconnecting for every asset.
const upstreamAgent = new http.Agent({ keepAlive: true, maxSockets: 128 });

/** How long the browser and Cloudflare's edge may keep a static response. */
function cacheControlFor(rawUrl) {
  const path = normalizePath(rawUrl);
  if (path === null || path.startsWith('/api/')) return null;
  // Vite writes content-hashed names under /assets/, so they never change.
  if (path.startsWith('/assets/')) return ONE_YEAR;
  if (path.startsWith('/cesium/') || path.startsWith('/models/')) return ONE_WEEK;
  return STATIC_EXTENSIONS.test(path) ? ONE_DAY : null;
}

/** Upstream headers, with framing opened to the hub and static files cacheable. */
function publicHeaders(req, upstreamRes) {
  const headers = { ...upstreamRes.headers };
  delete headers['x-frame-options'];
  const csp = headers['content-security-policy'];
  if (csp) {
    headers['content-security-policy'] = String(csp)
      .split(';')
      .map((directive) => directive.trim())
      .filter((directive) => directive && !/^frame-ancestors\b/i.test(directive))
      .concat(`frame-ancestors ${FRAME_ANCESTORS}`)
      .join('; ');
  }
  if ((req.method === 'GET' || req.method === 'HEAD') && upstreamRes.statusCode === 200) {
    const cacheControl = cacheControlFor(req.url);
    if (cacheControl) headers['cache-control'] = cacheControl;
  }
  return headers;
}

// ── Vietnamese UI layer ───────────────────────────────────────────────────
// /spacet-vi.js = the dictionary (i18n/dict.vi.json + i18n/overrides.vi.json,
// overrides win) followed by the engine, rebuilt whenever a file changes.
let i18nCache = { stamp: '', body: '', etag: '' };

function i18nBundle() {
  const files = ['dict.vi.json', 'overrides.vi.json', 'engine.js'].map((name) => `${I18N_DIR}${name}`);
  const stamp = files
    .map((file) => {
      try {
        const stat = fs.statSync(file);
        return `${stat.mtimeMs}:${stat.size}`;
      } catch {
        return 'missing';
      }
    })
    .join('|');
  if (stamp === i18nCache.stamp) return i18nCache;
  const readJson = (file) => {
    try {
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch {
      return {};
    }
  };
  const dict = { ...readJson(files[0]), ...readJson(files[1]) };
  let engine = '';
  try {
    engine = fs.readFileSync(files[2], 'utf8');
  } catch {
    /* no engine: the page simply stays English */
  }
  const body = `window.__SPACET_DICT=${JSON.stringify(dict)};\n${engine}`;
  const etag = `"${crypto.createHash('sha1').update(body).digest('hex').slice(0, 20)}"`;
  i18nCache = { stamp, body, etag };
  return i18nCache;
}

function serveI18n(req, res) {
  const { body, etag } = i18nBundle();
  if (req.headers['if-none-match'] === etag) {
    res.writeHead(304, { etag, 'cache-control': 'no-cache' });
    res.end();
    return;
  }
  // The page links the bundle as /spacet-vi.js?v=<etag>, so a versioned URL never
  // changes content and can be cached for good; the bare URL always revalidates.
  const versioned = String(req.url).includes(`v=${etag.replace(/"/g, '')}`);
  res.writeHead(200, {
    'content-type': 'application/javascript; charset=utf-8',
    'cache-control': versioned ? ONE_YEAR : 'no-cache',
    etag,
  });
  res.end(req.method === 'HEAD' ? undefined : body);
}

/** Every HTML document gets lang="vi" and the engine ahead of the app's scripts. */
function injectI18n(html) {
  const version = i18nBundle().etag.replace(/"/g, '');
  return html
    .replace(/(<html\b[^>]*?\blang=")[^"]*(")/i, '$1vi$2')
    .replace(/<head\b[^>]*>/i, (open) => `${open}<script src="${I18N_PATH}?v=${version}"></script>`);
}

const isHtmlResponse = (upstreamRes) =>
  upstreamRes.statusCode === 200 && /text\/html/i.test(upstreamRes.headers['content-type'] || '');

const server = http.createServer((req, res) => {
  if (!ALLOWED_METHODS.has(req.method) || isBlocked(req.url)) {
    res.writeHead(403, { 'content-type': 'text/plain; charset=utf-8' });
    res.end('Forbidden');
    return;
  }
  const requestPath = normalizePath(req.url);
  if ((req.method === 'GET' || req.method === 'HEAD') && requestPath === I18N_PATH) {
    serveI18n(req, res);
    return;
  }
  // Uncompressed upstream bodies, so HTML can be rewritten; Cloudflare compresses at the edge.
  const headers = { ...req.headers };
  delete headers['accept-encoding'];
  if (requestPath === '/' || (requestPath || '').endsWith('.html')) {
    delete headers['if-none-match'];
    delete headers['if-modified-since'];
  }
  const upstream = http.request(
    {
      host: TARGET_HOST,
      port: TARGET_PORT,
      method: req.method,
      path: req.url,
      headers,
      agent: upstreamAgent,
    },
    (upstreamRes) => {
      const outHeaders = publicHeaders(req, upstreamRes);
      if (req.method === 'GET' && isHtmlResponse(upstreamRes)) {
        const chunks = [];
        upstreamRes.on('data', (chunk) => chunks.push(chunk));
        upstreamRes.on('end', () => {
          const body = Buffer.from(injectI18n(Buffer.concat(chunks).toString('utf8')), 'utf8');
          delete outHeaders['content-length'];
          delete outHeaders['content-encoding'];
          delete outHeaders['transfer-encoding'];
          delete outHeaders.etag;
          outHeaders['content-length'] = String(body.length);
          res.writeHead(200, outHeaders);
          res.end(body);
        });
        return;
      }
      res.writeHead(upstreamRes.statusCode || 502, outHeaders);
      upstreamRes.pipe(res);
    },
  );
  upstream.on('error', () => {
    if (!res.headersSent) res.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' });
    res.end('SpaceT is starting');
  });
  req.on('aborted', () => upstream.destroy());
  req.pipe(upstream);
});

server.requestTimeout = 0;
server.listen(LISTEN_PORT, LISTEN_HOST, () => {
  console.log(`[SpaceT gateway] ${LISTEN_HOST}:${LISTEN_PORT} -> ${TARGET_HOST}:${TARGET_PORT}`);
});
