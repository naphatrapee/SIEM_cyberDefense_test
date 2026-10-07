"""Worker: retention (daily) + alert rules (every 30s, TODO)."""
import os
import time
from datetime import date

import psycopg2

from app.config import DATABASE_ADMIN_URL, RETENTION_DAYS


def run_retention():
    """Create today..+2 partitions for every tenant, then drop partitions older than RETENTION_DAYS."""
    conn = psycopg2.connect(DATABASE_ADMIN_URL)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT ensure_all_partitions(0, 2)")
            cur.execute("SELECT drop_old_partitions(%s)", (RETENTION_DAYS,))
            dropped = cur.fetchone()[0]
        print(f"retention: partitions ensured, {dropped} old dropped", flush=True)
    finally:
        conn.close()


def main():
    print("worker started", flush=True)
    last_retention = None
    while True:
        if last_retention != date.today():
            run_retention()          # runs at startup and once per day
            last_retention = date.today()
        # TODO: run alert rules (GROUP BY src_ip HAVING count(*) >= threshold),
        #       insert into alerts, POST webhook
        time.sleep(30)


if __name__ == "__main__":
    main()
