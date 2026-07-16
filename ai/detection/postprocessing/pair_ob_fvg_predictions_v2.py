from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import csv
from collections import Counter


PRED_LABEL_DIR = Path("runs/detect/runs/predict/predict_test_v5_medium_conf035_txt/labels")

OUTPUT_DIR = Path("ai/detection/postprocessing/reports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "ob_fvg_pairs_v2.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "ob_fvg_pairing_summary_v2.md"

CLASS_ORDER_BLOCK = 0
CLASS_FVG = 1

MIN_CONF = {
    CLASS_ORDER_BLOCK: 0.35,
    CLASS_FVG: 0.35,
}

MAX_X_DISTANCE = 0.18
MAX_Y_DISTANCE = 0.35

# V2: hanya ambil top 1 pair per image
MAX_PAIRS_PER_IMAGE = 1


@dataclass
class Detection:
    file: str
    class_id: int
    x: float
    y: float
    w: float
    h: float
    conf: float

    @property
    def class_name(self) -> str:
        if self.class_id == CLASS_ORDER_BLOCK:
            return "order_block"
        if self.class_id == CLASS_FVG:
            return "fair_value_gap"
        return "unknown"

    @property
    def x1(self) -> float:
        return self.x - self.w / 2

    @property
    def x2(self) -> float:
        return self.x + self.w / 2

    @property
    def y1(self) -> float:
        return self.y - self.h / 2

    @property
    def y2(self) -> float:
        return self.y + self.h / 2


@dataclass
class Pair:
    file: str
    ob: Detection
    fvg: Detection
    x_distance: float
    y_distance: float
    direction: str
    score: float
    quality: str


def read_prediction_file(path: Path) -> List[Detection]:
    detections = []

    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()

        if len(parts) < 6:
            continue

        class_id = int(float(parts[0]))
        x = float(parts[1])
        y = float(parts[2])
        w = float(parts[3])
        h = float(parts[4])
        conf = float(parts[5])

        if class_id not in MIN_CONF:
            continue

        if conf < MIN_CONF[class_id]:
            continue

        detections.append(
            Detection(
                file=path.name,
                class_id=class_id,
                x=x,
                y=y,
                w=w,
                h=h,
                conf=conf,
            )
        )

    return detections


def estimate_direction(ob: Detection, fvg: Detection) -> str:
    """
    Estimasi awal berbasis posisi visual YOLO.
    Catatan:
    - Pada koordinat gambar, y kecil = area atas chart, y besar = area bawah chart.
    - Bullish candidate biasanya FVG relatif berada di atas OB setelah impulse naik.
    - Bearish candidate biasanya FVG relatif berada di bawah OB setelah impulse turun.
    """

    if fvg.y < ob.y:
        return "bullish_candidate"

    if fvg.y > ob.y:
        return "bearish_candidate"

    return "neutral_candidate"


def get_quality(score: float, ob_conf: float, fvg_conf: float) -> str:
    if score >= 0.75 and ob_conf >= 0.50 and fvg_conf >= 0.50:
        return "HIGH"

    if score >= 0.65 and ob_conf >= 0.40 and fvg_conf >= 0.40:
        return "MEDIUM"

    return "LOW"


def pair_score(ob: Detection, fvg: Detection) -> Optional[Pair]:
    x_distance = abs(ob.x - fvg.x)
    y_distance = abs(ob.y - fvg.y)

    if x_distance > MAX_X_DISTANCE:
        return None

    if y_distance > MAX_Y_DISTANCE:
        return None

    conf_score = (ob.conf + fvg.conf) / 2
    x_proximity_score = max(0.0, 1.0 - (x_distance / MAX_X_DISTANCE))
    y_proximity_score = max(0.0, 1.0 - (y_distance / MAX_Y_DISTANCE))

    # V2 scoring:
    # confidence masih utama, tapi proximity tetap berpengaruh.
    score = (
        conf_score * 0.65 +
        x_proximity_score * 0.25 +
        y_proximity_score * 0.10
    )

    direction = estimate_direction(ob, fvg)
    quality = get_quality(score, ob.conf, fvg.conf)

    return Pair(
        file=ob.file,
        ob=ob,
        fvg=fvg,
        x_distance=x_distance,
        y_distance=y_distance,
        direction=direction,
        score=score,
        quality=quality,
    )


def build_pairs(detections: List[Detection]) -> List[Pair]:
    order_blocks = [d for d in detections if d.class_id == CLASS_ORDER_BLOCK]
    fvgs = [d for d in detections if d.class_id == CLASS_FVG]

    pairs = []

    for ob in order_blocks:
        for fvg in fvgs:
            pair = pair_score(ob, fvg)
            if pair is not None:
                pairs.append(pair)

    pairs.sort(key=lambda p: p.score, reverse=True)

    # Top 1 pair per image untuk v2.
    return pairs[:MAX_PAIRS_PER_IMAGE]


def write_csv(rows: List[dict]):
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "file",
            "rank",
            "score",
            "quality",
            "direction",
            "x_distance",
            "y_distance",
            "ob_conf",
            "ob_x",
            "ob_y",
            "ob_w",
            "ob_h",
            "fvg_conf",
            "fvg_x",
            "fvg_y",
            "fvg_w",
            "fvg_h",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def write_summary(rows: List[dict], total_files: int, total_detections: int):
    if not rows:
        OUTPUT_SUMMARY.write_text(
            "# OB-FVG Pairing Summary v2\n\nNo pairs generated.\n",
            encoding="utf-8",
        )
        return

    scores = [float(row["score"]) for row in rows]
    ob_confs = [float(row["ob_conf"]) for row in rows]
    fvg_confs = [float(row["fvg_conf"]) for row in rows]
    x_distances = [float(row["x_distance"]) for row in rows]
    y_distances = [float(row["y_distance"]) for row in rows]

    quality_counter = Counter(row["quality"] for row in rows)
    direction_counter = Counter(row["direction"] for row in rows)

    top_rows = sorted(rows, key=lambda r: float(r["score"]), reverse=True)[:10]

    content = []

    content.append("# OB-FVG Pairing Summary v2")
    content.append("")
    content.append("## Purpose")
    content.append("")
    content.append("This report summarizes the second post-processing experiment for selecting the top OB-FVG setup candidate per image.")
    content.append("")
    content.append("## Input")
    content.append("")
    content.append("- Model: YOLOv8n medium baseline")
    content.append("- Dataset: yolo_v5_medium test split")
    content.append("- Prediction confidence threshold: 0.35")
    content.append("- IoU threshold: 0.40")
    content.append("- Classes:")
    content.append("  - 0: order_block")
    content.append("  - 1: fair_value_gap")
    content.append("")
    content.append("## Pairing Rule v2")
    content.append("")
    content.append("- Minimum confidence: 0.35")
    content.append("- Maximum horizontal distance: 0.18")
    content.append("- Maximum vertical distance: 0.35")
    content.append("- Maximum pairs per image: 1")
    content.append("- Direction estimate:")
    content.append("  - bullish_candidate if FVG is visually above OB")
    content.append("  - bearish_candidate if FVG is visually below OB")
    content.append("- Quality label:")
    content.append("  - HIGH: score >= 0.75 and both confidences >= 0.50")
    content.append("  - MEDIUM: score >= 0.65 and both confidences >= 0.40")
    content.append("  - LOW: remaining candidates")
    content.append("")
    content.append("## Result")
    content.append("")
    content.append(f"- Files processed: {total_files}")
    content.append(f"- Detections kept: {total_detections}")
    content.append(f"- Top pairs generated: {len(rows)}")
    content.append(f"- Highest score: {max(scores):.4f}")
    content.append(f"- Lowest score: {min(scores):.4f}")
    content.append(f"- Average score: {sum(scores) / len(scores):.4f}")
    content.append(f"- Average OB confidence: {sum(ob_confs) / len(ob_confs):.4f}")
    content.append(f"- Average FVG confidence: {sum(fvg_confs) / len(fvg_confs):.4f}")
    content.append(f"- Average horizontal distance: {sum(x_distances) / len(x_distances):.4f}")
    content.append(f"- Average vertical distance: {sum(y_distances) / len(y_distances):.4f}")
    content.append("")
    content.append("## Quality Distribution")
    content.append("")

    for key in ["HIGH", "MEDIUM", "LOW"]:
        content.append(f"- {key}: {quality_counter.get(key, 0)}")

    content.append("")
    content.append("## Direction Distribution")
    content.append("")

    for key, value in direction_counter.items():
        content.append(f"- {key}: {value}")

    content.append("")
    content.append("## Top 10 Pairs")
    content.append("")
    content.append("| Rank | File | Score | Quality | Direction | OB Conf | FVG Conf | X Distance |")
    content.append("|---:|---|---:|---|---|---:|---:|---:|")

    for idx, row in enumerate(top_rows, start=1):
        content.append(
            f"| {idx} | {row['file']} | {float(row['score']):.4f} | "
            f"{row['quality']} | {row['direction']} | "
            f"{float(row['ob_conf']):.4f} | {float(row['fvg_conf']):.4f} | "
            f"{float(row['x_distance']):.4f} |"
        )

    content.append("")
    content.append("## Interpretation")
    content.append("")
    content.append("The v2 pairing stage reduces YOLO detections into a single top OB-FVG candidate per image. This makes the output more suitable for downstream scoring and decision-support logic.")
    content.append("")
    content.append("## Next Step")
    content.append("")
    content.append("- Add duplicate/overlap removal before pairing.")
    content.append("- Improve direction validation using OHLCV context instead of image coordinates only.")
    content.append("- Add confluence scoring using trend, freshness, liquidity, and risk-reward feasibility.")
    content.append("- Prepare yearly dataset splits for incremental learning.")

    OUTPUT_SUMMARY.write_text("\n".join(content), encoding="utf-8")


def main():
    if not PRED_LABEL_DIR.exists():
        raise FileNotFoundError(
            f"Prediction label folder not found: {PRED_LABEL_DIR}\n"
            "Cari folder predict txt kamu, lalu ubah PRED_LABEL_DIR di script ini."
        )

    all_rows = []
    total_files = 0
    total_detections = 0

    for label_file in sorted(PRED_LABEL_DIR.glob("*.txt")):
        total_files += 1

        detections = read_prediction_file(label_file)
        total_detections += len(detections)

        pairs = build_pairs(detections)

        for rank, pair in enumerate(pairs, start=1):
            all_rows.append({
                "file": label_file.name,
                "rank": rank,
                "score": f"{pair.score:.6f}",
                "quality": pair.quality,
                "direction": pair.direction,
                "x_distance": f"{pair.x_distance:.6f}",
                "y_distance": f"{pair.y_distance:.6f}",

                "ob_conf": f"{pair.ob.conf:.6f}",
                "ob_x": f"{pair.ob.x:.6f}",
                "ob_y": f"{pair.ob.y:.6f}",
                "ob_w": f"{pair.ob.w:.6f}",
                "ob_h": f"{pair.ob.h:.6f}",

                "fvg_conf": f"{pair.fvg.conf:.6f}",
                "fvg_x": f"{pair.fvg.x:.6f}",
                "fvg_y": f"{pair.fvg.y:.6f}",
                "fvg_w": f"{pair.fvg.w:.6f}",
                "fvg_h": f"{pair.fvg.h:.6f}",
            })

    write_csv(all_rows)
    write_summary(all_rows, total_files, total_detections)

    print("OB-FVG pairing v2 finished.")
    print(f"Prediction folder : {PRED_LABEL_DIR}")
    print(f"Files processed   : {total_files}")
    print(f"Detections kept   : {total_detections}")
    print(f"Top pairs generated: {len(all_rows)}")
    print(f"CSV report        : {OUTPUT_CSV}")
    print(f"Summary report    : {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
