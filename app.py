import os
from flask import Flask, send_from_directory, jsonify
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

# --- Routes ---
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

@app.route("/")
def root():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 3000)))
