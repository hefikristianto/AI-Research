from __future__ import annotations

from pathlib import Path

import pandas as pd
from ultralytics import YOLO


MODEL_PATH = Path(
    "runs/detect/ai/benchmarks/runs/"
    "yolo11s_cumulative_2020_2024_50e/"
    "weights/best.pt"
)

DATASET_ROOT = Path(
    "ai/datasets/annotation/"
    "auto_labels_v5_medium"
)

IMAGE_ROOT = (
    DATASET_ROOT
    / "images"
    / "clean"
)

LABEL_ROOT = (
    DATASET_ROOT
    / "labels"
    / "clean"
)

OUTPUT_PATH = Path(
    "production_detection_diagnostic_50.csv"
)

THRESHOLDS = [
    0.001,
    0.01,
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
]


def find_label_path(
    image_path: Path,
) -> Path | None:
    expected = (
        LABEL_ROOT
        / f"{image_path.stem}.txt"
    )

    if expected.exists():
        return expected

    labels_root = (
        DATASET_ROOT / "labels"
    )

    if labels_root.exists():
        matches = list(
            labels_root.rglob(
                f"{image_path.stem}.txt"
            )
        )

        if matches:
            return matches[0]

    return None


def count_label_objects(
    label_path: Path | None,
) -> int:
    if (
        label_path is None
        or not label_path.exists()
    ):
        return 0

    lines = [
        line.strip()
        for line in label_path.read_text(
            encoding="utf-8-sig"
        ).splitlines()
        if line.strip()
    ]

    return len(lines)


if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Model tidak ditemukan: {MODEL_PATH}"
    )

if not IMAGE_ROOT.exists():
    raise FileNotFoundError(
        f"Folder gambar tidak ditemukan: "
        f"{IMAGE_ROOT}"
    )

images = sorted(
    IMAGE_ROOT.glob("*.png")
)[:50]

if not images:
    raise RuntimeError(
        "Tidak ada gambar untuk diuji."
    )

print(f"Model  : {MODEL_PATH}")
print(f"Images : {len(images)}")
print("Loading YOLO...")

model = YOLO(str(MODEL_PATH))

rows: list[dict] = []

for number, image_path in enumerate(
    images,
    start=1,
):
    print(
        f"[{number:02d}/{len(images):02d}] "
        f"{image_path.name}"
    )

    predictions = model.predict(
        source=str(image_path),
        conf=0.001,
        imgsz=640,
        device="cpu",
        verbose=False,
    )

    result = predictions[0]

    confidences: list[float] = []

    class_ids: list[int] = []

    if (
        result.boxes is not None
        and len(result.boxes) > 0
    ):
        confidences = [
            float(value)
            for value
            in result.boxes.conf.cpu().tolist()
        ]

        class_ids = [
            int(value)
            for value
            in result.boxes.cls.cpu().tolist()
        ]

    label_path = find_label_path(
        image_path
    )

    row = {
        "file_name": image_path.name,
        "label_path": (
            str(label_path)
            if label_path
            else ""
        ),
        "label_objects": (
            count_label_objects(
                label_path
            )
        ),
        "raw_predictions": (
            len(confidences)
        ),
        "max_conf": (
            max(confidences)
            if confidences
            else 0.0
        ),
        "order_blocks_raw": sum(
            1
            for class_id in class_ids
            if class_id == 0
        ),
        "fair_value_gaps_raw": sum(
            1
            for class_id in class_ids
            if class_id == 1
        ),
    }

    for threshold in THRESHOLDS:
        column = (
            "det_ge_"
            + str(threshold)
            .replace(".", "_")
        )

        row[column] = sum(
            1
            for confidence
            in confidences
            if confidence >= threshold
        )

    rows.append(row)

dataframe = pd.DataFrame(rows)

dataframe.to_csv(
    OUTPUT_PATH,
    index=False,
)

print()
print("=" * 80)
print("GROUND TRUTH")
print("=" * 80)

print(
    "Images with label file :",
    int(
        dataframe["label_path"]
        .ne("")
        .sum()
    ),
)

print(
    "Images with objects    :",
    int(
        dataframe["label_objects"]
        .gt(0)
        .sum()
    ),
)

print(
    "Total label objects    :",
    int(
        dataframe[
            "label_objects"
        ].sum()
    ),
)

print()
print("=" * 80)
print("DIRECT MODEL THRESHOLD SWEEP")
print("=" * 80)

for threshold in THRESHOLDS:
    column = (
        "det_ge_"
        + str(threshold)
        .replace(".", "_")
    )

    images_with_detection = int(
        dataframe[column]
        .gt(0)
        .sum()
    )

    total_detections = int(
        dataframe[column].sum()
    )

    print(
        f"conf >= {threshold:>5}: "
        f"images={images_with_detection:>2}/"
        f"{len(dataframe)}, "
        f"detections={total_detections}"
    )

print()
print("=" * 80)
print("TOP 15 MAX CONFIDENCE")
print("=" * 80)

columns = [
    "file_name",
    "label_objects",
    "raw_predictions",
    "max_conf",
    "det_ge_0_05",
    "det_ge_0_1",
    "det_ge_0_15",
    "det_ge_0_2",
    "det_ge_0_25",
]

print(
    dataframe
    .sort_values(
        "max_conf",
        ascending=False,
    )
    .head(15)[columns]
    .to_string(index=False)
)

print()
print(f"Saved: {OUTPUT_PATH.resolve()}")
