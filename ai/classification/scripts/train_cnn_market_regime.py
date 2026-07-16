from __future__ import annotations

import argparse
import csv
import json
import random
import time
from copy import deepcopy
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
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
from torchvision.models import (
    GoogLeNet_Weights,
    ResNet18_Weights,
    VGG11_Weights,
    VGG16_Weights,
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

SUPPORTED_MODELS = {
    "vgg11",
    "vgg16",
    "googlenet",
    "resnet18",
}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def create_transforms():
    imagenet_mean = [0.485, 0.456, 0.406]
    imagenet_std = [0.229, 0.224, 0.225]

    common_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=imagenet_mean,
                std=imagenet_std,
            ),
        ]
    )

    return common_transform


def create_datasets(dataset_root: Path):
    image_transform = create_transforms()

    train_dataset = datasets.ImageFolder(
        root=dataset_root / "train",
        transform=image_transform,
    )

    valid_dataset = datasets.ImageFolder(
        root=dataset_root / "valid",
        transform=image_transform,
    )

    test_dataset = datasets.ImageFolder(
        root=dataset_root / "test",
        transform=image_transform,
    )

    for split_name, dataset in [
        ("train", train_dataset),
        ("valid", valid_dataset),
        ("test", test_dataset),
    ]:
        if dataset.class_to_idx != EXPECTED_CLASS_TO_IDX:
            raise RuntimeError(
                f"Mapping kelas {split_name} tidak sesuai: "
                f"{dataset.class_to_idx}"
            )

    return train_dataset, valid_dataset, test_dataset


def create_dataloaders(
    dataset_root: Path,
    batch_size: int,
    workers: int,
    max_train_samples: int,
    max_valid_samples: int,
    max_test_samples: int,
):
    train_dataset, valid_dataset, test_dataset = (
        create_datasets(dataset_root)
    )

    def create_stratified_subset(
        dataset,
        maximum_samples: int,
        seed: int = 42,
    ):
        if maximum_samples <= 0:
            return dataset

        targets = np.asarray(dataset.targets)
        rng = np.random.default_rng(seed)

        class_indices = []

        samples_per_class = (
            maximum_samples // len(CLASS_NAMES)
        )

        remainder = (
            maximum_samples % len(CLASS_NAMES)
        )

        for class_index in range(len(CLASS_NAMES)):
            indices = np.where(
                targets == class_index
            )[0]

            rng.shuffle(indices)

            class_limit = samples_per_class

            if class_index < remainder:
                class_limit += 1

            selected = indices[
                :min(class_limit, len(indices))
            ]

            class_indices.extend(
                selected.tolist()
            )

        rng.shuffle(class_indices)

        return Subset(
            dataset,
            class_indices,
        )

    train_dataset = create_stratified_subset(
        train_dataset,
        max_train_samples,
        seed=42,
    )

    valid_dataset = create_stratified_subset(
        valid_dataset,
        max_valid_samples,
        seed=43,
    )

    test_dataset = create_stratified_subset(
        test_dataset,
        max_test_samples,
        seed=44,
    )

    pin_memory = torch.cuda.is_available()

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=workers,
        pin_memory=pin_memory,
    )

    valid_loader = DataLoader(
        valid_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=pin_memory,
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=pin_memory,
    )

    return (
        train_loader,
        valid_loader,
        test_loader,
        train_dataset,
        valid_dataset,
        test_dataset,
    )


