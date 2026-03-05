# Motor Bearing Replacement Procedure

**Document ID:** MNT-MOTOR-001
**Applies To:** ABB M3BP Series, Siemens 1LA7/1LA8, WEG W22 IE3
**Asset Types:** AC Induction Motors (Motor_1 through Motor_6)
**Revision:** 3.2
**Last Updated:** 2024-11-15

---

## 1. Purpose

This procedure documents the safe removal and replacement of drive-end and non-drive-end
bearings on three-phase induction motors. Correct bearing replacement eliminates the most
common cause of motor failure — accounting for approximately 40% of unplanned motor
outages in this facility.

---

## 2. When to Replace Bearings

Replace bearings immediately if ANY of the following conditions are observed:

| Symptom | Threshold | Action |
|---------|-----------|--------|
| Vibration (drive end) | > 7.0 mm/s RMS sustained > 30 min | STOP and replace |
| Vibration increasing trend | > 5% per hour for 8+ hours | Schedule within 24h |
| Audible grinding / rumbling | Any | STOP and inspect |
| Bearing temperature | > 85°C (Motor_4 limit: 80°C) | STOP and inspect |
| Grease discolouration | Dark brown or black | Replace at next scheduled window |

> **Motor_4 Note:** Due to its criticality_tier=1 rating on Line_1, the vibration threshold
> for Motor_4 (ABB M3BP-315) is reduced to **6.5 mm/s**. At 8.5 mm/s (rated max),
> catastrophic failure is imminent. Do not operate above 7.5 mm/s under any circumstances.

---

## 3. Parts and Tools Required

### Replacement Parts
- Drive-end bearing: SKF 6318/C3 (Motor_4 ABB-M3BP-315) or equivalent
- Non-drive-end bearing: SKF 6310/C3 (Motor_4 ABB-M3BP-315) or equivalent
- Bearing grease: SKF LGMT3 or equivalent, NLGI grade 3
- Shaft seals (replace as a set): Parker 2-350N70 or OEM equivalent
- Lock washers and circlips (replace if worn)

### Tools
- Mechanical bearing puller (SKF TMMP3 or equivalent)
- Hydraulic press or bearing heater (80–100°C)
- Digital infrared thermometer
- Torque wrench (capacity to 250 Nm)
- Vibration analyser (handheld, e.g. SKF CMVL 3600)
- Insulation resistance tester (Megger)

---

## 4. Safety Requirements

- **Lockout/Tagout (LOTO):** Apply LOTO to MCC panel before any work begins.
  Verify zero energy state with a voltage tester.
- **Permit required:** Hot work permit if using bearing heater above ambient +50°C.
- **PPE:** Safety glasses, anti-static gloves, steel-toe boots. Hearing protection if
  adjacent equipment is running.
- **Minimum crew:** 2 persons. One qualified electrician and one mechanical technician.

---

## 5. Step-by-Step Procedure

### Phase 1: Isolation and Preparation (estimated 30 min)

1. Notify production supervisor and control room. Log downtime start in CMMS.
2. Initiate planned shutdown: ramp motor to zero speed via VFD if fitted.
3. Apply LOTO at MCC panel. Confirm zero energy (test voltage at motor terminals).
4. Allow motor to cool to ≤ 40°C surface temperature before handling.
5. Disconnect coupling or belt drive. Photograph alignment marks before disassembly.
6. Remove motor from its baseplate mounting. Record torque values for re-installation.

### Phase 2: Disassembly (estimated 45 min)

7. Remove fan cover and cooling fan (usually 4× M8 bolts, 20 Nm).
8. Remove circlip from drive-end bearing housing.
9. Using the bearing puller, extract the drive-end bearing with steady, axial force.
   **Do not hammer the shaft directly — shaft damage will void warranty.**
10. Record bearing part number and inspect cage, inner/outer race for wear patterns.
    - Pitting or flaking → vibration fatigue failure (confirm with vibration history)
    - Brinelling (flat spots) → impact loading, investigate coupling alignment
    - Corrosion → inspect grease condition and sealing
11. Repeat steps 8–10 for non-drive-end bearing.
12. Clean bearing housings with lint-free cloth and isopropyl alcohol. Inspect for cracks.

### Phase 3: Installation (estimated 45 min)

13. Heat new bearings in oil bath or induction heater to 80°C (±5°C).
    **Do not exceed 120°C — bearing metallurgy changes above this temperature.**
14. Using insulated gloves, slide heated bearing onto shaft until it seats against
    the shoulder. Apply steady axial pressure — never use radial hammer blows.
15. Allow bearing to cool to ambient temperature before installing circlip and seals.
16. Pack bearing housing with 30–50% grease fill (LGMT3). Overfilling causes overheating.
17. Repeat steps 13–16 for second bearing.
18. Reinstall cooling fan and fan cover. Check impeller is not fouling the housing.
19. Reconnect motor to baseplate. Torque mounting bolts to specification (see nameplate).

### Phase 4: Alignment and Recommissioning (estimated 60 min)

20. Realign coupling or belt drive using laser alignment tool.
    Target: angular misalignment < 0.05 mm/m; parallel offset < 0.05 mm.
21. Reinstall coupling guard.
22. Perform insulation resistance test (Megger at 1000V DC):
    - Acceptable: > 100 MΩ winding to earth
    - Borderline: 10–100 MΩ (investigate moisture ingress)
    - Failed: < 10 MΩ (do not energise — escalate to engineering)
23. Remove LOTO. Perform test run:
    a. Start at no-load, listen for unusual noise (first 2 minutes).
    b. Measure vibration at bearing housings with handheld analyser.
       Target: < 3.0 mm/s RMS on drive end within 10 minutes of start.
    c. Monitor bearing temperature: should stabilise below 65°C within 30 minutes.
24. Restore to production load. Monitor vibration for first hour.
25. Log completion in CMMS. Record actual parts used, labour hours, and downtime.

---

## 6. Expected Outcomes

| Parameter | Pre-Replacement (Motor_4 example) | Post-Replacement Target |
|-----------|-----------------------------------|-------------------------|
| Vibration RMS | > 8.5 mm/s | < 2.5 mm/s |
| Bearing temperature | Elevated | < 65°C |
| Health Score | CRITICAL (< 30) | LOW (> 80) |
| Estimated RUL | < 6 hours | > 8,760 hours (1 year) |

---

## 7. Cost Reference

| Work Type | Typical Cost | Duration |
|-----------|-------------|----------|
| Planned bearing replacement | $2,400 – $3,200 | 4–6 hours |
| Emergency bearing replacement (unplanned) | $3,600 – $4,800 | 6–10 hours |
| Rewind after bearing-induced failure | $12,000 – $18,000 | 3–5 days |

> **Financial impact reminder:** Line_1 generates $52,000/hour. A 6-hour unplanned
> Motor_4 outage costs approximately $312,000 in lost production alone.

---

## 8. Related Documents

- `vibration_diagnostics.md` — interpreting vibration signatures before replacement
- `motor4_operating_specifications.md` — Motor_4 specific tolerances
- `preventive_maintenance_checklist.md` — scheduled maintenance intervals
