# G30: Frontend No-Logic Guardrail Guidelines

## Principle
The frontend (React + TypeScript dashboard) is strictly a **presentation and exploration layer**.
All ML scoring, baseline statistical calculations, cell transition detections, event grouping, anomaly classification, and diagnostic reasoning are performed exclusively by the backend streaming/batch engine and Python orchestrator.

The frontend **must never recompute or synthesize domain logic**.

---

## Allowed Operations
Frontend components and hooks are permitted to perform presentation-only operations:
1. **Data Loading & Subscription**: Ingesting static demo bundles (Contract C11), consuming WebSocket live telemetry events (Contract C8), or querying REST API endpoints.
2. **Filtering**: Filtering samples or events by device, operator, timestamp range, anomaly type, or severity (using server-provided classifications).
3. **Sorting**: Ordering items by time, sequence number, sample index, or severity priority for display.
4. **Formatting**: Converting ISO timestamps to local time display, adding unit suffixes (e.g., `dBm`, `dB`, `ms`), rounding floats for readability.
5. **Plotting & Visualization**: Passing server-computed metrics and pre-computed transition markers to uPlot, canvas, or SVG charts.
6. **UI State Management**: Controlling theme (light/dark), active routes, selected event modal, virtual scroll offsets, and connection state indicators.

---

## Forbidden Computations (Denylist)
Frontend code must **never** implement or invoke:
1. **Anomaly & ML Scoring**:
   - Isolation Forest algorithms or heuristic threshold comparisons.
   - Calling or simulating `decision_function`, `predict_proba`, or `if_score` calculations.
2. **Baseline & Statistical Scoring**:
   - Computing rolling means, rolling standard deviations, or z-scores (`baseline_z_*`).
   - Calculating signal quality deviation thresholds.
3. **Transition & Handover Detection**:
   - Comparing consecutive samples to detect PCI, NCI, or ARFCN changes (`detectTransitions`, `detectHandover`).
   - All transitions must be consumed directly from the `transitions` payload emitted by the backend.
4. **Event Grouping & Classification**:
   - Grouping contiguous anomalous samples into open/closed events.
   - Determining event start/end indices or applying gap-closure rules (`EVENT_CLOSE_GAP_SAMPLES`).
   - Classifying `anomaly_type` or computing `max_severity`.
5. **Diagnostic Inference & Recommendations**:
   - Synthesizing root-cause diagnoses or generating rule-based recommendations.
   - All diagnoses must come from the server/bundle `diagnosis` and `recommendation` fields.

---

## Automated Verification
Rule G30 is automatically enforced by:
- Python test suite: `tests/test_no_logic_lint.py`
- Frontend test suite: `frontend/src/no_logic.test.ts`
CI fails if any forbidden identifier or computational pattern is introduced into `frontend/src/`.
