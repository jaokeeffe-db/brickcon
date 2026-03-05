-- Unity Catalog Setup for Databricks Disruption Response Agent
-- Run this in a Databricks SQL editor or notebook against your workspace.
-- Requires CATALOG CREATE privilege on the metastore.

-- ===========================================================================
-- 1. CATALOG
-- ===========================================================================

CREATE CATALOG IF NOT EXISTS utility_ops
  COMMENT 'Top-level governance boundary for the Predictive Maintenance demo. Covers all sensor data, maintenance history, and AI assets.';

USE CATALOG utility_ops;

-- ===========================================================================
-- 2. SCHEMAS
-- ===========================================================================

-- Landing zone: raw files only, no Delta tables
CREATE SCHEMA IF NOT EXISTS utility_ops.raw_ingestion
  COMMENT 'Landing zone for raw CSV/JSON uploads and technical manuals. No processed tables.';

-- All medallion Delta tables + UC Functions
CREATE SCHEMA IF NOT EXISTS utility_ops.asset_intelligence
  COMMENT 'Bronze, Silver, and Gold Delta Lake tables for the asset health medallion pipeline. Also hosts UC Agent tool functions.';

-- Vector Search source tables and index metadata
CREATE SCHEMA IF NOT EXISTS utility_ops.vector_store
  COMMENT 'Source tables for Mosaic AI Vector Search indexes (technical manuals and failure patterns).';

-- ===========================================================================
-- 3. VOLUMES
-- ===========================================================================

CREATE VOLUME IF NOT EXISTS utility_ops.raw_ingestion.raw_telemetry
  COMMENT 'Raw sensor telemetry CSV/JSON files uploaded from local data generation scripts.';

CREATE VOLUME IF NOT EXISTS utility_ops.raw_ingestion.technical_manuals
  COMMENT 'Markdown technical manuals for motors, pumps, and compressors. Indexed by Vector Search.';

-- ===========================================================================
-- 4. TAGS
-- ===========================================================================

-- Tag the gold tables as critical_path so the agent understands data significance
ALTER TABLE utility_ops.asset_intelligence.gold_vibration_trends
  SET TAGS ('critical_path' = 'true');

ALTER TABLE utility_ops.asset_intelligence.gold_health_scores
  SET TAGS ('critical_path' = 'true');

ALTER TABLE utility_ops.asset_intelligence.gold_cost_impact
  SET TAGS ('critical_path' = 'true');

-- Tag bronze/silver sensor tables for data lineage classification
ALTER TABLE utility_ops.asset_intelligence.bronze_sensor_readings
  SET TAGS ('sensor_data' = 'true', 'pii' = 'false');

ALTER TABLE utility_ops.asset_intelligence.silver_sensor_readings
  SET TAGS ('sensor_data' = 'true', 'pii' = 'false');

-- All tables explicitly marked pii=false for compliance queries
ALTER TABLE utility_ops.asset_intelligence.bronze_maintenance_logs
  SET TAGS ('pii' = 'false');

ALTER TABLE utility_ops.asset_intelligence.silver_maintenance_logs
  SET TAGS ('pii' = 'false');

ALTER TABLE utility_ops.asset_intelligence.silver_asset_metadata
  SET TAGS ('pii' = 'false');

-- Note: Tags on gold tables are set above. Run the TAGS block AFTER the
-- Lakeflow pipeline has created the tables on its first run.
