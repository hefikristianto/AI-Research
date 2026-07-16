from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torchvision import transforms
from torchvision.models import (
    googlenet,
    resnet18,
    vgg11,
    vgg16,
)

CLASS_NAMES = [
    "bearish",
    "bullish",
    "sideways",
]


def create_model(
    architecture: str,
) -> nn.Module:
    if architecture == "vgg11":
        model = vgg11(weights=None)

        model.classifier[6] = nn.Linear(
            model.classifier[6].in_features,
            len(CLASS_NAMES),
        )

    elif architecture == "vgg16":
        model = vgg16(weights=None)

        model.classifier[6] = nn.Linear(
            model.classifier[6].in_features,
            len(CLASS_NAMES),
        )

    elif architecture == "googlenet":
        model = googlenet(
            weights=None,
            aux_logits=True,
            transform_input=True,
            init_weights=False,
        )

        model.aux_logits = False
        model.aux1 = None
        model.aux2 = None

        model.fc = nn.Linear(
            model.fc.in_features,
            len(CLASS_NAMES),
        )

    elif architecture == "resnet18":
        model = resnet18(weights=None)

        model.fc = nn.Linear(
            model.fc.in_features,
            len(CLASS_NAMES),
        )

    else:
        raise ValueError(
            f"Arsitektur tidak didukung: {architecture}"
        )

    return model


def create_transform(
    image_size: int,
    mean: list[float],
    std: list[float],
):
    return transforms.Compose(
        [
            transforms.Resize(
                (image_size, image_size)
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=mean,
                std=std,
            ),
        ]
    )


def resolve_checkpoint(
    config_path: Path,
    checkpoint_value: str,
) -> Path:
    checkpoint = Path(checkpoint_value)

    if checkpoint.exists():
        return checkpoint

    relative_to_project = (
        Path.cwd() / checkpoint
    )

    if relative_to_project.exists():
        return relative_to_project

    relative_to_config = (
        config_path.parent / checkpoint.name
    )

    if relative_to_config.exists():
        return relative_to_config

    raise FileNotFoundError(
        f"Checkpoint tidak ditemukan: {checkpoint_value}"
    )


def load_ensemble(
    config_path: Path,
    device: torch.device,
):
    config = json.loads(
        config_path.read_text(
            encoding="utf-8"
        )
    )

    models = {}

    for model_name, model_config in (
        config["models"].items()
    ):
        checkpoint_path = resolve_checkpoint(
            config_path,
            model_config["checkpoint"],
        )

        checkpoint = torch.load(
            checkpoint_path,
            map_location=device,
            weights_only=False,
        )

        architecture = checkpoint[
            "architecture"
        ]

        model = create_model(
            architecture
        )

        model.load_state_dict(
            checkpoint[
                "model_state_dict"
            ]
        )

        model = model.to(device)
        model.eval()

        models[model_name] = {
            "model": model,
            "architecture": architecture,
            "weight": float(
                model_config["weight"]
            ),
        }

    total_weight = sum(
        item["weight"]
        for item in models.values()
    )

    if abs(total_weight - 1.0) > 1e-6:
        raise RuntimeError(
            f"Total bobot ensemble bukan 1: {total_weight}"
        )

    return config, models


