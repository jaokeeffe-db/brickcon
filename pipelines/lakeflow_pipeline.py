"""
Lakeflow Spark Declarative Pipeline: Asset Health Intelligence
Catalog: utility_ops
Pipeline name: asset_health_pipeline

This declarative pipeline implements the Bronze → Silver → Gold medallion architecture
for the Predictive Maintenance demo. It ingests raw sensor telemetry from UC Volumes,
applies 5-point rolling smoothing and anomaly flagging in the Silver layer, then computes
Health Scores, Remaining Useful Life (RUL), and Cost Impact in the Gold layer.

Deploy this file to Databricks via:
  1. Create a new Lakeflow Pipeline in the workspace (Pipelines > Create)
  2. Set the source to this file (from repo or workspace files)
  3. Set target catalog: utility_ops
  4. Enable Unity Catalog mode
  5. Run in Triggered mode for the demo; switch to Continuous for production

Pipeline settings to configure:
  - target: utility_ops
  - channel: PREVIEW (for latest features)
  - catalog: utility_ops
"""

import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CATALOG = "utility_ops"
RAW_TELEMETRY_PATH = f"/Volumes/{CATALOG}/raw_ingestion/raw_telemetry"

# ---------------------------------------------------------------------------
# BRONZE LAYER — Auto-Loader streaming ingest from UC Volumes
# ---------------------------------------------------------------------------


@dlt.table(
    name="bronze_sensor_readings",
    comment="Raw sensor telemetry ingested directly from UC Volume via Auto-Loader. No transformations applied.",
    table_properties={
        "quality": "bronze",
        "sensor_data": "true",
        "pii": "false",
        "pipelines.autoOptimize.managed": "true",
    },
)
def bronze_sensor_readings():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("header", "true")
        .option("cloudFiles.schemaLocation", f"{RAW_TELEMETRY_PATH}/_schema/sensor")
        .load(f"{RAW_TELEMETRY_PATH}/sensor_readings.csv")
        .withColumn("ingestion_time", F.current_timestamp())
        .withColumn("source_file", F.col("_metadata.file_path"))
        .withColumn("timestamp", F.to_timestamp("timestamp"))
    )


@dlt.table(
    name="bronze_maintenance_logs",
    comment="Raw maintenance work order logs ingested from UC Volume via Auto-Loader.",
    table_properties={
        "quality": "bronze",
        "pii": "false",
        "pipelines.autoOptimize.managed": "true",
    },
)
def bronze_maintenance_logs():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("header", "true")
        .option("cloudFiles.schemaLocation", f"{RAW_TELEMETRY_PATH}/_schema/maintenance")
        .load(f"{RAW_TELEMETRY_PATH}/maintenance_logs.csv")
        .withColumn("ingestion_time", F.current_timestamp())
        .withColumn("source_file", F.col("_metadata.file_path"))
        .withColumn("timestamp", F.to_timestamp("timestamp"))
        .withColumn("first_time_fix", F.col("first_time_fix").cast("boolean"))
    )


@dlt.table(
    name="bronze_asset_metadata",
    comment="Asset reference data — dimensions, ratings, and criticality tiers.",
    table_properties={
        "quality": "bronze",
        "pii": "false",
    },
)
def bronze_asset_metadata():
    return (
        spark.read.format("csv")
        .option("header", "true")
        .option("inferSchema", "true")
        .load(f"{RAW_TELEMETRY_PATH}/asset_metadata.csv")
        .withColumn("manufacture_date", F.to_date("manufacture_date"))
        .withColumn("installation_date", F.to_date("installation_date"))
    )


@dlt.table(
    name="bronze_production_output",
    comment="Production line financial output values for cost impact calculations.",
    table_properties={"quality": "bronze"},
)
def bronze_production_output():
    return (
        spark.read.format("csv")
        .option("header", "true")
        .option("inferSchema", "true")
        .load(f"{RAW_TELEMETRY_PATH}/production_output.csv")
    )


# ---------------------------------------------------------------------------
# SILVER LAYER — Cleaned, enriched, anomaly-flagged
# ---------------------------------------------------------------------------


@dlt.table(
    name="silver_asset_metadata",
    comment="Cleaned asset reference data. Invalid rows (zero ratings) filtered out.",
    table_properties={"quality": "silver", "pii": "false"},
)
@dlt.expect_or_drop("valid_rated_max_vibration", "rated_max_vibration > 0")
@dlt.expect_or_drop("valid_rated_max_temp", "rated_max_temp > 0")
def silver_asset_metadata():
    return dlt.read("bronze_asset_metadata").dropna(subset=["asset_id"])


