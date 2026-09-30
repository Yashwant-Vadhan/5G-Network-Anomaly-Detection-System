# EDA Findings — 5G-NADS

> This file collects observations from exploratory data analysis and collector verification.
> Findings are evidence-based; no conclusions are drawn without data support.

---

## Collector CSV Verification (T2-002)

**Date:** 2026-09-30
**Device:** Redmi 13 5G (`2406ERN9CI`), Xiaomi, Android 16
**Operator:** Airtel (reported as `Airtel FastLane`)

### Header Match
The CSV header produced by the Android collector matches Data Contract C1 in `docs/planning/TECH_RULES.md` exactly:
```
timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn
```
**Result:** ✅ No mismatch.

### Timestamp Format (answers Open Question 1)
- **Observed format:** `dd-MM-yy HH:mm:ss` (e.g., `28-09-26 22:42:06`)
- This is local device time, not UTC, and not ISO-8601.
- Preprocessing (T3-002) must parse with `%d-%m-%y %H:%M:%S`.

### Sampling Interval
- Configured: 3000 ms.
- Observed: consistent 3-second gaps between consecutive rows.

### Missing Values and Sentinels
- `NA` appears as a literal string for unavailable CSI fields (`csi_rsrp`, `csi_rsrq`, `csi_sinr`) on the Redmi device.
- No `2147483647` sentinel observed in the Redmi datasets so far — may appear on other devices. `SENTINEL_INTS` in `ml/config.py` already includes it.

### Deployment Mode
- Consistently reported as `UNKNOWN` on Redmi 13 5G under Airtel.
- This is expected for NSA mode where the Android API cannot distinguish NSA from SA.
- Guardrail G4 applies: never infer SA from UNKNOWN.

### Other Observations
- `display_override` is `NONE` throughout — the `TelephonyDisplayInfo` override type.
- `registered` is `TRUE` throughout the stationary dataset; may vary during outdoor movement.
- `nci` values are 64-bit integers (e.g., `13322280247`) — must use `Int64` dtype, not `int32`.

---

## Notes for Future EDA (Phase 3)

- Full distribution analysis, device comparison, and threshold determination are in T3-009 through T3-012.
- Additional sentinel values may be discovered during Samsung data analysis.
