# Motor_4 Operating Specifications

**Document ID:** SPEC-MOTOR4-005
**Asset ID:** Motor_4
**Asset Type:** Three-Phase AC Induction Motor
**Model:** ABB M3BP-315
**Production Line:** Line_1
**Criticality Tier:** 1 (Critical — immediate action required on any alarm)
**Revision:** 1.3
**Last Updated:** 2025-02-10

---

## 1. Asset Overview

Motor_4 is the primary drive motor for the Line_1 material feed conveyor system.
It powers the main infeed belt at ~80% of rated load during normal operation.
As a Tier 1 critical asset, any unplanned downtime on Motor_4 results in a full
Line_1 shutdown, affecting all downstream equipment and $52,000/hour in production output.

---

## 2. Nameplate Specifications

| Parameter | Value |
|-----------|-------|
| **Model** | ABB M3BP-315 SMB 4 |
| **Power** | 200 kW |
| **Voltage** | 400V ± 10% (3-phase, 50 Hz) |
| **Rated Current** | 362 A |
| **Speed (synchronous)** | 1500 RPM |
| **Speed (full load)** | 1487 RPM |
| **Efficiency** | IE3 (95.0% at full load) |
| **Insulation Class** | F (thermal class 155°C) |
| **Protection** | IP55 |
| **Drive End Bearing** | SKF 6318/C3 |
| **Non-Drive End Bearing** | SKF 6310/C3 |
| **Weight** | 870 kg |
| **Serial Number** | ABB-M3BP-315-202007-4412 |

---

## 3. Operating Limits and Alarm Thresholds

### Vibration

| Level | Threshold | Response |
|-------|-----------|----------|
| Normal | < 2.5 mm/s RMS | No action |
| Watch | 2.5 – 4.0 mm/s | Increase monitoring frequency to hourly |
| Warning | 4.0 – 6.5 mm/s | Schedule maintenance within 48 hours |
| Alarm | 6.5 – 8.5 mm/s | Schedule immediate shutdown (next 8 hours) |
| **Critical** | **> 8.5 mm/s (rated max)** | **Emergency stop — do not continue operation** |

> **Current status (2025-03-05 23:50):** Vibration = 8.925 mm/s — **CRITICAL**.
> Health Score = 22/100. Estimated Remaining Useful Life = < 6 hours.
> Immediate bearing replacement required.

### Temperature

| Level | Threshold | Response |
|-------|-----------|----------|
| Normal | < 65°C | No action |
| Warning | 65 – 80°C | Inspect cooling system |
| **Alarm** | **> 85°C** | **Emergency stop** |

### Electrical

| Parameter | Normal | Alarm |
|-----------|--------|-------|
| Winding insulation resistance | > 100 MΩ | < 10 MΩ (do not energise) |
| Current imbalance | < 5% | > 10% |
| Voltage imbalance | < 2% | > 5% |

---

## 4. Maintenance History Summary

Based on records in `utility_ops.asset_intelligence.silver_maintenance_logs`:

| Metric | Motor_4 Value | Fleet Average |
|--------|--------------|---------------|
| Total work orders (2 years) | 12 | 8.4 |
| Mean Time Between Failures | 62 days | 87 days |
| Average cost per repair | $2,850 | $2,200 |
| First-Time Fix Rate | 83% | 80% |
| Last bearing replacement | Check CMMS | — |

> Motor_4 has a higher-than-average maintenance frequency due to its continuous high-load
> operation. The MTBF of 62 days suggests the current 18-month bearing replacement interval
> may need to be reduced to 12 months after engineering review.

---

## 5. Connected Equipment

Motor_4 directly drives the following equipment on Line_1:

- **Infeed Belt Conveyor (Conveyor_1):** Halts immediately on Motor_4 stop
- **Material Feed Hopper:** Will overflow within 8 minutes if infeed belt stops
- **Downstream Processing Unit DPU-101:** Auto-stops after 2-minute starve timeout

**Cascade shutdown sequence on Motor_4 failure:**
1. Motor_4 trips (0 sec)
2. Conveyor_1 halts (0 sec — directly coupled)
3. DPU-101 starve alarm activates (2 min)
4. DPU-101 auto-stops (4 min)
5. Line_1 full shutdown (6 min)
6. Upstream buffers reach capacity and halt (8–12 min)

Full Line_1 restart after Motor_4 emergency stop: estimated 45–90 minutes (including
safety checks on all cascade-stopped equipment).

---

## 6. Sensor Data Points

The following sensors are logged to Unity Catalog every 10 minutes:

| Sensor | Field Name | Location | Calibration Due |
|--------|-----------|----------|-----------------|
| Accelerometer (drive end) | `vibration_mm_s` | Drive-end bearing cap | 2025-09-01 |
| RTD temperature | `temp_c` | Motor body mid-frame | 2025-09-01 |
| Process pressure transducer | `pressure_psi` | Connected piping | 2025-06-01 |
| Tachometer | `rpm` | Shaft encoder | 2025-09-01 |
| Power analyser | `power_kw` | MCC panel | 2025-06-01 |
| Data source flag | `data_source` | — | PLC (automated) |

All sensor data flows through the Lakeflow pipeline into `utility_ops.asset_intelligence.silver_sensor_readings`
and is traceable via Unity Catalog data lineage.

---

## 7. Approved Spare Parts (Stocked)

| Part | Part Number | Min Stock | Current Stock |
|------|------------|-----------|---------------|
| Drive-end bearing | SKF 6318/C3 | 2 | Check stores |
| NDE bearing | SKF 6310/C3 | 2 | Check stores |
| Bearing grease | SKF LGMT3 (1kg) | 5 | Check stores |
| Shaft seal set | Parker 2-350N70 | 1 | Check stores |

> **Action required:** Verify spare bearing stock before scheduling Motor_4 repair.
> If SKF 6318/C3 is not in stock, lead time from preferred supplier is 24–48 hours.
> Emergency same-day delivery available at 1.8× standard price.

---

## 8. Contact and Escalation

| Role | Name | Contact |
|------|------|---------|
| Maintenance Lead | On-call rotation | Ext. 340 |
| Electrical Supervisor | — | Ext. 350 |
| ABB Service (warranty/technical) | — | 0800-ABB-SERV |
| Plant Manager | — | Ext. 201 |
