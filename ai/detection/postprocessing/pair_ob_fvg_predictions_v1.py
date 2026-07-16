from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import csv
import math


# Ubah path ini kalau output predict kamu beda.
PRED_LABEL_DIR = Path("runs/detect/runs/predict/predict_test_v5_medium_conf035_txt/labels")

OUTPUT_DIR = Path("ai/detection/postprocessing/reports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "ob_fvg_pairs_v1.csv"

CLASS_ORDER_BLOCK = 0
CLASS_FVG = 1

MIN_CONF = {
    CLASS_ORDER_BLOCK: 0.35,
    CLASS_FVG: 0.35,
}

# Jarak horizontal maksimum antara center OB dan FVG.
# Karena format YOLO normalized 0-1, 0.15 berarti 15% lebar gambar.
MAX_X_DISTANCE = 0.18

# Maksimal pair per gambar.
MAX_PAIRS_PER_IMAGE = 3


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
    score: float


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


def pair_score(ob: Detection, fvg: Detection) -> Optional[Pair]:
    x_distance = abs(ob.x - fvg.x)
    y_distance = abs(ob.y - fvg.y)

    if x_distance > MAX_X_DISTANCE:
        return None

    # Confidence gabungan.
    conf_score = (ob.conf + fvg.conf) / 2

    # Semakin dekat secara horizontal semakin bagus.
    x_proximity_score = max(0.0, 1.0 - (x_distance / MAX_X_DISTANCE))

    # Sedikit penalti kalau jarak vertikal terlalu jauh.
    y_proximity_score = max(0.0, 1.0 - min(y_distance, 0.50) / 0.50)

    # Score awal sederhana.
    score = (
        conf_score * 0.60 +
        x_proximity_score * 0.30 +
        y_proximity_score * 0.10
    )

    return Pair(
        file=ob.file,
        ob=ob,
        fvg=fvg,
        x_distance=x_distance,
        y_distance=y_distance,
        score=score,
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

    # Hindari satu OB/FVG dipakai berkali-kali.
    selected = []
    used_ob = set()
    used_fvg = set()

    for pair in pairs:
        ob_key = (pair.ob.x, pair.ob.y, pair.ob.w, pair.ob.h)
        fvg_key = (pair.fvg.x, pair.fvg.y, pair.fvg.w, pair.fvg.h)

        if ob_key in used_ob or fvg_key in used_fvg:
            continue

        selected.append(pair)
        used_ob.add(ob_key)
        used_fvg.add(fvg_key)

        if len(selected) >= MAX_PAIRS_PER_IMAGE:
            break

    return selected


def main():
    if not PRED_LABEL_DIR.exists():
        raise FileNotFoundError(
            f"Prediction label folder not found: {PRED_LABEL_DIR}\n"
            "Cari folder predict txt kamu, lalu ubah PRED_LABEL_DIR di script ini."
        )

    all_rows = []
    total_files = 0
    total_detections = 0
    total_pairs = 0

    for label_file in sorted(PRED_LABEL_DIR.glob("*.txt")):
        total_files += 1

        detections = read_prediction_file(label_file)
        total_detections += len(detections)

        pairs = build_pairs(detections)
        total_pairs += len(pairs)

        for rank, pair in enumerate(pairs, start=1):
            all_rows.append({
                "file": label_file.name,
                "rank": rank,
                "score": pair.score,
                "x_distance": pair.x_distance,
                "y_distance": pair.y_distance,

                "ob_conf": pair.ob.conf,
                "ob_x": pair.ob.x,
                "ob_y": pair.ob.y,
                "ob_w": pair.ob.w,
                "ob_h": pair.ob.h,

                "fvg_conf": pair.fvg.conf,
                "fvg_x": pair.fvg.x,
                "fvg_y": pair.fvg.y,
                "fvg_w": pair.fvg.w,
                "fvg_h": pair.fvg.h,
            })

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "file", "rank", "score", "x_distance", "y_distance",
            "ob_conf", "ob_x", "ob_y", "ob_w", "ob_h",
            "fvg_conf", "fvg_x", "fvg_y", "fvg_w", "fvg_h",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in all_rows:
            writer.writerow(row)

    print("OB-FVG pairing finished.")
    print(f"Prediction folder : {PRED_LABEL_DIR}")
    print(f"Files processed   : {total_files}")
    print(f"Detections kept   : {total_detections}")
    print(f"Pairs generated   : {total_pairs}")
    print(f"Report            : {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
