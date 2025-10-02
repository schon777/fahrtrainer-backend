// kv.js – Frontend-Helper für dein Render-Backend
// Falls du nichts setzt, wird die Render-URL genutzt.
const API =
  (typeof window !== "undefined" && typeof window.API === "string" && window.API) ||
  "https://fahrtrainer-backend.onrender.com";

// kleine Fetch-Hilfe mit Cache-Buster (HEAD/Proxy-Caches umgehen)
async function noStore(url, opts = {}) {
  const u = new URL(url, typeof location !== "undefined" ? location.href : undefined);
  u.searchParams.set("t", Date.now());
  return fetch(u.toString(), { cache: "no-store", ...opts });
}

/* ===== KV: key/value pro PAGE ===== */
const KV = {
  // Liste aller Einträge für eine Seite (Namespace)
  async list(page) {
    const r = await noStore(`${API}/api/kv?page=${encodeURIComponent(page)}`);
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    return data.items || [];
  },

  // Anlegen/Upsert eines Eintrags
  async set(page, key, value) {
    const r = await fetch(`${API}/api/kv`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page, key, value })
    });
    if (!r.ok) throw new Error(await r.text());
    return await r.json();
  },

  // Löschen per DB-id
  async remove(id) {
    const r = await fetch(`${API}/api/kv/${id}`, { method: "DELETE" });
    if (!r.ok) throw new Error(await r.text());
    return true;
  }
};

/* ===== Fahrten: CRUD ===== */
const Fahrten = {
  async list() {
    const r = await noStore(`${API}/api/fahrten`);
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    return data.items || data || [];
  },
  async create(payload) {
    const r = await fetch(`${API}/api/fahrten`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error(await r.text());
    return await r.json();
  },
  async update(id, payload) {
    const r = await fetch(`${API}/api/fahrten/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error(await r.text());
    return await r.json();
  },
  async remove(id) {
    const r = await fetch(`${API}/api/fahrten/${id}`, { method: "DELETE" });
    if (!r.ok) throw new Error(await r.text());
    return true;
  }
};

// global bereitstellen
window.KV = KV;
window.Fahrten = Fahrten;
window.API = API;
