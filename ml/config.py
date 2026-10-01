"""Shared constants for 5G-NADS.

Every value below carries a comment naming its origin: a source document, an
EDA finding, a documented assumption, or the task that will replace a
placeholder.  `docs/planning/TECH_RULES.md` (Coding Standards) forbids magic
numbers in code, so thresholds added in later phases must be declared here the
same way.  Importing this module must have no side effects.
"""

from __future__ import annotations

from pathlib import Path

# --- Contract C1: raw CSV columns from the Android collector -------------------
# Origin: `project-overview.md` §11 (dataset schema), header order preserved.
RAW_COLUMNS: list[str] = [
    "timestamp",
    "device",
    "manufacturer",
    "android",
    "operator",
    "network_type",
    "deployment_mode",
    "display_override",
    "registered",
    "ss_rsrp",
    "ss_rsrq",
    "ss_sinr",
    "csi_rsrp",
    "csi_rsrq",
    "csi_sinr",
    "pci",
    "nci",
    "nrarfcn",
]

# --- Missing-value policy -----------------------------------------------------
# Origin: `project-overview.md` §13 — the collector writes the literal `NA` for
# unavailable values, and the pipeline must treat it as missing, never as 0 (G3).
NA_TOKENS: list[str] = ["NA"]

# Origin: `project-overview.md` §13 and EDA findings (`docs/eda_findings.md`).
# Android integer "unavailable" sentinels: 2147483647 (Integer.MAX_VALUE),
# -1 (uninitialized/invalid cell info), 99 (unknown RSSI/signal), 999 (unknown ARFCN).
SENTINEL_INTS: list[int] = [2147483647, -1, 99, 999]

# --- Sampling and temporal windows --------------------------------------------
# Origin: `project-overview.md` §24 — the collector logs approximately every 3 s.
SAMPLING_SECONDS: int = 3

# Origin: `project-overview.md` §24 — candidate windows 5/10/20 samples
# (≈15/30/60 s). The final choice is made experimentally, not assumed.
WINDOW_SIZES: list[int] = [5, 10, 20]

# Mid-range candidate choice (30s history window).
DEFAULT_WINDOW: int = 10

# Origin: `docs/eda_findings.md` (PRD Open Question 3). 30 s threshold derived
# from observed gap distribution (3 s nominal sampling vs >60 s inter-session breaks).
SESSION_GAP_SECONDS: int = 30

# --- Plausible metric ranges for validity checking ----------------------------
# Origin: Android official API documentation for CellSignalStrengthNr
# https://developer.android.com/reference/android/telephony/CellSignalStrengthNr
# SS-RSRP / CSI-RSRP valid range: [-140, -44] dBm
# SS-RSRQ / CSI-RSRQ valid range: [-43, 20] dB
# SS-SINR / CSI-SINR valid range: [-23, 40] dB
VALID_RANGES: dict[str, tuple[float, float]] = {
    "ss_rsrp": (-140.0, -44.0),
    "ss_rsrq": (-43.0, 20.0),
    "ss_sinr": (-23.0, 40.0),
    "csi_rsrp": (-140.0, -44.0),
    "csi_rsrq": (-43.0, 20.0),
    "csi_sinr": (-23.0, 40.0),
}

# --- Reproducibility ----------------------------------------------------------
# Documented assumption, not a measured value: a fixed seed is required by the
# PRD (Success Metrics → Reproducibility) and TECH_RULES (Determinism), but no
# specific number is stated in `project-overview.md`.
RANDOM_STATE: int = 42

# --- Enumerations (UPPER_SNAKE strings) ---------------------------------------
# Origin: `docs/planning/TECH_RULES.md` (Coding Standards → Enums), which lists
# these from `project-overview.md` §17.
ANOMALY_TYPES: list[str] = [
    "NORMAL",
    "SIGNAL_DEGRADATION",
    "SUDDEN_SIGNAL_DEGRADATION",
    "CELL_TRANSITION",
    "NETWORK_STATE_TRANSITION",
    "PERSISTENT_POOR_QUALITY",
    "COMBINED_ANOMALY",
]

# Origin: `project-overview.md` §46 (severity is optional but must be
# documented and validated, not chosen arbitrarily).
SEVERITY_LEVELS: list[str] = ["LOW", "MEDIUM", "HIGH"]

# Origin: `project-overview.md` §8. `UNKNOWN` is a valid, expected value and is
# never promoted to `SA` (G4).
DEPLOYMENT_MODES: list[str] = ["NSA", "SA", "UNKNOWN"]

# --- Persistence and Anomaly Thresholds ---------------------------------------
# Origin: `docs/eda_findings.md` / `project-overview.md` §23 — dataset-specific
# poor quality thresholds derived from empirical EDA 10th-percentiles.
PERSIST_THRESHOLDS: dict[str, float] = {
    "weak_rsrp": -110.0,
    "poor_rsrq": -15.0,
    "poor_sinr": 0.0,
}

# Origin: `project-overview.md` §23 — threshold for rolling z-score baseline
BASELINE_Z_THRESHOLD: float = 2.5

# --- Model features (contract C3) ---------------------------------------------
# Origin: `project-overview.md` §22, in the order given there. PLACEHOLDER:
# "the final feature set must be determined after exploratory analysis" (§22);
# todo.md T4-005 finalises this list and records the decision on whether the
# categorical IDs (pci, nci, nrarfcn) are usable as numeric features.
# `csi_*` columns are deliberately absent: missing CSI is a device/API
# limitation, never an anomaly signal (G2, `project-overview.md` §48.2).
FEATURE_COLUMNS: list[str] = [
    "ss_rsrp",
    "ss_rsrq",
    "ss_sinr",
    "pci",
    "nci",
    "nrarfcn",
    "delta_rsrp",
    "delta_rsrq",
    "delta_sinr",
    "pci_changed",
    "nci_changed",
    "network_changed",
    "rolling_mean_rsrp",
    "rolling_mean_rsrq",
    "rolling_mean_sinr",
    "rolling_std_rsrp",
    "rolling_std_rsrq",
    "rolling_std_sinr",
]

# --- Repository paths ---------------------------------------------------------
# Derived from this file's location so the pipeline works from any working
# directory; no environment variable is needed for local execution
# (TECH_RULES → Deployment Rules: single local environment).
REPO_ROOT: Path = Path(__file__).resolve().parents[1]
DATA_DIR: Path = REPO_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
SAMPLE_DIR: Path = DATA_DIR / "sample"
MODELS_DIR: Path = REPO_ROOT / "models"
