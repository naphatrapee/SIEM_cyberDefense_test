import os

DATABASE_URL = os.environ["DATABASE_URL"]              # low-privilege role (log_app), subject to RLS
DATABASE_ADMIN_URL = os.getenv("DATABASE_ADMIN_URL", "")  # owner role, worker only (DDL / retention)
JWT_SECRET = os.getenv("JWT_SECRET", "")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
