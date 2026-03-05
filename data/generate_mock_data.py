"""
Generate mock datasets for the Databricks Disruption Response Agent demo.

Outputs:
  - sensor_readings.csv       (~288k rows, 90 days x 22 assets x 144 readings/day)
  - maintenance_logs.csv      (~240 work orders, 2 years of history)
  - asset_metadata.csv        (22 assets with ratings and criticality)
  - production_output.csv     (4 production lines with hourly output values)

Key demo signature: Motor_4 shows exponential vibration increase over the last 48 hours,
putting its health score into CRITICAL territory to drive the demo narrative.
"""

import csv
import math
import random
import os
from datetime import datetime, timedelta

random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Asset catalogue
# ---------------------------------------------------------------------------

ASSETS = [
    # asset_id, asset_type, model_number, production_line_id, criticality_tier,
    # rated_max_vibration (mm/s), rated_max_temp (C), replacement_cost ($)
    ("Motor_1",     "Motor",      "ABB-M3BP-355",  "Line_1", 2, 9.0,  85.0, 45000),
    ("Motor_2",     "Motor",      "ABB-M3BP-280",  "Line_1", 2, 8.0,  80.0, 38000),
    ("Motor_3",     "Motor",      "Siemens-1LA8",  "Line_2", 2, 9.5,  90.0, 52000),
    ("Motor_4",     "Motor",      "ABB-M3BP-315",  "Line_1", 1, 8.5,  85.0, 48000),  # DEMO ASSET
    ("Motor_5",     "Motor",      "Siemens-1LA7",  "Line_2", 3, 7.5,  78.0, 32000),
    ("Motor_6",     "Motor",      "WEG-W22-IE3",   "Line_3", 3, 8.0,  82.0, 35000),
    ("Pump_1",      "Pump",       "Grundfos-NK80", "Line_1", 2, 6.0,  70.0, 22000),
    ("Pump_2",      "Pump",       "Grundfos-NK65", "Line_2", 2, 5.5,  68.0, 18000),
    ("Pump_3",      "Pump",       "KSB-Etanorm",   "Line_3", 3, 6.5,  72.0, 24000),
    ("Pump_4",      "Pump",       "Grundfos-NK100","Line_4", 2, 7.0,  75.0, 28000),
    ("Compressor_1","Compressor", "Atlas-GA18",    "Line_1", 1, 10.0, 100.0, 95000),
    ("Compressor_2","Compressor", "Atlas-GA22",    "Line_2", 1, 10.0, 100.0, 98000),
    ("Compressor_3","Compressor", "Ingersoll-UP6", "Line_3", 2, 9.0,  95.0, 82000),
    ("Conveyor_1",  "Conveyor",   "Interroll-7000","Line_1", 3, 4.0,  60.0, 15000),
    ("Conveyor_2",  "Conveyor",   "Interroll-7000","Line_2", 3, 4.0,  60.0, 15000),
    ("Conveyor_3",  "Conveyor",   "Interroll-8000","Line_3", 3, 4.5,  62.0, 16500),
    ("Conveyor_4",  "Conveyor",   "Interroll-8000","Line_4", 3, 4.5,  62.0, 16500),
    ("Turbine_1",   "Turbine",    "GE-LM2500",     "Line_4", 1, 12.0, 120.0, 250000),
    ("Turbine_2",   "Turbine",    "GE-LM2500",     "Line_4", 1, 12.0, 120.0, 250000),
    ("HVAC_1",      "HVAC",       "Carrier-30XA",  "Line_1", 3, 3.5,  55.0, 28000),
    ("HVAC_2",      "HVAC",       "Carrier-30XA",  "Line_2", 3, 3.5,  55.0, 28000),
    ("HVAC_3",      "HVAC",       "Trane-CGAM",    "Line_3", 3, 4.0,  58.0, 30000),
]

ASSET_MAP = {a[0]: a for a in ASSETS}

PRODUCTION_LINES = [
    # line_id, hourly_output_value_usd, active_hours_per_day
    ("Line_1", 52000, 20),
    ("Line_2", 48000, 20),
    ("Line_3", 35000, 18),
    ("Line_4", 61000, 22),
]

# Baseline healthy vibration (mm/s) — roughly 25% of rated_max
BASELINES = {a[0]: round(a[5] * 0.25, 2) for a in ASSETS}

