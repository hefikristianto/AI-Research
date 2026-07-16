from pathlib import Path
import shutil
import random
import csv

SOURCE_DIR = Path("ai/datasets/raw/charts")
TARGET_DIR = Path("ai/datasets/annotation/samples/images")
REPORT_PATH = Path("ai/datasets/annotation/samples/sample_selection_report.csv")

SAMPLES_PER_GROUP = 20
RANDOM_SEED = 42

random.seed(RANDOM_SEED)

def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    total_copied = 0

    for pair_dir in sorted(SOURCE_DIR.iterdir()):
        if not pair_dir.is_dir():
            continue

        pair = pair_dir.name

        for tf_dir in sorted(pair_dir.iterdir()):
            if not tf_dir.is_dir():
                continue

            timeframe = tf_dir.name

            for year_dir in sorted(tf_dir.iterdir()):
                if not year_dir.is_dir():
                    continue

                year = year_dir.name
                images = sorted(year_dir.glob("*.png"))

                if not images:
                    continue

                sample_count = min(SAMPLES_PER_GROUP, len(images))
                selected = random.sample(images, sample_count)

                for image_path in selected:
                    target_name = image_path.name
                    target_path = TARGET_DIR / target_name

                    shutil.copy2(image_path, target_path)

                    rows.append({
                        "file_name": target_name,
                        "pair": pair,
                        "timeframe": timeframe,
                        "year": year,
                        "source_path": str(image_path).replace("\\\\", "/"),
                        "target_path": str(target_path).replace("\\\\", "/"),
                        "status": "selected_for_annotation"
                    })

                    total_copied += 1

                print(f"{pair} {timeframe} {year}: selected {sample_count} images")

    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "file_name",
                "pair",
                "timeframe",
                "year",
                "source_path",
                "target_path",
                "status"
            ]
        )
        writer.writeheader()
        writer.writerows(rows)

    print("")
    print("Sample selection finished.")
    print(f"Total copied images: {total_copied}")
    print(f"Report saved to: {REPORT_PATH}")

if __name__ == "__main__":
    main()
