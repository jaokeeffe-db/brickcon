"""
Agent Tool Definitions for the Maintenance Reasoning Agent.

These UC Functions are registered in Unity Catalog under
`utility_ops.asset_intelligence` and are used as tools by the
Mosaic AI Agent Framework.

Deploy to workspace via:
  1. Open a Databricks notebook
  2. Run each CREATE FUNCTION statement in order
  OR
  2. Use the Databricks SDK / databricks.yml bundle deployment

The functions use EXTERNAL access to query Lakebase (Postgres) directly.
Each tool is designed to be self-documenting so the LLM can select the
correct tool from the description alone.
"""

# This file documents the UC Function SQL definitions.
# The functions themselves are deployed as SQL in the workspace.
# Run these statements in a Databricks SQL editor or notebook.

TOOL_SQL_DEFINITIONS = {}

# ---------------------------------------------------------------------------
# Tool 1: get_asset_health
# ---------------------------------------------------------------------------

TOOL_SQL_DEFINITIONS["get_asset_health"] = """
CREATE OR REPLACE FUNCTION utility_ops.asset_intelligence.get_asset_health(
    asset_id STRING COMMENT 'The asset identifier, e.g. Motor_4, Pump_2, Compressor_1'
)
RETURNS STRING
COMMENT 'Returns the live health status for a specific asset from the Lakebase operational tier as a JSON string.
Fields: asset_id, health_score (0-100), risk_level (CRITICAL/HIGH/MEDIUM/LOW), current_vibration,
current_temp, rated_max_vibration, estimated_rul_hours (NULL if no degradation trend),
production_line_id, criticality_tier, last_updated.
Use this tool first when a user asks about a specific machine.
A health_score < 30 means CRITICAL — recommend immediate action.'
LANGUAGE PYTHON
AS $$
import os
import json
import psycopg2

def get_asset_health(asset_id):
    conn = psycopg2.connect(
        host=os.environ['LAKEBASE_HOST'],
        port=int(os.environ.get('LAKEBASE_PORT', '5432')),
        dbname=os.environ.get('LAKEBASE_DATABASE', 'databricks_postgres'),
        user=os.environ['LAKEBASE_USER'],
        password=os.environ['LAKEBASE_PASSWORD'],
        sslmode='require'
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                \"\"\"
                SELECT asset_id, health_score, risk_level, current_vibration,
                       current_temp, rated_max_vibration, estimated_rul_hours,
                       production_line_id, criticality_tier,
                       last_updated::text
                FROM asset_health_live
                WHERE asset_id = %s
                \"\"\",
                (asset_id,)
            )
            row = cur.fetchone()
            if row is None:
                return json.dumps({"error": f"Asset '{asset_id}' not found in health database"})
            cols = ['asset_id', 'health_score', 'risk_level', 'current_vibration',
                    'current_temp', 'rated_max_vibration', 'estimated_rul_hours',
                    'production_line_id', 'criticality_tier', 'last_updated']
            return json.dumps(dict(zip(cols, row)))
    finally:
        conn.close()

return get_asset_health(asset_id)
$$;
"""

# ---------------------------------------------------------------------------
# Tool 2: search_manuals
# ---------------------------------------------------------------------------

TOOL_SQL_DEFINITIONS["search_manuals"] = """
CREATE OR REPLACE FUNCTION utility_ops.asset_intelligence.search_manuals(
    symptom_description STRING COMMENT 'A natural language description of the fault or symptom, e.g. "high vibration on motor bearing" or "overheating pump seal"'
)
RETURNS TABLE (
    chunk_id    STRING,
    manual_name STRING,
    section     STRING,
    content     STRING,
    score       DOUBLE
)
COMMENT 'Searches technical manuals for repair procedures relevant to the symptom description.
Use this tool to retrieve relevant repair procedures, diagnostic steps, or specifications.
Always cite the manual_name and section in your recommendation for traceability.'
LANGUAGE SQL
RETURN
    SELECT
        chunk_id,
        manual_name,
        section,
        content,
        score
    FROM utility_ops.vector_store.technical_manuals_source
    WHERE content ILIKE CONCAT('%', search_manuals.symptom_description, '%')
       OR section ILIKE CONCAT('%', search_manuals.symptom_description, '%')
    ORDER BY score DESC
    LIMIT 5;
"""

# ---------------------------------------------------------------------------
# Tool 3: search_failure_patterns
# ---------------------------------------------------------------------------

