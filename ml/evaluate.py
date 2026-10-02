"""Evaluation module for 5G-NADS anomaly detection models (T7-015).

Computes sample-level and event-level precision, recall, F1, false-positive rate (FPR),
detection rate, and detection latency between ground-truth labels and model flags.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_metrics(
    y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series
) -> dict[str, float | int]:
    """Compute sample-level classification metrics safely with zero-division protection.

    Args:
        y_true: Ground truth binary boolean array/series.
        y_pred: Predicted binary boolean array/series.

    Returns:
        Dictionary containing counts, TP, FP, TN, FN, precision, recall, F1, and FPR.
    """
    yt = np.asarray(y_true, dtype=bool)
    yp = np.asarray(y_pred, dtype=bool)

    tp = int(np.sum(yt & yp))
    fp = int(np.sum((~yt) & yp))
    tn = int(np.sum((~yt) & (~yp)))
    fn = int(np.sum(yt & (~yp)))

    total = len(yt)
    positives = tp + fn
    negatives = tn + fp

    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    return {
        "total_samples": total,
        "actual_positives": positives,
        "actual_negatives": negatives,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "false_positive_rate": fpr,
    }


def compute_detection_latency(
    events_df: pd.DataFrame, scores_df: pd.DataFrame, flag_col: str = "if_flag"
) -> dict[str, Any]:
    """Compute detection latency (samples from event start to first model flag).

    Args:
        events_df: Ground truth events DataFrame containing start_idx and end_idx.
        scores_df: Scored measurements DataFrame containing flag_col.
        flag_col: Model flag column name to evaluate.

    Returns:
        Dictionary containing detected_events, mean_latency_samples, and per-event latencies.
    """
    latencies: list[int] = []
    detected_count = 0

    for _, row in events_df.iterrows():
        start_idx = int(row["start_idx"])
        end_idx = int(row["end_idx"])

        # Slice scores DataFrame window
        window_flags = scores_df.iloc[start_idx : end_idx + 1][flag_col]
        flagged_indices = window_flags[window_flags == True].index  # noqa: E712

        if len(flagged_indices) > 0:
            first_flag_idx = int(flagged_indices[0])
            latency = max(0, first_flag_idx - start_idx)
            latencies.append(latency)
            detected_count += 1

    mean_latency = float(np.mean(latencies)) if latencies else 0.0

    return {
        "total_events": len(events_df),
        "detected_events": detected_count,
        "detection_rate": float(detected_count / len(events_df)) if len(events_df) > 0 else 0.0,
        "mean_latency_samples": mean_latency,
        "event_latencies": latencies,
    }


def print_evaluation_report(
    name: str, metrics: dict[str, float | int], latency_info: dict[str, Any] | None = None
) -> None:
    """Print clean evaluation report with counts alongside every metric."""
    print(f"\n==================== Evaluation Report: {name} ====================")
    print(f"Total Samples          : {metrics['total_samples']}")
    print(f"Actual Positives       : {metrics['actual_positives']}")
    print(f"Actual Negatives       : {metrics['actual_negatives']}")
    print(f"True Positives (TP)    : {metrics['true_positives']}")
    print(f"False Positives (FP)   : {metrics['false_positives']}")
    print(f"True Negatives (TN)    : {metrics['true_negatives']}")
    print(f"False Negatives (FN)   : {metrics['false_negatives']}")
    print(f"Precision              : {metrics['precision']:.4f}")
    print(f"Recall (TPR)           : {metrics['recall']:.4f}")
    print(f"F1 Score               : {metrics['f1_score']:.4f}")
    print(f"False Positive Rate    : {metrics['false_positive_rate']:.4f}")

    if latency_info:
        print("\n--- Event Detection & Latency ---")
        print(f"Total Events           : {latency_info['total_events']}")
        print(f"Detected Events        : {latency_info['detected_events']}")
        print(f"Event Detection Rate   : {latency_info['detection_rate']:.4f}")
        print(f"Mean Latency (samples) : {latency_info['mean_latency_samples']:.2f}")
    print("===================================================================\n")


def evaluate_model_on_labels(
    scores_path: str | Path = "data/processed/scores.csv",
    labels_path: str | Path = "data/eval/labels_final.csv",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Evaluate baseline and Isolation Forest flags on labeled ground truth intervals.

    Returns:
        Tuple of (baseline_results_dict, if_results_dict).
    """
    scores_df = pd.read_csv(scores_path)
    labels_df = pd.read_csv(labels_path)

    # Normalize session matching (source_file vs session_id)
    scores_df["eval_session"] = scores_df["source_file"].str.replace(".csv", "", regex=False)

    target_sessions = labels_df["session_id"].unique()
    eval_scores = scores_df[
        scores_df["eval_session"].isin(target_sessions)
        | scores_df["session_id"].isin(target_sessions)
    ].copy()

    # Build ground-truth vector initialized to False
    eval_scores["y_true"] = False
    anom_events_list: list[dict[str, Any]] = []

    for _, row in labels_df.iterrows():
        sess_id = str(row["session_id"])
        start_idx = int(row["start_idx"])
        end_idx = int(row["end_idx"])
        lbl = str(row["label"])

        sess_mask = (eval_scores["eval_session"] == sess_id) | (
            eval_scores["session_id"] == sess_id
        )

        if lbl != "NORMAL_EVENT":
            mask = sess_mask & (eval_scores["sample_idx"].between(start_idx, end_idx))
            eval_scores.loc[mask, "y_true"] = True
            anom_events_list.append(
                {"session_id": sess_id, "start_idx": start_idx, "end_idx": end_idx, "label": lbl}
            )

    y_true = eval_scores["y_true"].to_numpy(dtype=bool)
    baseline_pred = eval_scores["baseline_flag"].fillna(False).to_numpy(dtype=bool)
    if_pred = eval_scores["if_flag"].fillna(False).to_numpy(dtype=bool)

    baseline_metrics = compute_metrics(y_true, baseline_pred)
    if_metrics = compute_metrics(y_true, if_pred)

    gt_events_df = pd.DataFrame(anom_events_list)
    baseline_lat = compute_detection_latency(gt_events_df, eval_scores, "baseline_flag")
    if_lat = compute_detection_latency(gt_events_df, eval_scores, "if_flag")

    return (
        {"metrics": baseline_metrics, "latency": baseline_lat},
        {"metrics": if_metrics, "latency": if_lat},
    )


def main() -> None:
    """CLI entrypoint for ml.evaluate module."""
    parser = argparse.ArgumentParser(description="5G-NADS Anomaly Detection Model Evaluator")
    parser.add_argument(
        "--labels", default="data/eval/labels_final.csv", help="Path to ground truth labels"
    )
    parser.add_argument(
        "--scores", default="data/processed/scores.csv", help="Path to model scores CSV"
    )
    args = parser.parse_args()

    print(f"Evaluating {args.scores} against {args.labels}...")
    baseline_res, if_res = evaluate_model_on_labels(args.scores, args.labels)

    print_evaluation_report(
        "Rolling Z-Score Baseline", baseline_res["metrics"], baseline_res["latency"]
    )
    print_evaluation_report("Isolation Forest (IF)", if_res["metrics"], if_res["latency"])


if __name__ == "__main__":
    main()
