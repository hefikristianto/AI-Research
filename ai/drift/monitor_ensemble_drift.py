from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


CLASSES = [
    "bearish",
    "bullish",
    "sideways",
]


def calculate_psi(
    expected: np.ndarray,
    actual: np.ndarray,
) -> float:
    epsilon = 1e-6

    expected = np.clip(
        expected,
        epsilon,
        None,
    )

    actual = np.clip(
        actual,
        epsilon,
        None,
    )

    return float(
        np.sum(
            (actual - expected)
            * np.log(actual / expected)
        )
    )


def normalize_histogram(
    values: pd.Series,
    bins: np.ndarray,
) -> np.ndarray:
    histogram, _ = np.histogram(
        values,
        bins=bins,
    )

    return (
        histogram
        / max(histogram.sum(), 1)
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(
            "ai/drift/baselines/"
            "cnn_ensemble_baseline.json"
        ),
    )

    parser.add_argument(
        "--current",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/drift/reports/"
            "cnn_ensemble_drift_report.json"
        ),
    )

    args = parser.parse_args()

    if not args.baseline.exists():
        raise FileNotFoundError(
            f"Baseline tidak ditemukan: "
            f"{args.baseline}"
        )

    if not args.current.exists():
        raise FileNotFoundError(
            f"Prediction tidak ditemukan: "
            f"{args.current}"
        )

    baseline = json.loads(
        args.baseline.read_text(
            encoding="utf-8"
        )
    )

    dataframe = pd.read_csv(
        args.current
    )

    label_column = (
        "ensemble_predicted_label"
        if "ensemble_predicted_label"
        in dataframe.columns
        else "cnn_label"
    )

    confidence_column = (
        "ensemble_confidence"
        if "ensemble_confidence"
        in dataframe.columns
        else "cnn_confidence"
    )

    entropy_column = (
        "ensemble_entropy"
        if "ensemble_entropy"
        in dataframe.columns
        else "cnn_entropy"
    )

    required_columns = {
        label_column,
        confidence_column,
        entropy_column,
    }

    missing_columns = (
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Kolom kurang: "
            f"{sorted(missing_columns)}"
        )

    current_class_distribution = (
        dataframe[label_column]
        .value_counts(normalize=True)
        .reindex(
            CLASSES,
            fill_value=0.0,
        )
    )

    baseline_class_distribution = np.asarray(
        [
            baseline[
                "class_distribution"
            ][class_name]
            for class_name in CLASSES
        ],
        dtype=float,
    )

    current_class_array = (
        current_class_distribution
        .to_numpy(dtype=float)
    )

    class_distribution_distance = float(
        0.5
        * np.abs(
            current_class_array
            - baseline_class_distribution
        ).sum()
    )

    confidence = pd.to_numeric(
        dataframe[confidence_column],
        errors="coerce",
    ).dropna()

    entropy = pd.to_numeric(
        dataframe[entropy_column],
        errors="coerce",
    ).dropna()

    confidence_bins = np.asarray(
        baseline["confidence"]["bins"],
        dtype=float,
    )

    entropy_bins = np.asarray(
        baseline["entropy"]["bins"],
        dtype=float,
    )

    current_confidence_distribution = (
        normalize_histogram(
            confidence,
            confidence_bins,
        )
    )

    current_entropy_distribution = (
        normalize_histogram(
            entropy,
            entropy_bins,
        )
    )

    baseline_confidence_distribution = (
        np.asarray(
            baseline["confidence"][
                "distribution"
            ],
            dtype=float,
        )
    )

    baseline_entropy_distribution = (
        np.asarray(
            baseline["entropy"][
                "distribution"
            ],
            dtype=float,
        )
    )

    confidence_psi = calculate_psi(
        baseline_confidence_distribution,
        current_confidence_distribution,
    )

    entropy_psi = calculate_psi(
        baseline_entropy_distribution,
        current_entropy_distribution,
    )

    class_component = min(
        class_distribution_distance
        / 0.30,
        1.0,
    )

    confidence_component = min(
        confidence_psi / 0.25,
        1.0,
    )

    entropy_component = min(
        entropy_psi / 0.25,
        1.0,
    )

    drift_score = float(
        0.40 * class_component
        + 0.35 * confidence_component
        + 0.25 * entropy_component
    )

    if drift_score >= 0.60:
        status = "DRIFT"
        recommendation = (
            "RETRAIN_REQUIRED"
        )

    elif drift_score >= 0.30:
        status = "WARNING"
        recommendation = (
            "REVIEW_AND_MONITOR"
        )

    else:
        status = "STABLE"
        recommendation = (
            "NO_ACTION"
        )

    report = {
        "status": status,
        "recommendation": recommendation,
        "drift_score": drift_score,
        "sample_count": int(
            len(dataframe)
        ),
        "class_distribution_distance": (
            class_distribution_distance
        ),
        "confidence_psi": confidence_psi,
        "entropy_psi": entropy_psi,
        "baseline_class_distribution": {
            class_name: float(
                baseline_class_distribution[
                    index
                ]
            )
            for index, class_name
            in enumerate(CLASSES)
        },
        "current_class_distribution": {
            class_name: float(
                current_class_array[index]
            )
            for index, class_name
            in enumerate(CLASSES)
        },
        "baseline_confidence_mean": float(
            baseline["confidence"]["mean"]
        ),
        "current_confidence_mean": float(
            confidence.mean()
        ),
        "baseline_entropy_mean": float(
            baseline["entropy"]["mean"]
        ),
        "current_entropy_mean": float(
            entropy.mean()
        ),
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print("CNN Ensemble Drift Monitor")
    print(f"Status         : {status}")
    print(
        f"Drift score    : "
        f"{drift_score:.4f}"
    )
    print(
        f"Class distance : "
        f"{class_distribution_distance:.4f}"
    )
    print(
        f"Confidence PSI : "
        f"{confidence_psi:.4f}"
    )
    print(
        f"Entropy PSI    : "
        f"{entropy_psi:.4f}"
    )
    print(
        f"Recommendation : "
        f"{recommendation}"
    )
    print(f"Output         : {args.output}")


if __name__ == "__main__":
    main()
