# Build Progress — Maintenance Control Tower

## Project Summary

A Databricks sales demo for manufacturing predictive maintenance. The demo tells the story of
**Motor_4 on Line_1** — a motor exhibiting exponential vibration growth that will reach critical
failure in ~6 hours. The platform detects it, reasons about it, and recommends a $3,200 repair
that avoids a $420,800 unplanned shutdown.

**Cloud**: Azure Databricks
**App framework**: Streamlit
**AI model**: Claude Sonnet 4.6 via Mosaic AI Model Serving
**Purpose**: Sales demo / POC — breadth over depth

---

## Phase History

### Phase 1 — Data Seed ✅

- `data/generate_mock_data.py` — generates 5 CSV/JSON files:
  - 22 assets, 90 days of 10-minute sensor telemetry (~288k rows)
  - Motor_4: healthy baseline for days 1–88, then exponential vibration growth over final 48h
  - 3 thermal spike events on Pump_2, Compressor_1, Motor_6
  - ~240 maintenance work orders over 2 years
- `infrastructure/uc_setup.sql` — `utility_ops` catalog, 3 schemas, 2 volumes, UC tags
- `data/upload_to_uc.py` — Databricks Connect uploads CSVs to UC Volumes
- 5 Markdown technical manuals in `manuals/`

### Phase 2 — Pulse (Pipeline + Lakebase) ✅

- `pipelines/lakeflow_pipeline.py` — Lakeflow declarative pipeline:
  - Bronze: Auto-Loader streaming ingestion from Volumes
  - Silver: cleaning, anomaly flags, asset metadata joins
  - Gold: health scores, vibration trends, cost impact (all tagged `critical_path`)
  - Key fix: `silver_maintenance_logs` kept as STREAMING_TABLE (LAG window functions
    not supported on unbounded streams — removed `days_since_last_failure`)
- `infrastructure/lakebase_setup.sql` — 3 Postgres tables in Lakebase:
  - `asset_health_live` — sub-second health state per asset
  - `asset_disruption` — active CRITICAL/HIGH alerts
  - `maintenance_recommendations` — AI-generated repair plans with RAG provenance
  - Note: must be run via `psql` against Lakebase endpoint, NOT in Databricks SQL editor
- `services/lakebase_sync.py` — reads `gold_health_scores`, upserts to Lakebase
  - Motor_4 correctly shows `risk_level=CRITICAL`, `health_score≈22` ✅
  - 22 assets synced successfully ✅

### Phase 3 — Brain (Agent) ✅ (in progress)

**UC Function Tools** (`agent/agent_tools.py`) — 6 functions deployed to `utility_ops.asset_intelligence`:

| Function | Status | Notes |
|---|---|---|
| `get_asset_health` | ✅ | Returns JSON string (scalar) — TVF HANDLER syntax avoided |
| `search_failure_patterns` | ✅ | SQL ILIKE over `silver_maintenance_logs` |
| `calculate_cost_impact` | ✅ | Queries `gold_cost_impact` |
| `get_maintenance_history` | ✅ | ROW_NUMBER() workaround for `LIMIT param` (unfoldable) |
| `upsert_recommendation` | ✅ | Writes to Lakebase `maintenance_recommendations` |
| `search_manuals` | ✅ | SQL ILIKE over `vector_store.technical_manuals_source` |

**Agent** (`agent/agent_model.py`, `agent/agent_definition.py`):
- MLflow ChatAgent backed by Claude Sonnet 4.6 (`databricks-claude-sonnet-4-6` endpoint)
- LangGraph ReAct agent with 6 UC Function tools
- Registered to `utility_ops.asset_intelligence.maintenance_agent` ✅
- Model Serving endpoint: `maintenance-agent-endpoint` — deployed, working through versions:
  - v1–v2: cloudpickle serialization failures → fixed with MLflow code-based logging
  - v3: `UCFunctionToolkit` auth failure → fixed by adding `DatabricksFunctionClient`
  - v4+: in progress

**Key fixes applied during agent deployment**:
- Switched from object-based to code-based MLflow logging (`python_model=Path(file)`)
  — LangGraph agent contains thread locks that cloudpickle cannot serialize
