from pathlib import Path
import csv


CONFIGS = [
    {
        "model_name": "yolo11s",
        "pred_label_dir": Path("runs/detect/ai/benchmarks/runs/yolo11s_final_test_2025_predict_conf035/labels"),
    },
    {
        "model_name": "yolo11n",
        "pred_label_dir": Path("runs/detect/ai/benchmarks/runs/yolo11n_final_test_2025_predict_conf035/labels"),
    },
]

TUNING_SETTINGS = [
    {
        "name": "strict",
        "conf": 0.35,
        "max_x": 0.08,
        "max_y": 0.25,
    },
    {
        "name": "balanced",
        "conf": 0.30,
        "max_x": 0.10,
        "max_y": 0.28,
    },
    {
        "name": "loose",
        "conf": 0.25,
        "max_x": 0.12,
        "max_y": 0.30,
    },
]

OUTPUT_DIR = Path("ai/benchmarks/reports/yolo11_pairing_tuning")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_OB = 0
CLASS_FVG = 1
MAX_PAIRS_PER_IMAGE = 1


def read_predictions(label_path: Path, conf_threshold: float):
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

        if conf < conf_threshold:
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


def pair_score(ob, fvg, max_x, max_y):
    x_distance = abs(ob["x"] - fvg["x"])
    y_distance = abs(ob["y"] - fvg["y"])

    if x_distance > max_x:
        return None

    if y_distance > max_y:
        return None

    avg_conf = (ob["conf"] + fvg["conf"]) / 2

    x_score = max(0.0, 1.0 - (x_distance / max_x))
    y_score = max(0.0, 1.0 - (y_distance / max_y))

    score = (avg_conf * 0.60) + (x_score * 0.25) + (y_score * 0.15)

    return score, x_distance, y_distance


def run_pairing(model_name, pred_label_dir, setting):
    pairs = []
    files_processed = 0
    detections_kept = 0

    if not pred_label_dir.exists():
        return {
            "model": model_name,
            "setting": setting["name"],
            "error": f"missing dir: {pred_label_dir}",
        }

    for label_path in sorted(pred_label_dir.glob("*.txt")):
        files_processed += 1

        detections = read_predictions(label_path, setting["conf"])
        detections_kept += len(detections)

        obs = [d for d in detections if d["cls"] == CLASS_OB]
        fvgs = [d for d in detections if d["cls"] == CLASS_FVG]

        image_pairs = []

        for ob in obs:
            for fvg in fvgs:
                score_data = pair_score(ob, fvg, setting["max_x"], setting["max_y"])

                if score_data is None:
                    continue

                score, x_distance, y_distance = score_data

                image_pairs.append({
                    "file": label_path.name,
                    "score": score,
                    "quality": quality_label(score, ob["conf"], fvg["conf"]),
                    "direction": estimate_direction(ob, fvg),
                    "x_distance": x_distance,
                    "y_distance": y_distance,
                    "ob_conf": ob["conf"],
                    "fvg_conf": fvg["conf"],
                })

        image_pairs.sort(key=lambda item: item["score"], reverse=True)
        pairs.extend(image_pairs[:MAX_PAIRS_PER_IMAGE])

    quality_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    direction_counts = {}

    for pair in pairs:
        quality_counts[pair["quality"]] += 1
        direction_counts[pair["direction"]] = direction_counts.get(pair["direction"], 0) + 1

    scores = [p["score"] for p in pairs]
    ob_confs = [p["ob_conf"] for p in pairs]
    fvg_confs = [p["fvg_conf"] for p in pairs]

    return {
        "model": model_name,
        "setting": setting["name"],
        "conf_threshold": setting["conf"],
        "max_x_distance": setting["max_x"],
        "max_y_distance": setting["max_y"],
        "files_processed": files_processed,
        "detections_kept": detections_kept,
        "pairs_generated": len(pairs),
        "high": quality_counts["HIGH"],
        "medium": quality_counts["MEDIUM"],
        "low": quality_counts["LOW"],
        "avg_score": sum(scores) / len(scores) if scores else 0,
        "avg_ob_conf": sum(ob_confs) / len(ob_confs) if ob_confs else 0,
        "avg_fvg_conf": sum(fvg_confs) / len(fvg_confs) if fvg_confs else 0,
        "highest_score": max(scores) if scores else 0,
    }


def main():
    results = []

    for config in CONFIGS:
        for setting in TUNING_SETTINGS:
            result = run_pairing(
                model_name=config["model_name"],
                pred_label_dir=config["pred_label_dir"],
                setting=setting,
            )
            results.append(result)

    csv_path = OUTPUT_DIR / "yolo11_pairing_tuning_results.csv"
    md_path = OUTPUT_DIR / "yolo11_pairing_tuning_summary.md"

    fieldnames = [
        "model",
        "setting",
        "conf_threshold",
        "max_x_distance",
        "max_y_distance",
        "files_processed",
        "detections_kept",
        "pairs_generated",
        "high",
        "medium",
        "low",
        "avg_score",
        "avg_ob_conf",
        "avg_fvg_conf",
        "highest_score",
        "error",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in results:
            writer.writerow(row)

    lines = []
    lines.append("# YOLO11 Pairing Threshold Tuning Summary")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    lines.append("| Model | Setting | Conf | Max X | Max Y | Detections | Pairs | HIGH | MEDIUM | LOW | Avg Score | Avg OB Conf | Avg FVG Conf | Highest |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for row in results:
        if "error" in row:
            lines.append(f"| {row['model']} | {row['setting']} | - | - | - | - | - | - | - | - | - | - | - | - |")
            continue

        lines.append(
            f"| {row['model']} | {row['setting']} | {row['conf_threshold']} | {row['max_x_distance']} | {row['max_y_distance']} | "
            f"{row['detections_kept']} | {row['pairs_generated']} | {row['high']} | {row['medium']} | {row['low']} | "
            f"{row['avg_score']:.4f} | {row['avg_ob_conf']:.4f} | {row['avg_fvg_conf']:.4f} | {row['highest_score']:.4f} |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- strict uses the original pairing threshold.")
    lines.append("- balanced slightly relaxes confidence and distance thresholds.")
    lines.append("- loose is used only for diagnostic analysis, not final decision.")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("YOLO11 pairing tuning finished.")
    print(f"CSV     : {csv_path}")
    print(f"Summary : {md_path}")


if __name__ == "__main__":
    main()
