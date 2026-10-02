# Device Generalisation and Cross-Device Evaluation Report (T7-017)

## Overview

This report evaluates model generalisation across different smartphone hardware modems (Xiaomi Redmi 13 5G vs. Samsung Galaxy A15 5G) per project specification §23 and Guardrail G11.

## Cross-Device Performance Matrix

| Training Device | Test Evaluation Device | Test Samples | Precision | Recall (TPR) | F1-Score | FPR |
|---|---|---|---|---|---|---|
| **Redmi 13 5G** | Samsung Galaxy A15 5G | 1772 | 0.4628 | 0.7576 | 0.5746 | 0.5596 |
| **Samsung Galaxy A15 5G** | Redmi 13 5G | 3756 | 0.2217 | 0.9427 | 0.3589 | 0.8507 |

## Hardware & Modem Caveats

1. **Android Telephony API Differences**: MediaTek/Qualcomm modems (Redmi) report discrete RSRP step increments, whereas Exynos/MediaTek modems (Samsung) exhibit different vendor-specific reporting thresholds for `csi_rsrp` and `deployment_mode`.
2. **Deployment Mode Exposure**: Samsung devices in the test suite report `deployment_mode` as `UNKNOWN` due to vendor API restrictions, whereas Redmi devices successfully expose `NSA`/`SA` status.
3. **No Generalisation Claims**: This evaluation is exploratory on a small multi-device sample set. No claim is made that the trained Isolation Forest generalizes to unseen carrier networks or un-tested modems without recalibration.

## Operator Variation (Airtel vs Vodafone)

- **Airtel 5G**: Covered extensively across Redmi and Samsung datasets (5528 samples).
- **Vodafone / OnePlus**: Omitted due to unavailability of hardware collector device for Vodafone 5G during data collection phase.