@dlt.table(
    name="silver_sensor_readings",
    comment="Smoothed sensor readings with 5-point rolling average and anomaly flags. Joined with asset metadata for rated thresholds.",
    table_properties={
        "quality": "silver",
        "sensor_data": "true",
        "pii": "false",
        "pipelines.autoOptimize.managed": "true",
    },
)
@dlt.expect("valid_asset_id", "asset_id IS NOT NULL")
@dlt.expect("valid_timestamp", "timestamp IS NOT NULL")
def silver_sensor_readings():
    raw = dlt.read_stream("bronze_sensor_readings")
    metadata = dlt.read("silver_asset_metadata").select(
        "asset_id",
        "rated_max_vibration",
        "rated_max_temp",
        "criticality_tier",
        F.col("production_line_id").alias("line_id_ref"),
    )

    # Rolling averages cannot be applied on unbounded streams — they are computed
    # in gold_vibration_trends (Materialized View) which runs in batch mode.
    return (
        raw.join(metadata, on="asset_id", how="left")
        .withColumn(
            "vibration_anomaly_flag",
            F.when(
                F.col("vibration_mm_s") > F.col("rated_max_vibration") * 0.80,
                F.lit(True),
            ).otherwise(F.lit(False)),
        )
        .withColumn(
            "temp_anomaly_flag",
            F.when(
                F.col("temp_c") > F.col("rated_max_temp") * 0.80,
                F.lit(True),
            ).otherwise(F.lit(False)),
        )
        .select(
            "timestamp", "asset_id", "asset_type", "production_line_id",
            "vibration_mm_s", "temp_c", "pressure_psi", "rpm", "power_kw",
            "data_source", "vibration_anomaly_flag", "temp_anomaly_flag",
            "rated_max_vibration", "rated_max_temp", "criticality_tier",
            "ingestion_time", "source_file",
        )
    )


@dlt.table(
    name="silver_maintenance_logs",
    comment="Cleaned maintenance history with asset context. MTBF computed downstream in gold_cost_impact.",
    table_properties={"quality": "silver", "pii": "false"},
)
@dlt.expect_or_drop("valid_work_order", "work_order_id IS NOT NULL")
def silver_maintenance_logs():
    # Keep as STREAMING_TABLE (read_stream) — lag() window is not supported on streams.
    # MTBF / days_since_last_failure is computed at Gold level via MIN/MAX aggregation.
    logs = dlt.read_stream("bronze_maintenance_logs")
    metadata = dlt.read("silver_asset_metadata").select(
        "asset_id", "asset_type", "production_line_id", "criticality_tier"
    )

    return (
        logs.join(metadata, on="asset_id", how="left")
        .dropna(subset=["asset_id", "timestamp"])
        .select(
            "work_order_id", "asset_id", "timestamp", "fault_type",
            "part_replaced", "technician_id", "labor_hours", "cost_to_fix",
            "first_time_fix", "downtime_hours",
            "asset_type", "production_line_id", "criticality_tier",
            "ingestion_time", "source_file",
        )
    )


# ---------------------------------------------------------------------------
# GOLD LAYER — Aggregated, scored, cost-calculated (Materialized Views)
# ---------------------------------------------------------------------------


@dlt.table(
    name="gold_vibration_trends",
    comment="Hourly vibration aggregates per asset. Tagged critical_path. Feeds Genie and health score calculations.",
    table_properties={
        "quality": "gold",
        "critical_path": "true",
        "pii": "false",
    },
)
def gold_vibration_trends():
    # Apply 5-point rolling average here (Materialized View = batch, window functions OK)
    w5 = Window.partitionBy("asset_id").orderBy("timestamp").rowsBetween(-4, 0)
    smoothed = (
        dlt.read("silver_sensor_readings")
        .withColumn("vibration_smoothed", F.avg("vibration_mm_s").over(w5))
        .withColumn("temp_smoothed", F.avg("temp_c").over(w5))
    )
    return (
        smoothed
        .withColumn("hour_window", F.date_trunc("hour", "timestamp"))
        .groupBy("hour_window", "asset_id", "production_line_id", "criticality_tier")
        .agg(
            F.avg("vibration_smoothed").alias("vibration_avg"),
            F.max("vibration_mm_s").alias("vibration_max"),
            F.stddev("vibration_mm_s").alias("vibration_stddev"),
            F.avg("temp_smoothed").alias("temp_avg"),
            F.max("temp_c").alias("temp_max"),
            F.sum(F.col("vibration_anomaly_flag").cast("int")).alias("anomaly_count"),
            F.count("*").alias("reading_count"),
        )
        .withColumn("vibration_stddev", F.round("vibration_stddev", 4))
        .withColumn("vibration_avg", F.round("vibration_avg", 4))
        .withColumn("temp_avg", F.round("temp_avg", 2))
    )


