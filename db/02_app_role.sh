#!/bin/bash
# Creates the low-privilege role the API/ingest connect as. It is NOT superuser and does NOT
# bypass RLS. It only has rights on the parent `events` table (not on partitions), so it
# cannot read a tenant partition directly. The owner role (POSTGRES_USER) is for the worker (DDL).
set -e
psql -v ON_ERROR_STOP=1 -v app_pw="$APP_DB_PASSWORD" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE ROLE log_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO log_app;
GRANT SELECT, INSERT ON events TO log_app;
GRANT USAGE ON SEQUENCE events_id_seq TO log_app;
GRANT SELECT ON tenants TO log_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON alert_rules, alerts, users TO log_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO log_app;
EOSQL
