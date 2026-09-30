# Real-Data Sample (`data/sample/`)

This directory contains a committed sample of real 5G NR network measurements for testing, CI pipelines, and live demonstration without relying on external raw data files.

## Files

- `sample_measurements.csv`: 70 consecutive rows of real measurement data extracted from `data/raw/5G_measurements_Redmi_Indoor-Movement.csv`.

## Provenance & Details

- **Source File**: `data/raw/5G_measurements_Redmi_Indoor-Movement.csv`
- **Device**: Redmi 13 5G (`2406ERN9CI`)
- **Operator**: Airtel India
- **Scenario**: Scenario B (Indoor Movement)
- **Row Range**: Rows 93 to 162 (70 measurement samples, 3s sampling interval)
- **Data Authenticity**: Real, unmodified collector output.
- **Key Characteristics**: Contains actual physical cell identifier (PCI) and NR cell identifier (NCI) transitions during indoor movement, along with standard radio signal metrics (`ss_rsrp`, `ss_rsrq`, `ss_sinr`, `csi_rsrp`, etc.).
