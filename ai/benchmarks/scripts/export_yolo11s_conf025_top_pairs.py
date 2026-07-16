from pathlib import Path
import csv
from PIL import Image, ImageDraw, ImageFont


PAIR_CSV = Path(
    "ai/benchmarks/reports/yolo11s_pairing_conf025/"
    "yolo11s_conf025_ob_fvg_pairs_v2.csv"
)

IMAGE_DIR = Path(
    "ai/datasets/annotation/exports/"
    "cumulative_yolo_2020_2024/images/test"
)

OUTPUT_DIR = Path(
    "ai/benchmarks/reports/"
    "yolo11s_pairing_conf025/visual_review_top10"
)

TOP_N = 10

OB_COLOR = "red"
FVG_COLOR = "blue"
TEXT_COLOR = "white"
TEXT_BG = "black"


def find_image(stem: str):
    extensions = [".png", ".jpg", ".jpeg", ".webp"]

    for extension in extensions:
        candidate = IMAGE_DIR / f"{stem}{extension}"

        if candidate.exists():
            return candidate

    return None


def yolo_to_box(x, y, w, h, image_width, image_height):
    center_x = x * image_width
    center_y = y * image_height
    box_width = w * image_width
    box_height = h * image_height

    x1 = center_x - box_width / 2
    y1 = center_y - box_height / 2
    x2 = center_x + box_width / 2
    y2 = center_y + box_height / 2

    return (
        int(max(0, x1)),
        int(max(0, y1)),
        int(min(image_width - 1, x2)),
        int(min(image_height - 1, y2)),
    )


def draw_label(draw, position, text):
    x, y = position

    bbox = draw.textbbox((x, y), text=text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    draw.rectangle(
        [
            x,
            y,
            x + text_width + 8,
            y + text_height + 6,
        ],
        fill=TEXT_BG,
    )

    draw.text(
        (x + 4, y + 3),
        text,
        fill=TEXT_COLOR,
    )


def main():
    if not PAIR_CSV.exists():
        raise FileNotFoundError(f"Pair CSV not found: {PAIR_CSV}")

    if not IMAGE_DIR.exists():
        raise FileNotFoundError(f"Image directory not found: {IMAGE_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with PAIR_CSV.open("r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    rows.sort(
        key=lambda row: float(row["score"]),
        reverse=True,
    )

    selected = rows[:TOP_N]
    report_rows = []

    for index, row in enumerate(selected, start=1):
        label_filename = row["file"]
        image_stem = Path(label_filename).stem

        image_path = find_image(image_stem)

        if image_path is None:
            print(f"Image not found for: {label_filename}")
            continue

        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)

        width, height = image.size

        ob_box = yolo_to_box(
            float(row["ob_x"]),
            float(row["ob_y"]),
            float(row["ob_w"]),
            float(row["ob_h"]),
            width,
            height,
        )

        fvg_box = yolo_to_box(
            float(row["fvg_x"]),
            float(row["fvg_y"]),
            float(row["fvg_w"]),
            float(row["fvg_h"]),
            width,
            height,
        )

        draw.rectangle(
            ob_box,
            outline=OB_COLOR,
            width=3,
        )

        draw.rectangle(
            fvg_box,
            outline=FVG_COLOR,
            width=3,
        )

        draw_label(
            draw,
            (ob_box[0], max(0, ob_box[1] - 22)),
            f"OB {float(row['ob_conf']):.2f}",
        )

        draw_label(
            draw,
            (fvg_box[0], max(0, fvg_box[1] - 22)),
            f"FVG {float(row['fvg_conf']):.2f}",
        )

        header_text = (
            f"Rank {index} | "
            f"Score {float(row['score']):.4f} | "
            f"{row['quality']} | "
            f"{row['direction']}"
        )

        draw.rectangle(
            [0, 0, width, 28],
            fill=TEXT_BG,
        )

        draw.text(
            (8, 7),
            header_text,
            fill=TEXT_COLOR,
        )

        output_filename = (
            f"rank_{index:02d}_"
            f"{image_stem}_"
            f"score_{float(row['score']):.4f}.jpg"
        )

        output_path = OUTPUT_DIR / output_filename
        image.save(output_path, quality=95)

        report_rows.append({
            "rank": index,
            "file": label_filename,
            "image": str(image_path),
            "output": str(output_path),
            "score": row["score"],
            "quality": row["quality"],
            "direction": row["direction"],
            "ob_conf": row["ob_conf"],
            "fvg_conf": row["fvg_conf"],
            "x_distance": row["x_distance"],
            "y_distance": row["y_distance"],
        })

    report_csv = OUTPUT_DIR / "visual_review_index.csv"

    with report_csv.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        fieldnames = [
            "rank",
            "file",
            "image",
            "output",
            "score",
            "quality",
            "direction",
            "ob_conf",
            "fvg_conf",
            "x_distance",
            "y_distance",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(report_rows)

    summary_path = OUTPUT_DIR / "visual_review_summary.md"

    lines = []
    lines.append("# YOLO11s Conf025 Top Pair Visual Review")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append("- Model: YOLO11s 50e")
    lines.append("- Prediction confidence: 0.25")
    lines.append("- Pairing confidence: 0.25")
    lines.append(f"- Top pairs exported: {len(report_rows)}")
    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append("- Red box: Order Block")
    lines.append("- Blue box: Fair Value Gap")
    lines.append("")
    lines.append("## Exported Pairs")
    lines.append("")
    lines.append(
        "| Rank | File | Score | Quality | Direction | "
        "OB Conf | FVG Conf |"
    )
    lines.append(
        "|---:|---|---:|---|---|---:|---:|"
    )

    for row in report_rows:
        lines.append(
            f"| {row['rank']} | {row['file']} | "
            f"{float(row['score']):.4f} | "
            f"{row['quality']} | "
            f"{row['direction']} | "
            f"{float(row['ob_conf']):.4f} | "
            f"{float(row['fvg_conf']):.4f} |"
        )

    summary_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("YOLO11s visual review export finished.")
    print(f"Images exported : {len(report_rows)}")
    print(f"Output folder   : {OUTPUT_DIR}")
    print(f"Index           : {report_csv}")
    print(f"Summary         : {summary_path}")


if __name__ == "__main__":
    main()
