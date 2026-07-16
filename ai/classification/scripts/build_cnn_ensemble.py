from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


MODEL_NAMES = [
    "vgg11",
    "vgg16",
    "googlenet",
    "resnet18",
]


def load_macro_f1(path: Path) -> float:
    if not path.exists():
        raise FileNotFoundError(
            f"Metrics tidak ditemukan: {path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    return float(
        data["metrics"]["macro_f1"]
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--vgg11-checkpoint",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--vgg16-checkpoint",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--googlenet-checkpoint",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--resnet18-checkpoint",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--metrics-root",
        type=Path,
        default=Path(
            "ai/classification/reports/ensemble"
        ),
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            "ai/classification/models/ensemble"
        ),
    )

    args = parser.parse_args()

    checkpoints = {
        "vgg11": args.vgg11_checkpoint,
        "vgg16": args.vgg16_checkpoint,
        "googlenet": args.googlenet_checkpoint,
        "resnet18": args.resnet18_checkpoint,
    }

    macro_f1 = {}

    for model_name in MODEL_NAMES:
        checkpoint = checkpoints[model_name]

        if not checkpoint.exists():
            raise FileNotFoundError(
                f"Checkpoint tidak ditemukan: {checkpoint}"
            )

        metrics_path = (
            args.metrics_root
            / f"{model_name}_valid_metrics.json"
        )

        macro_f1[model_name] = load_macro_f1(
            metrics_path
        )

        if macro_f1[model_name] < 0.70:
            raise RuntimeError(
                f"{model_name} Macro F1 terlalu rendah: "
                f"{macro_f1[model_name]:.4f}"
            )

    total_f1 = sum(macro_f1.values())

    weights = {
        model_name: (
            macro_f1[model_name]
            / total_f1
        )
        for model_name in MODEL_NAMES
    }

    args.output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    models_config = {}

    for model_name in MODEL_NAMES:
        destination = (
            args.output_root
            / f"{model_name}.pt"
        )

        shutil.copy2(
            checkpoints[model_name],
            destination,
        )

        models_config[model_name] = {
            "architecture": model_name,
            "checkpoint": str(destination),
            "source_checkpoint": str(
                checkpoints[model_name]
            ),
            "validation_macro_f1": (
                macro_f1[model_name]
            ),
            "weight": weights[model_name],
        }

    config = {
        "ensemble_name": (
            "AI-TDSS Market Regime CNN Ensemble"
        ),
        "method": "weighted_soft_voting",
        "weight_source": (
            "validation_macro_f1"
        ),
        "classes": [
            "bearish",
            "bullish",
            "sideways",
        ],
        "class_to_idx": {
            "bearish": 0,
            "bullish": 1,
            "sideways": 2,
        },
        "image_size": 224,
        "normalization": {
            "mean": [
                0.485,
                0.456,
                0.406,
            ],
            "std": [
                0.229,
                0.224,
                0.225,
            ],
        },
        "models": models_config,
    }

    config_path = (
        args.output_root
        / "ensemble_config.json"
    )

    config_path.write_text(
        json.dumps(
            config,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print("CNN ensemble berhasil dibangun")
    print("")

    for model_name in MODEL_NAMES:
        print(
            f"{model_name:10s} | "
            f"Macro F1={macro_f1[model_name]:.4f} | "
            f"Weight={weights[model_name]:.4f}"
        )

    print("")
    print(
        f"Total weight : "
        f"{sum(weights.values()):.6f}"
    )
    print(
        f"Config       : {config_path}"
    )


if __name__ == "__main__":
    main()
