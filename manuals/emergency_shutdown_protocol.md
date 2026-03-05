# Emergency Shutdown Protocol

**Document ID:** MNT-EMRG-003
**Applies To:** All production lines (Line_1 through Line_4)
**Revision:** 4.0
**Last Updated:** 2025-01-08

---

## 1. Purpose

This protocol defines the conditions requiring an immediate (unplanned) emergency shutdown
of equipment, the procedure for executing the shutdown safely, and the escalation path
for management notification. It is distinct from a **planned shutdown** which is scheduled
in advance through the CMMS.

---

## 2. Mandatory Stop Conditions

Stop the equipment **immediately** if ANY of the following are observed:

### Vibration
| Asset Type | Stop Condition |
|------------|---------------|
| Motor (criticality_tier 1) | Vibration > rated_max OR health_score < 20 |
| Motor (criticality_tier 2–3) | Vibration > rated_max × 1.05 |
| Pump | Vibration > rated_max AND temperature > rated_max_temp × 0.75 |
| Compressor | Vibration > rated_max × 0.9 (compressors have stricter limits) |
| Turbine | Any reading > rated_max (turbines are zero-tolerance) |
| Conveyor | Physical jam or belt tracking failure |

### Temperature
- Any asset: `temp_c > rated_max_temp` for more than 2 consecutive readings
- Motor: Winding temperature > 130°C (if winding sensors are fitted)

### Other Conditions
- Visible smoke, burning smell, or unusual noise from any rotating equipment
- Fire alarm activation in the production area
- Process pressure beyond safe operating limits (any compressor or pump)
- Safety system intervention (e.g. over-current relay trip)

---

## 3. Shutdown Procedure — Immediate Stop

### For VFD-Controlled Motors (Motor_1, Motor_2, Motor_4, Motor_5)

1. Press the **EMERGENCY STOP** button on the local control panel (red mushroom button).
2. The VFD will apply controlled deceleration (ramp-down over 5 seconds).
3. If the VFD does not respond, open the main isolator on the MCC panel (ask for assistance
   from the control room — do not work alone near live panels).
4. Confirm equipment has reached zero speed before approaching.

### For Direct-On-Line (DOL) Equipment

1. Press the local stop button on the motor starter panel.
2. If no response, open the MCC circuit breaker for that equipment.
3. Wait for full stop before approaching.

### For Compressors (Compressor_1, Compressor_2, Compressor_3)

1. Set compressor controller to STOP mode.
2. Allow automatic purge cycle to complete (approximately 90 seconds).
3. **Do not** open discharge line while pressure remains — depressurise using the
   manual bleed valve first.

### For Turbines (Turbine_1, Turbine_2)

1. Initiate shutdown from the turbine control panel (TCS). **Never use local isolator
   as first action on a turbine.**
2. Contact Plant Supervisor immediately.
3. Coast-down may take up to 15 minutes — do not approach until full stop confirmed.

---

## 4. Post-Shutdown Actions (First 15 minutes)

1. **Notify immediately:**
   - Production Supervisor (radio channel 2 or ext. 220)
   - Control Room (ext. 201)
   - Maintenance Lead (ext. 340)

2. **Record in CMMS:**
   - Time of shutdown
   - Asset ID and line affected
   - Observation that triggered the stop (vibration reading, temperature, visual)
   - Operator name

3. **Assess immediate safety:**
   - Is there a fire or chemical hazard? If yes, activate general alarm and evacuate.
   - Are there personnel in the exclusion zone? Clear immediately.
   - Is adjacent equipment at risk? Assess cascade failure potential.

4. **Do not restart** until:
   - Maintenance Lead has assessed the fault
   - Health score is confirmed above 50 in the Maintenance Control Tower app
   - Written authorisation is issued by the Shift Supervisor

---

## 5. Financial Impact Calculator

Use the following to estimate the cost of an unplanned stop to communicate to management:

```
Unplanned outage cost = (Line hourly output × Estimated hours down)
                        + (Average repair cost × Emergency premium of 1.5×)
                        + (Collateral damage assessment, if any)

Example — Motor_4 failure on Line_1:
  Line_1 output = $52,000/hour
  Estimated downtime = 8 hours (vs. 4 hours for planned)
  Emergency repair = $3,200 × 1.5 = $4,800
  Total estimated cost = ($52,000 × 8) + $4,800 = $420,800

Same scenario if planned:
  Line_1 downtime = 4 hours (planned off-shift)
  Planned repair = $3,200
  Total cost = ($52,000 × 4) + $3,200 = $211,200 (if in production hours)
  Off-shift planned = $3,200 only (no production loss)
```

This comparison is automatically calculated and available in the Maintenance Control Tower
app. Query the AI agent: *"What is the cost comparison for a Motor_4 emergency stop vs.
a planned repair tonight?"*

---

## 6. Restart Authorisation Checklist

Before restarting after any emergency shutdown:

- [ ] Root cause identified and documented in CMMS
- [ ] Repair completed and signed off by qualified technician
- [ ] Health score > 50 confirmed in `asset_health_live` (Lakebase)
- [ ] Insulation resistance test passed (if motor was involved)
- [ ] Alignment check completed (if coupling was disconnected)
- [ ] No active alerts in the Maintenance Control Tower for this asset
- [ ] Shift Supervisor sign-off obtained

---

## 7. Related Documents

- `vibration_diagnostics.md` — how to diagnose the root cause
- `motor_bearing_replacement.md` — most common repair after emergency motor stop
- `motor4_operating_specifications.md` — Motor_4 thresholds
