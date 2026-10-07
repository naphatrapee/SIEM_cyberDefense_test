# Log Management Demo

> **New to the project? Start with [`docs/HANDOVER.md`](docs/HANDOVER.md)** (status, architecture, known issues, remaining work).
Mini SIEM: multi-source ingest -> normalize -> enrich -> PostgreSQL (partition per tenant + RLS) -> dashboard + alerts.
Appliance and SaaS modes from one Docker Compose file.

    make up      # start everything (creates .env from .env.example if missing)
    make geoip   # optional: GeoIP enrichment database
    make seed    # send sample data
    make test    # pytest (DB integration tests run when DATABASE_URL / DATABASE_ADMIN_URL are set)

Docs: `docs/architecture.md`, `docs/setup_appliance.md`, `docs/setup_saas.md`. IaC: `terraform/`. CI/CD: `.github/workflows/`.

## Nice-to-have status
| Item | Status |
|---|---|
| True multi-tenancy (partition per tenant) + RLS + field-level RBAC | schema, policy and tests done; API wiring TODO |
| Enrichment (GeoIP + reverse DNS) | done for syslog path; call `enrich()` from `/api/ingest` TODO |
| CI/CD (GitHub Actions) | written, not yet run on GitHub |
| IaC (Terraform, AWS) | written, not yet applied |
| Tests | 16 passing locally incl. Postgres integration |
"# SIEM_cyberDefense_test" 