def find_images(
    source: Path,
) -> list[Path]:
    if source.is_file():
        return [source]

    extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }

    return sorted(
        path
        for path in source.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower()
            in extensions
        )
    )


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
        "--source",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/classification/reports/"
            "ensemble/"
            "ensemble_inference_predictions.csv"
        ),
    )

    args = parser.parse_args()

    if not args.config.exists():
        raise FileNotFoundError(
            f"Config tidak ditemukan: {args.config}"
        )

    if not args.source.exists():
        raise FileNotFoundError(
            f"Source tidak ditemukan: {args.source}"
        )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    config, models = load_ensemble(
        config_path=args.config,
        device=device,
    )

    transform = create_transform(
        image_size=int(
            config["image_size"]
        ),
        mean=config[
            "normalization"
        ]["mean"],
        std=config[
            "normalization"
        ]["std"],
    )

    image_paths = find_images(
        args.source
    )

    if not image_paths:
        raise RuntimeError(
            f"Tidak ada gambar pada: {args.source}"
        )

    rows = []

    with torch.no_grad():
        for image_path in image_paths:
            with Image.open(
                image_path
            ) as image:
                image = image.convert(
                    "RGB"
                )

                tensor = transform(
                    image
                ).unsqueeze(0).to(
                    device
                )

            ensemble_probability = (
                torch.zeros(
                    len(CLASS_NAMES),
                    dtype=torch.float32,
                    device=device,
                )
            )

            individual = {}

            for model_name, item in (
                models.items()
            ):
                logits = item[
                    "model"
                ](tensor)

                if isinstance(
                    logits,
                    tuple,
                ):
                    logits = logits[0]

                probability = torch.softmax(
                    logits,
                    dim=1,
                )[0]

                ensemble_probability += (
                    item["weight"]
                    * probability
                )

                model_confidence, model_index = (
                    probability.max(dim=0)
                )

                individual[model_name] = {
                    "label": CLASS_NAMES[
                        int(
                            model_index.item()
                        )
                    ],
                    "confidence": float(
                        model_confidence.item()
                    ),
                }

            ensemble_probability = (
                ensemble_probability
                / ensemble_probability.sum()
            )

            confidence, predicted_index = (
                ensemble_probability.max(
                    dim=0
                )
            )

            entropy = -torch.sum(
                ensemble_probability
                * torch.log(
                    ensemble_probability.clamp_min(
                        1e-12
                    )
                )
            )

            row = {
                "sample_id": image_path.stem,
                "image_path": str(
                    image_path
                ),
                "cnn_label": CLASS_NAMES[
                    int(
                        predicted_index.item()
                    )
                ],
                "cnn_confidence": float(
                    confidence.item()
                ),
                "cnn_entropy": float(
                    entropy.item()
                ),
                "prob_bearish": float(
                    ensemble_probability[
                        0
                    ].item()
                ),
                "prob_bullish": float(
                    ensemble_probability[
                        1
                    ].item()
                ),
                "prob_sideways": float(
                    ensemble_probability[
                        2
                    ].item()
                ),
                "vgg11_label": (
                    individual["vgg11"][
                        "label"
                    ]
                ),
                "vgg11_confidence": (
                    individual["vgg11"][
                        "confidence"
                    ]
                ),
                "vgg16_label": (
                    individual["vgg16"][
                        "label"
                    ]
                ),
                "vgg16_confidence": (
                    individual["vgg16"][
                        "confidence"
                    ]
                ),
                "googlenet_label": (
                    individual["googlenet"][
                        "label"
                    ]
                ),
                "googlenet_confidence": (
                    individual["googlenet"][
                        "confidence"
                    ]
                ),
                "resnet18_label": (
                    individual["resnet18"][
                        "label"
                    ]
                ),
                "resnet18_confidence": (
                    individual["resnet18"][
                        "confidence"
                    ]
                ),
                "ensemble_method": (
                    config["method"]
                ),
            }

            rows.append(row)

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)

    print("")
    print("Inference CNN Ensemble selesai")
    print(f"Device      : {device}")
    print(f"Images      : {len(rows)}")
    print(f"Output      : {args.output}")

    if len(rows) == 1:
        print(
            f"Prediction  : "
            f"{rows[0]['cnn_label']}"
        )
        print(
            f"Confidence  : "
            f"{rows[0]['cnn_confidence']:.4f}"
        )
        print(
            f"Bearish     : "
            f"{rows[0]['prob_bearish']:.4f}"
        )
        print(
            f"Bullish     : "
            f"{rows[0]['prob_bullish']:.4f}"
        )
        print(
            f"Sideways    : "
            f"{rows[0]['prob_sideways']:.4f}"
        )


if __name__ == "__main__":
    main()