- `ChatAgentMessage` requires `id=str(uuid.uuid4())` field
- `MLflow ChatAgent.predict` signature: `(self, messages, context=None, custom_inputs=None)`
  — messages is first, not context
- `UCFunctionToolkit` requires explicit `DatabricksFunctionClient` client on serving endpoint
- `LIMIT param` in UC SQL UDFs is unfoldable — use `ROW_NUMBER() OVER (...) WHERE rn <= param`
- Python TVFs in UC require class-based HANDLER — workaround: return JSON string (scalar UDF)
- `wait_timeout` in Databricks SDK statement execution: must be `0s` or `5s–50s` (not `60s`)
- `DEFAULT` column values in Delta tables require feature flag — omit DEFAULT instead
- Lakebase `.env` uses `LAKEBASE_DATABASE=databricks_postgres` (not `maintenance_ops`)

### Phase 4 — Control Tower (App) 🔄 In Progress

- `app/control_tower_app.py` — Streamlit app written:
  - Floor map: 22 assets colour-coded by risk level (live from Lakebase)
  - Active alerts panel with "Ask AI →" quick-action buttons
  - AI chat interface routing to `maintenance-agent-endpoint`
  - Cost comparison table (planned vs. unplanned failure cost)
  - Mock data fallback if Lakebase is unreachable
- `app/app.yaml` — Databricks App deployment manifest

**Remaining steps**:
- [ ] Verify `maintenance-agent-endpoint` is fully operational (current version resolving UCFunctionToolkit auth)
- [ ] Run app locally: `streamlit run app/control_tower_app.py`
- [ ] Deploy to Databricks Apps

### Phase 3 (Genie) — Pending

- `genie/genie_instructions.md` — written with certified calculations and sample queries
- Genie Space configuration in Databricks UI: pending

---

## Environment

```
Workspace:      https://adb-472044062106526.6.azuredatabricks.net
Catalog:        utility_ops
Agent endpoint: maintenance-agent-endpoint
Claude endpoint: databricks-claude-sonnet-4-6
Lakebase host:  instance-ec782d24-538b-49a5-bc2a-065f9c90bfc0.database.azuredatabricks.net
Lakebase DB:    databricks_postgres
```

---

## Lessons Learned

| Problem | Root Cause | Fix |
|---|---|---|
| `lakebase_setup.sql` fails with `UNSUPPORTED_DATATYPE TEXT` | Run in Databricks SQL editor (Spark SQL) instead of psql | Run via `psql` against Lakebase endpoint directly |
| `source .env` doesn't export vars to child processes | `.env` uses `KEY=VALUE` not `export KEY=VALUE` | Use `set -a; source .env; set +a` |
| cloudpickle fails on LangGraph agent | Thread locks in LangGraph state can't be serialized | Use MLflow code-based logging (`python_model=Path(file)`) |
| `ChatAgentMessage` pydantic validation error | Missing required `id` field | Add `id=str(uuid.uuid4())` to every `ChatAgentMessage` |
| `AgentExecutor` import error | Removed in LangChain 0.3+ | Replace with `langgraph.prebuilt.create_react_agent` |
| UC Python TVF requires HANDLER class | Python TVFs need class-based handler syntax | Return JSON string as scalar UDF instead |
| `LIMIT param` is unfoldable in UC SQL UDFs | SQL planner can't fold parameterized LIMIT | Use `ROW_NUMBER() OVER (...) WHERE rn <= param` |
| MLflow `wait_timeout` invalid | SDK max is 50s | Change `"60s"` → `"50s"` |
| Delta `DEFAULT` column values fail | `delta.feature.allowColumnDefaults` not enabled | Omit DEFAULT from CREATE TABLE |
| `UCFunctionToolkit` no client error | Requires explicit `DatabricksFunctionClient` | Pass `client=DatabricksFunctionClient()` |
| `azure` module missing for MLflow artifact upload | Azure workspace needs `mlflow[databricks]` | `pip install "mlflow[databricks]"` |