TOOL_SQL_DEFINITIONS["search_failure_patterns"] = """
CREATE OR REPLACE FUNCTION utility_ops.asset_intelligence.search_failure_patterns(
    fault_description STRING COMMENT 'Description of the current fault or symptom, e.g. "progressive bearing vibration increase over 48 hours" or "motor overheating"'
)
RETURNS TABLE (
    pattern_id          STRING,
    asset_id            STRING,
    fault_type          STRING,
    symptom_description STRING,
    resolution          STRING,
    score               DOUBLE
)
COMMENT 'Searches historical maintenance records for failures similar to the current fault description.
Use this tool to find how similar failures were resolved in the past, what parts were replaced,
and how long the repair took. Improves recommendation accuracy by grounding in historical data.
Returns up to 5 similar historical failure patterns ranked by recency and cost.'
LANGUAGE SQL
RETURN
    SELECT
        work_order_id                                                               AS pattern_id,
        asset_id,
        fault_type,
        CONCAT(fault_type, ' on ', asset_id,
               ' — vibration-related: ', CASE WHEN fault_type ILIKE '%bearing%'
                   OR fault_type ILIKE '%vibrat%' THEN 'YES' ELSE 'NO' END,
               ', downtime: ', ROUND(downtime_hours, 1), 'h')                      AS symptom_description,
        CONCAT('Part replaced: ', COALESCE(part_replaced, 'unspecified'),
               '. Cost: $', ROUND(cost_to_fix, 0),
               '. First-time fix: ', CAST(first_time_fix AS STRING),
               '. Downtime: ', ROUND(downtime_hours, 1), 'h')                      AS resolution,
        0.9                                                                         AS score
    FROM utility_ops.asset_intelligence.silver_maintenance_logs
    WHERE fault_type ILIKE CONCAT('%', search_failure_patterns.fault_description, '%')
       OR fault_type ILIKE '%bearing%'
       OR fault_type ILIKE '%vibrat%'
    ORDER BY cost_to_fix DESC
    LIMIT 5;
"""

# ---------------------------------------------------------------------------
# Tool 4: calculate_cost_impact
# ---------------------------------------------------------------------------

TOOL_SQL_DEFINITIONS["calculate_cost_impact"] = """
CREATE OR REPLACE FUNCTION utility_ops.asset_intelligence.calculate_cost_impact(
    asset_id STRING COMMENT 'The asset identifier to calculate cost impact for, e.g. Motor_4',
    estimated_repair_hours DOUBLE COMMENT 'Estimated hours needed for the planned repair. Use 4.0 if unknown for a motor bearing replacement.'
)
RETURNS TABLE (
    asset_id                    STRING,
    production_line_id          STRING,
    cost_to_fix_planned         DOUBLE,
    cost_of_unplanned_failure   DOUBLE,
    savings_by_acting_now       DOUBLE,
    estimated_rul_hours         DOUBLE,
    net_recommendation          STRING
)
COMMENT 'Calculates and compares the financial cost of a planned repair now vs. waiting for an unplanned failure.
Use this tool to provide the cost-aware recommendation required by the business.
cost_to_fix_planned = estimated_repair_hours * labour_rate + avg_parts_cost
cost_of_unplanned_failure = remaining_production_hours * line_hourly_output + emergency_repair_premium
Always include this cost comparison in any repair recommendation.'
LANGUAGE SQL
RETURN
    SELECT
        c.asset_id,
        c.production_line_id,
        ROUND(estimated_repair_hours * 85.0 + c.avg_cost_to_fix * 0.6, 2) AS cost_to_fix_planned,
        ROUND(c.cost_of_unplanned_failure, 2) AS cost_of_unplanned_failure,
        ROUND(c.cost_of_unplanned_failure - (estimated_repair_hours * 85.0 + c.avg_cost_to_fix * 0.6), 2) AS savings_by_acting_now,
        c.estimated_rul_hours,
        c.net_recommendation
    FROM utility_ops.asset_intelligence.gold_cost_impact c
    WHERE c.asset_id = calculate_cost_impact.asset_id;
"""

# ---------------------------------------------------------------------------
# Tool 5: get_maintenance_history
# ---------------------------------------------------------------------------

TOOL_SQL_DEFINITIONS["get_maintenance_history"] = """
CREATE OR REPLACE FUNCTION utility_ops.asset_intelligence.get_maintenance_history(
    asset_id STRING COMMENT 'The asset identifier to retrieve maintenance history for, e.g. Motor_4',
    n_recent INT COMMENT 'Number of most recent work orders to return. Use 5 for a summary, 20 for full history.'
)
RETURNS TABLE (
    work_order_id           STRING,
    timestamp               TIMESTAMP,
    fault_type              STRING,
    part_replaced           STRING,
    cost_to_fix             DOUBLE,
    first_time_fix          BOOLEAN,
    downtime_hours          DOUBLE,
    days_since_prev_failure DOUBLE
)
COMMENT 'Returns the N most recent maintenance work orders for a specific asset from Unity Catalog.
Use this tool to understand the failure history of an asset: what parts have been replaced,
how often it has failed, and the cost and downtime patterns.
This also helps identify if the current failure matches a known recurring fault type.'
LANGUAGE SQL
RETURN
    WITH windowed AS (
        SELECT
            work_order_id,
            timestamp,
            fault_type,
            part_replaced,
            cost_to_fix,
            first_time_fix,
            downtime_hours,
            DATEDIFF(
                timestamp,
                LAG(timestamp) OVER (PARTITION BY asset_id ORDER BY timestamp)
            ) AS days_since_prev_failure,
            ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY timestamp DESC) AS rn
        FROM utility_ops.asset_intelligence.silver_maintenance_logs
        WHERE asset_id = get_maintenance_history.asset_id
    )
    SELECT
        work_order_id, timestamp, fault_type, part_replaced,
        cost_to_fix, first_time_fix, downtime_hours, days_since_prev_failure
    FROM windowed
    WHERE rn <= n_recent;
"""

