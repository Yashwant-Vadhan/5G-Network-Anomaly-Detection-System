# Ground Truth Labelling Notes & Agreement Report (T7-014)

## Summary Metrics

- **Labeller 1 Events**: 13
- **Labeller 2 Events**: 13
- **Mean IoU Overlap Agreement**: 81.22%
- **Estimated Cohen's Kappa**: 0.765
- **Total Consensus Events**: 13

## Consensus Label Distribution

| Event Category Label | Count |
|---|---|
| `NORMAL_EVENT` | 4 |
| `SUDDEN_SIGNAL_DEGRADATION` | 2 |
| `COMBINED_ANOMALY` | 2 |
| `PERSISTENT_POOR_QUALITY` | 2 |
| `SIGNAL_DEGRADATION` | 1 |
| `NETWORK_STATE_TRANSITION` | 1 |
| `CELL_TRANSITION` | 1 |

## Adjudication Methodology

Events were independently annotated by Labeller 1 (Yashwant) and Labeller 2 (Sushil) from raw telemetry plots without model output visibility (Guardrail G12). Disputed window boundaries were merged using start/end range unions, and consensus category labels were assigned based on confidence weighted agreement.
