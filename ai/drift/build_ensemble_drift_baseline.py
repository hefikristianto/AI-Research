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


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/drift/baselines/"
            "cnn_ensemble_baseline.json"
        ),
    )

    args = parser.parse_args()

    dataframe = pd.read_csv(
        args.predictions
    )

    required_columns = {
        "ensemble_predicted_label",
        "ensemble_confidence",
        "ensemble_entropy",
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

    class_distribution = (
        dataframe[
            "ensemble_predicted_label"
        ]
        .value_counts(normalize=True)
        .reindex(
            CLASSES,
            fill_value=0.0,
        )
    )

    confidence = pd.to_numeric(
        dataframe[
            "ensemble_confidence"
        ],
        errors="coerce",
    ).dropna()

    entropy = pd.to_numeric(
        dataframe[
            "ensemble_entropy"
        ],
        errors="coerce",
    ).dropna()

    confidence_bins = np.linspace(
        0.0,
        1.0,
        11,
    )

    confidence_histogram, _ = (
        np.histogram(
            confidence,
            bins=confidence_bins,
        )
    )

    confidence_distribution = (
        confidence_histogram
        / max(
            confidence_histogram.sum(),
            1,
        )
    )

    max_entropy = float(
        np.log(len(CLASSES))
    )

    entropy_bins = np.linspace(
        0.0,
        max_entropy,
        11,
    )

    entropy_histogram, _ = (
        np.histogram(
            entropy,
            bins=entropy_bins,
        )
    )

    entropy_distribution = (
        entropy_histogram
        / max(
            entropy_histogram.sum(),
            1,
        )
    )

    baseline = {
        "source": str(
            args.predictions
        ),
        "sample_count": int(
            len(dataframe)
        ),
        "classes": CLASSES,
        "class_distribution": {
            class_name: float(
                class_distribution[
                    class_name
                ]
            )
            for class_name in CLASSES
        },
        "confidence": {
            "mean": float(
                confidence.mean()
            ),
            "std": float(
                confidence.std()
            ),
            "minimum": float(
                confidence.min()
            ),
            "maximum": float(
                confidence.max()
            ),
            "bins": (
                confidence_bins.tolist()
            ),
            "distribution": (
                confidence_distribution.tolist()
            ),
        },
        "entropy": {
            "mean": float(
                entropy.mean()
            ),
            "std": float(
                entropy.std()
            ),
            "minimum": float(
                entropy.min()
            ),
            "maximum": float(
                entropy.max()
            ),
            "bins": (
                entropy_bins.tolist()
            ),
            "distribution": (
                entropy_distribution.tolist()
            ),
        },
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            baseline,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print("Drift baseline ensemble selesai")
    print(
        f"Samples          : "
        f"{baseline['sample_count']}"
    )
    print(
        f"Confidence mean  : "
        f"{baseline['confidence']['mean']:.4f}"
    )
    print(
        f"Entropy mean     : "
        f"{baseline['entropy']['mean']:.4f}"
    )
    print("")
    print("Class distribution:")

    for class_name in CLASSES:
        print(
            f"{class_name:8s}: "
            f"{baseline['class_distribution'][class_name]:.4f}"
        )

    print("")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
