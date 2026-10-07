from fastapi import FastAPI

app = FastAPI(title="Log Management API", root_path="")

# TODO: POST /api/ingest, /api/ingest/file, /api/auth/login, routes from routes.py


@app.get("/api/health")
def health():
    return {"status": "ok"}
