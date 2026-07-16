from pathlib import Path
import shutil
import random
import csv
import json
import pandas as pd


AUTO_LABEL_REPORT = Path("ai/datasets/annotation/auto_labels_v5_medium/reports/auto_label_report.csv")

OUTPUT_ROOT = Path("ai/datasets/annotation/exports/incremental_yolo")

SEED = 42
VALID_RATIO = 0.20
REPLAY_RATIO = 0.25

CLASS_NAMES = {
    0: "order_block",
    1: "fair_value_gap",
}

STAGES = [
    {
        "name": "base_2020",
        "current_year": 2020,
        "previous_years": [],
        "mode": "train",
    },
    {
        "name": "inc_2021",
        "current_year": 2021,
        "previous_years": [2020],
        "mode": "train",
    },
    {
        "name": "inc_2022",
        "current_year": 2022,
        "previous_years": [2020, 2021],
        "mode": "train",
    },
    {
        "name": "inc_2023",
        "current_year": 2023,
        "previous_years": [2020, 2021, 2022],
        "mode": "train",
    },
    {
        "name": "inc_2024",
        "current_year": 2024,
        "previous_years": [2020, 2021, 2022, 2023],
        "mode": "train",
    },
    {
        "name": "final_test_2025",
        "current_year": 2025,
        "previous_years": [],
        "mode": "test",
    },
]


def reset_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_split_dirs(stage_dir: Path):
    for split in ["train", "valid", "test"]:
        (stage_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (stage_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    (stage_dir / "reports").mkdir(parents=True, exist_ok=True)


def normalize_image_path(path: str) -> Path:
    return Path(path)


def normalize_label_path(path: str) -> Path:
    return Path(path)


def copy_sample(row, stage_dir: Path, split: str):
    image_path = normalize_image_path(row["clean_image_path"])
    label_path = normalize_label_path(row["label_path"])

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if not label_path.exists():
        raise FileNotFoundError(f"Label not found: {label_path}")

    target_image = stage_dir / "images" / split / image_path.name
    target_label = stage_dir / "labels" / split / label_path.name

    shutil.copy2(image_path, target_image)
    shutil.copy2(label_path, target_label)


def split_current_year(rows, valid_ratio: float):
    rows = list(rows)
    random.shuffle(rows)

    if len(rows) <= 1:
        return rows, []

    valid_count = max(1, int(len(rows) * valid_ratio))
    valid_rows = rows[:valid_count]
    train_rows = rows[valid_count:]

    return train_rows, valid_rows


def sample_replay(rows, target_count: int):
    rows = list(rows)

    if target_count <= 0 or not rows:
        return []

    random.shuffle(rows)

    if target_count >= len(rows):
        return rows

    return rows[:target_count]


def write_dataset_yaml(stage_dir: Path, stage_name: str, mode: str):
    yaml_path = stage_dir / "dataset.yaml"

    if mode == "test":
        content = f"""# AI-TDSS Incremental YOLO Dataset - {stage_name}

path: {stage_dir.as_posix()}

train: images/test
val: images/test
test: images/test

names:
  0: order_block
  1: fair_value_gap
"""
    else:
        content = f"""# AI-TDSS Incremental YOLO Dataset - {stage_name}

path: {stage_dir.as_posix()}

train: images/train
val: images/valid
test: images/test

names:
  0: order_block
  1: fair_value_gap
"""

    yaml_path.write_text(content, encoding="utf-8")


def count_objects(label_path: Path):
    if not label_path.exists():
        return 0, 0, 0

    ob_count = 0
    fvg_count = 0

    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        class_id = int(float(line.split()[0]))

        if class_id == 0:
            ob_count += 1
        elif class_id == 1:
            fvg_count += 1

    return ob_count + fvg_count, ob_count, fvg_count


def collect_split_stats(stage_dir: Path):
    stats = []

    for split in ["train", "valid", "test"]:
        image_dir = stage_dir / "images" / split
        label_dir = stage_dir / "labels" / split

        image_count = len(list(image_dir.glob("*.*")))
        label_count = len(list(label_dir.glob("*.txt")))

        total_objects = 0
        total_ob = 0
        total_fvg = 0

        for label_path in label_dir.glob("*.txt"):
            obj_count, ob_count, fvg_count = count_objects(label_path)
            total_objects += obj_count
            total_ob += ob_count
            total_fvg += fvg_count

        stats.append({
            "split": split,
            "image_count": image_count,
            "label_count": label_count,
            "object_count": total_objects,
            "order_block_count": total_ob,
            "fair_value_gap_count": total_fvg,
        })

    return stats


def write_stage_report(stage_dir: Path, stage_name: str, current_year: int, previous_years, mode: str, split_stats, selected_rows):
    report_csv = stage_dir / "reports" / "split_report.csv"

    with report_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "image_id",
            "pair",
            "timeframe",
            "year",
            "start_datetime",
            "end_datetime",
            "split",
            "source_type",
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
                "source_type": row["source_type"],
                "object_count": row["object_count"],
                "ob_count": row["ob_count"],
                "fvg_count": row["fvg_count"],
                "clean_image_path": row["clean_image_path"],
                "label_path": row["label_path"],
            })

    summary = {
        "stage_name": stage_name,
        "mode": mode,
        "current_year": current_year,
        "previous_years": previous_years,
        "replay_ratio": REPLAY_RATIO,
        "valid_ratio": VALID_RATIO,
        "split_stats": split_stats,
    }

    summary_json = stage_dir / "reports" / "summary.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary_md = stage_dir / "reports" / "summary.md"

    lines = []
    lines.append(f"# Incremental YOLO Dataset - {stage_name}")
    lines.append("")
    lines.append("## Stage")
    lines.append("")
    lines.append(f"- Mode: {mode}")
    lines.append(f"- Current year: {current_year}")
    lines.append(f"- Previous replay years: {previous_years if previous_years else 'None'}")
    lines.append(f"- Replay ratio: {REPLAY_RATIO}")
    lines.append(f"- Validation ratio: {VALID_RATIO}")
    lines.append("")
    lines.append("## Split Statistics")
    lines.append("")
    lines.append("| Split | Images | Labels | Objects | Order Blocks | Fair Value Gaps |")
    lines.append("|---|---:|---:|---:|---:|---:|")

    for stat in split_stats:
        lines.append(
            f"| {stat['split']} | {stat['image_count']} | {stat['label_count']} | "
            f"{stat['object_count']} | {stat['order_block_count']} | {stat['fair_value_gap_count']} |"
        )

    summary_md.write_text("\n".join(lines), encoding="utf-8")


