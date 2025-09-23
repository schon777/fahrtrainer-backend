# app.py — Flask + SQLAlchemy Engine (Neon Postgres)
import os, json
from datetime import datetime
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from sqlalchemy import create_engine, text

# ---------- Flask ----------
# static_url_path="/static", damit /api/* nicht mit Static kollidiert
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app, resources={r"/*": {"origins": os.getenv("ALLOWED_ORIGINS", "*").split(",")}})

# ---------- DB ----------
db_url = os.getenv("DATABASE_URL", "")
# Render/Neon liefert oft "postgres://" -> für SQLAlchemy auf "postgresql://"
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url, pool_pre_ping=True) if db_url else None

def init_fahrten():
    if not engine:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fahrten (
              id BIGSERIAL PRIMARY KEY,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              start TEXT NOT NULL,
              ziel  TEXT NOT NULL,
              dauer_minutes INT
            )
        """))

def init_kv():
    if not engine:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS kv_items (
              id BIGSERIAL PRIMARY KEY,
              page TEXT NOT NULL,
              k    TEXT NOT NULL,
              v    JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              UNIQUE(page, k)
            )
        """))

init_fahrten()
init_kv()

# ---------- No-Cache für API ----------
@app.after_request
def add_no_cache_headers(resp):
    # API-Responses niemals cachen
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp

# ---------- Health & Debug ----------
@app.get("/api/ping")
def ping():
    return jsonify(ok=True)

@app.get("/api/time")
def get_time():
    if not engine:
        return {"error": "DATABASE_URL not set"}, 500
    with engine.connect() as conn:
        now = conn.execute(text("SELECT NOW()")).scalar_one()
    return {"server_time": str(now)}

@app.get("/api/debug/db")
def db_debug():
    if not engine:
        return {"engine": None}, 500
    with engine.connect() as conn:
        db, host = conn.execute(text("select current_database(), inet_server_addr()::text")).one()
    return {"db": db, "host": host}

# ---------- Fahrten-API (CRUD) ----------
@app.post("/api/fahrten")
def create_fahrt():
    if not engine:
        return {"error": "DB not ready"}, 500
    data = request.get_json(force=True) or {}
    start = (data.get("start") or "").strip()
    ziel  = (data.get("ziel")  or "").strip()
    dauer = data.get("dauer_minutes")
    if not start or not ziel:
        return {"error": "start und ziel sind Pflicht"}, 400
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO fahrten (start, ziel, dauer_minutes)
            VALUES (:start, :ziel, :dauer)
            RETURNING id, created_at, start, ziel, dauer_minutes
        """), {"start": start, "ziel": ziel, "dauer": dauer}).mappings().one()
    r = dict(row); r["created_at"] = r["created_at"].isoformat()
    return r, 201

@app.get("/api/fahrten")
def list_fahrten():
    if not engine:
        return {"error": "DB not ready"}, 500
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, created_at, start, ziel, dauer_minutes
            FROM fahrten
            ORDER BY created_at DESC
            LIMIT 100
        """)).mappings().all()
    items = []
    for row in rows:
        d = dict(row); d["created_at"] = d["created_at"].isoformat()
        items.append(d)
    return {"items": items}

@app.get("/api/fahrten/<int:id>")
def get_fahrt(id):
    if not engine:
        return {"error": "DB not ready"}, 500
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, created_at, start, ziel, dauer_minutes
            FROM fahrten WHERE id=:id
        """), {"id": id}).mappings().first()
    if not row:
        return {"error": "not found"}, 404
    r = dict(row); r["created_at"] = r["created_at"].isoformat()
    return r

@app.put("/api/fahrten/<int:id>")
def update_fahrt(id):
    if not engine:
        return {"error": "DB not ready"}, 500
    data = request.get_json(force=True) or {}
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE fahrten
            SET start = COALESCE(:start, start),
                ziel  = COALESCE(:ziel,  ziel),
                dauer_minutes = COALESCE(:dauer, dauer_minutes)
            WHERE id = :id
            RETURNING id, created_at, start, ziel, dauer_minutes
        """), {
            "id": id,
            "start": (data.get("start").strip() if data.get("start") else None),
            "ziel":  (data.get("ziel").strip()  if data.get("ziel")  else None),
            "dauer": data.get("dauer_minutes")
        }).mappings().first()
    if not row:
        return {"error": "not found"}, 404
    r = dict(row); r["created_at"] = r["created_at"].isoformat()
    return r

@app.delete("/api/fahrten/<int:id>")
def delete_fahrt(id):
    if not engine:
        return {"error": "DB not ready"}, 500
    with engine.begin() as conn:
        row = conn.execute(text("DELETE FROM fahrten WHERE id=:id RETURNING id"), {"id": id}).first()
    return ({"deleted": row[0]}, 200) if row else ({"error": "not found"}, 404)

# ---------- KV-API (Key/Value für Seiten) ----------
# Format wie dein Frontend erwartet:
# GET  /api/kv?page=kalender        -> { items: [ {id, k, v}, ... ] }
# POST /api/kv {page,key,value}     -> { id, k, v }  (UPSERT)
# DEL  /api/kv/<id>                 -> { deleted: id }
@app.get("/api/kv")
def kv_list():
    if not engine:
        return {"error": "DB not ready"}, 500
    page = request.args.get("page")
    if not page:
        return {"error": "missing ?page="}, 400
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, k, v
            FROM kv_items
            WHERE page = :page
            ORDER BY updated_at DESC, id DESC
        """), {"page": page}).mappings().all()
    return {"items": [dict(r) for r in rows]}

@app.post("/api/kv")
def kv_upsert():
    if not engine:
        return {"error": "DB not ready"}, 500
    data = request.get_json(force=True) or {}
    page = (data.get("page") or "").strip()
    key  = (data.get("key")  or "").strip()
    val  = data.get("value", {})

    if not page or not key:
        return {"error":"page and key required"}, 400

    # Immer gültiges JSON und als jsonb casten
    val_json = json.dumps(val)

    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO kv_items (page, k, v, created_at, updated_at)
            VALUES (:page, :k, :v::jsonb, NOW(), NOW())
            ON CONFLICT (page, k)
            DO UPDATE SET v = EXCLUDED.v, updated_at = NOW()
            RETURNING id, k, v
        """), {"page": page, "k": key, "v": val_json}).mappings().one()

    return dict(row), 200  # {id, k, v}

@app.delete("/api/kv/<int:item_id>")
def kv_delete(item_id: int):
    if not engine:
        return {"error":"DB not ready"}, 500
    with engine.begin() as conn:
        row = conn.execute(text("DELETE FROM kv_items WHERE id=:id RETURNING id"), {"id": item_id}).first()
    return ({"deleted": row[0]}, 200) if row else ({"error":"not found"}, 404)

# ---------- Static: Catch-All ----------
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    full = os.path.join(app.static_folder, path)
    if path and os.path.exists(full):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

# ---------- Local run ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 3000)))
