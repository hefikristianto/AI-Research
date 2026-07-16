from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

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


PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENSEMBLE_DIR = (
    PROJECT_ROOT
    / "ai"
    / "classification"
    / "models"
    / "ensemble"
)

CONFIG_PATH = ENSEMBLE_DIR / "ensemble_config.json"

CLASS_NAMES = [
    "bearish",
    "bullish",
    "sideways",
]


class CNNEnsembleService:
    def __init__(self) -> None:
        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        self.models: dict[str, nn.Module] = {}
        self.weights: dict[str, float] = {}

        self.loaded = False
        self.load_lock = Lock()

        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[
                        0.485,
                        0.456,
                        0.406,
                    ],
                    std=[
                        0.229,
                        0.224,
                        0.225,
                    ],
                ),
            ]
        )

    @staticmethod
    def extract_state_dict(
        checkpoint: Any,
    ) -> dict[str, torch.Tensor]:
        if isinstance(checkpoint, dict):
            for key in (
                "model_state_dict",
                "state_dict",
                "model",
            ):
                value = checkpoint.get(key)

                if isinstance(value, dict):
                    return value

            if checkpoint and all(
                isinstance(value, torch.Tensor)
                for value in checkpoint.values()
            ):
                return checkpoint

        raise ValueError(
            "State dict tidak ditemukan dalam checkpoint."
        )

    @staticmethod
    def clean_state_dict(
        state_dict: dict[str, torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        cleaned = {}

        for key, value in state_dict.items():
            clean_key = key

            for prefix in (
                "module.",
                "model.",
            ):
                if clean_key.startswith(prefix):
                    clean_key = clean_key[
                        len(prefix):
                    ]

            cleaned[clean_key] = value

        return cleaned

    @staticmethod
    def build_vgg11() -> nn.Module:
        model = vgg11(weights=None)

        model.classifier[6] = nn.Linear(
            model.classifier[6].in_features,
            len(CLASS_NAMES),
        )

        return model

    @staticmethod
    def build_vgg16() -> nn.Module:
        model = vgg16(weights=None)

        model.classifier[6] = nn.Linear(
            model.classifier[6].in_features,
            len(CLASS_NAMES),
        )

        return model

    @staticmethod
    def build_googlenet() -> nn.Module:
        model = googlenet(
            weights=None,
            aux_logits=True,
            transform_input=True,
            init_weights=False,
        )

        model.fc = nn.Linear(
            model.fc.in_features,
            len(CLASS_NAMES),
        )

        model.aux_logits = False
        model.aux1 = None
        model.aux2 = None

        return model

    @staticmethod
    def build_resnet18() -> nn.Module:
        model = resnet18(weights=None)

        model.fc = nn.Linear(
            model.fc.in_features,
            len(CLASS_NAMES),
        )

        return model

    def build_model(
        self,
        model_name: str,
    ) -> nn.Module:
        builders = {
            "vgg11": self.build_vgg11,
            "vgg16": self.build_vgg16,
            "googlenet": self.build_googlenet,
            "resnet18": self.build_resnet18,
        }

        builder = builders.get(
            model_name.lower()
        )

        if builder is None:
            raise ValueError(
                f"Model tidak didukung: {model_name}"
            )

        return builder()

    def read_config(self) -> dict[str, Any]:
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Config ensemble tidak ditemukan: "
                f"{CONFIG_PATH}"
            )

        return json.loads(
            CONFIG_PATH.read_text(
                encoding="utf-8"
            )
        )

    def load(self) -> None:
        if self.loaded:
            return

        with self.load_lock:
            if self.loaded:
                return

            config = self.read_config()

            model_configs = config.get("models")

            if not isinstance(
                model_configs,
                dict,
            ):
                raise ValueError(
                    "Format 'models' pada "
                    "ensemble_config.json tidak valid."
                )

            for model_name, model_config in (
                model_configs.items()
            ):
                checkpoint_value = (
                    model_config.get("checkpoint")
                    or model_config.get(
                        "checkpoint_path"
                    )
                    or f"{model_name}.pt"
                )

                checkpoint_path = Path(
                    checkpoint_value
                )

                if not checkpoint_path.is_absolute():
                    checkpoint_path = (
                        ENSEMBLE_DIR
                        / checkpoint_path.name
                    )

                if not checkpoint_path.exists():
                    raise FileNotFoundError(
                        f"Checkpoint tidak ditemukan: "
                        f"{checkpoint_path}"
                    )

                model = self.build_model(
                    model_name
                )

                checkpoint = torch.load(
                    checkpoint_path,
                    map_location=self.device,
                    weights_only=False,
                )

                state_dict = (
                    self.extract_state_dict(
                        checkpoint
                    )
                )

                state_dict = (
                    self.clean_state_dict(
                        state_dict
                    )
                )

                missing, unexpected = (
                    model.load_state_dict(
                        state_dict,
                        strict=False,
                    )
                )

                if missing:
                    print(
                        f"[WARNING] {model_name} "
                        f"missing keys: {missing}"
                    )

                if unexpected:
                    print(
                        f"[WARNING] {model_name} "
                        f"unexpected keys: {unexpected}"
                    )

                model.to(self.device)
                model.eval()

                self.models[model_name] = model

                self.weights[model_name] = float(
                    model_config["weight"]
                )

            total_weight = sum(
                self.weights.values()
            )

            if total_weight <= 0:
                raise ValueError(
                    "Total bobot ensemble tidak valid."
                )

            self.weights = {
                name: weight / total_weight
                for name, weight
                in self.weights.items()
            }

            self.loaded = True

    def predict(
        self,
        image: Image.Image,
    ) -> dict[str, Any]:
        self.load()

        image_tensor = (
            self.transform(
                image.convert("RGB")
            )
            .unsqueeze(0)
            .to(self.device)
        )

        weighted_probabilities = torch.zeros(
            len(CLASS_NAMES),
            device=self.device,
        )

        individual_models = {}

        with torch.inference_mode():
            for model_name, model in (
                self.models.items()
            ):
                logits = model(image_tensor)

                if hasattr(logits, "logits"):
                    logits = logits.logits

                probabilities = torch.softmax(
                    logits,
                    dim=1,
                )[0]

                weight = self.weights[
                    model_name
                ]

                weighted_probabilities += (
                    probabilities * weight
                )

                individual_models[
                    model_name
                ] = {
                    CLASS_NAMES[index]: float(
                        probabilities[index]
                        .detach()
                        .cpu()
                        .item()
                    )
                    for index in range(
                        len(CLASS_NAMES)
                    )
                }

        prediction_index = int(
            weighted_probabilities.argmax().item()
        )

        probabilities = {
            CLASS_NAMES[index]: float(
                weighted_probabilities[index]
                .detach()
                .cpu()
                .item()
            )
            for index in range(
                len(CLASS_NAMES)
            )
        }

        predicted_label = CLASS_NAMES[
            prediction_index
        ]

        return {
            "label": predicted_label,
            "confidence": probabilities[
                predicted_label
            ],
            "probabilities": probabilities,
            "individual_models": (
                individual_models
            ),
            "weights": self.weights,
            "device": str(self.device),
        }
