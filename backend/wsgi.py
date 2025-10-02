from app import app, init_db

# DB beim dyno-start sicherstellen
init_db()

# für Gunicorn
if __name__ != "__main__":
    application = app
