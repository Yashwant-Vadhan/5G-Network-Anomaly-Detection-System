"""Script for T9-004: Evaluate Local Outlier Factor (LOF) and One-Class SVM.

Trains LOF (novelty=True) and OneClassSVM on the same engineered features
(features.csv), evaluates on ground truth (labels_final.csv), and compares
metrics against Baseline z-score and Isolation Forest.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from ml.config import FEATURE_COLUMNS
from ml.evaluate import compute_detection_latency, compute_metrics, print_evaluation_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_extra_model_evaluation(
    scores_path: str | Path = "data/processed/scores.csv",
    labels_path: str | Path = "data/eval/labels_final.csv",
) -> dict[str, dict]:
    """Train LOF and One-Class SVM on features and evaluate against ground truth labels."""
    scores_df = pd.read_csv(scores_path)
    labels_df = pd.read_csv(labels_path)

    # Filter model eligible rows
    train_mask = scores_df["model_eligible"].fillna(False)
    train_df = scores_df[train_mask].copy()

    # Extract feature matrix X
    X_train = train_df[FEATURE_COLUMNS].fillna(0.0).values
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    # 1. Train One-Class SVM
    logger.info("Training One-Class SVM...")
    oc_svm = OneClassSVM(kernel="rbf", gamma="scale", nu=0.05)
    oc_svm.fit(X_train_scaled)

    # Predict on entire scores_df
    X_all = scores_df[FEATURE_COLUMNS].fillna(0.0).values
    X_all_scaled = scaler.transform(X_all)
    oc_svm_preds = oc_svm.predict(X_all_scaled)
    # sklearn OneClassSVM returns -1 for outlier/anomaly, +1 for inlier/normal
    scores_df["oc_svm_flag"] = (oc_svm_preds == -1) & scores_df["model_eligible"].fillna(False)

    # 2. Train Local Outlier Factor (LOF)
    logger.info("Training Local Outlier Factor (novelty=True)...")
    lof = LocalOutlierFactor(n_neighbors=20, novelty=True, contamination=0.05)
    lof.fit(X_train_scaled)
    lof_preds = lof.predict(X_all_scaled)
    scores_df["lof_flag"] = (lof_preds == -1) & scores_df["model_eligible"].fillna(False)

    # Evaluation alignment
    scores_df["eval_session"] = scores_df["source_file"].str.replace(".csv", "", regex=False)
    target_sessions = labels_df["session_id"].unique()
    eval_scores = scores_df[
        scores_df["eval_session"].isin(target_sessions)
        | scores_df["session_id"].isin(target_sessions)
    ].copy()

    y_true = np.zeros(len(eval_scores), dtype=bool)
    for _, row in labels_df.iterrows():
        sess_name = row["session_id"]
        start_idx = int(row["start_idx"])
        end_idx = int(row["end_idx"])

        sess_mask = (eval_scores["eval_session"] == sess_name) | (eval_scores["session_id"] == sess_name)
        sess_indices = eval_scores[sess_mask].index

        for idx in range(start_idx, end_idx + 1):
            if idx < len(sess_indices):
                target_df_idx = sess_indices[idx]
                eval_scores.loc[target_df_idx, "ground_truth"] = True

    y_true = eval_scores["ground_truth"].fillna(False).values

    # Compute metrics for baseline, IF, OC-SVM, LOF
    results = {}
    for name, flag_col in [
        ("Baseline Z-Score", "baseline_flag"),
        ("Isolation Forest", "if_flag"),
        ("One-Class SVM", "oc_svm_flag"),
        ("Local Outlier Factor", "lof_flag"),
    ]:
        y_pred = eval_scores[flag_col].fillna(False).values
        metrics = compute_metrics(y_true, y_pred)
        latency = compute_detection_latency(labels_df, eval_scores, flag_col=flag_col)
        print_evaluation_report(name, metrics, latency)
        results[name] = {"metrics": metrics, "latency": latency}

    return results


if __name__ == "__main__":
    run_extra_model_evaluation()
