-- Lakebase (Serverless Postgres on AWS) — Operational Tier Setup
-- Run this against your Lakebase instance using psql or any Postgres client.
-- Connection details are in .env (LAKEBASE_HOST, LAKEBASE_PORT, etc.)
--
-- Usage:
--   psql "host=$LAKEBASE_HOST port=$LAKEBASE_PORT dbname=$LAKEBASE_DATABASE user=$LAKEBASE_USER password=$LAKEBASE_PASSWORD sslmode=require" -f lakebase_setup.sql

-- ===========================================================================
-- 1. LIVE ASSET HEALTH STATE
-- Updated by lakebase_sync.py every pipeline run (sub-second via UPSERT).
-- Primary source for the Control Tower floor map and active alert feed.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS asset_health_live (
    asset_id              TEXT        PRIMARY KEY,
    health_score          FLOAT       NOT NULL,
    risk_level            TEXT        NOT NULL,    -- CRITICAL / HIGH / MEDIUM / LOW
    current_vibration     FLOAT,
    current_temp          FLOAT,
    rated_max_vibration   FLOAT,
    estimated_rul_hours   FLOAT,                  -- NULL if no degradation trend
    production_line_id    TEXT,
    criticality_tier      INT,
    calculated_at         TIMESTAMPTZ,
    last_updated          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast risk_level filtering (floor map queries)
CREATE INDEX IF NOT EXISTS idx_asset_health_risk
    ON asset_health_live (risk_level, production_line_id);

COMMENT ON TABLE asset_health_live IS
    'Live asset health state updated from Gold layer after each Lakeflow pipeline run. '
    'Primary source for the Maintenance Control Tower floor map.';

-- ===========================================================================
-- 2. ACTIVE DISRUPTION EVENTS
-- Inserted when an asset transitions to CRITICAL or HIGH risk.
-- Resolved by the Control Tower or by the agent upsert tool.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS asset_disruption (
    disruption_id           SERIAL      PRIMARY KEY,
    asset_id                TEXT        NOT NULL,
    machine_id              TEXT,                   -- human-readable alias (e.g. "Motor_4")
    risk_level              TEXT        NOT NULL,
    impacted_line_id        TEXT,
    detection_timestamp     TIMESTAMPTZ NOT NULL DEFAULT now(),
    estimated_rul_hours     FLOAT,
    estimated_downtime_cost FLOAT,
    recommended_action      TEXT,
    status                  TEXT        NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE / ACKNOWLEDGED / RESOLVED
    resolved_at             TIMESTAMPTZ,
    resolved_by             TEXT
);

CREATE INDEX IF NOT EXISTS idx_disruption_status
    ON asset_disruption (status, risk_level, detection_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_disruption_asset
    ON asset_disruption (asset_id, status);

COMMENT ON TABLE asset_disruption IS
    'Active disruption events. Inserted when health score drops to CRITICAL or HIGH. '
    'Linked to Unity Catalog via asset_id for full lineage traceability.';

-- ===========================================================================
-- 3. AI-GENERATED MAINTENANCE RECOMMENDATIONS
-- Written by the agent upsert_recommendation tool after each reasoning loop.
-- Stores RAG provenance (vector search sources) for lineage and trust.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS maintenance_recommendations (
    rec_id                  SERIAL      PRIMARY KEY,
    asset_id                TEXT        NOT NULL,
    recommendation_text     TEXT        NOT NULL,
    cost_to_fix             FLOAT,
    cost_of_downtime        FLOAT,
    urgency_hours           FLOAT,
    net_recommendation      TEXT,                   -- SCHEDULE_IMMEDIATE / SCHEDULE_PLANNED / MONITOR
    vector_search_sources   TEXT[],                 -- RAG provenance: chunk_ids used
    manual_references       TEXT[],                 -- e.g. ['motor_bearing_replacement.md#section-5']
    health_score_at_time    FLOAT,
    created_by_session      TEXT,                   -- Databricks Apps session ID
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rec_asset_recent
    ON maintenance_recommendations (asset_id, created_at DESC);

COMMENT ON TABLE maintenance_recommendations IS
    'AI-generated repair plans from the Mosaic AI maintenance agent. '
    'vector_search_sources and manual_references columns provide full RAG provenance '
    'for the Lineage & Trust customer requirement.';

-- ===========================================================================
-- 4. SEED DATA FUNCTION
-- Call this to reset the demo to initial state (e.g. before a live demo).
-- ===========================================================================

CREATE OR REPLACE FUNCTION reset_demo_state()
RETURNS void AS $$
BEGIN
    DELETE FROM maintenance_recommendations;
    DELETE FROM asset_disruption;
    UPDATE asset_health_live
    SET status = 'ACTIVE'  -- no-op, just confirming reset
    WHERE 1=0;             -- reset_demo_state does not wipe health scores
                           -- (those are re-populated by lakebase_sync.py)
    RAISE NOTICE 'Demo state reset: recommendations and disruptions cleared.';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION reset_demo_state IS
    'Convenience function to clear AI recommendations and disruption events '
    'before a live customer demo. Does not clear asset_health_live as that '
    'is repopulated automatically by lakebase_sync.py.';
