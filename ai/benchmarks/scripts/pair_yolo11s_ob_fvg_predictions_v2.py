from pathlib import Path
import csv
import math


PRED_LABEL_DIR = Path("runs/detect/ai/benchmarks/runs/yolo11s_final_test_2025_predict_conf035/labels")

OUTPUT_DIR = Path("ai/benchmarks/reports/yolo11s_pairing")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "yolo11s_ob_fvg_pairs_v2.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "yolo11s_ob_fvg_pairing_summary_v2.md"

CONF_THRESHOLD = 0.35
MAX_X_DISTANCE = 0.08
MAX_Y_DISTANCE = 0.25
MAX_PAIRS_PER_IMAGE = 1

CLASS_OB = 0
CLASS_FVG = 1


def read_predictions(label_path: Path):
    detections = []

    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        parts = line.strip().split()

        if len(parts) < 6:
            continue

        cls = int(float(parts[0]))
        x = float(parts[1])
        y = float(parts[2])
        w = float(parts[3])
        h = float(parts[4])
        conf = float(parts[5])

        if conf < CONF_THRESHOLD:
            continue

        detections.append({
            "cls": cls,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "conf": conf,
        })

    return detections


def estimate_direction(ob, fvg):
    if fvg["y"] < ob["y"]:
        return "bullish_candidate"
    if fvg["y"] > ob["y"]:
        return "bearish_candidate"
    return "neutral_candidate"


def quality_label(score, ob_conf, fvg_conf):
    if score >= 0.75 and ob_conf >= 0.50 and fvg_conf >= 0.50:
        return "HIGH"

    if score >= 0.65 and ob_conf >= 0.40 and fvg_conf >= 0.40:
        return "MEDIUM"

    return "LOW"


def pair_score(ob, fvg):
    x_distance = abs(ob["x"] - fvg["x"])
    y_distance = abs(ob["y"] - fvg["y"])

    if x_distance > MAX_X_DISTANCE:
        return None

    if y_distance > MAX_Y_DISTANCE:
        return None

    avg_conf = (ob["conf"] + fvg["conf"]) / 2

    x_score = max(0.0, 1.0 - (x_distance / MAX_X_DISTANCE))
    y_score = max(0.0, 1.0 - (y_distance / MAX_Y_DISTANCE))

    score = (avg_conf * 0.60) + (x_score * 0.25) + (y_score * 0.15)

    return {
        "score": score,
        "x_distance": x_distance,
        "y_distance": y_distance,
    }


def main():
    if not PRED_LABEL_DIR.exists():
        raise FileNotFoundError(f"Prediction label directory not found: {PRED_LABEL_DIR}")

    all_pairs = []
    files_processed = 0
    detections_kept = 0

    for label_path in sorted(PRED_LABEL_DIR.glob("*.txt")):
        files_processed += 1

        detections = read_predictions(label_path)
        detections_kept += len(detections)

        obs = [d for d in detections if d["cls"] == CLASS_OB]
        fvgs = [d for d in detections if d["cls"] == CLASS_FVG]

        image_pairs = []

        for ob in obs:
            for fvg in fvgs:
                score_data = pair_score(ob, fvg)

                if score_data is None:
                    continue

                direction = estimate_direction(ob, fvg)
                score = score_data["score"]

                image_pairs.append({
                    "file": label_path.name,
                    "score": score,
                    "quality": quality_label(score, ob["conf"], fvg["conf"]),
                    "direction": direction,
                    "x_distance": score_data["x_distance"],
                    "y_distance": score_data["y_distance"],
                    "ob_conf": ob["conf"],
                    "ob_x": ob["x"],
                    "ob_y": ob["y"],
                    "ob_w": ob["w"],
                    "ob_h": ob["h"],
                    "fvg_conf": fvg["conf"],
                    "fvg_x": fvg["x"],
                    "fvg_y": fvg["y"],
                    "fvg_w": fvg["w"],
                    "fvg_h": fvg["h"],
                })

        image_pairs.sort(key=lambda item: item["score"], reverse=True)

        for rank, pair in enumerate(image_pairs[:MAX_PAIRS_PER_IMAGE], start=1):
            pair["rank"] = rank
            all_pairs.append(pair)

    all_pairs.sort(key=lambda item: item["score"], reverse=True)

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

        for pair in all_pairs:
            writer.writerow(pair)

    quality_counts = {}
    direction_counts = {}

    for pair in all_pairs:
        quality_counts[pair["quality"]] = quality_counts.get(pair["quality"], 0) + 1
        direction_counts[pair["direction"]] = direction_counts.get(pair["direction"], 0) + 1

    lines = []
    lines.append("# YOLO11s OB-FVG Pairing v2 Summary")
    lines.append("")
    lines.append("## Input")
    lines.append("")
    lines.append(f"- Prediction labels: {PRED_LABEL_DIR}")
    lines.append(f"- Confidence threshold: {CONF_THRESHOLD}")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    lines.append(f"- Files processed: {files_processed}")
    lines.append(f"- Detections kept: {detections_kept}")
    lines.append(f"- Top pairs generated: {len(all_pairs)}")
    lines.append("")
    lines.append("## Quality Distribution")
    lines.append("")

    if quality_counts:
        for key, value in sorted(quality_counts.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No pairs generated")

    lines.append("")
    lines.append("## Direction Distribution")
    lines.append("")

    if direction_counts:
        for key, value in sorted(direction_counts.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No directions generated")

    if all_pairs:
        lines.append("")
        lines.append("## Score Summary")
        lines.append("")
        scores = [p["score"] for p in all_pairs]
        ob_confs = [p["ob_conf"] for p in all_pairs]
        fvg_confs = [p["fvg_conf"] for p in all_pairs]

        lines.append(f"- Highest score: {max(scores):.4f}")
        lines.append(f"- Lowest score: {min(scores):.4f}")
        lines.append(f"- Average score: {sum(scores) / len(scores):.4f}")
        lines.append(f"- Average OB confidence: {sum(ob_confs) / len(ob_confs):.4f}")
        lines.append(f"- Average FVG confidence: {sum(fvg_confs) / len(fvg_confs):.4f}")

    OUTPUT_SUMMARY.write_text("\n".join(lines), encoding="utf-8")

    print("YOLO11s pairing finished.")
    print(f"Files processed : {files_processed}")
    print(f"Detections kept : {detections_kept}")
    print(f"Pairs generated : {len(all_pairs)}")
    print(f"CSV             : {OUTPUT_CSV}")
    print(f"Summary         : {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
