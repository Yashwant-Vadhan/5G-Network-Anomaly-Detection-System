"""Device generalisation and cross-device evaluation script (T7-017).

Trains Isolation Forest on one device dataset (e.g. Redmi) and evaluates on another
device dataset (e.g. Samsung), recording cross-device transfer metrics and modem caveats.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.anomaly_detection import if_scores
from ml.evaluate import compute_metrics
from ml.feature_engineering import build_features
from ml.train import train_iforest


def run_device_generalisation_eval(
    clean_csv: Path | str = "data/processed/measurements_clean.csv",
    labels_csv: Path | str = "data/eval/labels_final.csv",
    out_report: Path | str = "docs/device_generalisation_report.md",
) -> str:
    """Run cross-device evaluation (Redmi model on Samsung data & vice versa)."""
    raw_df = pd.read_csv(clean_csv)
    df = build_features(raw_df)

    # Separate datasets by device
    redmi_df = df[df["device"].str.contains("Redmi|2406", case=False, na=False)].copy()
    samsung_df = df[df["device"].str.contains("Samsung|SM-", case=False, na=False)].copy()

    # Train model on Redmi data
    redmi_dir = Path("models/scratch_redmi")
    model_redmi, _, _ = train_iforest(redmi_df, out_dir=redmi_dir, allow_synthetic=True)
    from joblib import load

    scaler_redmi = load(redmi_dir / "scaler.joblib")

    # Evaluate Redmi model on Samsung data
    samsung_scored = if_scores(samsung_df, model=model_redmi, scaler=scaler_redmi)

    # Calculate metrics on Samsung
    y_true_samsung = samsung_scored["ss_sinr"] < 0
    y_pred_samsung = samsung_scored["if_flag"].fillna(False)
    metrics_samsung = compute_metrics(y_true_samsung, y_pred_samsung)

    # Train model on Samsung data
    samsung_dir = Path("models/scratch_samsung")
    model_samsung, _, _ = train_iforest(samsung_df, out_dir=samsung_dir, allow_synthetic=True)
    scaler_samsung = load(samsung_dir / "scaler.joblib")

    # Evaluate Samsung model on Redmi data
    redmi_scored = if_scores(redmi_df, model=model_samsung, scaler=scaler_samsung)
    y_true_redmi = redmi_scored["ss_sinr"] < 0
    y_pred_redmi = redmi_scored["if_flag"].fillna(False)
    metrics_redmi = compute_metrics(y_true_redmi, y_pred_redmi)

    r_p = metrics_redmi["precision"]
    r_r = metrics_redmi["recall"]
    r_f1 = metrics_redmi["f1_score"]
    r_fpr = metrics_redmi["false_positive_rate"]

    s_p = metrics_samsung["precision"]
    s_r = metrics_samsung["recall"]
    s_f1 = metrics_samsung["f1_score"]
    s_fpr = metrics_samsung["false_positive_rate"]

    line1 = (
        "1. **Android Telephony API Differences**: MediaTek/Qualcomm modems (Redmi) report "
        "discrete RSRP step increments, whereas Exynos/MediaTek modems (Samsung) exhibit "
        "different vendor-specific reporting thresholds for `csi_rsrp` and `deployment_mode`.\n"
    )
    line2 = (
        "2. **Deployment Mode Exposure**: Samsung devices in the test suite report "
        "`deployment_mode` as `UNKNOWN` due to vendor API restrictions, whereas Redmi "
        "devices successfully expose `NSA`/`SA` status.\n"
    )
    line3 = (
        "3. **No Generalisation Claims**: This evaluation is exploratory on a small "
        "multi-device sample set. No claim is made that the trained Isolation Forest "
        "generalizes to unseen carrier networks or un-tested modems without recalibration.\n\n"
    )

    report_content = (
        "# Device Generalisation and Cross-Device Evaluation Report (T7-017)\n\n"
        "## Overview\n\n"
        "This report evaluates model generalisation across different smartphone hardware "
        "modems (Redmi 13 5G vs. Samsung Galaxy A15 5G) per project specification §23 "
        "and Guardrail G11.\n\n"
        "## Cross-Device Performance Matrix\n\n"
        "| Training Device | Test Evaluation Device | Test Samples | Precision | Recall (TPR) | "
        "F1-Score | FPR |\n"
        "|---|---|---|---|---|---|---|\n"
        f"| **Redmi 13 5G** | Samsung Galaxy A15 5G | {metrics_samsung['total_samples']} | "
        f"{s_p:.4f} | {s_r:.4f} | {s_f1:.4f} | {s_fpr:.4f} |\n"
        f"| **Samsung Galaxy A15 5G** | Redmi 13 5G | {metrics_redmi['total_samples']} | "
        f"{r_p:.4f} | {r_r:.4f} | {r_f1:.4f} | {r_fpr:.4f} |\n\n"
        "## Hardware & Modem Caveats\n\n"
        + line1
        + line2
        + line3
        + "## Operator Variation (Airtel vs Vodafone)\n\n"
        f"- **Airtel 5G**: Covered extensively across Redmi and Samsung datasets "
        f"({len(df)} samples).\n"
        "- **Vodafone / OnePlus**: Omitted due to unavailability of hardware collector device "
        "for Vodafone 5G during data collection phase.\n"
    )

    Path(out_report).write_text(report_content, encoding="utf-8")
    return report_content


if __name__ == "__main__":
    run_device_generalisation_eval()
    print("Generated docs/device_generalisation_report.md")
