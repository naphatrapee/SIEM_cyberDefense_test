# Architecture

## Data flow
```
Syslog UDP/TCP (514) ─┐
POST /api/ingest ─────┼─► normalizers (per source) ─► enrich (GeoIP, reverse DNS) ─► PostgreSQL
File batch upload ────┘                                                               ▲   ▲
                                                           worker (alerts, retention) ┘   │
                                  React UI ◄── Caddy (HTTPS) ◄── API (JWT, RBAC, RLS) ────┘
```
Containers: `caddy`, `frontend`, `api`, `ingest`, `worker`, `postgres`. One Python image runs
`api`, `ingest` and `worker` (only the command differs), so `ingest/normalizers.py` is shared.

## Tenant model (true multi-tenancy, three layers)
1. **Physical separation.** `events` is partitioned `LIST (tenant)` and each tenant partition is
   sub-partitioned `RANGE (ts)` by day: `events_t_demoa_20261001`. Every tenant has its own tables
   and its own indexes. Retention drops a day-partition per tenant (`drop_old_partitions(7)`).
2. **Row-Level Security.** The API/ingest connect as `log_app` (not superuser, no `BYPASSRLS`).
   Each transaction sets `app.tenant` / `app.is_admin`; the policy is fail-closed (no setting = no rows).
   `log_app` has rights on the parent table only, so it cannot read a partition directly.
3. **API authorisation.** Tenant comes from the JWT claim, never from a request parameter
   (`app/policy.py: resolve_tenant`). Admin may pass `?tenant=`.

**Field-level RBAC** (`app/policy.py: HIDDEN_FIELDS`): viewers never receive `raw` or `extra`.

**Provisioning.** A tenant must exist before data is accepted (`SELECT provision_tenant('name')`).
Events for an unknown tenant fail (no partition) — sending data cannot create tenants.

**Trade-off.** Partition-per-tenant is great for tens of tenants; thousands would need a different
layout (too many tables). RLS protects against bugs in the API, not against a compromised app server
(which can set `app.is_admin`).

## Enrichment
At ingest, public `src_ip`/`dst_ip` get `extra.{src,dst}_geo` (country, city) from an offline MMDB and
`extra.{src,dst}_rdns` from reverse DNS (1 s timeout, cached). Private/documentation ranges
(e.g. 203.0.113.0/24 used in the sample files) are skipped by design. GeoIP is optional: `make geoip`
downloads the DB-IP City Lite database — *IP Geolocation by DB-IP* (CC BY 4.0).

## Why PostgreSQL
One system to operate for events, users and alerts; partitions give cheap retention; JSONB + GIN for
extra fields; RLS for isolation. Trade-off: free-text search over `raw` is weaker than OpenSearch.
