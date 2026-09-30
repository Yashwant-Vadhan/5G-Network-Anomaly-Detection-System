# Raw Data Conventions and Metadata Guide — 5G-NADS

This directory (`data/raw/`) stores immutable raw CSV files captured directly by the Android **5G Network Tester** collector app (`com.example.a5gnetworktester`).

> **CRITICAL RULE**: Files placed in `data/raw/` must **never** be edited, modified, or renamed after being added to the manifest (`MANIFEST.sha256`). `data/raw/*.csv` files are git-ignored and preserved as raw measurements.

---

## 1. Filename Naming Convention

All raw CSV files MUST follow this naming format:

```text
<device>_<operator>_<scenario>_<YYYYMMDD>_<HHMM>.csv
```

### Components:
- `<device>`: Lowercase device slug matching project overview §10 (e.g., `redmi`, `samsung`, `oneplus`).
- `<operator>`: Lowercase cellular operator name (e.g., `airtel`, `jio`, `vodafone`).
- `<scenario>`: Single uppercase scenario letter code from project overview §41:
  - `scenario_a` or `scenarioA`: Stationary phone (baseline radio environment).
  - `scenario_b` or `scenarioB`: Indoor movement (walking within a building).
  - `scenario_c` or `scenarioC`: Outdoor movement (walking through outdoor areas across cells).
  - `scenario_d` or `scenarioD`: High mobility / vehicular travel.
  - `scenario_e` or `scenarioE`: Degraded signal / coverage edge area.
  - `scenario_f` or `scenarioF`: Rapid cell-switching / ping-pong zone.
- `<YYYYMMDD>`: Date of collection in ISO numeric format (e.g. `20260930`).
- `<HHMM>`: Local start time in 24-hour format (e.g. `1430`).

### Naming Examples (Matching §10 Devices):
- `redmi_airtel_scenarioA_20260930_1430.csv`
- `samsung_airtel_scenarioB_20260930_1600.csv`
- `oneplus_vodafone_scenarioC_20261001_1015.csv`

---

## 2. Metadata Sidecar File (`<filename>.meta.json`)

Every raw CSV file placed in `data/raw/` MUST be accompanied by a JSON sidecar metadata file with the exact same basename plus `.meta.json` (e.g., `redmi_airtel_scenarioA_20260930_1430.meta.json`).

Use `data/raw/meta.template.json` as the template.

### Privacy Rules (Overview §49):
- **NO precise location**: No GPS coordinates, latitude, longitude, address, or street names.
- **NO PII**: No phone numbers, IMSI, IMEI, IP addresses, or user identifiers.
- **Coarse location labels only**: Use general coarse descriptive labels such as `"campus_outdoor"`, `"hostel_indoor"`, `"library_floor2"`.

---

## 3. Data Integrity & Backup Strategy

1. **Manifest Integrity**: Run `python scripts/make_manifest.py data/raw` to generate or update `MANIFEST.sha256`. Verify integrity anytime using `python scripts/make_manifest.py data/raw --verify`.
2. **Backup Location**: Mirror raw CSV files to a private shared team drive (e.g. Google Drive) shared between Yashwant and Sushil. Never rely solely on a single local laptop.
