# backend/
FastAPI app: auth (JWT, admin/viewer, tenant from token), ingest endpoints, search, stats, alerts.
`app/worker.py` runs as a separate container (alert rules + retention).