def build_stage(df: pd.DataFrame, stage: dict):
    stage_name = stage["name"]
    current_year = stage["current_year"]
    previous_years = stage["previous_years"]
    mode = stage["mode"]

    stage_dir = OUTPUT_ROOT / stage_name
    reset_dir(stage_dir)
    ensure_split_dirs(stage_dir)

    selected_rows = []

    current_rows = df[df["year"] == current_year].to_dict("records")

    if mode == "test":
        for row in current_rows:
            copy_sample(row, stage_dir, "test")
            row_copy = dict(row)
            row_copy["split"] = "test"
            row_copy["source_type"] = "final_test"
            selected_rows.append(row_copy)

    else:
        train_rows, valid_rows = split_current_year(current_rows, VALID_RATIO)

        previous_rows = df[df["year"].isin(previous_years)].to_dict("records")
        replay_target_count = int(len(train_rows) * REPLAY_RATIO)
        replay_rows = sample_replay(previous_rows, replay_target_count)

        for row in train_rows:
            copy_sample(row, stage_dir, "train")
            row_copy = dict(row)
            row_copy["split"] = "train"
            row_copy["source_type"] = "current_year"
            selected_rows.append(row_copy)

        for row in replay_rows:
            copy_sample(row, stage_dir, "train")
            row_copy = dict(row)
            row_copy["split"] = "train"
            row_copy["source_type"] = "replay"
            selected_rows.append(row_copy)

        for row in valid_rows:
            copy_sample(row, stage_dir, "valid")
            row_copy = dict(row)
            row_copy["split"] = "valid"
            row_copy["source_type"] = "current_year_valid"
            selected_rows.append(row_copy)

    write_dataset_yaml(stage_dir, stage_name, mode)

    split_stats = collect_split_stats(stage_dir)
    write_stage_report(
        stage_dir=stage_dir,
        stage_name=stage_name,
        current_year=current_year,
        previous_years=previous_years,
        mode=mode,
        split_stats=split_stats,
        selected_rows=selected_rows,
    )

    return {
        "stage": stage_name,
        "stage_dir": str(stage_dir),
        "split_stats": split_stats,
    }


def main():
    random.seed(SEED)

    if not AUTO_LABEL_REPORT.exists():
        raise FileNotFoundError(f"Auto-label report not found: {AUTO_LABEL_REPORT}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

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
        raise ValueError(f"Missing columns in auto-label report: {missing}")

    all_results = []

    for stage in STAGES:
        result = build_stage(df, stage)
        all_results.append(result)

    index_path = OUTPUT_ROOT / "incremental_dataset_index.md"

    lines = []
    lines.append("# Incremental YOLO Dataset Index")
    lines.append("")
    lines.append("## Source")
    lines.append("")
    lines.append(f"- Auto-label report: {AUTO_LABEL_REPORT}")
    lines.append("- Source dataset: auto_labels_v5_medium")
    lines.append("")
    lines.append("## Stages")
    lines.append("")
    lines.append("| Stage | Train Images | Valid Images | Test Images | Train Objects | Valid Objects | Test Objects |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for result in all_results:
        stats = {item["split"]: item for item in result["split_stats"]}

        train = stats["train"]
        valid = stats["valid"]
        test = stats["test"]

        lines.append(
            f"| {result['stage']} | "
            f"{train['image_count']} | {valid['image_count']} | {test['image_count']} | "
            f"{train['object_count']} | {valid['object_count']} | {test['object_count']} |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- base_2020 uses only 2020 data.")
    lines.append("- inc_2021 to inc_2024 use current-year data plus replay samples from previous years.")
    lines.append("- final_test_2025 is reserved as unseen final test data.")
    lines.append("- YOLOv8n remains a temporary pipeline baseline. Final benchmark targets are YOLOv9, YOLOv11, and YOLOv26.")

    index_path.write_text("\n".join(lines), encoding="utf-8")

    print("Incremental YOLO dataset build finished.")
    print(f"Output root: {OUTPUT_ROOT}")
    print(f"Index      : {index_path}")

    for result in all_results:
        print("")
        print(f"Stage: {result['stage']}")

        for stat in result["split_stats"]:
            print(
                f"  {stat['split']}: "
                f"images={stat['image_count']}, "
                f"objects={stat['object_count']}, "
                f"OB={stat['order_block_count']}, "
                f"FVG={stat['fair_value_gap_count']}"
            )


if __name__ == "__main__":
    main()
