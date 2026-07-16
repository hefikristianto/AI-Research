from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
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

EXPECTED_CLASS_TO_IDX = {
    "bearish": 0,
    "bullish": 1,
    "sideways": 2,
}


class ImageFolderWithPath(datasets.ImageFolder):
    def __getitem__(self, index):
        image, target = super().__getitem__(index)
        path, _ = self.samples[index]
        return image, target, path


def create_model(
    architecture: str,
    num_classes: int,
) -> nn.Module:
    if architecture == "vgg11":
        model = vgg11(weights=None)

        model.classifier[6] = nn.Linear(
            model.classifier[6].in_features,
            num_classes,
        )

    elif architecture == "vgg16":
        model = vgg16(weights=None)

        model.classifier[6] = nn.Linear(
            model.classifier[6].in_features,
            num_classes,
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
            num_classes,
        )

    elif architecture == "resnet18":
        model = resnet18(weights=None)

        model.fc = nn.Linear(
            model.fc.in_features,
            num_classes,
        )

    else:
        raise ValueError(
            f"Arsitektur tidak didukung: {architecture}"
        )

    return model

def create_transform():
    return transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )


def calculate_metrics(
    targets: list[int],
    predictions: list[int],
    average_confidence: float,
    average_entropy: float,
    inference_seconds: float,
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

    for index, class_name in enumerate(CLASS_NAMES):
        per_class[class_name] = {
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }

    total_images = len(targets)

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
            average_confidence
        ),
        "average_entropy": float(
            average_entropy
        ),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
        "classification_report": report,
        "inference": {
            "total_images": total_images,
            "total_seconds": float(
                inference_seconds
            ),
            "milliseconds_per_image": float(
                inference_seconds
                / max(total_images, 1)
                * 1000.0
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path(
            "ai/datasets/classification/"
            "market_regime"
        ),
    )

    parser.add_argument(
        "--split",
        choices=["valid", "test"],
        required=True,
    )

    parser.add_argument(
        "--predictions-output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--metrics-output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=0,
    )

    args = parser.parse_args()

    if not args.checkpoint.exists():
        raise FileNotFoundError(
            f"Checkpoint tidak ditemukan: "
            f"{args.checkpoint}"
        )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    checkpoint = torch.load(
        args.checkpoint,
        map_location=device,
        weights_only=False,
    )

    architecture = checkpoint["architecture"]

    model = create_model(
        architecture=architecture,
        num_classes=len(CLASS_NAMES),
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model = model.to(device)
    model.eval()

    dataset_path = args.dataset_root / args.split

    dataset = ImageFolderWithPath(
        root=dataset_path,
        transform=create_transform(),
    )

    if dataset.class_to_idx != EXPECTED_CLASS_TO_IDX:
        raise RuntimeError(
            f"Mapping kelas tidak sesuai: "
            f"{dataset.class_to_idx}"
        )

    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=torch.cuda.is_available(),
    )

    rows = []

    all_targets = []
    all_predictions = []
    all_confidences = []
    all_entropies = []

    started_at = time.perf_counter()

    with torch.no_grad():
        for images, targets, paths in loader:
            images = images.to(
                device,
                non_blocking=True,
            )

            logits = model(images)

            if isinstance(logits, tuple):
                logits = logits[0]

            probabilities = torch.softmax(
                logits,
                dim=1,
            )

            confidences, predictions = (
                probabilities.max(dim=1)
            )

            entropy = -torch.sum(
                probabilities
                * torch.log(
                    probabilities.clamp_min(
                        1e-12
                    )
                ),
                dim=1,
            )

            probabilities_cpu = (
                probabilities.cpu().numpy()
            )

            predictions_cpu = (
                predictions.cpu().numpy()
            )

            confidences_cpu = (
                confidences.cpu().numpy()
            )

            entropy_cpu = (
                entropy.cpu().numpy()
            )

            targets_cpu = (
                targets.cpu().numpy()
            )

            for index, path_value in enumerate(paths):
                image_path = Path(path_value)

                target_index = int(
                    targets_cpu[index]
                )

                predicted_index = int(
                    predictions_cpu[index]
                )

                rows.append(
                    {
                        "sample_id": image_path.stem,
                        "image_path": str(
                            image_path
                        ),
                        "true_index": target_index,
                        "true_label": (
                            CLASS_NAMES[target_index]
                        ),
                        "predicted_index": (
                            predicted_index
                        ),
                        "predicted_label": (
                            CLASS_NAMES[
                                predicted_index
                            ]
                        ),
                        "confidence": float(
                            confidences_cpu[index]
                        ),
                        "entropy": float(
                            entropy_cpu[index]
                        ),
                        "prob_bearish": float(
                            probabilities_cpu[
                                index, 0
                            ]
                        ),
                        "prob_bullish": float(
                            probabilities_cpu[
                                index, 1
                            ]
                        ),
                        "prob_sideways": float(
                            probabilities_cpu[
                                index, 2
                            ]
                        ),
                        "architecture": (
                            architecture
                        ),
                        "split": args.split,
                    }
                )

                all_targets.append(
                    target_index
                )

                all_predictions.append(
                    predicted_index
                )

                all_confidences.append(
                    float(
                        confidences_cpu[index]
                    )
                )

                all_entropies.append(
                    float(
                        entropy_cpu[index]
                    )
                )

    elapsed = (
        time.perf_counter()
        - started_at
    )

    metrics = calculate_metrics(
        targets=all_targets,
        predictions=all_predictions,
        average_confidence=float(
            np.mean(all_confidences)
        ),
        average_entropy=float(
            np.mean(all_entropies)
        ),
        inference_seconds=elapsed,
    )

    result = {
        "architecture": architecture,
        "checkpoint": str(
            args.checkpoint
        ),
        "split": args.split,
        "dataset": str(
            dataset_path
        ),
        "device": str(device),
        "metrics": metrics,
    }

    args.predictions_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.metrics_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.predictions_output.open(
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

    args.metrics_output.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print("Evaluasi CNN selesai")
    print(
        f"Architecture      : "
        f"{architecture}"
    )
    print(
        f"Split             : "
        f"{args.split}"
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
    print(
        f"ms/image          : "
        f"{metrics['inference']['milliseconds_per_image']:.2f}"
    )
    print(
        f"Predictions       : "
        f"{args.predictions_output}"
    )
    print(
        f"Metrics           : "
        f"{args.metrics_output}"
    )


if __name__ == "__main__":
    main()