@dlt.table(
    name="gold_health_scores",
    comment="Per-asset composite health score (0-100), risk level, and Remaining Useful Life (RUL) estimate. Tagged critical_path.",
    table_properties={
        "quality": "gold",
        "critical_path": "true",
        "pii": "false",
    },
)
def gold_health_scores():
    trends = dlt.read("gold_vibration_trends")
    metadata = dlt.read("silver_asset_metadata").select(
        "asset_id", "rated_max_vibration", "rated_max_temp"
    )

    # Get the most recent hourly window per asset
    w_latest = Window.partitionBy("asset_id").orderBy(F.desc("hour_window"))

    latest = (
        trends.withColumn("rn", F.row_number().over(w_latest))
        .filter(F.col("rn") == 1)
        .drop("rn")
    )

    # Linear regression slope over last 48 hours (vibration_avg vs unix timestamp)
    # A positive slope means vibration is increasing — used to compute RUL
    trend_48h = (
        trends.filter(
            F.col("hour_window") >= F.date_sub(F.current_timestamp(), 2)
        )
        .groupBy("asset_id")
        .agg(
            F.regr_slope(
                F.col("vibration_avg"),
                F.unix_timestamp("hour_window").cast("double"),
            ).alias("vibration_slope_per_sec")
        )
    )

    return (
        latest.join(metadata, on="asset_id", how="left")
        .join(trend_48h, on="asset_id", how="left")
        .withColumn(
            "health_score",
            F.greatest(
                F.lit(0.0),
                F.least(
                    F.lit(100.0),
                    F.lit(100.0) - (F.col("vibration_avg") / F.col("rated_max_vibration") * 100.0),
                ),
            ),
        )
        .withColumn(
            "risk_level",
            F.when(F.col("health_score") < 30, "CRITICAL")
            .when(F.col("health_score") < 60, "HIGH")
            .when(F.col("health_score") < 80, "MEDIUM")
            .otherwise("LOW"),
        )
        .withColumn(
            "estimated_rul_hours",
            F.when(
                F.col("vibration_slope_per_sec") > 0,
                F.greatest(
                    F.lit(0.0),
                    (F.col("rated_max_vibration") - F.col("vibration_avg"))
                    / (F.col("vibration_slope_per_sec") * 3600.0),
                ),
            ).otherwise(F.lit(None).cast("double")),
        )
        .select(
            "asset_id",
            F.col("hour_window").alias("calculated_at"),
            "production_line_id",
            "criticality_tier",
            F.round("vibration_avg", 4).alias("current_vibration"),
            F.round("temp_avg", 2).alias("current_temp"),
            "rated_max_vibration",
            F.round("health_score", 2).alias("health_score"),
            "risk_level",
            F.round("estimated_rul_hours", 1).alias("estimated_rul_hours"),
        )
    )


@dlt.table(
    name="gold_cost_impact",
    comment="Cost-to-fix vs cost-of-unplanned-failure per asset. Enables the AI agent's cost-aware repair recommendations.",
    table_properties={
        "quality": "gold",
        "critical_path": "true",
        "pii": "false",
    },
)
def gold_cost_impact():
    health = dlt.read("gold_health_scores")
    logs = dlt.read("silver_maintenance_logs")
    prod = dlt.read("bronze_production_output")

    avg_repair = (
        logs.groupBy("asset_id")
        .agg(
            F.avg("cost_to_fix").alias("avg_cost_to_fix"),
            F.avg("downtime_hours").alias("avg_downtime_hours"),
            F.avg("labor_hours").alias("avg_labor_hours"),
            (
                F.sum(F.col("first_time_fix").cast("int")) * 100.0 / F.count("*")
            ).alias("first_time_fix_rate"),
        )
    )

    return (
        health.join(avg_repair, on="asset_id", how="left")
        .join(
            prod.withColumnRenamed("line_id", "production_line_id"),
            on="production_line_id",
            how="left",
        )
        # Cost to fix now (planned)
        .withColumn("cost_to_fix_now", F.round(F.col("avg_cost_to_fix"), 2))
        # Cost of unplanned failure = lost production + emergency repair premium
        .withColumn(
            "cost_of_unplanned_failure",
            F.round(
                F.coalesce(F.col("estimated_rul_hours"), F.lit(0.0))
                * F.col("hourly_output_value_usd")
                + F.col("avg_cost_to_fix") * F.lit(1.5),
                2,
            ),
        )
        # Net recommendation
        .withColumn(
            "net_recommendation",
            F.when(
                (F.col("avg_cost_to_fix") < F.col("cost_of_unplanned_failure") * 0.5)
                & F.col("risk_level").isin("CRITICAL", "HIGH"),
                "SCHEDULE_IMMEDIATE",
            )
            .when(F.col("risk_level").isin("CRITICAL", "HIGH"), "SCHEDULE_IMMEDIATE")
            .when(F.col("risk_level") == "MEDIUM", "SCHEDULE_PLANNED")
            .otherwise("MONITOR"),
        )
        .select(
            "asset_id",
            "calculated_at",
            "production_line_id",
            "health_score",
            "risk_level",
            "estimated_rul_hours",
            "avg_cost_to_fix",
            "avg_downtime_hours",
            F.round("first_time_fix_rate", 1).alias("first_time_fix_rate"),
            "hourly_output_value_usd",
            "cost_to_fix_now",
            "cost_of_unplanned_failure",
            "net_recommendation",
        )
    )
