// _worker.js
const CORS = {
  "access-control-allow-origin": "https://regal-pudding-94ed42.netlify.app",
  "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
  "access-control-allow-headers": "content-type, authorization",
  "access-control-allow-credentials": "true",
};

const RENDER_BACKEND = "https://fahrtrainer-backend.onrender.com"; // solange Flask noch dort läuft

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    // --- API ---
    if (url.pathname === "/api/ping") {
      return new Response(JSON.stringify({ ok: true, ts: Date.now() }), {
        status: 200,
        headers: { "content-type": "application/json", ...CORS },
      });
    }

    if (url.pathname.startsWith("/api/")) {
      const proxied = new URL(url.pathname + url.search, RENDER_BACKEND);
      const resp = await fetch(proxied, {
        method: request.method,
        headers: request.headers,
        body: ["GET", "HEAD", "OPTIONS"].includes(request.method)
          ? undefined
          : await request.arrayBuffer(),
      });
      const hdrs = new Headers(resp.headers);
      for (const [k, v] of Object.entries(CORS)) hdrs.set(k, v);
      return new Response(resp.body, { status: resp.status, headers: hdrs });
    }

    // --- Static (Pages Assets) ---
    return env.ASSETS.fetch(request);
  },
};
