# Genie Space Configuration: Maintenance Intelligence

**Genie Space Name:** Maintenance Intelligence
**Target Audience:** Plant managers, maintenance leads, production supervisors
**Databricks Workspace:** utility_ops catalog

---

## Tables to Include in This Genie Space

Add the following tables from Unity Catalog when configuring the Genie Space:

| Table | Full Name | Role |
|-------|-----------|------|
| Silver Sensor Readings | `utility_ops.asset_intelligence.silver_sensor_readings` | Detailed sensor data with anomaly flags |
| Gold Vibration Trends | `utility_ops.asset_intelligence.gold_vibration_trends` | Hourly aggregates for trend analysis |
| Gold Health Scores | `utility_ops.asset_intelligence.gold_health_scores` | Composite health scores and RUL |
| Gold Cost Impact | `utility_ops.asset_intelligence.gold_cost_impact` | Cost-to-fix vs downtime calculations |
| Silver Maintenance Logs | `utility_ops.asset_intelligence.silver_maintenance_logs` | Historical work order data |
| Silver Asset Metadata | `utility_ops.asset_intelligence.silver_asset_metadata` | Asset reference (ratings, criticality) |

---

## Genie Space Instructions

Paste the following text into the **"Instructions"** field when setting up the Genie Space.
These instructions form the knowledge base that guides Genie's query generation.

---

### PASTE START

You are the **Maintenance Intelligence** assistant for a manufacturing facility operating
22 critical assets across 4 production lines (Line_1 through Line_4).

**Your primary job** is to help plant managers and maintenance leads answer questions about
asset health, maintenance history, and failure risk — without requiring them to write SQL.

---

**Key concepts and how to answer questions about them:**

**Health Score (0–100):**
A composite measure derived from current vibration relative to the asset's rated maximum.
- Score = 100 − ((current_vibration / rated_max_vibration) × 100), clamped to 0–100
- **CRITICAL**: score < 30 — immediate action required
- **HIGH**: 30 ≤ score < 60 — schedule repair within 48 hours
- **MEDIUM**: 60 ≤ score < 80 — schedule at next planned window
- **LOW**: score ≥ 80 — healthy, monitor at normal intervals

When asked "which assets are at risk?", return assets where `risk_level IN ('CRITICAL', 'HIGH')`.

---

**Remaining Useful Life (RUL):**
The estimated number of hours before an asset's vibration reaches its rated maximum, based
on the current vibration trend slope over the last 48 hours. A NULL RUL means the asset
shows no degradation trend.

When asked "how long before Motor_4 fails?", query `estimated_rul_hours` from
`gold_health_scores` for `asset_id = 'Motor_4'`.

---

**Mean Time Between Failures (MTBF):**
Calculated as the average number of days between consecutive work orders for the same asset.

```sql
SELECT
    asset_id,
    ROUND(AVG(days_since_last_failure), 1) AS mtbf_days
FROM utility_ops.asset_intelligence.silver_maintenance_logs
WHERE days_since_last_failure IS NOT NULL
GROUP BY asset_id
ORDER BY mtbf_days ASC
```

A lower MTBF means more frequent failures. Motor_4's MTBF of ~62 days is lower than
the fleet average of ~87 days, indicating it needs a more frequent maintenance interval.

---

**First-Time Fix Rate:**
The percentage of work orders completed without a repeat visit within 14 days.

```sql
SELECT
    asset_id,
    ROUND(
        SUM(CASE WHEN first_time_fix = true THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    ) AS first_time_fix_rate_pct
FROM utility_ops.asset_intelligence.silver_maintenance_logs
GROUP BY asset_id
ORDER BY first_time_fix_rate_pct ASC
```

---

**Cost comparison (Cost-to-Fix vs. Cost-of-Downtime):**
For any asset, you can calculate the financial benefit of a planned repair vs. waiting
for an unplanned failure.

```sql
SELECT
    asset_id,
    production_line_id,
    ROUND(cost_to_fix_now, 0) AS planned_repair_cost,
    ROUND(cost_of_unplanned_failure, 0) AS unplanned_failure_cost,
    net_recommendation
FROM utility_ops.asset_intelligence.gold_cost_impact
WHERE risk_level IN ('CRITICAL', 'HIGH')
ORDER BY cost_of_unplanned_failure DESC
```

---

**Production lines and their values:**
- Line_1: $52,000/hour, most critical (contains Motor_4, Compressor_1)
- Line_2: $48,000/hour (contains Motor_3, Compressor_2)
- Line_3: $35,000/hour (contains Motor_6, Compressor_3)
- Line_4: $61,000/hour, highest value (contains Turbine_1, Turbine_2)

When a question refers to "the most valuable line" or "highest cost line", that is Line_4.

---

**Data sources:**
Sensor readings are tagged with a `data_source` field:
- `PLC` — automated reading from a Programmable Logic Controller (trusted, high frequency)
- `manual` — hand-entered by a technician (less frequent, may have higher variance)

All data is governed by Unity Catalog with full lineage tracking.

---

