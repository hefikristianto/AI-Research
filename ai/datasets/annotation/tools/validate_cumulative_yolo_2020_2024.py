from pathlib import Path

ROOT = Path("ai/datasets/annotation/exports/cumulative_yolo_2020_2024")

VALID_CLASSES = {0, 1}
SPLITS = ["train", "valid", "test"]


def validate_label_file(path: Path):
    errors = []
    total = 0
    ob = 0
    fvg = 0

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

        total += 1

        if cls == 0:
            ob += 1
        elif cls == 1:
            fvg += 1

    return errors, total, ob, fvg


def main():
    errors = []
    stats = []

    dataset_yaml = ROOT / "dataset.yaml"

    if not dataset_yaml.exists():
        errors.append(f"Missing dataset.yaml: {dataset_yaml}")

    for split in SPLITS:
        image_dir = ROOT / "images" / split
        label_dir = ROOT / "labels" / split

        split_errors = []

        if not image_dir.exists():
            split_errors.append(f"Missing image dir: {image_dir}")

        if not label_dir.exists():
            split_errors.append(f"Missing label dir: {label_dir}")

        images = sorted(image_dir.glob("*.*")) if image_dir.exists() else []
        labels = sorted(label_dir.glob("*.txt")) if label_dir.exists() else []

        image_stems = {p.stem for p in images}
        label_stems = {p.stem for p in labels}

        for stem in sorted(image_stems - label_stems):
            split_errors.append(f"{split}: missing label for image {stem}")

        for stem in sorted(label_stems - image_stems):
            split_errors.append(f"{split}: missing image for label {stem}")

        object_count = 0
        ob_count = 0
        fvg_count = 0

        for label_path in labels:
            label_errors, total, ob, fvg = validate_label_file(label_path)
            split_errors.extend(label_errors)
            object_count += total
            ob_count += ob
            fvg_count += fvg

        errors.extend(split_errors)

        stats.append({
            "split": split,
            "images": len(images),
            "labels": len(labels),
            "objects": object_count,
            "ob": ob_count,
            "fvg": fvg_count,
            "errors": len(split_errors),
        })

    report_dir = ROOT / "validation_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = report_dir / "cumulative_validation_report.csv"
    md_path = report_dir / "cumulative_validation_summary.md"

    with csv_path.open("w", encoding="utf-8") as f:
        f.write("split,images,labels,objects,order_blocks,fair_value_gaps,errors\n")

        for stat in stats:
            f.write(
                f"{stat['split']},{stat['images']},{stat['labels']},"
                f"{stat['objects']},{stat['ob']},{stat['fvg']},{stat['errors']}\n"
            )

    lines = []
    lines.append("# Cumulative YOLO Dataset Validation")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    lines.append(f"- Total errors: {len(errors)}")
    lines.append("")
    lines.append("## Statistics")
    lines.append("")
    lines.append("| Split | Images | Labels | Objects | OB | FVG | Errors |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for stat in stats:
        lines.append(
            f"| {stat['split']} | {stat['images']} | {stat['labels']} | "
            f"{stat['objects']} | {stat['ob']} | {stat['fvg']} | {stat['errors']} |"
        )

    if errors:
        lines.append("")
        lines.append("## Errors")
        lines.append("")

        for error in errors:
            lines.append(f"- {error}")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Cumulative dataset validation finished.")
    print(f"Total errors : {len(errors)}")
    print(f"CSV report   : {csv_path}")
    print(f"Summary      : {md_path}")

    if len(errors) == 0:
        print("")
        print("Validation PASS.")
    else:
        print("")
        print("Validation FAILED. Open the summary report.")


if __name__ == "__main__":
    main()
