"""Integration test against a real Postgres that has db/01_schema.sql + 02_app_role.sh applied.
Skipped unless DATABASE_URL (log_app) and DATABASE_ADMIN_URL (owner) are set. CI sets both."""
import os
from datetime import datetime, timezone

import psycopg2
import pytest

pytestmark = pytest.mark.skipif(
    not (os.getenv("DATABASE_URL") and os.getenv("DATABASE_ADMIN_URL")),
    reason="needs DATABASE_URL and DATABASE_ADMIN_URL pointing at an initialised database",
)


@pytest.fixture()
def db():
    from app import db as appdb
    admin = psycopg2.connect(os.environ["DATABASE_ADMIN_URL"])
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("TRUNCATE events")
    now = datetime.now(timezone.utc)
    appdb.insert_events([
        {"tenant": "demoA", "source": "api", "event_type": "a1", "src_ip": "1.1.1.1", "ts": now, "raw": {"k": 1}},
        {"tenant": "demoA", "source": "api", "event_type": "a2", "src_ip": "not-an-ip", "ts": now},
        {"tenant": "demoB", "source": "aws", "event_type": "b1", "ts": now, "cloud": {"region": "x"}},
    ])
    yield appdb, admin
    admin.close()


def _types(appdb, tenant, is_admin=False):
    with appdb.scoped_cursor(tenant, is_admin) as cur:
        cur.execute("SELECT event_type FROM events ORDER BY event_type")
        return [r["event_type"] for r in cur.fetchall()]


def test_viewer_sees_only_own_tenant(db):
    appdb, _ = db
    assert _types(appdb, "demoA") == ["a1", "a2"]
    assert _types(appdb, "demoB") == ["b1"]


def test_no_tenant_context_sees_nothing(db):
    appdb, _ = db
    assert _types(appdb, None) == []          # fail-closed


def test_admin_sees_everything(db):
    appdb, _ = db
    assert _types(appdb, None, is_admin=True) == ["a1", "a2", "b1"]


def test_viewer_cannot_read_a_partition_directly(db):
    appdb, _ = db
    name = f"events_t_demob_{datetime.now(timezone.utc):%Y%m%d}"
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with appdb.scoped_cursor("demoA", False) as cur:
            cur.execute(f"SELECT * FROM {name}")


def test_unprovisioned_tenant_is_rejected(db):
    appdb, _ = db
    with pytest.raises(psycopg2.Error):
        appdb.insert_events([{"tenant": "ghost", "source": "api", "ts": datetime.now(timezone.utc)}])


def test_retention_drops_only_old_partitions(db):
    _, admin = db
    with admin.cursor() as cur:
        cur.execute("SELECT drop_old_partitions(7)")
        assert cur.fetchone()[0] == 0           # nothing older than 7 days yet
        cur.execute("SELECT drop_old_partitions(0)")
        assert cur.fetchone()[0] == 14          # 2 tenants x 7 past days
        cur.execute("SELECT ensure_all_partitions(7, 2)")   # restore for other tests
