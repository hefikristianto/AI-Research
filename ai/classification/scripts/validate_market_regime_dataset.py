from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


DATASET_ROOT = Path(
    "ai/datasets/classification/market_regime"
)

REPORT_PATH = Path(
    "ai/classification/reports/"
    "market_regime_dataset_validation.json"
)

EXPECTED = {
    "train": {
        "bearish": 2630,
        "bullish": 2854,
        "sideways": 2854,
    },
    "valid": {
        "bearish": 684,
        "bullish": 843,
        "sideways": 2631,
    },
    "test": {
        "bearish": 601,
        "bullish": 958,
        "sideways": 2568,
    },
}


def main() -> None:
    result = {
        "status": "PASS",
        "expected": EXPECTED,
        "actual": {},
        "invalid_images": [],
        "unexpected_files": [],
        "total_images": 0,
    }

    for split, labels in EXPECTED.items():
        result["actual"][split] = {}

        for label, expected_count in labels.items():
            folder = DATASET_ROOT / split / label

            if not folder.exists():
                result["status"] = "FAIL"
                result["actual"][split][label] = 0
                result["invalid_images"].append(
                    {
                        "path": str(folder),
                        "error": "Folder tidak ditemukan",
                    }
                )
                continue

            image_files = sorted(
                folder.glob("*.png")
            )

            actual_count = len(image_files)

            result["actual"][split][label] = (
                actual_count
            )

            result["total_images"] += actual_count

            if actual_count != expected_count:
                result["status"] = "FAIL"

            for image_path in image_files:
                try:
                    with Image.open(image_path) as image:
                        image.verify()

                    with Image.open(image_path) as image:
                        if image.size != (224, 224):
                            result["status"] = "FAIL"
                            result["invalid_images"].append(
                                {
                                    "path": str(image_path),
                                    "error": (
                                        f"Ukuran {image.size}, "
                                        "seharusnya (224, 224)"
                                    ),
                                }
                            )

                        if image.mode not in {
                            "RGB",
                            "RGBA",
                        }:
                            result["status"] = "FAIL"
                            result["invalid_images"].append(
                                {
                                    "path": str(image_path),
                                    "error": (
                                        f"Mode gambar {image.mode}"
                                    ),
                                }
                            )

                except Exception as exc:
                    result["status"] = "FAIL"
                    result["invalid_images"].append(
                        {
                            "path": str(image_path),
                            "error": str(exc),
                        }
                    )

    for file_path in DATASET_ROOT.rglob("*"):
        if (
            file_path.is_file()
            and file_path.suffix.lower()
            not in {".png", ".csv"}
        ):
            result["unexpected_files"].append(
                str(file_path)
            )

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
        )

    print("")
    print("Dataset validation selesai")
    print(f"Status       : {result['status']}")
    print(
        f"Total images : {result['total_images']}"
    )
    print(
        f"Invalid      : "
        f"{len(result['invalid_images'])}"
    )
    print(f"Report       : {REPORT_PATH}")
    print("")

    for split, labels in result["actual"].items():
        print(split)

        for label, count in labels.items():
            expected_count = EXPECTED[split][label]

            print(
                f"  {label:8s}: "
                f"{count} / {expected_count}"
            )


if __name__ == "__main__":
    main()
