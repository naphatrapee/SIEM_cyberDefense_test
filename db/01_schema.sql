-- =====================================================================
-- Multi-tenant event store
--   events  --LIST(tenant)-->  events_t_<tenant>  --RANGE(ts)-->  events_t_<tenant>_YYYYMMDD
-- Each tenant gets physically separate tables; retention = DROP a day-partition.
-- Row-Level Security is a second layer (defence in depth) on top of API checks.
-- =====================================================================
SET timezone = 'UTC';

CREATE TABLE tenants (
    name       TEXT PRIMARY KEY CHECK (name ~ '^[A-Za-z0-9_]{1,40}$'),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX tenants_lower_name ON tenants (lower(name));

CREATE TABLE events (
    id            BIGSERIAL,
    ts            TIMESTAMPTZ NOT NULL,          -- @timestamp
    tenant        TEXT NOT NULL,
    source        TEXT NOT NULL,                 -- firewall|crowdstrike|aws|m365|ad|api|network
    vendor        TEXT,
    product       TEXT,
    event_type    TEXT,
    event_subtype TEXT,
    severity      SMALLINT DEFAULT 0,            -- 0-10
    action        TEXT,                          -- allow|deny|create|delete|login|logout|alert
    src_ip        INET,
    src_port      INTEGER,
    dst_ip        INET,
    dst_port      INTEGER,
    protocol      TEXT,
    user_name     TEXT,
    host          TEXT,
    process       TEXT,
    url           TEXT,
    http_method   TEXT,
    status_code   INTEGER,
    rule_name     TEXT,
    rule_id       TEXT,
    cloud         JSONB,                         -- account_id, region, service
    raw           TEXT,
    tags          TEXT[] DEFAULT '{}',
    extra         JSONB DEFAULT '{}',            -- enrichment: src_geo, dst_geo, src_rdns, dst_rdns
    PRIMARY KEY (id, tenant, ts)
) PARTITION BY LIST (tenant);

-- Indexes on the parent are created automatically on every (future) partition
CREATE INDEX idx_events_ts        ON events (ts DESC);
CREATE INDEX idx_events_source    ON events (source, ts DESC);
CREATE INDEX idx_events_src_ip    ON events (src_ip);
CREATE INDEX idx_events_user      ON events (user_name);
CREATE INDEX idx_events_extra_gin ON events USING GIN (extra);

-- ---------- partition management ----------
CREATE OR REPLACE FUNCTION ensure_tenant(t TEXT) RETURNS VOID AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM tenants WHERE lower(name) = lower(t) AND name <> t) THEN
        RAISE EXCEPTION 'tenant % clashes with an existing tenant that differs only by case', t;
    END IF;
    INSERT INTO tenants (name) VALUES (t) ON CONFLICT DO NOTHING;
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF events FOR VALUES IN (%L) PARTITION BY RANGE (ts)',
        'events_t_' || lower(t), t);
END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ensure_partition(t TEXT, d DATE) RETURNS VOID AS $$
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
        'events_t_' || lower(t) || '_' || to_char(d, 'YYYYMMDD'),
        'events_t_' || lower(t),
        (d::timestamp AT TIME ZONE 'UTC'),
        ((d + 1)::timestamp AT TIME ZONE 'UTC'));
END $$ LANGUAGE plpgsql;

-- Day-partitions for every tenant from (today - back) to (today + ahead)
CREATE OR REPLACE FUNCTION ensure_all_partitions(back INT, ahead INT) RETURNS VOID AS $$
DECLARE r RECORD; g INT;
BEGIN
    FOR r IN SELECT name FROM tenants LOOP
        FOR g IN -back..ahead LOOP
            PERFORM ensure_partition(r.name, (now() AT TIME ZONE 'UTC')::date + g);
        END LOOP;
    END LOOP;
END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION provision_tenant(t TEXT) RETURNS VOID AS $$
DECLARE g INT;
BEGIN
    PERFORM ensure_tenant(t);
    FOR g IN -7..2 LOOP
        PERFORM ensure_partition(t, (now() AT TIME ZONE 'UTC')::date + g);
    END LOOP;
END $$ LANGUAGE plpgsql;

-- Drop day-partitions older than keep_days (retention)
CREATE OR REPLACE FUNCTION drop_old_partitions(keep_days INT) RETURNS INT AS $$
DECLARE r RECORD; n INT := 0;
BEGIN
    FOR r IN SELECT c.relname FROM pg_inherits i
             JOIN pg_class c ON c.oid = i.inhrelid
             JOIN pg_class p ON p.oid = i.inhparent
             WHERE p.relname LIKE 'events\_t\_%'
               AND c.relkind IN ('r', 'p')          -- tables only (skip child indexes)
               AND right(c.relname, 8) ~ '^[0-9]{8}$'
               AND right(c.relname, 8) < to_char((now() AT TIME ZONE 'UTC')::date - keep_days, 'YYYYMMDD')
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I', r.relname);
        n := n + 1;
    END LOOP;
    RETURN n;
END $$ LANGUAGE plpgsql;

SELECT provision_tenant('demoA');
SELECT provision_tenant('demoB');

-- ---------- Row-Level Security ----------
-- Fail-closed: if app.tenant is unset the policy matches nothing.
-- app.is_admin is set by trusted server code only (API from the JWT, ingest path).
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE events FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON events
    USING      (current_setting('app.is_admin', true) = 'on' OR tenant = current_setting('app.tenant', true))
    WITH CHECK (current_setting('app.is_admin', true) = 'on' OR tenant = current_setting('app.tenant', true));

-- ---------- users / alerts ----------
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin','viewer')),
    tenant        TEXT REFERENCES tenants(name),        -- NULL for admin (all tenants)
    CHECK ((role = 'admin') OR (tenant IS NOT NULL))
);

CREATE TABLE alert_rules (
    id             SERIAL PRIMARY KEY,
    name           TEXT NOT NULL,
    tenant         TEXT,                                -- NULL = all tenants
    threshold      INTEGER NOT NULL DEFAULT 5,
    window_minutes INTEGER NOT NULL DEFAULT 5,
    webhook_url    TEXT,
    enabled        BOOLEAN DEFAULT TRUE
);

CREATE TABLE alerts (
    id        BIGSERIAL PRIMARY KEY,
    rule_id   INTEGER REFERENCES alert_rules(id),
    tenant    TEXT NOT NULL,
    fired_at  TIMESTAMPTZ DEFAULT now(),
    src_ip    INET,
    count     INTEGER,
    message   TEXT,
    notified  BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_alerts_tenant ON alerts (tenant, fired_at DESC);

INSERT INTO alert_rules (name, threshold, window_minutes)
VALUES ('Repeated failed logins from same IP', 5, 5);
-- Users are seeded by the backend on startup (bcrypt hashes from .env passwords)