**Asset criticality tiers:**
- Tier 1 (most critical): Motor_4, Compressor_1, Compressor_2, Turbine_1, Turbine_2
- Tier 2: Motor_1, Motor_2, Motor_3, Pump_1, Pump_2, Pump_3, Pump_4, Compressor_3
- Tier 3 (lowest criticality): Motor_5, Motor_6, Conveyor_1–4, HVAC_1–3

When asked about "critical assets", filter by `criticality_tier = 1`.

---

**What I cannot answer:**
I cannot access real-time operational chat (use the Maintenance Control Tower app for that).
I cannot initiate work orders (those go through the CMMS). I work with historical and
pipeline-generated data only.

### PASTE END

---

## Certified Calculations

Add the following as **Certified SQL** in the Genie Space knowledge store. These are
pre-validated queries that Genie will use when questions match these patterns, and will
mark answers as "Trusted".

### 1. Current Health Status (All Assets)
**Trigger phrases:** "health status", "which assets are healthy", "show me the dashboard"

```sql
SELECT
    asset_id,
    production_line_id,
    criticality_tier,
    ROUND(health_score, 1) AS health_score,
    risk_level,
    ROUND(current_vibration, 3) AS vibration_mm_s,
    ROUND(estimated_rul_hours, 1) AS rul_hours,
    calculated_at
FROM utility_ops.asset_intelligence.gold_health_scores
ORDER BY health_score ASC
```

### 2. MTBF by Asset
**Trigger phrases:** "mean time between failures", "MTBF", "failure frequency"

```sql
SELECT
    asset_id,
    asset_type,
    production_line_id,
    COUNT(*) AS total_failures,
    ROUND(AVG(days_since_last_failure), 1) AS mtbf_days,
    ROUND(AVG(cost_to_fix), 0) AS avg_repair_cost,
    ROUND(AVG(downtime_hours), 1) AS avg_downtime_hours
FROM utility_ops.asset_intelligence.silver_maintenance_logs
WHERE days_since_last_failure IS NOT NULL
GROUP BY asset_id, asset_type, production_line_id
ORDER BY mtbf_days ASC
```

### 3. Vibration Trend — Last 48 Hours
**Trigger phrases:** "vibration trend", "vibration over time", "is vibration increasing"

```sql
SELECT
    asset_id,
    hour_window,
    ROUND(vibration_avg, 3) AS vibration_avg,
    ROUND(vibration_max, 3) AS vibration_max,
    anomaly_count,
    production_line_id
FROM utility_ops.asset_intelligence.gold_vibration_trends
WHERE hour_window >= DATEADD(HOUR, -48, CURRENT_TIMESTAMP())
ORDER BY asset_id, hour_window
```

### 4. Cost Impact Summary
**Trigger phrases:** "cost to fix", "financial impact", "should I repair", "ROI"

```sql
SELECT
    asset_id,
    production_line_id,
    risk_level,
    ROUND(estimated_rul_hours, 1) AS rul_hours,
    ROUND(cost_to_fix_now, 0) AS cost_to_fix_usd,
    ROUND(cost_of_unplanned_failure, 0) AS cost_if_fails_usd,
    ROUND(cost_of_unplanned_failure - cost_to_fix_now, 0) AS savings_by_fixing_now,
    net_recommendation
FROM utility_ops.asset_intelligence.gold_cost_impact
WHERE risk_level IN ('CRITICAL', 'HIGH')
ORDER BY cost_of_unplanned_failure DESC
```

### 5. First-Time Fix Rate by Technician
**Trigger phrases:** "technician performance", "first time fix", "which technician"

```sql
SELECT
    technician_id,
    COUNT(*) AS total_jobs,
    ROUND(
        SUM(CASE WHEN first_time_fix = true THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    ) AS first_time_fix_rate_pct,
    ROUND(AVG(labor_hours), 1) AS avg_labor_hours,
    ROUND(AVG(cost_to_fix), 0) AS avg_repair_cost
FROM utility_ops.asset_intelligence.silver_maintenance_logs
GROUP BY technician_id
ORDER BY first_time_fix_rate_pct DESC
```

---

## Sample Demo Questions

Use these during a live demo to showcase Genie's capability:

1. **"Which production lines are at risk due to rising vibration levels in Motor 4?"**
   → Should return Line_1 with Motor_4 in CRITICAL status and RUL < 6 hours

2. **"What is the mean time between failures for all motors?"**
   → Should return MTBF table with Motor_4 having the lowest MTBF (~62 days)

3. **"How much money would we lose if Motor 4 fails tonight?"**
   → Should return cost_of_unplanned_failure for Motor_4 (expected: ~$420,000)

4. **"Show me all assets with a health score below 60"**
   → Should return Motor_4 plus any HIGH assets

5. **"Which technician has the best first-time fix rate?"**
   → Should return ranked technician table from maintenance logs

6. **"What has been the total maintenance spend on Motor 4 in the last 2 years?"**
   → Should sum `cost_to_fix` from `silver_maintenance_logs` for `asset_id='Motor_4'`
