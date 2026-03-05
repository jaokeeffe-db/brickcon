# Maintenance Control Tower

> **Agentic Predictive Maintenance & Asset Health Intelligence**
> Industry: Manufacturing | Platform: Databricks (Azure)

---

## Business Problem

Unplanned downtime on high-volume manufacturing lines costs **$50k+ per hour**. Traditional
maintenance approaches fail in two ways:

- **Reactive** — fixing equipment after it breaks (maximum cost, maximum disruption)
- **Preventative** — replacing healthy parts on a fixed schedule (wasteful, ignores real condition)

When a machine does fail, technicians lack immediate context — maintenance history, live sensor
anomalies, and repair procedures — needed for a first-time fix. Repeated visits and extended
outages are the result.

---

## How Databricks Helps

Databricks unifies the entire asset lifecycle into a single source of truth. By applying AI as a
reasoning engine, the platform can read unstructured data (technical manuals, repair logs, sensor
streams) and simulate the downstream impact of a mechanical anomaly — automatically suggesting the
optimal maintenance window with a pre-diagnosed repair plan.

**Outcome**: Reduce unplanned outages and response times by over 80%.

---

## Demo Narrative

> *"Motor 4 on Line 1 is vibrating at 8.9 mm/s — should I stop the line?"*

The platform responds with a complete reasoning chain:

1. **Health check** → Motor_4 health score: 22/100, CRITICAL, ~6 hours RUL
2. **Pattern match** → 3 historical bearing failures with the same exponential vibration signature
3. **Manual retrieval** → `motor_bearing_replacement.md`, Section 5: bearing swap procedure
4. **Cost analysis** → Planned repair: **$3,200** vs. unplanned failure: **$420,800**
5. **Decision** → Schedule immediate bearing replacement tonight (off-shift)

---

## Architecture

```
MOCK DATA (generate_mock_data.py)
  └─ 22 assets · 90 days telemetry · Motor_4 degradation signature
        │
        ▼
UNITY CATALOG VOLUMES
  utility_ops.raw_ingestion.raw_telemetry/      ← sensor CSVs
  utility_ops.raw_ingestion.technical_manuals/  ← Markdown manuals
        │
        ▼
LAKEFLOW PIPELINE (Bronze → Silver → Gold)
  bronze_sensor_readings       bronze_maintenance_logs
        │                              │
  silver_sensor_readings        silver_maintenance_logs
        │                              │
        └──────────┬───────────────────┘
                   ▼
           gold_health_scores    gold_vibration_trends    gold_cost_impact
           (tagged: critical_path)
                   │
                   ▼ (lakebase_sync.py)
LAKEBASE (Serverless Postgres)
  asset_health_live             ← sub-second health state
  asset_disruption              ← active CRITICAL/HIGH alerts
  maintenance_recommendations   ← AI-generated repair plans
                   │
                   ▼
MOSAIC AI AGENT (maintenance-agent-endpoint)
  Model: Claude Sonnet 4.6 via External Model Serving
  Tools: 6 UC Functions (health · manuals · patterns · cost · history · write)
                   │
                   ▼
DATABRICKS APP (Maintenance Control Tower — Streamlit)
  Floor map · Active alerts · AI chat · Cost comparison
```

---

## File Structure

```
vibecode/brickcon/
├── README.md
├── progress.md                       ← build history and current status
├── GEMINI-research.md
├── databricks.yml                    ← Databricks Asset Bundle config
├── .env                              ← workspace credentials (gitignored)
├── requirements.txt
│
├── data/
│   ├── generate_mock_data.py         ← generates CSVs + Motor_4 failure signature
│   └── upload_to_uc.py               ← uploads files to UC Volumes
│
├── infrastructure/
│   ├── uc_setup.sql                  ← CREATE CATALOG/SCHEMA/VOLUME + tags
│   └── lakebase_setup.sql            ← CREATE TABLE for 3 Postgres tables
│
├── pipelines/
│   └── lakeflow_pipeline.py          ← Bronze → Silver → Gold declarative pipeline
│
├── services/
│   └── lakebase_sync.py              ← Gold → Lakebase upsert job
│
├── agent/
│   ├── agent_tools.py                ← 6 UC Function definitions (deploy with --deploy)
│   ├── agent_model.py                ← MLflow ChatAgent class (code-based logging)
│   └── agent_definition.py           ← registration CLI (python agent_definition.py --register)
│
├── genie/
│   └── genie_instructions.md         ← Genie Space config + certified calculations
│
├── app/
│   ├── control_tower_app.py          ← Streamlit Control Tower app
│   └── app.yaml                      ← Databricks App deployment manifest
│
└── manuals/
    ├── motor_bearing_replacement.md
    ├── vibration_diagnostics.md
    ├── emergency_shutdown_protocol.md
    ├── preventive_maintenance_checklist.md
    └── motor4_operating_specifications.md
```

---

## Quick Start

### Prerequisites

- Databricks workspace (Azure) with Serverless enabled
- Lakebase instance created (Compute > Lakebase in UI)
- Claude Sonnet 4.6 external model endpoint deployed
- `.env` configured (copy `.env.example` and fill in values)

### Setup Order

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate and upload mock data
python data/generate_mock_data.py
set -a; source .env; set +a
python data/upload_to_uc.py

# 3. Create Unity Catalog structure
# Run infrastructure/uc_setup.sql in Databricks SQL editor

# 4. Create Lakebase tables
# Run infrastructure/lakebase_setup.sql via psql against your Lakebase endpoint

# 5. Deploy and run the Lakeflow pipeline
# Upload pipelines/lakeflow_pipeline.py as a Lakeflow pipeline in the UI

# 6. Sync Gold layer to Lakebase
python services/lakebase_sync.py

# 7. Deploy UC Function tools
python agent/agent_tools.py --deploy

# 8. Register the agent to MLflow
python agent/agent_definition.py --register
# Then deploy the registered model to the 'maintenance-agent-endpoint' in the UI

# 9. Run the Control Tower app locally
streamlit run app/control_tower_app.py
```

---

## Customer Requirements

| Requirement | Implementation |
|---|---|
| **Self-Service Discovery** | Genie Space over Gold tables — plain-English queries, no SQL required |
| **Lineage & Trust** | Unity Catalog tags (`critical_path`, `sensor_data`, `pii=false`) + RAG provenance stored in `maintenance_recommendations.vector_search_sources` |
| **Cost-Aware Mitigation** | `calculate_cost_impact` UC Function computes planned vs. unplanned costs; agent cites actual values |

---

## Unity Catalog Namespace

| Catalog | Schema | Purpose |
|---|---|---|
| `utility_ops` | `raw_ingestion` | Landing zone: Volumes only |
| `utility_ops` | `asset_intelligence` | Medallion tables + UC Functions |
| `utility_ops` | `vector_store` | Vector Search source tables |