# ---------------------------------------------------------------------------
# Tool 6: upsert_recommendation
# ---------------------------------------------------------------------------

TOOL_SQL_DEFINITIONS["upsert_recommendation"] = """
CREATE OR REPLACE FUNCTION utility_ops.asset_intelligence.upsert_recommendation(
    asset_id                STRING  COMMENT 'The asset this recommendation applies to, e.g. Motor_4',
    recommendation_text     STRING  COMMENT 'The full repair plan and recommendation to store',
    cost_to_fix             DOUBLE  COMMENT 'Estimated cost to perform the recommended repair',
    cost_of_downtime        DOUBLE  COMMENT 'Estimated cost of unplanned downtime if repair is not performed',
    urgency_hours           DOUBLE  COMMENT 'Estimated hours until failure if no action is taken (the RUL)',
    net_recommendation      STRING  COMMENT 'One of: SCHEDULE_IMMEDIATE, SCHEDULE_PLANNED, MONITOR',
    vector_search_sources   ARRAY<STRING>  COMMENT 'List of chunk_ids from Vector Search that informed this recommendation',
    manual_references       ARRAY<STRING>  COMMENT 'List of manual document names cited in the recommendation'
)
RETURNS STRING
COMMENT 'Persists the AI-generated maintenance recommendation to Lakebase for the Control Tower to display.
Always call this tool LAST, after you have gathered all information and generated the recommendation.
The vector_search_sources and manual_references parameters are critical for the Lineage & Trust
customer requirement — they enable users to verify which data sources informed the AI recommendation.
Returns a confirmation string with the recommendation ID.'
LANGUAGE PYTHON
AS $$
import os
import psycopg2

def upsert_recommendation(asset_id, recommendation_text, cost_to_fix,
                           cost_of_downtime, urgency_hours, net_recommendation,
                           vector_search_sources, manual_references):
    conn = psycopg2.connect(
        host=os.environ['LAKEBASE_HOST'],
        port=int(os.environ.get('LAKEBASE_PORT', '5432')),
        dbname=os.environ.get('LAKEBASE_DATABASE', 'databricks_postgres'),
        user=os.environ['LAKEBASE_USER'],
        password=os.environ['LAKEBASE_PASSWORD'],
        sslmode='require'
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                \"\"\"
                INSERT INTO maintenance_recommendations (
                    asset_id, recommendation_text, cost_to_fix, cost_of_downtime,
                    urgency_hours, net_recommendation, vector_search_sources,
                    manual_references, health_score_at_time
                )
                SELECT %s, %s, %s, %s, %s, %s, %s, %s, health_score
                FROM asset_health_live
                WHERE asset_id = %s
                RETURNING rec_id
                \"\"\",
                (asset_id, recommendation_text, cost_to_fix, cost_of_downtime,
                 urgency_hours, net_recommendation,
                 list(vector_search_sources) if vector_search_sources else [],
                 list(manual_references) if manual_references else [],
                 asset_id)
            )
            rec_id = cur.fetchone()[0]
            conn.commit()
            return f'Recommendation REC-{rec_id:05d} saved for {asset_id}'
    finally:
        conn.close()

return upsert_recommendation(
    asset_id, recommendation_text, cost_to_fix,
    cost_of_downtime, urgency_hours, net_recommendation,
    vector_search_sources, manual_references
)
$$;
"""


