import os, sqlite3, json
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.sqlite3"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    # KV-Tabelle (seitenbezogene Key/Value)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kv (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          page TEXT NOT NULL,
          key TEXT NOT NULL,
          value TEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Fahrten-Tabelle (einfaches CRUD)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fahrten (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          datum TEXT,
          start TEXT,
          ziel TEXT,
          kilometer REAL,
          bemerkung TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

@app.route("/")
def root_ok():
    return "OK", 200

# -------- KV --------
@app.route("/api/kv", methods=["GET"])
def kv_list():
    page = request.args.get("page", "")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM kv WHERE page = ? ORDER BY id DESC", (page,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"items": rows})

@app.route("/api/kv", methods=["POST"])
def kv_set():
    payload = request.get_json(force=True)
    page = payload.get("page","")
    key  = payload.get("key","")
    value = json.dumps(payload.get("value", None), ensure_ascii=False)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO kv(page,key,value) VALUES (?,?,?)", (page,key,value))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"id": new_id, "page": page, "key": key})

@app.route("/api/kv/<int:row_id>", methods=["DELETE"])
def kv_delete(row_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM kv WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
    return ("", 204)

# -------- Fahrten --------
@app.route("/api/fahrten", methods=["GET"])
def fahrten_list():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fahrten ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"items": rows})

@app.route("/api/fahrten", methods=["POST"])
def fahrten_create():
    payload = request.get_json(force=True)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO fahrten(datum,start,ziel,kilometer,bemerkung)
        VALUES (?,?,?,?,?)
    """, (
        payload.get("datum"),
        payload.get("start"),
        payload.get("ziel"),
        payload.get("kilometer"),
        payload.get("bemerkung"),
    ))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"id": new_id}), 201

@app.route("/api/fahrten/<int:fid>", methods=["PUT"])
def fahrten_update(fid):
    payload = request.get_json(force=True)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE fahrten
           SET datum=?, start=?, ziel=?, kilometer=?, bemerkung=?
         WHERE id=?
    """, (
        payload.get("datum"),
        payload.get("start"),
        payload.get("ziel"),
        payload.get("kilometer"),
        payload.get("bemerkung"),
        fid,
    ))
    conn.commit()
    conn.close()
    return ("", 204)

@app.route("/api/fahrten/<int:fid>", methods=["DELETE"])
def fahrten_delete(fid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM fahrten WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    return ("", 204)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

# --- Health checks ---------------------------------------------
@app.get("/api/ping")
def ping():
    return {"status": "ok"}, 200

@app.get("/")
def root_ok():
    # Falls der Health Check mal auf / gestellt wird
    return "OK", 200
