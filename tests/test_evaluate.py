"""Unit tests for ml/evaluate.py metrics module (T7-015)."""

from __future__ import annotations

import pandas as pd

from ml.evaluate import compute_detection_latency, compute_metrics


def test_compute_metrics_handmade_example():
    """Verify compute_metrics calculates exact expected TP, FP, TN, FN, precision, recall, F1, FPR."""
    # 5 samples: TP=2, FP=1, TN=1, FN=1
    y_true = [True, True, True, False, False]
    y_pred = [True, True, False, True, False]

    m = compute_metrics(y_true, y_pred)

    assert m["total_samples"] == 5
    assert m["actual_positives"] == 3
    assert m["actual_negatives"] == 2
    assert m["true_positives"] == 2
    assert m["false_positives"] == 1
    assert m["true_negatives"] == 1
    assert m["false_negatives"] == 1

    assert m["precision"] == 2 / 3  # 0.6667
    assert m["recall"] == 2 / 3  # 0.6667
    assert m["f1_score"] == 2 / 3  # 0.6667
    assert m["false_positive_rate"] == 0.5


def test_compute_metrics_zero_positives_handled():
    """Verify compute_metrics handles zero positives and zero predictions safely without division by zero."""
    y_true = [False, False, False]
    y_pred = [False, False, False]

    m = compute_metrics(y_true, y_pred)

    assert m["total_samples"] == 3
    assert m["actual_positives"] == 0
    assert m["precision"] == 0.0
    assert m["recall"] == 0.0
    assert m["f1_score"] == 0.0
    assert m["false_positive_rate"] == 0.0


def test_compute_detection_latency():
    """Verify compute_detection_latency calculates latency from event start to first flag."""
    events_df = pd.DataFrame(
        [
            {"event_id": "e1", "start_idx": 2, "end_idx": 5},
            {"event_id": "e2", "start_idx": 8, "end_idx": 10},
        ]
    )
    scores_df = pd.DataFrame(
        {
            "if_flag": [
                False,
                False,
                False,
                True,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
            ]
        }
    )

    lat = compute_detection_latency(events_df, scores_df, flag_col="if_flag")

    assert lat["total_events"] == 2
    assert lat["detected_events"] == 1
    assert lat["detection_rate"] == 0.5
    assert lat["mean_latency_samples"] == 1.0  # idx 3 - idx 2 = 1 sample