def print_deployment_instructions():
    """Print instructions for deploying these tools to a Databricks workspace."""
    print("=" * 70)
    print("AGENT TOOL DEPLOYMENT INSTRUCTIONS")
    print("=" * 70)
    print()
    print("1. Open a Databricks SQL editor or notebook connected to your workspace.")
    print("2. Ensure the following environment variables are configured in the")
    print("   Model Serving endpoint secret scope:")
    print("   - LAKEBASE_HOST, LAKEBASE_PORT, LAKEBASE_DATABASE")
    print("   - LAKEBASE_USER, LAKEBASE_PASSWORD")
    print()
    print("3. Run each SQL definition in order:")
    for i, name in enumerate(TOOL_SQL_DEFINITIONS, 1):
        print(f"   {i}. {name}")
    print()
    print("4. Verify each function exists:")
    print("   SELECT * FROM utility_ops.asset_intelligence.information_schema.routines")
    print("   WHERE routine_name LIKE '%maintenance%' OR routine_name IN (")
    for name in TOOL_SQL_DEFINITIONS:
        print(f"       '{name}',")
    print("   );")
    print()
    print("5. Grant EXECUTE permission to the agent service principal:")
    print("   GRANT EXECUTE ON FUNCTION utility_ops.asset_intelligence.<function_name>")
    print("   TO `your-agent-service-principal@databricks.com`;")
    print()


def _run_sql(client, warehouse_id: str, statement: str) -> bool:
    """Execute a SQL statement and return True on success."""
    import time
    from databricks.sdk.service.sql import StatementState

    stmt = client.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=statement.strip(),
        wait_timeout="50s",
    )
    while stmt.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        stmt = client.statement_execution.get_statement(stmt.statement_id)
    if stmt.status.state == StatementState.SUCCEEDED:
        return True
    print(f" FAILED: {stmt.status.error}")
    return False


def _seed_manuals_table(client, warehouse_id: str) -> None:
    """Create and populate the technical_manuals_source Delta table from local markdown files."""
    from pathlib import Path

    manuals_dir = Path(__file__).parent.parent / "manuals"
    if not manuals_dir.exists():
        print("  WARN: manuals/ directory not found — skipping manuals table seed")
        return

    print("  Creating utility_ops.vector_store.technical_manuals_source ...", end="", flush=True)
    create_sql = """
    CREATE TABLE IF NOT EXISTS utility_ops.vector_store.technical_manuals_source (
        chunk_id    STRING,
        manual_name STRING,
        section     STRING,
        content     STRING,
        score       DOUBLE
    ) USING DELTA
    """
    if not _run_sql(client, warehouse_id, create_sql):
        return
    print(" ✓")

    for md_file in sorted(manuals_dir.glob("*.md")):
        text = md_file.read_text()
        # Split on ## headings to create chunks
        import re
        sections = re.split(r'\n(?=## )', text)
        manual_name = md_file.stem
        for i, section_text in enumerate(sections):
            section_title = (re.match(r'^##\s+(.+)', section_text) or
                             re.match(r'^#\s+(.+)', section_text))
            section_name = section_title.group(1).strip() if section_title else f"section_{i}"
            chunk_id = f"{manual_name}_{i}"
            # Escape single quotes
            content = section_text.replace("'", "''")
            section_name_esc = section_name.replace("'", "''")
            insert_sql = f"""
            INSERT INTO utility_ops.vector_store.technical_manuals_source
            (chunk_id, manual_name, section, content, score)
            VALUES ('{chunk_id}', '{manual_name}', '{section_name_esc}', '{content}', 1.0)
            """
            print(f"    Inserting {chunk_id} ...", end="", flush=True)
            ok = _run_sql(client, warehouse_id, insert_sql)
            print(" ✓" if ok else "")


def deploy_tools() -> None:
    """Deploy all UC Functions to the workspace using the Databricks SDK."""
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient()

    # Pick first running warehouse
    warehouses = [w for w in client.warehouses.list() if w.state and w.state.value == "RUNNING"]
    if not warehouses:
        warehouses = list(client.warehouses.list())
    if not warehouses:
        raise SystemExit("No SQL warehouses found. Create one in the Databricks UI first.")
    warehouse_id = warehouses[0].id
    print(f"Using warehouse: {warehouses[0].name} ({warehouse_id})")
    print()

    # Deploy all functions except search_manuals first
    for name, sql in TOOL_SQL_DEFINITIONS.items():
        if name == "search_manuals":
            continue
        print(f"  Deploying {name} ...", end="", flush=True)
        ok = _run_sql(client, warehouse_id, sql)
        if ok:
            print(" ✓")

    # Seed manuals table, then deploy search_manuals
    print()
    _seed_manuals_table(client, warehouse_id)
    print(f"  Deploying search_manuals ...", end="", flush=True)
    ok = _run_sql(client, warehouse_id, TOOL_SQL_DEFINITIONS["search_manuals"])
    if ok:
        print(" ✓")

    print()
    print("All UC Functions deployed.")
    print("Now run: python agent/agent_definition.py --register")


if __name__ == "__main__":
    import sys
    if "--deploy" in sys.argv:
        deploy_tools()
    else:
        print_deployment_instructions()
        print()
        print("SQL Definitions (copy to workspace):")
        print()
        for name, sql in TOOL_SQL_DEFINITIONS.items():
            print(f"-- {name}")
            print(sql.strip())
            print()
