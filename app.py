import os
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from sqlalchemy import create_engine, text

# --- Flask ---
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app, resources={r"/*": {"origins": os.getenv("ALLOWED_ORIGINS", "*").split(",")}})

# --- DB ---
db_url = os.getenv("DATABASE_URL", "")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
engine = create_engine(db_url, pool_pre_ping=True) if db_url else None

def init_db():
    if not engine:
        return
    # Tabelle für Beispiel-Daten
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fahrten (
              id BIGSERIAL PRIMARY KEY,
              created_at TIMESTAMPTZ DEFAULT NOW(),
              start TEXT NOT NULL,
              ziel  TEXT NOT NULL,
              dauer_minutes INT
            )
        """))
init_db()

# --- Health & DB-Check ---
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

# --- Daten-API ---
@app.post("/api/fahrten")
def create_fahrt():
    if not engine:
        return {"error": "DATABASE_URL not set"}, 500
    data = request.get_json(force=True) or {}
    start = (data.get("start") or "").strip()
    ziel  = (data.get("ziel") or "").strip()
    dauer = data.get("dauer_minutes")
    if not start or not ziel:
        return {"error": "start und ziel sind Pflicht"}, 400
    with engine.begin() as conn:
        row = conn.execute(
            text("""INSERT INTO fahrten (start, ziel, dauer_minutes)
                    VALUES (:start,:ziel,:dauer)
                    RETURNING id, created_at, start, ziel, dauer_minutes"""),
            {"start": start, "ziel": ziel, "dauer": dauer}
        ).mappings().one()
    return dict(row), 201

@app.get("/api/fahrten")
def list_fahrten():
    if not engine:
        return {"error": "DATABASE_URL not set"}, 500
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT id, created_at, start, ziel, dauer_minutes
                    FROM fahrten
                    ORDER BY created_at DESC
                    LIMIT 100""")
        ).mappings().all()
    return {"items": [dict(r) for r in rows]}

# --- Static (optional, falls du dort ein Frontend ablegst) ---
@app.route("/")
def root():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 3000)))
