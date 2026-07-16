from pathlib import Path
import shutil
import random
import csv
import json
import pandas as pd


AUTO_LABEL_REPORT = Path("ai/datasets/annotation/auto_labels_v5_medium/reports/auto_label_report.csv")

OUTPUT_ROOT = Path("ai/datasets/annotation/exports/cumulative_yolo_2020_2024")

SEED = 42
VALID_RATIO = 0.20

TRAIN_YEARS = [2020, 2021, 2022, 2023, 2024]
TEST_YEAR = 2025

CLASS_NAMES = {
    0: "order_block",
    1: "fair_value_gap",
}


def reset_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_dirs():
    for split in ["train", "valid", "test"]:
        (OUTPUT_ROOT / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_ROOT / "labels" / split).mkdir(parents=True, exist_ok=True)

    (OUTPUT_ROOT / "reports").mkdir(parents=True, exist_ok=True)


def copy_sample(row, split: str):
    image_path = Path(row["clean_image_path"])
    label_path = Path(row["label_path"])

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if not label_path.exists():
        raise FileNotFoundError(f"Label not found: {label_path}")

    shutil.copy2(image_path, OUTPUT_ROOT / "images" / split / image_path.name)
    shutil.copy2(label_path, OUTPUT_ROOT / "labels" / split / label_path.name)


def split_train_valid(rows):
    rows = list(rows)
    random.shuffle(rows)

    valid_count = max(1, int(len(rows) * VALID_RATIO))

    valid_rows = rows[:valid_count]
    train_rows = rows[valid_count:]

    return train_rows, valid_rows


def count_objects(label_path: Path):
    total = 0
    ob = 0
    fvg = 0

    if not label_path.exists():
        return total, ob, fvg

    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        class_id = int(float(line.split()[0]))

        total += 1

        if class_id == 0:
            ob += 1
        elif class_id == 1:
            fvg += 1

    return total, ob, fvg


def collect_stats():
    stats = []

    for split in ["train", "valid", "test"]:
        image_dir = OUTPUT_ROOT / "images" / split
        label_dir = OUTPUT_ROOT / "labels" / split

        images = list(image_dir.glob("*.*"))
        labels = list(label_dir.glob("*.txt"))

        total_objects = 0
        total_ob = 0
        total_fvg = 0

        for label_path in labels:
            obj, ob, fvg = count_objects(label_path)
            total_objects += obj
            total_ob += ob
            total_fvg += fvg

        stats.append({
            "split": split,
            "images": len(images),
            "labels": len(labels),
            "objects": total_objects,
            "order_blocks": total_ob,
            "fair_value_gaps": total_fvg,
        })

    return stats


def write_dataset_yaml():
    content = f"""# AI-TDSS Cumulative YOLO Dataset 2020-2024

path: {OUTPUT_ROOT.as_posix()}

train: images/train
val: images/valid
test: images/test

names:
  0: order_block
  1: fair_value_gap
"""

    (OUTPUT_ROOT / "dataset.yaml").write_text(content, encoding="utf-8")


def write_reports(selected_rows, stats):
    report_csv = OUTPUT_ROOT / "reports" / "split_report.csv"

    with report_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "image_id",
            "pair",
            "timeframe",
            "year",
            "start_datetime",
            "end_datetime",
            "split",
            "object_count",
            "ob_count",
            "fvg_count",
            "clean_image_path",
            "label_path",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in selected_rows:
            writer.writerow({
                "image_id": row["image_id"],
                "pair": row["pair"],
                "timeframe": row["timeframe"],
                "year": row["year"],
                "start_datetime": row["start_datetime"],
                "end_datetime": row["end_datetime"],
                "split": row["split"],
                "object_count": row["object_count"],
                "ob_count": row["ob_count"],
                "fvg_count": row["fvg_count"],
                "clean_image_path": row["clean_image_path"],
                "label_path": row["label_path"],
            })

    summary = {
        "status": "READY",
        "dataset": "cumulative_yolo_2020_2024",
        "train_years": TRAIN_YEARS,
        "test_year": TEST_YEAR,
        "valid_ratio": VALID_RATIO,
        "stats": stats,
    }

    (OUTPUT_ROOT / "reports" / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8"
    )

    lines = []
    lines.append("# Cumulative YOLO Dataset 2020-2024")
    lines.append("")
    lines.append("## Status")
    lines.append("READY")
    lines.append("")
    lines.append("## Purpose")
    lines.append("This dataset is used as a non-incremental baseline for comparison against the incremental YOLO workflow.")
    lines.append("")
    lines.append("## Split Design")
    lines.append("")
    lines.append("- Train/valid source years: 2020, 2021, 2022, 2023, 2024")
    lines.append("- Final test year: 2025")
    lines.append("- Validation ratio: 0.20")
    lines.append("")
    lines.append("## Statistics")
    lines.append("")
    lines.append("| Split | Images | Labels | Objects | OB | FVG |")
    lines.append("|---|---:|---:|---:|---:|---:|")

    for stat in stats:
        lines.append(
            f"| {stat['split']} | {stat['images']} | {stat['labels']} | "
            f"{stat['objects']} | {stat['order_blocks']} | {stat['fair_value_gaps']} |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This dataset trains the model directly on 2020-2024 data.")
    lines.append("- The 2025 data is reserved as unseen final test data.")
    lines.append("- This baseline will be compared against the incremental YOLOv8n development result.")

    (OUTPUT_ROOT / "reports" / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    random.seed(SEED)

    if not AUTO_LABEL_REPORT.exists():
        raise FileNotFoundError(f"Auto-label report not found: {AUTO_LABEL_REPORT}")

    reset_dir(OUTPUT_ROOT)
    ensure_dirs()

    df = pd.read_csv(AUTO_LABEL_REPORT)

    required = [
        "image_id",
        "pair",
        "timeframe",
        "year",
        "start_datetime",
        "end_datetime",
        "clean_image_path",
        "label_path",
        "ob_count",
        "fvg_count",
        "object_count",
    ]

    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f"Missing columns in report: {missing}")

    train_valid_df = df[df["year"].isin(TRAIN_YEARS)]
    test_df = df[df["year"] == TEST_YEAR]

    train_rows, valid_rows = split_train_valid(train_valid_df.to_dict("records"))
    test_rows = test_df.to_dict("records")

    selected_rows = []

    for row in train_rows:
        copy_sample(row, "train")
        row_copy = dict(row)
        row_copy["split"] = "train"
        selected_rows.append(row_copy)

    for row in valid_rows:
        copy_sample(row, "valid")
        row_copy = dict(row)
        row_copy["split"] = "valid"
        selected_rows.append(row_copy)

    for row in test_rows:
        copy_sample(row, "test")
        row_copy = dict(row)
        row_copy["split"] = "test"
        selected_rows.append(row_copy)

    write_dataset_yaml()

    stats = collect_stats()
    write_reports(selected_rows, stats)

    print("Cumulative YOLO dataset build finished.")
    print(f"Output root: {OUTPUT_ROOT}")
    print("")
    for stat in stats:
        print(
            f"{stat['split']}: "
            f"images={stat['images']}, "
            f"objects={stat['objects']}, "
            f"OB={stat['order_blocks']}, "
            f"FVG={stat['fair_value_gaps']}"
        )


if __name__ == "__main__":
    main()
