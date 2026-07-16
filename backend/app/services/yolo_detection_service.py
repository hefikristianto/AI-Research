from __future__ import annotations

import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

from PIL import Image
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODEL_PATH = (
    PROJECT_ROOT
    / "runs"
    / "detect"
    / "ai"
    / "benchmarks"
    / "runs"
    / "yolo11s_cumulative_2020_2024_50e"
    / "weights"
    / "best.pt"
)


class YOLODetectionService:
    def __init__(
        self,
        confidence_threshold: float = 0.05,
        image_size: int = 640,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.image_size = image_size

        self._model: YOLO | None = None
        self._load_lock = Lock()

    def load(self) -> None:
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return

            if not MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"Checkpoint YOLO tidak ditemukan: {MODEL_PATH}"
                )

            self._model = YOLO(str(MODEL_PATH))

    def predict(
        self,
        image: Image.Image,
    ) -> dict[str, Any]:
        self.load()

        if self._model is None:
            raise RuntimeError(
                "Model YOLO gagal dimuat."
            )

        rgb_image = image.convert("RGB")

        temp_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".png",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)

            rgb_image.save(
                temp_path,
                format="PNG",
            )

            results = self._model.predict(
                source=str(temp_path),
                conf=self.confidence_threshold,
                iou=0.70,
                imgsz=self.image_size,
                max_det=300,
                verbose=False,
            )

        finally:
            if (
                temp_path is not None
                and temp_path.exists()
            ):
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        if not results:
            return {
                "total": 0,
                "class_counts": {},
                "detections": [],
                "model_path": str(MODEL_PATH),
                "confidence_threshold": (
                    self.confidence_threshold
                ),
                "image_size": self.image_size,
            }

        result = results[0]
        names = result.names

        width = rgb_image.width
        height = rgb_image.height

        detections: list[dict[str, Any]] = []

        if result.boxes is not None:
            for index, box in enumerate(
                result.boxes
            ):
                class_id = int(
                    box.cls[0].item()
                )

                confidence = float(
                    box.conf[0].item()
                )

                x1, y1, x2, y2 = [
                    float(value)
                    for value in (
                        box.xyxy[0]
                        .detach()
                        .cpu()
                        .tolist()
                    )
                ]

                center_x = (
                    x1 + x2
                ) / 2.0

                center_y = (
                    y1 + y2
                ) / 2.0

                box_width = x2 - x1
                box_height = y2 - y1

                class_name = (
                    names[class_id]
                    if isinstance(names, dict)
                    else names[class_id]
                )

                detections.append(
                    {
                        "detection_id": index,
                        "class_id": class_id,
                        "class_name": class_name,
                        "confidence": confidence,
                        "bbox_pixel": {
                            "x1": x1,
                            "y1": y1,
                            "x2": x2,
                            "y2": y2,
                            "center_x": center_x,
                            "center_y": center_y,
                            "width": box_width,
                            "height": box_height,
                        },
                        "bbox_normalized": {
                            "x": center_x / width,
                            "y": center_y / height,
                            "width": box_width / width,
                            "height": box_height / height,
                        },
                    }
                )

        detections.sort(
            key=lambda item: item["confidence"],
            reverse=True,
        )

        class_counts: dict[str, int] = {}

        for detection in detections:
            class_name = detection[
                "class_name"
            ]

            class_counts[class_name] = (
                class_counts.get(
                    class_name,
                    0,
                )
                + 1
            )

        return {
            "total": len(detections),
            "class_counts": class_counts,
            "detections": detections,
            "model_path": str(MODEL_PATH),
            "confidence_threshold": (
                self.confidence_threshold
            ),
            "image_size": self.image_size,
        }
