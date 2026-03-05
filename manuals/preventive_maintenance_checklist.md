# Preventive Maintenance Checklist

**Document ID:** MNT-PM-004
**Applies To:** All rotating equipment
**Revision:** 2.5
**Last Updated:** 2024-12-01

---

## 1. Purpose

This checklist defines the scheduled preventive maintenance (PM) tasks and intervals
for all 22 assets in the facility. Following this schedule is the primary mechanism for
preventing the bearing failures, seal leaks, and overheating events that drive unplanned
downtime.

The Genie Space calculates **Mean Time Between Failures (MTBF)** for each asset using
the `silver_maintenance_logs` table. Assets where actual MTBF falls below the target
interval in this document should be escalated to engineering for a reliability review.

---

## 2. Maintenance Intervals by Asset Type

### Motors (Motor_1 through Motor_6)

| Task | Criticality Tier 1 | Criticality Tier 2 | Criticality Tier 3 |
|------|-------------------|-------------------|-------------------|
| Vibration check (handheld) | Weekly | Monthly | Quarterly |
| Bearing re-grease | 3 months | 6 months | 12 months |
| Bearing replacement | 2 years | 3 years | 5 years |
| Insulation resistance test | 6 months | 12 months | 2 years |
| Coupling inspection | 6 months | 12 months | 2 years |
| Full overhaul | 4 years | 6 years | 8 years |

**Motor_4 specific (Tier 1, ABB-M3BP-315):**
- Bearing replacement interval: 18 months (reduced due to high load cycle on Line_1)
- Last bearing replacement: Check `maintenance_logs` — filter `asset_id='Motor_4'`
  and `part_replaced LIKE '%bearing%'`

---

### Pumps (Pump_1 through Pump_4)

| Task | Interval |
|------|----------|
| Seal inspection | Quarterly |
| Mechanical seal replacement | 18 months or at first leak |
| Impeller clearance check | Annually |
| Bearing re-grease | 4 months |
| Bearing replacement | 3 years |
| Casing pressure test | Biannually |

---

### Compressors (Compressor_1 through Compressor_3)

| Task | Interval |
|------|----------|
| Air filter replacement | Monthly |
| Oil level and quality check | Weekly |
| Belt tension and wear | Monthly |
| Oil separator element | 4,000 operating hours |
| Full service (valve kit + bearing) | 8,000 operating hours or 2 years |
| Load/unload valve test | Quarterly |

---

### Conveyors (Conveyor_1 through Conveyor_4)

| Task | Interval |
|------|----------|
| Belt tracking inspection | Weekly |
| Drive belt tension check | Monthly |
| Roller rotation check | Monthly |
| Gearbox oil change | 12 months |
| Belt replacement | 3 years or at first cracking |
| Tensioner spring check | 6 months |

---

### Turbines (Turbine_1, Turbine_2)

| Task | Interval |
|------|----------|
| Lube oil analysis | Monthly |
| Lube filter replacement | 500 operating hours |
| Blade inspection (borescope) | 2,000 operating hours |
| Full overhaul | 25,000 operating hours |

> **Note:** Turbine maintenance must be planned with minimum 72 hours notice and requires
> a specialist contractor (GE Vernova Service). Estimated lead time for parts: 3–6 weeks.

---

### HVAC Units (HVAC_1, HVAC_2, HVAC_3)

| Task | Interval |
|------|----------|
| Filter replacement | Monthly |
| Coil cleaning | Quarterly |
| Refrigerant level check | Biannually |
| Fan motor bearing re-grease | 12 months |
| Compressor service | 3 years |

---

## 3. Scheduling Rules

1. **Criticality Tier 1 assets** (Motor_4, Compressor_1, Compressor_2, Turbine_1,
   Turbine_2): All PM tasks must be completed within ±1 week of their due date.
   Overdue tasks escalate automatically to the Maintenance Lead.

2. **Off-shift preference:** Plan PM tasks for off-shift windows to minimise production
   impact. Line_1 maintenance window: Sundays 02:00–06:00 (4-hour window).

3. **Combination maintenance:** Where two tasks are due within 30 days of each other on
   the same asset, combine them into a single work order to reduce total downtime.

4. **CMMS integration:** All PM tasks should be created as recurring work orders in the
   CMMS. The `cost_to_fix` field should be populated with the estimated cost from this
   checklist to enable accurate Cost-to-Fix vs. Downtime calculations.

---

## 4. Failure Pattern Analysis

The Maintenance Control Tower agent can query historical patterns to identify assets
that are trending toward failure before their scheduled PM date. Use the following
queries in the Maintenance Intelligence Genie space:

- "Which assets are due for bearing replacement in the next 90 days?"
- "Show me the first-time fix rate for each technician over the last 12 months"
- "Which assets have the highest average repair cost per work order?"
- "How does the MTBF for Motor_4 compare to Motor_1 and Motor_2?"

---

## 5. Cost Benchmarks for PM Planning

| Asset Type | Typical PM Cost | Avoided Failure Cost | ROI |
|------------|----------------|---------------------|-----|
| Motor bearing re-grease | $150 | $3,200 bearing replacement | 21× |
| Motor bearing replacement (planned) | $3,200 | $48,000+ (winding rewind + downtime) | 15× |
| Pump seal replacement (planned) | $1,200 | $8,000 (emergency seal + cleanup) | 7× |
| Compressor belt + oil (planned) | $800 | $25,000+ (compressor failure) | 31× |

---

## 6. Related Documents

- `motor_bearing_replacement.md` — detailed procedure for bearing replacement tasks
- `vibration_diagnostics.md` — understanding vibration readings during inspections
- `emergency_shutdown_protocol.md` — what to do if a PM reveals a critical finding