def create_model(
    model_name: str,
    num_classes: int,
    freeze_backbone: bool,
) -> nn.Module:
    if model_name == "vgg11":
        model = vgg11(
            weights=VGG11_Weights.DEFAULT
        )

        input_features = model.classifier[6].in_features

        model.classifier[6] = nn.Linear(
            input_features,
            num_classes,
        )

        if freeze_backbone:
            for parameter in model.parameters():
                parameter.requires_grad = False

            for parameter in model.classifier[6].parameters():
                parameter.requires_grad = True

    elif model_name == "vgg16":
        model = vgg16(
            weights=VGG16_Weights.DEFAULT
        )

        input_features = model.classifier[6].in_features

        model.classifier[6] = nn.Linear(
            input_features,
            num_classes,
        )

        if freeze_backbone:
            for parameter in model.parameters():
                parameter.requires_grad = False

            for parameter in model.classifier[6].parameters():
                parameter.requires_grad = True

    elif model_name == "googlenet":
        model = googlenet(
            weights=GoogLeNet_Weights.DEFAULT,
        )

        model.aux_logits = False
        model.aux1 = None
        model.aux2 = None

        input_features = model.fc.in_features

        model.fc = nn.Linear(
            input_features,
            num_classes,
        )

        if freeze_backbone:
            for parameter in model.parameters():
                parameter.requires_grad = False

            for parameter in model.fc.parameters():
                parameter.requires_grad = True

    elif model_name == "resnet18":
        model = resnet18(
            weights=ResNet18_Weights.DEFAULT
        )

        if freeze_backbone:
            for name, parameter in model.named_parameters():
                if not name.startswith("fc."):
                    parameter.requires_grad = False

        input_features = model.fc.in_features

        model.fc = nn.Linear(
            input_features,
            num_classes,
        )

    else:
        raise ValueError(
            f"Model tidak didukung: {model_name}"
        )

    return model


def calculate_metrics(
    targets: list[int],
    predictions: list[int],
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
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
        "classification_report": report,
    }


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
) -> dict:
    training = optimizer is not None

    if training:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    all_targets: list[int] = []
    all_predictions: list[int] = []

    context = (
        torch.enable_grad()
        if training
        else torch.no_grad()
    )

    with context:
        for images, targets in loader:
            images = images.to(
                device,
                non_blocking=True,
            )

            targets = targets.to(
                device,
                non_blocking=True,
            )

            if training:
                optimizer.zero_grad(
                    set_to_none=True
                )

            logits = model(images)

            if isinstance(logits, tuple):
                logits = logits[0]

            loss = criterion(
                logits,
                targets,
            )

            if training:
                loss.backward()
                optimizer.step()

            predictions = logits.argmax(dim=1)

            total_loss += (
                loss.item() * images.size(0)
            )

            all_targets.extend(
                targets.detach().cpu().tolist()
            )

            all_predictions.extend(
                predictions.detach().cpu().tolist()
            )

    metrics = calculate_metrics(
        all_targets,
        all_predictions,
    )

    metrics["loss"] = float(
        total_loss / len(loader.dataset)
    )

    return metrics


def save_history(
    history: list[dict],
    output_path: Path,
) -> None:
    if not history:
        return

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(history[0].keys()),
        )

        writer.writeheader()
        writer.writerows(history)


def count_parameters(
    model: nn.Module,
) -> tuple[int, int]:
    total = sum(
        parameter.numel()
        for parameter in model.parameters()
    )

    trainable = sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )

    return total, trainable


