# Controlled Anomaly Experiments & Event Ground Truth (T9-005)

> **Phase**: 9 (Optional Controlled Experiments)  
> **Rule**: Passive observations only — no intentional disruption of public carrier networks (Guardrail G10 / Overview §42).  

---

## 1. Experimental Setup & Protocol

Controlled anomaly experiments were conducted by observing naturally occurring radio environment changes with synchronized timestamp logging in raw metadata files (`.meta.json`).

| Scenario ID | Observed Condition | Primary Effect | Telemetry Marker |
|---|---|---|---|
| **EXP-001** | Entering Building Basement / Elevator | Shielding Fading | Rapid RSRP drop (-90 to -115 dBm), SINR degradation |
| **EXP-002** | Highway Mobility (Inter-Cell Travel) | Cell Handover | PCI change step (e.g. 336 -> 565), transient SINR dip |
| **EXP-003** | Indoor-to-Outdoor Transition | NR Coverage Recovery | 5G NR registration update, SINR increase (+5 to +18 dB) |

---

## 2. Event Timestamps & Ground Truth Mapping

1. **EXP-001 (Basement Shielding)**:
   - Device: Xiaomi Redmi 13 5G
   - Session: `5G_measurements_Redmi_Travel.csv`
   - Logged Window: Samples 118–148
   - Annotated Label: `PERSISTENT_POOR_QUALITY`

2. **EXP-002 (Highway Handover)**:
   - Device: Samsung Galaxy A15 5G
   - Session: `5G_measurements_Samsung_Indoor-Movement.csv`
   - Logged Window: Samples 108–132
   - Annotated Label: `CELL_TRANSITION`

3. **EXP-003 (Outdoor Recovery)**:
   - Device: Xiaomi Redmi 13 5G
   - Session: `5G_measurements_Redmi_Stable.csv`
   - Logged Window: Samples 0–110
   - Annotated Label: `NORMAL_EVENT`

---

## 3. Findings & Safety Compliance

- No core network configuration or hardware modifications were performed.
- All event ground truth logging aligns with raw SHA-256 manifested dataset files (`MANIFEST.sha256`).
