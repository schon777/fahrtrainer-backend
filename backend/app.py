from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Erlaube Frontend-Zugriff (Cloudflare Pages/localhost)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- KV Mini-Store im Speicher (einfach, flüchtig) ---
KV_STORE = {}

@app.get("/api/kv/<key>")
def kv_get(key):
    if key in KV_STORE:
        return jsonify({"key": key, "value": KV_STORE[key]})
    return jsonify({"error": "not found"}), 404

@app.post("/api/kv/<key>")
def kv_set(key):
    data = request.get_json(silent=True) or {}
    value = data.get("value")
    KV_STORE[key] = value
    return jsonify({"ok": True, "key": key, "value": value})

@app.delete("/api/kv/<key>")
def kv_delete(key):
    KV_STORE.pop(key, None)
    return jsonify({"ok": True})

# --- simple health check ---
@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