# Thermal spike events: (asset_id, spike_start_hour_from_end, spike_duration_readings, delta_temp)
THERMAL_SPIKES = [
    ("Pump_2",       72 * 6, 3, 18.0),   # 3 days from end
    ("Compressor_1", 48 * 6, 2, 22.0),   # 2 days from end
    ("Motor_6",      24 * 6, 3, 15.0),   # 1 day from end
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def jitter(value: float, pct: float = 0.03) -> float:
    """Apply ±pct random noise to value."""
    return round(value * (1 + random.uniform(-pct, pct)), 4)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Sensor readings
# ---------------------------------------------------------------------------

def generate_sensor_readings(days: int = 90, interval_minutes: int = 10) -> list[dict]:
    """Generate sensor readings for all assets over `days` days."""
    now = datetime(2025, 3, 5, 0, 0, 0)
    start = now - timedelta(days=days)

    readings_per_day = (24 * 60) // interval_minutes
    total_readings = days * readings_per_day

    # Build spike lookup: set of (asset_id, reading_index_from_end)
    spike_set: set[tuple[str, int]] = set()
    for asset_id, idx_from_end, duration, _ in THERMAL_SPIKES:
        for d in range(duration):
            spike_set.add((asset_id, total_readings - idx_from_end + d))

    rows = []
    for asset in ASSETS:
        asset_id = asset[0]
        asset_type = asset[1]
        line_id = asset[3]
        rated_max_vib = asset[5]
        rated_max_temp = asset[6]
        base_vib = BASELINES[asset_id]
        base_temp = rated_max_temp * 0.45  # healthy operating temp ~45% of max

        # Find thermal spike config for this asset (if any)
        spike_cfg = next(
            (s for s in THERMAL_SPIKES if s[0] == asset_id), None
        )

        for i in range(total_readings):
            ts = start + timedelta(minutes=i * interval_minutes)

            # Motor_4: exponential vibration ramp in last 48 hours
            if asset_id == "Motor_4":
                cutoff = total_readings - (48 * 60 // interval_minutes)
                if i >= cutoff:
                    hours_elapsed = (i - cutoff) * interval_minutes / 60.0
                    vibration = min(
                        rated_max_vib * 1.05,  # cap slightly above rated max
                        base_vib * math.pow(1.05, hours_elapsed)
                    )
                else:
                    vibration = jitter(base_vib)
            else:
                vibration = jitter(base_vib)

            # Thermal spike
            if spike_cfg and (asset_id, i) in spike_set:
                temp = jitter(base_temp + spike_cfg[3])
            else:
                temp = jitter(base_temp)

            pressure = jitter(base_vib * 0.8 + 1.2)   # pressure correlates loosely
            rpm = jitter(1450.0 if asset_type == "Motor" else 2900.0 if asset_type == "Pump" else 3000.0)
            power = jitter(rated_max_vib * 8.5)          # rough proxy

            rows.append({
                "timestamp": iso(ts),
                "asset_id": asset_id,
                "asset_type": asset_type,
                "production_line_id": line_id,
                "vibration_mm_s": round(vibration, 4),
                "temp_c": round(temp, 2),
                "pressure_psi": round(pressure, 2),
                "rpm": round(rpm, 1),
                "power_kw": round(power, 2),
                "data_source": "PLC",
            })

    return rows


# ---------------------------------------------------------------------------
# Maintenance logs
# ---------------------------------------------------------------------------

FAULT_TYPES = [
    "Bearing failure", "Seal leak", "Shaft misalignment", "Overheating",
    "Vibration imbalance", "Electrical fault", "Corrosion", "Lubrication failure",
    "Belt wear", "Impeller damage",
]

PARTS_BY_TYPE = {
    "Motor":      ["Drive bearing", "Shaft seal", "Rotor winding", "Fan blade", "Terminal block"],
    "Pump":       ["Mechanical seal", "Impeller", "Wear ring", "Bearing", "Coupling"],
    "Compressor": ["Air filter", "Belt", "Oil separator", "Valve kit", "Bearing set"],
    "Conveyor":   ["Drive belt", "Roller", "Tensioner", "Gearbox oil", "Pulley"],
    "Turbine":    ["Blade set", "Bearing race", "Seal kit", "Control valve", "Lube filter"],
    "HVAC":       ["Compressor kit", "Condenser coil", "Fan motor", "Refrigerant", "Filter set"],
}

TECHNICIANS = ["T001", "T002", "T003", "T004", "T005"]


def generate_maintenance_logs(days: int = 730) -> list[dict]:
    """Generate ~240 maintenance work orders over 2 years."""
    now = datetime(2025, 3, 5, 0, 0, 0)
    start = now - timedelta(days=days)

    rows = []
    order_num = 1000

    for asset in ASSETS:
        asset_id = asset[0]
        asset_type = asset[1]
        criticality = asset[4]

        # Higher criticality → more frequent maintenance
        events_per_year = {1: 8, 2: 5, 3: 3}[criticality]
        total_events = int(events_per_year * (days / 365))

        for _ in range(total_events):
            offset_days = random.uniform(0, days)
            ts = start + timedelta(days=offset_days)
            fault = random.choice(FAULT_TYPES)
            part = random.choice(PARTS_BY_TYPE.get(asset_type, ["Generic part"]))
            tech = random.choice(TECHNICIANS)
            labor_hours = round(random.uniform(1.5, 12.0), 1)
            parts_cost = random.uniform(200, 3500)
            cost_to_fix = round(labor_hours * 85 + parts_cost, 2)  # $85/hr labor
            first_time_fix = random.random() > 0.2  # 80% first-time fix rate
            downtime = round(labor_hours * random.uniform(0.8, 1.5), 1)

            rows.append({
                "work_order_id": f"WO-{order_num:05d}",
                "asset_id": asset_id,
                "timestamp": iso(ts),
                "fault_type": fault,
                "part_replaced": part,
                "technician_id": tech,
                "labor_hours": labor_hours,
                "cost_to_fix": cost_to_fix,
                "first_time_fix": first_time_fix,
                "downtime_hours": downtime,
            })
            order_num += 1

    rows.sort(key=lambda r: r["timestamp"])
    return rows


# ---------------------------------------------------------------------------
# Asset metadata
# ---------------------------------------------------------------------------

def generate_asset_metadata() -> list[dict]:
    now = datetime(2025, 3, 5)
    rows = []
    for asset in ASSETS:
        install_years_ago = random.randint(2, 10)
        manufacture_years_ago = install_years_ago + random.randint(0, 1)
        rows.append({
            "asset_id": asset[0],
            "asset_type": asset[1],
            "model_number": asset[2],
            "manufacture_date": (now - timedelta(days=manufacture_years_ago * 365)).strftime("%Y-%m-%d"),
            "installation_date": (now - timedelta(days=install_years_ago * 365)).strftime("%Y-%m-%d"),
            "production_line_id": asset[3],
            "criticality_tier": asset[4],
            "rated_max_vibration": asset[5],
            "rated_max_temp": asset[6],
            "replacement_cost": asset[7],
        })
    return rows


# ---------------------------------------------------------------------------
# Production output
# ---------------------------------------------------------------------------

def generate_production_output() -> list[dict]:
    return [
        {"line_id": line[0], "hourly_output_value_usd": line[1], "active_hours_per_day": line[2]}
        for line in PRODUCTION_LINES
    ]


# ---------------------------------------------------------------------------
# Write CSVs
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict], filename: str) -> None:
    if not rows:
        return
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written {len(rows):,} rows → {path}")


