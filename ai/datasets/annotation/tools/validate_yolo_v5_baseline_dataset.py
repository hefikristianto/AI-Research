from pathlib import Path
from PIL import Image
import csv

DATASET_DIR = Path("ai/datasets/annotation/exports/yolo_v5_baseline")

IMAGE_DIR = DATASET_DIR / "images"
LABEL_DIR = DATASET_DIR / "labels"
REPORT_DIR = DATASET_DIR / "reports"
REPORT_PATH = REPORT_DIR / "yolo_dataset_validation_report.csv"

VALID_CLASS_IDS = {0, 1}
SPLITS = ["train", "valid", "test"]

def validate_label_file(label_path: Path):
    errors = []
    object_count = 0
    class_counts = {0: 0, 1: 0}

    lines = label_path.read_text(encoding="utf-8").splitlines()

    for line_number, line in enumerate(lines, start=1):
        line = line.strip()

        if not line:
            continue

        object_count += 1
        parts = line.split()

        if len(parts) != 5:
            errors.append(f"line {line_number}: expected 5 values, got {len(parts)}")
            continue

        raw_class_id, raw_x, raw_y, raw_w, raw_h = parts

        try:
            class_id = int(raw_class_id)
        except ValueError:
            errors.append(f"line {line_number}: class_id is not integer")
            continue

        if class_id not in VALID_CLASS_IDS:
            errors.append(f"line {line_number}: invalid class_id {class_id}")
        else:
            class_counts[class_id] += 1

        try:
            x = float(raw_x)
            y = float(raw_y)
            w = float(raw_w)
            h = float(raw_h)
        except ValueError:
            errors.append(f"line {line_number}: coordinate is not numeric")
            continue

        values = {
            "x_center": x,
            "y_center": y,
            "width": w,
            "height": h,
        }

        for name, value in values.items():
            if value < 0 or value > 1:
                errors.append(f"line {line_number}: {name} out of range {value}")

        if w <= 0:
            errors.append(f"line {line_number}: width must be > 0")

        if h <= 0:
            errors.append(f"line {line_number}: height must be > 0")

    return errors, object_count, class_counts

def validate_image(image_path: Path):
    errors = []

    try:
        with Image.open(image_path) as img:
            width, height = img.size

        if width <= 0 or height <= 0:
            errors.append("invalid image size")

        return errors, width, height

    except Exception as error:
        errors.append(f"cannot open image: {error}")
        return errors, None, None

def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    report_rows = []

    total_images = 0
    total_labels = 0
    total_objects = 0
    total_ob = 0
    total_fvg = 0
    total_invalid = 0

    for split in SPLITS:
        split_image_dir = IMAGE_DIR / split
        split_label_dir = LABEL_DIR / split

        if not split_image_dir.exists():
            print(f"[MISSING] image dir: {split_image_dir}")
            continue

        if not split_label_dir.exists():
            print(f"[MISSING] label dir: {split_label_dir}")
            continue

        image_files = sorted(split_image_dir.glob("*.png"))

        for image_path in image_files:
            total_images += 1

            label_path = split_label_dir / f"{image_path.stem}.txt"

            image_errors, width, height = validate_image(image_path)

            if not label_path.exists():
                label_errors = [f"missing label file: {label_path.name}"]
                object_count = 0
                class_counts = {0: 0, 1: 0}
            else:
                total_labels += 1
                label_errors, object_count, class_counts = validate_label_file(label_path)

            errors = image_errors + label_errors
            status = "valid" if not errors else "invalid"

            if status == "invalid":
                total_invalid += 1

            total_objects += object_count
            total_ob += class_counts[0]
            total_fvg += class_counts[1]

            report_rows.append({
                "split": split,
                "image_name": image_path.name,
                "label_name": label_path.name,
                "width": width,
                "height": height,
                "object_count": object_count,
                "order_block_count": class_counts[0],
                "fair_value_gap_count": class_counts[1],
                "status": status,
                "errors": " | ".join(errors),
            })

    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "split",
            "image_name",
            "label_name",
            "width",
            "height",
            "object_count",
            "order_block_count",
            "fair_value_gap_count",
            "status",
            "errors",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    print("YOLO dataset validation finished.")
    print(f"Total images   : {total_images}")
    print(f"Total labels   : {total_labels}")
    print(f"Total objects  : {total_objects}")
    print(f"Order blocks   : {total_ob}")
    print(f"Fair value gaps: {total_fvg}")
    print(f"Invalid files  : {total_invalid}")
    print(f"Report         : {REPORT_PATH}")

if __name__ == "__main__":
    main()
