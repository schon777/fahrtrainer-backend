// _worker.js
const FRONT_HTML = `<!doctype html><meta charset="utf-8">
<title>fahrtrainer-backend</title>
<h1>Backend läuft ✅</h1>
<p>Healthcheck: <a href="/api/ping">/api/ping</a></p>`;

const CORS = {
  "access-control-allow-origin": "https://regal-pudding-94ed42.netlify.app",
  "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
  "access-control-allow-headers": "content-type, authorization",
  "access-control-allow-credentials": "true",
};

const RENDER_BACKEND = "https://fahrtrainer-backend.onrender.com"; // falls noch aktiv

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });

    // 1) Root nie 404:
    if (url.pathname === "/") {
      return new Response(FRONT_HTML, { status: 200, headers: { "content-type": "text/html; charset=utf-8" } });
    }

    // 2) API: optional Proxy zu Render (oder später eigene Handler bauen)
    if (url.pathname.startsWith("/api/")) {
      // Proxy weiter zu Render (Method, Body, Headers übernehmen)
      const proxied = new URL(url.pathname + url.search, RENDER_BACKEND);
      const resp = await fetch(proxied, {
        method: request.method,
        headers: request.headers,
        body: ["GET","HEAD","OPTIONS"].includes(request.method) ? undefined : await request.arrayBuffer(),
      });
      // CORS hinzufügen
      const hdrs = new Headers(resp.headers);
      for (const [k,v] of Object.entries(CORS)) hdrs.set(k, v);
      return new Response(resp.body, { status: resp.status, headers: hdrs });
    }

    // 3) Alles andere: JSON 404 (mit CORS)
    return new Response(JSON.stringify({ error: "Not Found", path: url.pathname }), {
      status: 404,
      headers: { "content-type": "application/json", ...CORS },
    });
  },
};
