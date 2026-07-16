from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

CLASS_NAMES = [
    "bearish",
    "bullish",
    "sideways",
]

MODEL_NAMES = [
    "vgg11",
    "vgg16",
    "googlenet",
    "resnet18",
]

PROBABILITY_COLUMNS = [
    "prob_bearish",
    "prob_bullish",
    "prob_sideways",
]


def load_prediction(
    path: Path,
    model_name: str,
) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Prediction tidak ditemukan: {path}"
        )

    dataframe = pd.read_csv(path)

    required_columns = {
        "sample_id",
        "true_index",
        "true_label",
        *PROBABILITY_COLUMNS,
    }

    missing_columns = (
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Kolom kurang pada {path}: "
            f"{sorted(missing_columns)}"
        )

    if dataframe["sample_id"].duplicated().any():
        raise ValueError(
            f"Duplicate sample_id pada {path}"
        )

    selected = dataframe[
        [
            "sample_id",
            "image_path",
            "true_index",
            "true_label",
            *PROBABILITY_COLUMNS,
        ]
    ].copy()

    selected = selected.rename(
        columns={
            column: f"{model_name}_{column}"
            for column in PROBABILITY_COLUMNS
        }
    )

    return selected


def calculate_metrics(
    targets: np.ndarray,
    predictions: np.ndarray,
    confidences: np.ndarray,
    entropies: np.ndarray,
) -> dict:
    labels = list(range(len(CLASS_NAMES)))

    accuracy = accuracy_score(
        targets,
        predictions,
    )

    balanced_accuracy = balanced_accuracy_score(
        targets,
        predictions,
    )

    precision, recall, f1, support = (
        precision_recall_fscore_support(
            targets,
            predictions,
            labels=labels,
            zero_division=0,
        )
    )

    matrix = confusion_matrix(
        targets,
        predictions,
        labels=labels,
    )

    report = classification_report(
        targets,
        predictions,
        labels=labels,
        target_names=CLASS_NAMES,
        zero_division=0,
        output_dict=True,
    )

    per_class = {}

    for index, class_name in enumerate(
        CLASS_NAMES
    ):
        per_class[class_name] = {
            "precision": float(
                precision[index]
            ),
            "recall": float(
                recall[index]
            ),
            "f1": float(
                f1[index]
            ),
            "support": int(
                support[index]
            ),
        }

    return {
        "accuracy": float(accuracy),
        "balanced_accuracy": float(
            balanced_accuracy
        ),
        "macro_precision": float(
            np.mean(precision)
        ),
        "macro_recall": float(
            np.mean(recall)
        ),
        "macro_f1": float(
            np.mean(f1)
        ),
        "average_confidence": float(
            confidences.mean()
        ),
        "average_entropy": float(
            entropies.mean()
        ),
        "per_class": per_class,
        "confusion_matrix": (
            matrix.tolist()
        ),
        "classification_report": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "ai/classification/models/"
            "ensemble/ensemble_config.json"
        ),
    )

    parser.add_argument(
        "--vgg11",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--vgg16",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--googlenet",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--resnet18",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--predictions-output",
        type=Path,
        default=Path(
            "ai/classification/reports/"
            "ensemble/"
            "ensemble_test_predictions.csv"
        ),
    )

    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path(
            "ai/classification/reports/"
            "ensemble/"
            "ensemble_test_metrics.json"
        ),
    )

    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path(
            "ai/classification/reports/"
            "FINAL_CNN_ENSEMBLE_RESULT.md"
        ),
    )

    args = parser.parse_args()

    if not args.config.exists():
        raise FileNotFoundError(
            f"Config tidak ditemukan: "
            f"{args.config}"
        )

    config = json.loads(
        args.config.read_text(
            encoding="utf-8"
        )
    )

    prediction_paths = {
        "vgg11": args.vgg11,
        "vgg16": args.vgg16,
        "googlenet": args.googlenet,
        "resnet18": args.resnet18,
    }

    merged = None

    for model_name in MODEL_NAMES:
        dataframe = load_prediction(
            prediction_paths[model_name],
            model_name,
        )

        if merged is None:
            merged = dataframe
        else:
            merged = merged.merge(
                dataframe.drop(
                    columns=[
                        "image_path",
                        "true_index",
                        "true_label",
                    ]
                ),
                on="sample_id",
                how="inner",
                validate="one_to_one",
            )

    if merged is None or merged.empty:
        raise RuntimeError(
            "Tidak ada data yang berhasil digabung."
        )

    expected_samples = len(
        pd.read_csv(args.vgg11)
    )

    if len(merged) != expected_samples:
        raise RuntimeError(
            f"Jumlah sample ensemble tidak cocok. "
            f"Expected={expected_samples}, "
            f"merged={len(merged)}"
        )

    ensemble_probabilities = np.zeros(
        (
            len(merged),
            len(CLASS_NAMES),
        ),
        dtype=np.float64,
    )

    weights = {}

    for model_name in MODEL_NAMES:
        weight = float(
            config["models"][
                model_name
            ]["weight"]
        )

        weights[model_name] = weight

        model_probabilities = merged[
            [
                f"{model_name}_prob_bearish",
                f"{model_name}_prob_bullish",
                f"{model_name}_prob_sideways",
            ]
        ].to_numpy(
            dtype=np.float64
        )

        ensemble_probabilities += (
            weight
            * model_probabilities
        )

    total_weight = sum(
        weights.values()
    )

    if not np.isclose(
        total_weight,
        1.0,
        atol=1e-6,
    ):
        raise RuntimeError(
            f"Total bobot bukan 1.0: "
            f"{total_weight}"
        )

    probability_sum = (
        ensemble_probabilities.sum(
            axis=1,
            keepdims=True,
        )
    )

    ensemble_probabilities = (
        ensemble_probabilities
        / np.clip(
            probability_sum,
            1e-12,
            None,
        )
    )

    predictions = (
        ensemble_probabilities.argmax(
            axis=1
        )
    )

    confidences = (
        ensemble_probabilities.max(
            axis=1
        )
    )

    entropies = -np.sum(
        ensemble_probabilities
        * np.log(
            np.clip(
                ensemble_probabilities,
                1e-12,
                1.0,
            )
        ),
        axis=1,
    )

    targets = merged[
        "true_index"
    ].to_numpy(
        dtype=int
    )

    merged[
        "ensemble_predicted_index"
    ] = predictions

    merged[
        "ensemble_predicted_label"
    ] = [
        CLASS_NAMES[index]
        for index in predictions
    ]

    merged[
        "ensemble_confidence"
    ] = confidences

    merged[
        "ensemble_entropy"
    ] = entropies

    merged[
        "ensemble_prob_bearish"
    ] = ensemble_probabilities[:, 0]

    merged[
        "ensemble_prob_bullish"
    ] = ensemble_probabilities[:, 1]

    merged[
        "ensemble_prob_sideways"
    ] = ensemble_probabilities[:, 2]

    metrics = calculate_metrics(
        targets=targets,
        predictions=predictions,
        confidences=confidences,
        entropies=entropies,
    )

    args.predictions_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.metrics_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.report_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    merged.to_csv(
        args.predictions_output,
        index=False,
    )

    result = {
        "method": config["method"],
        "weight_source": config[
            "weight_source"
        ],
        "weights": weights,
        "sample_count": int(
            len(merged)
        ),
        "metrics": metrics,
    }

    args.metrics_output.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Final CNN Ensemble Result",
        "",
        "## Method",
        "",
        "Weighted soft voting based on validation Macro F1.",
        "",
        "## Ensemble Weights",
        "",
        "| Model | Weight |",
        "|---|---:|",
    ]

    for model_name in MODEL_NAMES:
        lines.append(
            f"| {model_name} | "
            f"{weights[model_name]:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Test 2025 Result",
            "",
            "| Metric | Value |",
            "|---|---:|",
            (
                f"| Accuracy | "
                f"{metrics['accuracy']:.4f} |"
            ),
            (
                f"| Balanced Accuracy | "
                f"{metrics['balanced_accuracy']:.4f} |"
            ),
            (
                f"| Macro Precision | "
                f"{metrics['macro_precision']:.4f} |"
            ),
            (
                f"| Macro Recall | "
                f"{metrics['macro_recall']:.4f} |"
            ),
            (
                f"| Macro F1 | "
                f"{metrics['macro_f1']:.4f} |"
            ),
            (
                f"| Average Confidence | "
                f"{metrics['average_confidence']:.4f} |"
            ),
            (
                f"| Average Entropy | "
                f"{metrics['average_entropy']:.4f} |"
            ),
            "",
            "## Per-Class Metrics",
            "",
            "| Class | Precision | Recall | F1 | Support |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for class_name in CLASS_NAMES:
        class_metrics = (
            metrics["per_class"][
                class_name
            ]
        )

        lines.append(
            f"| {class_name} | "
            f"{class_metrics['precision']:.4f} | "
            f"{class_metrics['recall']:.4f} | "
            f"{class_metrics['f1']:.4f} | "
            f"{class_metrics['support']} |"
        )

    lines.extend(
        [
            "",
            "## Confusion Matrix",
            "",
            "Class order: bearish, bullish, sideways",
            "",
            "```text",
            str(
                np.asarray(
                    metrics[
                        "confusion_matrix"
                    ]
                )
            ),
            "```",
            "",
            "## Final Decision",
            "",
            "The weighted four-model CNN ensemble is used as the primary market-regime classifier.",
        ]
    )

    args.report_output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("")
    print("Evaluasi CNN Ensemble selesai")
    print(
        f"Samples           : "
        f"{len(merged)}"
    )
    print(
        f"Accuracy          : "
        f"{metrics['accuracy']:.4f}"
    )
    print(
        f"Balanced accuracy : "
        f"{metrics['balanced_accuracy']:.4f}"
    )
    print(
        f"Macro F1          : "
        f"{metrics['macro_f1']:.4f}"
    )
    print(
        f"Confidence        : "
        f"{metrics['average_confidence']:.4f}"
    )
    print("")
    print("Confusion matrix:")
    print(
        np.asarray(
            metrics["confusion_matrix"]
        )
    )
    print("")
    print(
        f"Predictions : "
        f"{args.predictions_output}"
    )
    print(
        f"Metrics     : "
        f"{args.metrics_output}"
    )
    print(
        f"Report      : "
        f"{args.report_output}"
    )


if __name__ == "__main__":
    main()
