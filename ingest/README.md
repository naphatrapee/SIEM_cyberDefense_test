# ingest/
- `syslog_listener.py` — UDP+TCP listener (5514 in the container, host 514). Queue → batches of 200 / 1 s →
  normalize → enrich → INSERT (DB work runs in a thread so receiving never stalls).
- `normalizers.py` — one function per source into the common schema (shared with the backend).
- `enrich.py` — GeoIP (offline MMDB, optional) + reverse DNS; never raises, times out at 1 s, cached.
