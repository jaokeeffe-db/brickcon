"""
Lakebase Sync Service: Gold → Lakebase (Serverless Postgres)

Reads the latest records from `gold_health_scores` and `gold_cost_impact` in Unity Catalog
and upserts them into the Lakebase operational tier for sub-second dashboard updates.

Also inserts new disruption events into `asset_disruption` when an asset transitions to
CRITICAL or HIGH risk level.

Run this:
  - As a Databricks Job after each Lakeflow pipeline run (triggered mode)
  - Or as a scheduled job every 10 minutes in continuous pipelines

Prerequisites:
  - Databricks Connect configured
  - Lakebase connection details in environment variables (see .env.example)
  - Unity Catalog tables populated by lakeflow_pipeline.py

Usage:
  python services/lakebase_sync.py
  # Or deploy as a Databricks job via databricks.yml
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

from databricks.connect import DatabricksSession

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CATALOG = os.getenv("UC_CATALOG", "utility_ops")
SCHEMA = os.getenv("UC_SCHEMA", "asset_intelligence")

LAKEBASE_CONFIG = {
    "host": os.getenv("LAKEBASE_HOST"),
    "port": int(os.getenv("LAKEBASE_PORT", "5432")),
    "dbname": os.getenv("LAKEBASE_DATABASE", "maintenance_ops"),
    "user": os.getenv("LAKEBASE_USER"),
    "password": os.getenv("LAKEBASE_PASSWORD"),
    "sslmode": "require",
    "connect_timeout": 10,
}

# Risk levels that trigger a disruption event insertion
DISRUPTION_RISK_LEVELS = {"CRITICAL", "HIGH"}


# ---------------------------------------------------------------------------
# Read from Unity Catalog (Gold layer)
# ---------------------------------------------------------------------------

REQUIRED_TABLES = [
    f"{CATALOG}.{SCHEMA}.gold_health_scores",
    f"{CATALOG}.{SCHEMA}.gold_cost_impact",
]


def check_tables_exist(spark) -> None:
    """Raise a clear error if the Gold tables haven't been created by the pipeline yet."""
    missing = [t for t in REQUIRED_TABLES if not spark.catalog.tableExists(t)]
    if missing:
        raise SystemExit(
            "\nERROR: The following tables do not exist yet:\n"
            + "\n".join(f"  - {t}" for t in missing)
            + "\n\nThe Gold tables are created by the Lakeflow pipeline. Run it first:\n"
            "  1. In your Databricks workspace, go to Pipelines\n"
            "  2. Create a pipeline from pipelines/lakeflow_pipeline.py\n"
            "  3. Start a pipeline run and wait for it to complete\n"
            "  4. Then re-run this script\n"
        )


def fetch_latest_health_scores(spark) -> list[dict]:
    """Read the most recent health score per asset from gold_health_scores."""
    df = spark.sql(f"""
        SELECT
            h.asset_id,
            h.health_score,
            h.risk_level,
            h.current_vibration,
            h.current_temp,
            h.rated_max_vibration,
            h.estimated_rul_hours,
            h.production_line_id,
            h.criticality_tier,
            h.calculated_at,
            c.cost_to_fix_now,
            c.cost_of_unplanned_failure,
            c.net_recommendation
        FROM {CATALOG}.{SCHEMA}.gold_health_scores h
        LEFT JOIN {CATALOG}.{SCHEMA}.gold_cost_impact c
            ON h.asset_id = c.asset_id
    """)
    return [row.asDict() for row in df.collect()]


# ---------------------------------------------------------------------------
# Upsert asset health to Lakebase
# ---------------------------------------------------------------------------