def measure_inference_speed(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    maximum_batches: int = 20,
) -> dict:
    model.eval()

    total_images = 0
    total_seconds = 0.0

    with torch.no_grad():
        for batch_index, (images, _) in enumerate(loader):
            if batch_index >= maximum_batches:
                break

            images = images.to(device)

            started_at = time.perf_counter()

            outputs = model(images)

            if isinstance(outputs, tuple):
                outputs = outputs[0]

            if device.type == "cuda":
                torch.cuda.synchronize()

            elapsed = time.perf_counter() - started_at

            total_seconds += elapsed
            total_images += images.size(0)

    milliseconds_per_image = (
        total_seconds / total_images * 1000.0
        if total_images > 0
        else 0.0
    )

    return {
        "measured_images": total_images,
        "total_seconds": total_seconds,
        "milliseconds_per_image": (
            milliseconds_per_image
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train VGG11, VGG16, GoogLeNet, "
            "atau ResNet18 untuk market regime."
        )
    )

    parser.add_argument(
        "--model",
        required=True,
        choices=sorted(SUPPORTED_MODELS),
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
        "--output-dir",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.001,
    )

    parser.add_argument(
        "--weight-decay",
        type=float,
        default=0.0001,
    )

    parser.add_argument(
        "--patience",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--freeze-backbone",
        action="store_true",
    )

    parser.add_argument(
        "--skip-test",
        action="store_true",
    )

    parser.add_argument(
        "--resume-checkpoint",
        type=Path,
        default=None,
        help="Lanjutkan training dari checkpoint best.pt.",
    )

    parser.add_argument(
        "--max-train-samples",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--max-valid-samples",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--max-test-samples",
        type=int,
        default=0,
    )

    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = Path(
            "ai/classification/runs"
        ) / f"{args.model}_baseline"

    set_seed(args.seed)

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        train_loader,
        valid_loader,
        test_loader,
        train_dataset,
        valid_dataset,
        test_dataset,
    ) = create_dataloaders(
        dataset_root=args.dataset_root,
        batch_size=args.batch_size,
        workers=args.workers,
        max_train_samples=args.max_train_samples,
        max_valid_samples=args.max_valid_samples,
        max_test_samples=args.max_test_samples,
    )

    model = create_model(
        model_name=args.model,
        num_classes=len(CLASS_NAMES),
        freeze_backbone=args.freeze_backbone,
    ).to(device)

    resumed_from_epoch = 0

    if args.resume_checkpoint is not None:
        if not args.resume_checkpoint.exists():
            raise FileNotFoundError(
                f"Checkpoint tidak ditemukan: "
                f"{args.resume_checkpoint}"
            )

        checkpoint = torch.load(
            args.resume_checkpoint,
            map_location=device,
            weights_only=False,
        )

        checkpoint_architecture = checkpoint.get(
            "architecture"
        )

        if (
            checkpoint_architecture is not None
            and checkpoint_architecture != args.model
        ):
            raise ValueError(
                f"Checkpoint model "
                f"{checkpoint_architecture}, "
                f"tetapi argumen model {args.model}."
            )

        model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        resumed_from_epoch = int(
            checkpoint.get("epoch", 0)
        )

        print(
            f"Checkpoint dimuat: "
            f"{args.resume_checkpoint}"
        )
        print(
            f"Bobot berasal dari epoch: "
            f"{resumed_from_epoch}"
        )

    total_parameters, trainable_parameters_count = (
        count_parameters(model)
    )

    trainable_parameters = [
        parameter
        for parameter in model.parameters()
        if parameter.requires_grad
    ]

    criterion = nn.CrossEntropyLoss()

    optimizer = AdamW(
        trainable_parameters,
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    scheduler = ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=3,
    )

    print("")
    print("CNN Market Regime Training")
    print(f"Model            : {args.model}")
    print(f"Device           : {device}")
    print(f"Train images     : {len(train_dataset)}")
    print(f"Valid images     : {len(valid_dataset)}")
    print(f"Test images      : {len(test_dataset)}")
    print(f"Batch size       : {args.batch_size}")
    print(f"Epochs           : {args.epochs}")
    print(f"Freeze backbone  : {args.freeze_backbone}")
    print(f"Total parameters : {total_parameters:,}")
    print(
        f"Trainable params : "
        f"{trainable_parameters_count:,}"
    )
    print("")

    best_macro_f1 = -1.0
    best_epoch = 0
    best_state = None
    best_valid_metrics = None
    epochs_without_improvement = 0
    history: list[dict] = []

    training_started = time.time()

    for epoch in range(
        1,
        args.epochs + 1,
    ):
        epoch_started = time.time()

        train_metrics = run_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion,
            device=device,
            optimizer=optimizer,
        )

        valid_metrics = run_epoch(
            model=model,
            loader=valid_loader,
            criterion=criterion,
            device=device,
            optimizer=None,
        )

        scheduler.step(
            valid_metrics["macro_f1"]
        )

        current_lr = optimizer.param_groups[0]["lr"]

        history_row = {
            "epoch": epoch,
            "learning_rate": current_lr,
            "train_loss": train_metrics["loss"],
            "train_accuracy": train_metrics["accuracy"],
            "train_balanced_accuracy": (
                train_metrics["balanced_accuracy"]
            ),
            "train_macro_f1": train_metrics["macro_f1"],
            "valid_loss": valid_metrics["loss"],
            "valid_accuracy": valid_metrics["accuracy"],
            "valid_balanced_accuracy": (
                valid_metrics["balanced_accuracy"]
            ),
            "valid_macro_precision": (
                valid_metrics["macro_precision"]
            ),
            "valid_macro_recall": (
                valid_metrics["macro_recall"]
            ),
            "valid_macro_f1": valid_metrics["macro_f1"],
            "seconds": round(
                time.time() - epoch_started,
                2,
            ),
        }

        history.append(history_row)

        print(
            f"Epoch {epoch:03d}/{args.epochs} | "
            f"train loss={train_metrics['loss']:.4f} "
            f"acc={train_metrics['accuracy']:.4f} "
            f"macroF1={train_metrics['macro_f1']:.4f} | "
            f"valid loss={valid_metrics['loss']:.4f} "
            f"acc={valid_metrics['accuracy']:.4f} "
            f"balAcc={valid_metrics['balanced_accuracy']:.4f} "
            f"macroF1={valid_metrics['macro_f1']:.4f} | "
            f"lr={current_lr:.6f}"
        )

        if valid_metrics["macro_f1"] > best_macro_f1:
            best_macro_f1 = valid_metrics["macro_f1"]
            best_epoch = epoch
            best_state = deepcopy(
                model.state_dict()
            )
            best_valid_metrics = valid_metrics
            epochs_without_improvement = 0

            torch.save(
                {
                    "epoch": best_epoch,
                    "architecture": args.model,
                    "model_state_dict": best_state,
                    "class_names": CLASS_NAMES,
                    "class_to_idx": (
                        EXPECTED_CLASS_TO_IDX
                    ),
                    "image_size": 224,
                    "valid_metrics": valid_metrics,
                    "total_parameters": total_parameters,
                    "trainable_parameters": (
                        trainable_parameters_count
                    ),
                },
                args.output_dir / "best.pt",
            )

            with (
                args.output_dir
                / "best_valid_metrics.json"
            ).open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    valid_metrics,
                    file,
                    indent=2,
                )

        else:
            epochs_without_improvement += 1

        save_history(
            history,
            args.output_dir / "history.csv",
        )

        if (
            epochs_without_improvement
            >= args.patience
        ):
            print(
                f"Early stopping pada epoch {epoch}."
            )
            break

    if best_state is None:
        raise RuntimeError(
            "Checkpoint terbaik tidak tersimpan."
        )

    model.load_state_dict(best_state)

    result = {
        "architecture": args.model,
        "device": str(device),
        "best_epoch": best_epoch,
        "best_valid_macro_f1": best_macro_f1,
        "best_valid_metrics": best_valid_metrics,
        "total_parameters": total_parameters,
        "trainable_parameters": (
            trainable_parameters_count
        ),
        "training_seconds": round(
            time.time() - training_started,
            2,
        ),
        "configuration": {
            "dataset_root": str(args.dataset_root),
            "output_dir": str(args.output_dir),
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "workers": args.workers,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "patience": args.patience,
            "seed": args.seed,
            "freeze_backbone": (
                args.freeze_backbone
            ),
        },
    }

    if not args.skip_test:
        test_metrics = run_epoch(
            model=model,
            loader=test_loader,
            criterion=criterion,
            device=device,
            optimizer=None,
        )

        speed_metrics = measure_inference_speed(
            model=model,
            loader=test_loader,
            device=device,
        )

        result["test_metrics"] = test_metrics
        result["inference_speed"] = speed_metrics

        with (
            args.output_dir
            / "test_metrics.json"
        ).open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                test_metrics,
                file,
                indent=2,
            )

        print("")
        print("Final Test 2025")
        print(
            f"Accuracy          : "
            f"{test_metrics['accuracy']:.4f}"
        )
        print(
            f"Balanced accuracy : "
            f"{test_metrics['balanced_accuracy']:.4f}"
        )
        print(
            f"Macro precision   : "
            f"{test_metrics['macro_precision']:.4f}"
        )
        print(
            f"Macro recall      : "
            f"{test_metrics['macro_recall']:.4f}"
        )
        print(
            f"Macro F1          : "
            f"{test_metrics['macro_f1']:.4f}"
        )
        print(
            f"Inference ms/img  : "
            f"{speed_metrics['milliseconds_per_image']:.2f}"
        )
        print("")
        print("Confusion matrix:")
        print(
            np.asarray(
                test_metrics["confusion_matrix"]
            )
        )

    with (
        args.output_dir / "result.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            default=str,
        )

    print("")
    print("Training selesai")
    print(f"Model         : {args.model}")
    print(f"Best epoch    : {best_epoch}")
    print(f"Best macro F1 : {best_macro_f1:.4f}")
    print(
        f"Checkpoint    : "
        f"{args.output_dir / 'best.pt'}"
    )


if __name__ == "__main__":
    main()
