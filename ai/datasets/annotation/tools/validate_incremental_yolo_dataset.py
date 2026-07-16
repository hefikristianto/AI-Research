from pathlib import Path
import yaml

ROOT = Path("ai/datasets/annotation/exports/incremental_yolo")

STAGES = [
    "base_2020",
    "inc_2021",
    "inc_2022",
    "inc_2023",
    "inc_2024",
    "final_test_2025",
]

VALID_CLASSES = {0, 1}

def validate_label_file(path: Path):
    errors = []
    object_count = 0
    ob_count = 0
    fvg_count = 0

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue

        parts = line.strip().split()

        if len(parts) != 5:
            errors.append(f"{path}: line {line_no}: expected 5 values, got {len(parts)}")
            continue

        try:
            cls = int(float(parts[0]))
            x, y, w, h = map(float, parts[1:])
        except ValueError:
            errors.append(f"{path}: line {line_no}: invalid numeric value")
            continue

        if cls not in VALID_CLASSES:
            errors.append(f"{path}: line {line_no}: invalid class {cls}")

        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            errors.append(f"{path}: line {line_no}: invalid bbox {x}, {y}, {w}, {h}")

        object_count += 1

        if cls == 0:
            ob_count += 1
        elif cls == 1:
            fvg_count += 1

    return errors, object_count, ob_count, fvg_count


def validate_stage(stage: str):
    stage_dir = ROOT / stage

    if not stage_dir.exists():
        return {
            "stage": stage,
            "errors": [f"Stage folder missing: {stage_dir}"],
            "stats": [],
        }

    dataset_yaml = stage_dir / "dataset.yaml"

    errors = []

    if not dataset_yaml.exists():
        errors.append(f"Missing dataset.yaml: {dataset_yaml}")

    stats = []

    for split in ["train", "valid", "test"]:
        image_dir = stage_dir / "images" / split
        label_dir = stage_dir / "labels" / split

        split_errors = []

        if not image_dir.exists():
            split_errors.append(f"Missing image dir: {image_dir}")

        if not label_dir.exists():
            split_errors.append(f"Missing label dir: {label_dir}")

        images = sorted([p for p in image_dir.glob("*.*")]) if image_dir.exists() else []
        labels = sorted([p for p in label_dir.glob("*.txt")]) if label_dir.exists() else []

        image_stems = {p.stem for p in images}
        label_stems = {p.stem for p in labels}

        missing_labels = sorted(image_stems - label_stems)
        missing_images = sorted(label_stems - image_stems)

        for stem in missing_labels:
            split_errors.append(f"{stage}/{split}: missing label for image {stem}")

        for stem in missing_images:
            split_errors.append(f"{stage}/{split}: missing image for label {stem}")

        total_objects = 0
        total_ob = 0
        total_fvg = 0

        for label_path in labels:
            label_errors, object_count, ob_count, fvg_count = validate_label_file(label_path)
            split_errors.extend(label_errors)
            total_objects += object_count
            total_ob += ob_count
            total_fvg += fvg_count

        errors.extend(split_errors)

        stats.append({
            "split": split,
            "images": len(images),
            "labels": len(labels),
            "objects": total_objects,
            "order_blocks": total_ob,
            "fair_value_gaps": total_fvg,
            "errors": len(split_errors),
        })

    return {
        "stage": stage,
        "errors": errors,
        "stats": stats,
    }


def main():
    all_results = []
    total_errors = 0

    for stage in STAGES:
        result = validate_stage(stage)
        all_results.append(result)
        total_errors += len(result["errors"])

    report_dir = ROOT / "validation_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = report_dir / "incremental_validation_report.csv"
    md_path = report_dir / "incremental_validation_summary.md"

    with csv_path.open("w", encoding="utf-8") as f:
        f.write("stage,split,images,labels,objects,order_blocks,fair_value_gaps,errors\n")

        for result in all_results:
            for stat in result["stats"]:
                f.write(
                    f"{result['stage']},{stat['split']},{stat['images']},{stat['labels']},"
                    f"{stat['objects']},{stat['order_blocks']},{stat['fair_value_gaps']},{stat['errors']}\n"
                )

    lines = []
    lines.append("# Incremental YOLO Dataset Validation")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    lines.append(f"- Total stages: {len(STAGES)}")
    lines.append(f"- Total errors: {total_errors}")
    lines.append("")
    lines.append("## Stage Statistics")
    lines.append("")
    lines.append("| Stage | Split | Images | Labels | Objects | OB | FVG | Errors |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")

    for result in all_results:
        for stat in result["stats"]:
            lines.append(
                f"| {result['stage']} | {stat['split']} | {stat['images']} | {stat['labels']} | "
                f"{stat['objects']} | {stat['order_blocks']} | {stat['fair_value_gaps']} | {stat['errors']} |"
            )

    if total_errors > 0:
        lines.append("")
        lines.append("## Errors")
        lines.append("")

        for result in all_results:
            for error in result["errors"]:
                lines.append(f"- {error}")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Incremental dataset validation finished.")
    print(f"Total errors : {total_errors}")
    print(f"CSV report   : {csv_path}")
    print(f"Summary      : {md_path}")

    if total_errors > 0:
        print("")
        print("Errors found. Open the summary report.")
    else:
        print("")
        print("Validation PASS.")


if __name__ == "__main__":
    main()
