# Vibration Diagnostics Procedure

**Document ID:** MNT-DIAG-002
**Applies To:** All rotating equipment (motors, pumps, compressors, conveyors, turbines)
**Revision:** 2.1
**Last Updated:** 2024-09-20

---

## 1. Purpose

This procedure provides guidance for interpreting vibration sensor readings from the
plant's PLC-connected accelerometers. Correct diagnosis of vibration signatures enables
technicians to identify the root cause of degradation before catastrophic failure.

---

## 2. Vibration Severity Scale (ISO 10816-3)

| Zone | RMS Velocity (mm/s) | Condition | Action |
|------|---------------------|-----------|--------|
| A    | 0 – 2.3             | New / excellent | No action |
| B    | 2.3 – 4.5           | Acceptable      | Monitor at next PM |
| C    | 4.5 – 7.1           | Alarm — investigate | Schedule repair within 7 days |
| D    | > 7.1               | Danger — risk of damage | Stop and repair |

> **Facility adjustment:** Due to continuous 24/7 operation and high criticality of
> Line_1 assets, the facility uses a **conservative threshold of 80% of rated_max_vibration**
> as the alarm trigger rather than the ISO 10816-3 defaults above.

---

## 3. Common Vibration Signatures and Causes

### 3.1 Bearing Defect

**Signature:** Broadband noise floor increase; high-frequency impulsive content
**Characteristic frequencies:**
- BPFO (ball pass frequency outer race) = n × RPM/60 × (1 - Bd/Pd × cos α) / 2
- BPFI (ball pass frequency inner race) = n × RPM/60 × (1 + Bd/Pd × cos α) / 2

**What it looks like in data:**
- Steady increase in vibration_mm_s baseline over hours to days (as seen in Motor_4)
- Trend slope > 2% per hour sustained → bearing replacement imminent
- Vibration does not decrease after thermal normalisation

**Diagnosis confidence:** HIGH when:
1. Vibration increase is monotonic (not correlated with load changes)
2. Temperature at bearing housing elevated by > 10°C vs baseline
3. Work order history shows bearing not replaced in > 2 years

---

### 3.2 Shaft Misalignment

**Signature:** 1× and 2× running speed harmonics dominant
**What it looks like in data:**
- Vibration correlates with RPM changes
- Both axial and radial vibration elevated simultaneously
- Often appears shortly after a coupling change or maintenance event

**Action:** Check laser alignment. Do not replace bearings until alignment is corrected —
misalignment will destroy new bearings within weeks.

---

### 3.3 Imbalance

**Signature:** 1× running speed dominant, sinusoidal
**What it looks like in data:**
- Clean, single-frequency elevation
- Vibration higher on radial axes, lower on axial
- Not temperature-dependent

**Action:** Dynamic balancing at next planned shutdown. Not an emergency unless vibration
exceeds Zone C.

---

### 3.4 Resonance

**Signature:** Sudden large amplitude at a specific speed (critical speed)
**What it looks like in data:**
- Vibration spike at a fixed RPM, not at harmonics of running speed
- Appears during run-up/coast-down, not at steady state

**Action:** Engineering evaluation required. May require damping modification or speed
change. Do not attempt to repair without engineering sign-off.

---

### 3.5 Thermal Spike (Overheating)

**Signature:** Rapid temperature increase (> 10°C/hour) without corresponding vibration
**What it looks like in data:**
- `temp_c` spikes 15–25°C above baseline over 2–3 readings, then returns
- `vibration_mm_s` remains within normal range during the spike
- Correlates with high ambient temperature or coolant failure

**Typical causes:** Blocked cooling fins, low lubricant, overloading, coolant valve failure
**Action:** Check cooling system immediately. If temperature exceeds rated_max_temp,
stop equipment and investigate before restarting.

---

## 4. Motor_4 Case Study — Current Scenario

Based on current sensor data, Motor_4 (ABB-M3BP-315, Line_1) is exhibiting the following
pattern consistent with progressive bearing failure:

| Time window | Average vibration | Trend |
|-------------|-------------------|-------|
| 7 days ago | 2.1 mm/s | Stable |
| 3 days ago | 2.3 mm/s | Marginal increase |
| 48 hours ago | 2.8 mm/s | Increasing |
| 24 hours ago | 5.2 mm/s | Rapid increase |
| Current | 8.5+ mm/s | CRITICAL — exceeds rated max |

**Diagnosis:** Classic progressive bearing failure (outer race spalling). The exponential
increase in the last 48 hours indicates the bearing cage has begun to fragment.

**Recommended action:** Immediate planned shutdown for bearing replacement.
Refer to `motor_bearing_replacement.md` for the full procedure.

---

## 5. Vibration Data Interpretation in Genie

When querying the Maintenance Intelligence Genie space, the following natural language
questions will return relevant vibration trend analysis:

- "Show me vibration trends for Motor_4 over the last 7 days"
- "Which assets have a vibration anomaly flag set to true?"
- "List all assets where current vibration exceeds 80% of their rated maximum"
- "What is the vibration slope for all motors on Line_1?"

---

## 6. Related Documents

- `motor_bearing_replacement.md` — replacement procedure once diagnosis is confirmed
- `motor4_operating_specifications.md` — Motor_4 specific vibration tolerances
- `emergency_shutdown_protocol.md` — when to initiate immediate stop