UPSERT_HEALTH_SQL = """
    INSERT INTO asset_health_live (
        asset_id, health_score, risk_level, current_vibration,
        current_temp, rated_max_vibration, estimated_rul_hours,
        production_line_id, criticality_tier, calculated_at, last_updated
    ) VALUES (
        %(asset_id)s, %(health_score)s, %(risk_level)s, %(current_vibration)s,
        %(current_temp)s, %(rated_max_vibration)s, %(estimated_rul_hours)s,
        %(production_line_id)s, %(criticality_tier)s, %(calculated_at)s, now()
    )
    ON CONFLICT (asset_id) DO UPDATE SET
        health_score          = EXCLUDED.health_score,
        risk_level            = EXCLUDED.risk_level,
        current_vibration     = EXCLUDED.current_vibration,
        current_temp          = EXCLUDED.current_temp,
        rated_max_vibration   = EXCLUDED.rated_max_vibration,
        estimated_rul_hours   = EXCLUDED.estimated_rul_hours,
        production_line_id    = EXCLUDED.production_line_id,
        criticality_tier      = EXCLUDED.criticality_tier,
        calculated_at         = EXCLUDED.calculated_at,
        last_updated          = now()
"""

INSERT_DISRUPTION_SQL = """
    INSERT INTO asset_disruption (
        asset_id, machine_id, risk_level, impacted_line_id,
        estimated_rul_hours, estimated_downtime_cost, recommended_action
    )
    SELECT
        %(asset_id)s, %(asset_id)s, %(risk_level)s, %(production_line_id)s,
        %(estimated_rul_hours)s, %(estimated_downtime_cost)s, %(net_recommendation)s
    WHERE NOT EXISTS (
        SELECT 1 FROM asset_disruption
        WHERE asset_id = %(asset_id)s
          AND status = 'ACTIVE'
          AND detection_timestamp > now() - INTERVAL '1 hour'
    )
"""


def sync_to_lakebase(records: list[dict]) -> None:
    """Upsert health records and insert new disruption events."""
    conn = psycopg2.connect(**LAKEBASE_CONFIG)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            upsert_count = 0
            disruption_count = 0

            for record in records:
                # Upsert live health state
                cur.execute(UPSERT_HEALTH_SQL, record)
                upsert_count += 1

                # Insert disruption event if asset is in an alarm state
                if record.get("risk_level") in DISRUPTION_RISK_LEVELS:
                    downtime_cost = (
                        (record.get("estimated_rul_hours") or 0.0)
                        * (record.get("cost_of_unplanned_failure") or 0.0)
                    )
                    cur.execute(INSERT_DISRUPTION_SQL, {
                        **record,
                        "estimated_downtime_cost": round(downtime_cost, 2),
                    })
                    disruption_count += cur.rowcount

            conn.commit()
            print(f"  Upserted {upsert_count} health records to asset_health_live")
            print(f"  Inserted {disruption_count} new disruption events to asset_disruption")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting Lakebase sync...")
    print()

    spark = DatabricksSession.builder.serverless(True).getOrCreate()
    print(f"  Spark session ready. Catalog: {CATALOG}.{SCHEMA}")

    check_tables_exist(spark)

    print("  Reading latest health scores from Unity Catalog Gold layer...")
    records = fetch_latest_health_scores(spark)
    print(f"  Fetched {len(records)} asset records.")
    print()

    if not records:
        print("  No records to sync. Exiting.")
        return

    # Summary before sync
    critical_assets = [r["asset_id"] for r in records if r.get("risk_level") == "CRITICAL"]
    high_assets = [r["asset_id"] for r in records if r.get("risk_level") == "HIGH"]
    print(f"  Risk summary: CRITICAL={len(critical_assets)}, HIGH={len(high_assets)}")
    if critical_assets:
        print(f"  CRITICAL assets: {', '.join(critical_assets)}")
    print()

    print("  Syncing to Lakebase (Serverless Postgres)...")
    sync_to_lakebase(records)
    print()
    print(f"[{datetime.now(timezone.utc).isoformat()}] Lakebase sync complete.")


if __name__ == "__main__":
    main()
