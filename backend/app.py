# backend/app.py
# Flask API für Fahrtrainer – KV & Fahrten (Postgres auf Render / Neon)
import os
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import (
    create_engine, text
)
from sqlalchemy.dialects.postgresql import JSONB

# ------------------------------------------------------------
# Flask & CORS
# ------------------------------------------------------------
app = Flask(__name__)

ALLOWED_ORIGINS = [
    "https://fahrtrainer-backend.pages.dev",   # Cloudflare Pages (Frontend)
    "http://localhost:5500",                   # lokalen Test erlauben (VSCode Live Server)
]
# Für schnelle Tests nicht zu streng sein – aber nur /api/**
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}}, supports_credentials=False)

# ------------------------------------------------------------
# Datenbank (Render: DATABASE_URL gesetzt)
# ------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")  # z.B. postgres://...
engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None


def init_db() -> None:
    """Erstellt Tabellen, falls nicht vorhanden."""
    if not engine:
        app.logger.warning("Keine DATABASE_URL; init_db wird übersprungen.")
        return

    with engine.begin() as conn:
        # KV-Tabelle: (page, key) eindeutig, value als JSONB
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS kv (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                page TEXT NOT NULL,
                key  TEXT NOT NULL,
                value JSONB,
                UNIQUE (page, key)
            );
        """))

        # Fahrten – ganz einfache Beispielstruktur
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fahrten (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                start TEXT NOT NULL,
                ziel  TEXT NOT NULL,
                dauer_minutes INT
            );
        """))

# Beim Import einmal versuchen
try:
    init_db()
except Exception as e:
    # Beim ersten Start ohne DB nicht crashen – Logs reichen
    print("init_db() Fehler:", e)

# ------------------------------------------------------------
# Health / Ping
# ------------------------------------------------------------
@app.get("/")
def root_ok():
    return jsonify({"ok": True, "service": "fahrtrainer-backend"})

@app.get("/api/ping")
def api_ping():
    # von Render-Healthcheck verwendet
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat() + "Z"})

@app.get("/api/health")
def api_health():
    try:
        if engine:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def require_db():
    if not engine:
        return jsonify({"error": "DATABASE_URL not configured"}), 503
    return None

def json_body() -> Dict[str, Any]:
    if not request.is_json:
        return {}
    return request.get_json(silent=True) or {}

# ------------------------------------------------------------
# KV: key/value pro Seite (Namespace)
# ------------------------------------------------------------
@app.get("/api/kv")
def kv_list():
    err = require_db()
    if err:
        return err
    page = request.args.get("page", "").strip()
    if not page:
        return jsonify({"error": "missing ?page"}), 400

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, page, key, value, created_at
            FROM kv
            WHERE page = :page
            ORDER BY created_at DESC, id DESC
        """), {"page": page}).mappings().all()

    return jsonify({"items": [dict(r) for r in rows]})

@app.post("/api/kv")
def kv_set():
    err = require_db()
    if err:
        return err
    data = json_body()
    page = (data.get("page") or "").strip()
    key  = (data.get("key") or "").strip()
    value = data.get("value", None)

    if not page or not key:
        return jsonify({"error": "page and key required"}), 400

    with engine.begin() as conn:
        # Upsert via ON CONFLICT
        row = conn.execute(text("""
            INSERT INTO kv (page, key, value)
            VALUES (:page, :key, CAST(:value AS JSONB))
            ON CONFLICT (page, key)
            DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
            RETURNING id, page, key, value, created_at
        """), {"page": page, "key": key, "value": value}).mappings().first()

    return jsonify(dict(row)), 201

@app.delete("/api/kv/<int:item_id>")
def kv_delete(item_id: int):
    err = require_db()
    if err:
        return err
    with engine.begin() as conn:
        row = conn.execute(text("""
            DELETE FROM kv
            WHERE id = :id
            RETURNING id
        """), {"id": item_id}).first()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({"deleted": row[0]})

# ------------------------------------------------------------
# Fahrten CRUD (Beispiel)
# ------------------------------------------------------------
@app.get("/api/fahrten")
def fahrten_list():
    err = require_db()
    if err:
        return err
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, created_at, start, ziel, dauer_minutes
            FROM fahrten
            ORDER BY created_at DESC, id DESC
        """)).mappings().all()
    return jsonify({"items": [dict(r) for r in rows]})

@app.post("/api/fahrten")
def fahrten_create():
    err = require_db()
    if err:
        return err
    data = json_body()
    start = (data.get("start") or "").strip()
    ziel  = (data.get("ziel") or "").strip()
    dauer = data.get("dauer_minutes")

    if not start or not ziel:
        return jsonify({"error": "start and ziel required"}), 400

    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO fahrten (start, ziel, dauer_minutes)
            VALUES (:start, :ziel, :dauer)
            RETURNING id, created_at, start, ziel, dauer_minutes
        """), {"start": start, "ziel": ziel, "dauer": dauer}).mappings().first()
    return jsonify(dict(row)), 201

@app.put("/api/fahrten/<int:item_id>")
def fahrten_update(item_id: int):
    err = require_db()
    if err:
        return err
    data = json_body()
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE fahrten
            SET start = COALESCE(:start, start),
                ziel  = COALESCE(:ziel, ziel),
                dauer_minutes = COALESCE(:dauer, dauer_minutes)
            WHERE id = :id
            RETURNING id, created_at, start, ziel, dauer_minutes
        """), {
            "id": item_id,
            "start": data.get("start"),
            "ziel":  data.get("ziel"),
            "dauer": data.get("dauer_minutes"),
        }).mappings().first()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))

@app.delete("/api/fahrten/<int:item_id>")
def fahrten_delete(item_id: int):
    err = require_db()
    if err:
        return err
    with engine.begin() as conn:
        row = conn.execute(text("""
            DELETE FROM fahrten
            WHERE id = :id
            RETURNING id
        """), {"id": item_id}).first()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({"deleted": row[0]})

# ------------------------------------------------------------
# Lokaler Start
# ------------------------------------------------------------
if __name__ == "__main__":
    # Für lokalen Test ohne Render (z.B. python backend/app.py)
    port = int(os.getenv("PORT", "3000"))
    print(f"Starting dev server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
