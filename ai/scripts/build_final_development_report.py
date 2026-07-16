from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(".")

ENSEMBLE_METRICS = Path(
    "ai/classification/reports/ensemble/"
    "ensemble_test_metrics.json"
)

ENSEMBLE_CONFIG = Path(
    "ai/classification/models/ensemble/"
    "ensemble_config.json"
)

SCORING_V4 = Path(
    "ai/decision/reports/scoring_v4_results.csv"
)

DRIFT_REPORT = Path(
    "ai/drift/reports/"
    "cnn_ensemble_drift_report.json"
)

OUTPUT = Path(
    "AI_TDSS_FINAL_DEVELOPMENT_REPORT.md"
)


def read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"File tidak ditemukan: {path}"
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def main() -> None:
    ensemble_result = read_json(
        ENSEMBLE_METRICS
    )

    ensemble_config = read_json(
        ENSEMBLE_CONFIG
    )

    drift = read_json(
        DRIFT_REPORT
    )

    scoring = pd.read_csv(
        SCORING_V4
    )

    metrics = ensemble_result["metrics"]

    decision_counts = (
        scoring["decision_v4"]
        .value_counts()
        .reindex(
            [
                "ACCEPT",
                "REVIEW",
                "WATCHLIST",
                "REJECT",
            ],
            fill_value=0,
        )
    )

    conflict_count = int(
        scoring[
            "direction_conflict"
        ].astype(str).str.lower()
        .eq("true")
        .sum()
    )

    missing_count = int(
        scoring[
            "cnn_missing"
        ].astype(str).str.lower()
        .eq("true")
        .sum()
    )

    lines = [
        "# AI-TDSS Final Development Report",
        "",
        "## Project",
        "",
        "AI Trading Decision Support System",
        "",
        "Author: Hefi Kristianto",
        "",
        "## Final Architecture",
        "",
        "```text",
        "Chart image and OHLCV",
        "-> YOLO11s OB/FVG detection",
        "-> OB-FVG pairing",
        "-> OHLCV structural validation",
        "-> CNN weighted ensemble",
        "-> scoring v4",
        "-> ACCEPT / REVIEW / WATCHLIST / REJECT",
        "-> drift monitoring",
        "```",
        "",
        "## Detection Model",
        "",
        "- Primary model: YOLO11s",
        "- Training: 50 epochs",
        "- Prediction confidence: 0.25",
        "- Classes: order_block and fair_value_gap",
        "- Test mAP50: 0.590",
        "- Test mAP50-95: 0.452",
        "- Pair direction match rate: 95.83%",
        "",
        "## CNN Ensemble",
        "",
        "- Method: weighted soft voting",
        "- Members: VGG11, VGG16, GoogLeNet, ResNet18",
        "- Weight source: validation Macro F1",
        "",
        "| Model | Validation Macro F1 | Weight |",
        "|---|---:|---:|",
    ]

    for model_name, config in (
        ensemble_config["models"].items()
    ):
        lines.append(
            f"| {model_name} | "
            f"{config['validation_macro_f1']:.4f} | "
            f"{config['weight']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## CNN Ensemble Final Test 2025",
            "",
            "| Metric | Result |",
            "|---|---:|",
            (
                f"| Accuracy | "
                f"{metrics['accuracy']:.4f} |"
            ),
            (
                f"| Balanced accuracy | "
                f"{metrics['balanced_accuracy']:.4f} |"
            ),
            (
                f"| Macro precision | "
                f"{metrics['macro_precision']:.4f} |"
            ),
            (
                f"| Macro recall | "
                f"{metrics['macro_recall']:.4f} |"
            ),
            (
                f"| Macro F1 | "
                f"{metrics['macro_f1']:.4f} |"
            ),
            (
                f"| Average confidence | "
                f"{metrics['average_confidence']:.4f} |"
            ),
            "",
            "## CNN Per-Class Performance",
            "",
            "| Class | Precision | Recall | F1 | Support |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for class_name, result in (
        metrics["per_class"].items()
    ):
        lines.append(
            f"| {class_name} | "
            f"{result['precision']:.4f} | "
            f"{result['recall']:.4f} | "
            f"{result['f1']:.4f} | "
            f"{result['support']} |"
        )

    lines.extend(
        [
            "",
            "## Scoring v4",
            "",
            "- Base scoring v3 weight: 80%",
            "- CNN context weight: 20%",
            (
                "- Average scoring v3: "
                f"{scoring['base_score_v3'].mean():.4f}"
            ),
            (
                "- Average scoring v4: "
                f"{scoring['final_score_v4'].mean():.4f}"
            ),
            (
                "- CNN matched samples: "
                f"{len(scoring) - missing_count}"
            ),
            (
                "- CNN missing samples: "
                f"{missing_count}"
            ),
            (
                "- Direction conflicts: "
                f"{conflict_count}"
            ),
            "",
            "| Decision | Count |",
            "|---|---:|",
        ]
    )

    for decision, count in (
        decision_counts.items()
    ):
        lines.append(
            f"| {decision} | {int(count)} |"
        )

    lines.extend(
        [
            "",
            "## Drift Monitoring",
            "",
            f"- Status: {drift['status']}",
            (
                "- Drift score: "
                f"{drift['drift_score']:.4f}"
            ),
            (
                "- Class distribution distance: "
                f"{drift['class_distribution_distance']:.4f}"
            ),
            (
                "- Confidence PSI: "
                f"{drift['confidence_psi']:.4f}"
            ),
            (
                "- Entropy PSI: "
                f"{drift['entropy_psi']:.4f}"
            ),
            (
                "- Recommendation: "
                f"{drift['recommendation']}"
            ),
            "",
            "## Final Model Files",
            "",
            "- ai/classification/models/ensemble/vgg11.pt",
            "- ai/classification/models/ensemble/vgg16.pt",
            "- ai/classification/models/ensemble/googlenet.pt",
            "- ai/classification/models/ensemble/resnet18.pt",
            "- ai/classification/models/ensemble/ensemble_config.json",
            "",
            "## Final Result Files",
            "",
            "- ai/classification/reports/FINAL_CNN_ENSEMBLE_RESULT.md",
            "- ai/decision/reports/scoring_v4_results.csv",
            "- ai/decision/reports/SCORING_V4_SUMMARY.md",
            "- ai/drift/baselines/cnn_ensemble_baseline.json",
            "- ai/drift/reports/cnn_ensemble_drift_report.json",
            "",
            "## Development Status",
            "",
            "| Stage | Status |",
            "|---|---|",
            "| Dataset preparation | COMPLETE |",
            "| YOLO training and benchmark | COMPLETE |",
            "| Detection model selection | COMPLETE |",
            "| OB-FVG pairing | COMPLETE |",
            "| OHLCV validation | COMPLETE |",
            "| CNN training | COMPLETE |",
            "| CNN ensemble | COMPLETE |",
            "| Final test 2025 | COMPLETE |",
            "| Scoring v4 | COMPLETE |",
            "| Drift monitoring | COMPLETE |",
            "| FastAPI integration | NEXT |",
            "| Frontend integration | NEXT |",
            "| End-to-end system test | NEXT |",
            "",
            "## Next Implementation Stage",
            "",
            "1. Implement reusable Python services for YOLO and CNN ensemble.",
            "2. Add FastAPI analysis endpoint.",
            "3. Connect frontend chart upload to the endpoint.",
            "4. Store analysis history and scoring results.",
            "5. Display drift status on the dashboard.",
            "6. Run black-box and end-to-end testing.",
            "",
            "## Final Research Conclusion",
            "",
            (
                "The four-model weighted CNN ensemble outperformed "
                "all individual CNN models on the unseen 2025 test set. "
                "The ensemble reached accuracy 0.8607, balanced accuracy "
                "0.8746, and Macro F1 0.8427. Integration with YOLO11s, "
                "OHLCV structural validation, and scoring v4 produced a "
                "complete decision-support pipeline capable of filtering "
                "detected setups according to market-regime alignment."
            ),
        ]
    )

    OUTPUT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(
        f"Final report dibuat: {OUTPUT}"
    )


if __name__ == "__main__":
    main()
