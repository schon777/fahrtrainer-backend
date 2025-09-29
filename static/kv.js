// kv.js – Hilfsskript für DB-Speichern über dein Backend
const API = "https://fahrtrainer-backend.onrender.com";  // <— ggf. anpassen

async function noStore(url, opts = {}) {
  const u = new URL(url, typeof location !== "undefined" ? location.href : undefined);
  u.searchParams.set("t", Date.now()); // Cache-Buster
  return fetch(u.toString(), { cache: "no-store", ...opts });
}

const KV = {
  // Liste aller Einträge für eine Seite (Namespace)
  async list(page) {
    const r = await noStore(`${API}/api/kv?page=${encodeURIComponent(page)}`);
    if (!r.ok) throw new Error(await r.text());
    // Erwartete Struktur: { items: [{ id, k, v }, ...] }
    return (await r.json()).items || [];
  },

  // Anlegen/Upsert eines Eintrags (key ist dein eigener Identifier)
  async set(page, key, value) {
    const r = await fetch(`${API}/api/kv`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page, key, value })
    });
    if (!r.ok) throw new Error(await r.text());
    // Erwartete Struktur: { id, k, v }
    return await r.json();
  },

  // Löschen per DB-id (numerisch)
  async remove(id) {
    const r = await fetch(`${API}/api/kv/${id}`, { method: "DELETE" });
    if (!r.ok) throw new Error(await r.text());
    return true;
  }
};

// global bereitstellen (für <script src="kv.js"></script>)
window.KV = KV;
window.API = API;