def main() -> None:
    print("Generating mock datasets for Databricks Disruption Response Agent demo...")
    print()

    print("1/4  Sensor readings (90 days, 22 assets, 10-min intervals)...")
    sensor_rows = generate_sensor_readings()
    write_csv(sensor_rows, "sensor_readings.csv")

    print("2/4  Maintenance logs (2 years of work orders)...")
    maintenance_rows = generate_maintenance_logs()
    write_csv(maintenance_rows, "maintenance_logs.csv")

    print("3/4  Asset metadata (22 assets)...")
    metadata_rows = generate_asset_metadata()
    write_csv(metadata_rows, "asset_metadata.csv")

    print("4/4  Production output (4 lines)...")
    output_rows = generate_production_output()
    write_csv(output_rows, "production_output.csv")

    print()
    print("Done. Files in:", OUTPUT_DIR)

    # Spot-check: show Motor_4 final 5 readings to confirm the failure signature
    motor4_last = [
        r for r in sensor_rows
        if r["asset_id"] == "Motor_4"
    ][-5:]
    print()
    print("Motor_4 final 5 readings (confirm failure signature):")
    for r in motor4_last:
        print(f"  {r['timestamp']}  vibration={r['vibration_mm_s']} mm/s  temp={r['temp_c']}°C")


if __name__ == "__main__":
    main()
