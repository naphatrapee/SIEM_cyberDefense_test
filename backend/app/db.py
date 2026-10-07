import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from ipaddress import ip_address

from psycopg2.extras import Json, RealDictCursor, execute_values
from psycopg2.pool import ThreadedConnectionPool

_pool = None

COLUMNS = [
    "ts", "tenant", "source", "vendor", "product", "event_type", "event_subtype",
    "severity", "action", "src_ip", "src_port", "dst_ip", "dst_port", "protocol",
    "user_name", "host", "process", "url", "http_method", "status_code",
    "rule_name", "rule_id", "cloud", "raw", "tags", "extra",
]
SQL = f"INSERT INTO events ({', '.join(COLUMNS)}) VALUES %s"


@contextmanager
def get_conn():
    global _pool
    if _pool is None:  # lazy: importing this module never needs a database
        _pool = ThreadedConnectionPool(1, 10, dsn=os.environ["DATABASE_URL"])
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


@contextmanager
def scoped_cursor(tenant: str | None, is_admin: bool):
    """Cursor whose transaction carries the caller's tenant for Row-Level Security.
    set_config(..., true) is transaction-local, so nothing leaks to the next pooled use."""
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT set_config('app.tenant', %s, true), set_config('app.is_admin', %s, true)",
                    (tenant or "", "on" if is_admin else "off"),
                )
                yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _ip(v):
    try:
        return str(ip_address(str(v).strip())) if v else None
    except ValueError:
        return None


def _row(e: dict) -> tuple:
    raw = e.get("raw")
    if raw is not None and not isinstance(raw, str):
        raw = json.dumps(raw, default=str)
    return (
        e.get("ts") or datetime.now(timezone.utc), e["tenant"], e.get("source"),
        e.get("vendor"), e.get("product"), e.get("event_type"), e.get("event_subtype"),
        e.get("severity", 1), e.get("action"), _ip(e.get("src_ip")), e.get("src_port"),
        _ip(e.get("dst_ip")), e.get("dst_port"), e.get("protocol"),
        e.get("user_name") or e.get("user"), e.get("host"), e.get("process"),
        e.get("url"), e.get("http_method"), e.get("status_code"),
        e.get("rule_name"), e.get("rule_id"),
        Json(e["cloud"]) if e.get("cloud") else None,
        raw, e.get("tags") or [], Json(e.get("extra") or {}),
    )


def insert_events(events: list[dict]) -> int:
    """Trusted server-side insert (callers have already authorised the tenant).
    Events without a tenant are skipped. A tenant that was never provisioned has no
    partition, so the insert raises -> tenants cannot be created by sending data."""
    rows = [_row(e) for e in events if e.get("tenant")]
    if not rows:
        return 0
    with scoped_cursor(None, is_admin=True) as cur:
        execute_values(cur, SQL, rows)
    return len(rows)
