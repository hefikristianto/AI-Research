from pathlib import Path
import csv
import random
import shutil

SOURCE_DIR = Path("ai/datasets/annotation/auto_labels_v5_medium")
REPORT_PATH = SOURCE_DIR / "reports" / "auto_label_report.csv"

SOURCE_IMAGE_DIR = SOURCE_DIR / "images" / "clean"
SOURCE_LABEL_DIR = SOURCE_DIR / "labels" / "yolo"

OUTPUT_DIR = Path("ai/datasets/annotation/exports/yolo_v5_medium")

IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"
LABEL_OUTPUT_DIR = OUTPUT_DIR / "labels"
REPORT_OUTPUT_DIR = OUTPUT_DIR / "reports"

DATASET_YAML_PATH = OUTPUT_DIR / "dataset.yaml"
SPLIT_REPORT_PATH = REPORT_OUTPUT_DIR / "split_report.csv"

RANDOM_SEED = 42

TRAIN_RATIO = 0.70
VALID_RATIO = 0.20
TEST_RATIO = 0.10

# Negative sample = gambar tanpa object.
# Kita ambil maksimal 50% dari jumlah image berlabel.
NEGATIVE_SAMPLE_RATIO = 0.50

random.seed(RANDOM_SEED)

def reset_output_dirs():
    for split in ["train", "valid", "test"]:
        image_dir = IMAGE_OUTPUT_DIR / split
        label_dir = LABEL_OUTPUT_DIR / split

        if image_dir.exists():
            shutil.rmtree(image_dir)

        if label_dir.exists():
            shutil.rmtree(label_dir)

        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)

    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def read_report():
    if not REPORT_PATH.exists():
        raise FileNotFoundError(f"Report not found: {REPORT_PATH}")

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def split_rows(rows):
    rows = rows[:]
    random.shuffle(rows)

    total = len(rows)
    train_end = int(total * TRAIN_RATIO)
    valid_end = train_end + int(total * VALID_RATIO)

    return {
        "train": rows[:train_end],
        "valid": rows[train_end:valid_end],
        "test": rows[valid_end:],
    }

def copy_pair(row, split):
    image_id = row["image_id"]

    src_image = SOURCE_IMAGE_DIR / f"{image_id}.png"
    src_label = SOURCE_LABEL_DIR / f"{image_id}.txt"

    dst_image = IMAGE_OUTPUT_DIR / split / f"{image_id}.png"
    dst_label = LABEL_OUTPUT_DIR / split / f"{image_id}.txt"

    if not src_image.exists():
        raise FileNotFoundError(f"Missing image: {src_image}")

    if not src_label.exists():
        raise FileNotFoundError(f"Missing label: {src_label}")

    shutil.copy2(src_image, dst_image)
    shutil.copy2(src_label, dst_label)

def write_dataset_yaml():
    content = """# AI-TDSS YOLO v5 Medium Dataset

path: ai/datasets/annotation/exports/yolo_v5_medium

train: images/train
val: images/valid
test: images/test

names:
  0: order_block
  1: fair_value_gap
"""
    DATASET_YAML_PATH.write_text(content, encoding="utf-8")

def main():
    reset_output_dirs()

    rows = read_report()

    labeled_rows = [
        row for row in rows
        if int(row.get("object_count", "0")) > 0
    ]

    negative_rows = [
        row for row in rows
        if int(row.get("object_count", "0")) == 0
    ]

    negative_target = int(len(labeled_rows) * NEGATIVE_SAMPLE_RATIO)
    selected_negative_rows = random.sample(
        negative_rows,
        min(negative_target, len(negative_rows))
    )

    selected_rows = labeled_rows + selected_negative_rows

    split_data = split_rows(selected_rows)

    report_rows = []

    for split, split_rows_data in split_data.items():
        for row in split_rows_data:
            copy_pair(row, split)

            report_rows.append({
                "image_id": row["image_id"],
                "pair": row["pair"],
                "timeframe": row["timeframe"],
                "year": row["year"],
                "object_count": row["object_count"],
                "ob_count": row["ob_count"],
                "fvg_count": row["fvg_count"],
                "split": split,
                "status": "copied",
            })

    write_dataset_yaml()

    with open(SPLIT_REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "image_id",
            "pair",
            "timeframe",
            "year",
            "object_count",
            "ob_count",
            "fvg_count",
            "split",
            "status",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    print("YOLO baseline dataset created.")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Total labeled images  : {len(labeled_rows)}")
    print(f"Total negative images : {len(selected_negative_rows)}")
    print(f"Total selected images : {len(selected_rows)}")

    for split in ["train", "valid", "test"]:
        image_count = len(list((IMAGE_OUTPUT_DIR / split).glob("*.png")))
        label_count = len(list((LABEL_OUTPUT_DIR / split).glob("*.txt")))
        print(f"{split}: images={image_count}, labels={label_count}")

    print(f"Dataset YAML: {DATASET_YAML_PATH}")
    print(f"Split report: {SPLIT_REPORT_PATH}")

if __name__ == "__main__":
    main()
