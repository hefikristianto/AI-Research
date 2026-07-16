from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import csv

RAW_DIR = Path("ai/datasets/raw/ohlcv")
OUTPUT_DIR = Path("ai/datasets/annotation/auto_labels_v5")

CLEAN_IMAGE_DIR = OUTPUT_DIR / "images" / "clean"
PREVIEW_IMAGE_DIR = OUTPUT_DIR / "images" / "preview"
YOLO_LABEL_DIR = OUTPUT_DIR / "labels" / "yolo"
REPORT_PATH = OUTPUT_DIR / "reports" / "auto_label_report.csv"

WINDOW_SIZE = 100
STEP_SIZE = 100
MAX_WINDOWS_PER_FILE = 5

IMAGE_WIDTH = 640
IMAGE_HEIGHT = 640

PLOT_LEFT = 40
PLOT_RIGHT = 30
PLOT_TOP = 30
PLOT_BOTTOM = 40

CLASS_ORDER_BLOCK = 0
CLASS_FVG = 1

# =========================
# Detection Config
# =========================

MAX_PAIRS_PER_IMAGE = 2

# Candle 2 harus impulsif.
MIN_IMPULSE_BODY_MULTIPLIER = 1.60
MIN_IMPULSE_RANGE_MULTIPLIER = 1.30
MIN_IMPULSE_BODY_RATIO = 0.55

# Candle OB jangan doji terlalu kecil.
MIN_OB_BODY_RATIO = 0.30

# FVG minimal harus cukup kelihatan.
MIN_GAP_RANGE_MULTIPLIER = 0.12

# FVG terlalu besar biasanya efek spike ekstrem, skip.
MAX_GAP_RANGE_MULTIPLIER = 1.50

# Hindari deteksi terlalu dekat pinggir window.
EDGE_SKIP = 3

# Optional: cek apakah FVG langsung ketutup.
CHECK_FVG_FILL = True
FVG_FORWARD_CHECK = 6
MIN_REMAINING_GAP_RATIO = 0.25

# Box style
CANDLE_BULL = (25, 150, 90)
CANDLE_BEAR = (210, 65, 65)
WICK_COLOR = (35, 35, 35)
BACKGROUND = (255, 255, 255)

OB_BOX = (155, 80, 220)
FVG_BOX = (40, 120, 230)

MIN_OB_BOX_WIDTH_PX = 16
MIN_FVG_BOX_WIDTH_PX = 28
MIN_BOX_HEIGHT_PX = 8

def ensure_dirs():
    CLEAN_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    YOLO_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

def read_ohlcv(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(file_path, sep="\t")

    required = [
        "<DATE>",
        "<TIME>",
        "<OPEN>",
        "<HIGH>",
        "<LOW>",
        "<CLOSE>",
        "<TICKVOL>",
        "<VOL>",
        "<SPREAD>",
    ]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df["datetime"] = pd.to_datetime(
        df["<DATE>"] + " " + df["<TIME>"],
        format="%Y.%m.%d %H:%M:%S",
        errors="coerce",
    )

    df = df.rename(
        columns={
            "<OPEN>": "open",
            "<HIGH>": "high",
            "<LOW>": "low",
            "<CLOSE>": "close",
            "<TICKVOL>": "tick_volume",
            "<VOL>": "volume",
            "<SPREAD>": "spread",
        }
    )

    df = df[
        [
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "volume",
            "spread",
        ]
    ].dropna()

    df = df.sort_values("datetime").reset_index(drop=True)
    return df

def candle_body(candle):
    return abs(candle["close"] - candle["open"])

def candle_range(candle):
    return candle["high"] - candle["low"]

def is_bullish(candle):
    return candle["close"] > candle["open"]

def is_bearish(candle):
    return candle["close"] < candle["open"]

def body_ratio(candle):
    r = candle_range(candle)
    if r <= 0:
        return 0
    return candle_body(candle) / r

def is_bullish_engulf_like(ob, impulse):
    # Tidak harus engulfing textbook sempurna,
    # tapi close impulse minimal menembus open/high OB agar displacement terasa.
    return impulse["close"] > ob["open"] or impulse["close"] > ob["high"]

def is_bearish_engulf_like(ob, impulse):
    # Tidak harus engulfing textbook sempurna,
    # tapi close impulse minimal menembus open/low OB.
    return impulse["close"] < ob["open"] or impulse["close"] < ob["low"]

def is_fvg_still_relevant(window, direction, start_idx, gap_low, gap_high):
    if not CHECK_FVG_FILL:
        return True

    gap_size = gap_high - gap_low
    if gap_size <= 0:
        return False

    future = window.iloc[
        start_idx + 3 : min(len(window), start_idx + 3 + FVG_FORWARD_CHECK)
    ]

    if future.empty:
        return True

    if direction == "bullish":
        # Bullish FVG invalid kalau future low mengisi gap terlalu dalam.
        lowest = future["low"].min()

        if lowest <= gap_low:
            remaining_ratio = 0
        elif lowest >= gap_high:
            remaining_ratio = 1
        else:
            remaining_ratio = (lowest - gap_low) / gap_size

        return remaining_ratio >= MIN_REMAINING_GAP_RATIO

    if direction == "bearish":
        # Bearish FVG invalid kalau future high mengisi gap terlalu dalam.
        highest = future["high"].max()

        if highest >= gap_high:
            remaining_ratio = 0
        elif highest <= gap_low:
            remaining_ratio = 1
        else:
            remaining_ratio = (gap_high - highest) / gap_size

        return remaining_ratio >= MIN_REMAINING_GAP_RATIO

    return True

def detect_paired_ob_fvg(window: pd.DataFrame):
    zones = []

    avg_range = (window["high"] - window["low"]).mean()
    avg_body = (window["close"] - window["open"]).abs().mean()

    if avg_range <= 0 or avg_body <= 0:
        return zones

    candidates = []

    start = EDGE_SKIP
    end = len(window) - 2 - EDGE_SKIP

    for i in range(start, end):
        ob = window.iloc[i]
        impulse = window.iloc[i + 1]
        third = window.iloc[i + 2]

        ob_body_ratio = body_ratio(ob)
        impulse_body = candle_body(impulse)
        impulse_range = candle_range(impulse)
        impulse_body_ratio = body_ratio(impulse)

        if ob_body_ratio < MIN_OB_BODY_RATIO:
            continue

        if impulse_range <= 0:
            continue

        if impulse_body < avg_body * MIN_IMPULSE_BODY_MULTIPLIER:
            continue

        if impulse_range < avg_range * MIN_IMPULSE_RANGE_MULTIPLIER:
            continue

        if impulse_body_ratio < MIN_IMPULSE_BODY_RATIO:
            continue

        # =========================
        # Bullish OB + Bullish FVG
        # =========================
        if is_bearish(ob) and is_bullish(impulse):
            if not is_bullish_engulf_like(ob, impulse):
                continue

            # FVG antara OB candle dan candle ke-3:
            # high OB < low candle ke-3
            if ob["high"] < third["low"]:
                gap_low = ob["high"]
                gap_high = third["low"]
                gap_size = gap_high - gap_low

                if gap_size < avg_range * MIN_GAP_RANGE_MULTIPLIER:
                    continue

                if gap_size > avg_range * MAX_GAP_RANGE_MULTIPLIER:
                    continue

                if not is_fvg_still_relevant(window, "bullish", i, gap_low, gap_high):
                    continue

                score = (
                    impulse_body / avg_body
                    + impulse_body_ratio
                    + gap_size / avg_range
                )

                candidates.append(
                    {
                        "direction": "bullish",
                        "score": score,
                        "ob": {
                            "type": "bullish_ob",
                            "class_id": CLASS_ORDER_BLOCK,
                            "idx": i,
                            "price_low": ob["low"],
                            "price_high": ob["high"],
                        },
                        "fvg": {
                            "type": "bullish_fvg",
                            "class_id": CLASS_FVG,
                            "start_idx": i,
                            "mid_idx": i + 1,
                            "end_idx": i + 2,
                            "price_low": gap_low,
                            "price_high": gap_high,
                        },
                    }
                )

        # =========================
        # Bearish OB + Bearish FVG
        # =========================
        if is_bullish(ob) and is_bearish(impulse):
            if not is_bearish_engulf_like(ob, impulse):
                continue

            # FVG antara OB candle dan candle ke-3:
            # low OB > high candle ke-3
            if ob["low"] > third["high"]:
                gap_low = third["high"]
                gap_high = ob["low"]
                gap_size = gap_high - gap_low

                if gap_size < avg_range * MIN_GAP_RANGE_MULTIPLIER:
                    continue

                if gap_size > avg_range * MAX_GAP_RANGE_MULTIPLIER:
                    continue

                if not is_fvg_still_relevant(window, "bearish", i, gap_low, gap_high):
                    continue

                score = (
                    impulse_body / avg_body
                    + impulse_body_ratio
                    + gap_size / avg_range
                )

                candidates.append(
                    {
                        "direction": "bearish",
                        "score": score,
                        "ob": {
                            "type": "bearish_ob",
                            "class_id": CLASS_ORDER_BLOCK,
                            "idx": i,
                            "price_low": ob["low"],
                            "price_high": ob["high"],
                        },
                        "fvg": {
                            "type": "bearish_fvg",
                            "class_id": CLASS_FVG,
                            "start_idx": i,
                            "mid_idx": i + 1,
                            "end_idx": i + 2,
                            "price_low": gap_low,
                            "price_high": gap_high,
                        },
                    }
                )

    candidates = sorted(candidates, key=lambda item: item["score"], reverse=True)

    selected = []
    used_indices = set()

    for candidate in candidates:
        ob_idx = candidate["ob"]["idx"]
        fvg_mid_idx = candidate["fvg"]["mid_idx"]

        # Hindari zona terlalu nempel / duplicate.
        too_close = False
        for used in used_indices:
            if abs(ob_idx - used) <= 3 or abs(fvg_mid_idx - used) <= 3:
                too_close = True
                break

        if too_close:
            continue

        selected.append(candidate)
        used_indices.add(ob_idx)
        used_indices.add(fvg_mid_idx)

        if len(selected) >= MAX_PAIRS_PER_IMAGE:
            break

    for candidate in selected:
        zones.append(candidate["ob"])
        zones.append(candidate["fvg"])

    return zones

def price_to_y(price: float, price_min: float, price_max: float) -> int:
    plot_height = IMAGE_HEIGHT - PLOT_TOP - PLOT_BOTTOM

    if price_max == price_min:
        return PLOT_TOP + plot_height // 2

    y = PLOT_TOP + ((price_max - price) / (price_max - price_min)) * plot_height
    return int(round(y))

def index_to_x(index: int, total_candles: int) -> int:
    plot_width = IMAGE_WIDTH - PLOT_LEFT - PLOT_RIGHT
    candle_slot = plot_width / total_candles
    x = PLOT_LEFT + (index + 0.5) * candle_slot
    return int(round(x))

def candle_width(total_candles: int) -> int:
    plot_width = IMAGE_WIDTH - PLOT_LEFT - PLOT_RIGHT
    candle_slot = plot_width / total_candles
    return max(2, int(round(candle_slot * 0.55)))

def make_yolo_box(x1, y1, x2, y2):
    x1 = max(0, min(IMAGE_WIDTH - 1, x1))
    x2 = max(0, min(IMAGE_WIDTH - 1, x2))
    y1 = max(0, min(IMAGE_HEIGHT - 1, y1))
    y2 = max(0, min(IMAGE_HEIGHT - 1, y2))

    if x2 < x1:
        x1, x2 = x2, x1

    if y2 < y1:
        y1, y2 = y2, y1

    width = x2 - x1
    height = y2 - y1

    if width <= 1 or height <= 1:
        return None

    x_center = (x1 + x2) / 2 / IMAGE_WIDTH
    y_center = (y1 + y2) / 2 / IMAGE_HEIGHT
    norm_width = width / IMAGE_WIDTH
    norm_height = height / IMAGE_HEIGHT

    return x_center, y_center, norm_width, norm_height

def zone_to_pixels(zone: dict, total_candles: int, price_min: float, price_max: float):
    cw = candle_width(total_candles)

    if zone["class_id"] == CLASS_FVG:
        x1 = index_to_x(zone["start_idx"], total_candles) - cw // 2
        x2 = index_to_x(zone["end_idx"], total_candles) + cw // 2
        min_width = MIN_FVG_BOX_WIDTH_PX
    else:
        x_center = index_to_x(zone["idx"], total_candles)
        x1 = x_center - cw // 2
        x2 = x_center + cw // 2
        min_width = MIN_OB_BOX_WIDTH_PX

    y_top = price_to_y(zone["price_high"], price_min, price_max)
    y_bottom = price_to_y(zone["price_low"], price_min, price_max)

    if x2 < x1:
        x1, x2 = x2, x1

    if y_bottom < y_top:
        y_top, y_bottom = y_bottom, y_top

    current_width = x2 - x1
    if current_width < min_width:
        center_x = (x1 + x2) / 2
        x1 = center_x - min_width / 2
        x2 = center_x + min_width / 2

    current_height = y_bottom - y_top
    if current_height < MIN_BOX_HEIGHT_PX:
        center_y = (y_top + y_bottom) / 2
        y_top = center_y - MIN_BOX_HEIGHT_PX / 2
        y_bottom = center_y + MIN_BOX_HEIGHT_PX / 2

    return int(round(x1)), int(round(y_top)), int(round(x2)), int(round(y_bottom))


def draw_chart(window: pd.DataFrame):
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    price_min = float(window["low"].min())
    price_max = float(window["high"].max())

    padding = (price_max - price_min) * 0.05

    if padding <= 0:
        padding = 1

    price_min -= padding
    price_max += padding

    total = len(window)
    cw = candle_width(total)

    for idx, candle in window.iterrows():
        x = index_to_x(idx, total)

        open_y = price_to_y(candle["open"], price_min, price_max)
        close_y = price_to_y(candle["close"], price_min, price_max)
        high_y = price_to_y(candle["high"], price_min, price_max)
        low_y = price_to_y(candle["low"], price_min, price_max)

        is_bull = candle["close"] >= candle["open"]
        body_color = CANDLE_BULL if is_bull else CANDLE_BEAR

        draw.line((x, high_y, x, low_y), fill=WICK_COLOR, width=1)

        top = min(open_y, close_y)
        bottom = max(open_y, close_y)

        if bottom - top < 2:
            bottom = top + 2

        draw.rectangle(
            (x - cw // 2, top, x + cw // 2, bottom),
            fill=body_color,
            outline=body_color,
        )

    return image, price_min, price_max

def draw_preview(clean_image: Image.Image, zones, total_candles, price_min, price_max):
    preview = clean_image.copy()
    draw = ImageDraw.Draw(preview)

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()

    for zone in zones:
        x1, y1, x2, y2 = zone_to_pixels(zone, total_candles, price_min, price_max)

        if zone["class_id"] == CLASS_ORDER_BLOCK:
            color = OB_BOX
            text = "OB"
        else:
            color = FVG_BOX
            text = "FVG"

        draw.rectangle((x1, y1, x2, y2), outline=color, width=2)
        draw.text((x1, max(0, y1 - 14)), text, fill=color, font=font)

    return preview

def save_yolo_label(label_path: Path, zones, total_candles, price_min, price_max):
    lines = []

    for zone in zones:
        x1, y1, x2, y2 = zone_to_pixels(zone, total_candles, price_min, price_max)
        yolo = make_yolo_box(x1, y1, x2, y2)

        if yolo is None:
            continue

        x_center, y_center, width, height = yolo

        lines.append(
            f"{zone['class_id']} "
            f"{x_center:.6f} "
            f"{y_center:.6f} "
            f"{width:.6f} "
            f"{height:.6f}"
        )

    label_path.write_text("\n".join(lines), encoding="utf-8")
    return len(lines)

def parse_path_info(file_path: Path):
    year = file_path.parent.name
    timeframe = file_path.parent.parent.name
    pair = file_path.parent.parent.parent.name
    return pair, timeframe, year

def process_file(file_path: Path):
    pair, timeframe, year = parse_path_info(file_path)
    df = read_ohlcv(file_path)

    rows = []
    window_counter = 0

    for start in range(0, len(df) - WINDOW_SIZE + 1, STEP_SIZE):
        if MAX_WINDOWS_PER_FILE is not None and window_counter >= MAX_WINDOWS_PER_FILE:
            break

        window = df.iloc[start : start + WINDOW_SIZE].reset_index(drop=True)

        start_dt = window.iloc[0]["datetime"].strftime("%Y%m%d_%H%M%S")
        end_dt = window.iloc[-1]["datetime"].strftime("%Y%m%d_%H%M%S")

        image_id = f"{pair.lower()}_{timeframe.lower()}_{year}_{start_dt}_{window_counter + 1:04d}"

        clean_path = CLEAN_IMAGE_DIR / f"{image_id}.png"
        preview_path = PREVIEW_IMAGE_DIR / f"{image_id}.png"
        label_path = YOLO_LABEL_DIR / f"{image_id}.txt"

        zones = detect_paired_ob_fvg(window)

        clean_image, price_min, price_max = draw_chart(window)
        clean_image.save(clean_path)

        preview_image = draw_preview(clean_image, zones, len(window), price_min, price_max)
        preview_image.save(preview_path)

        object_count = save_yolo_label(
            label_path,
            zones,
            len(window),
            price_min,
            price_max,
        )

        ob_count = len([z for z in zones if z["class_id"] == CLASS_ORDER_BLOCK])
        fvg_count = len([z for z in zones if z["class_id"] == CLASS_FVG])

        rows.append(
            {
                "image_id": image_id,
                "pair": pair,
                "timeframe": timeframe,
                "year": year,
                "start_datetime": str(window.iloc[0]["datetime"]),
                "end_datetime": str(window.iloc[-1]["datetime"]),
                "clean_image_path": str(clean_path).replace("\\", "/"),
                "preview_image_path": str(preview_path).replace("\\", "/"),
                "label_path": str(label_path).replace("\\", "/"),
                "ob_count": ob_count,
                "fvg_count": fvg_count,
                "object_count": object_count,
                "status": "auto_labeled_v5_paired_ob_fvg",
            }
        )

        window_counter += 1

    return rows

def main():
    ensure_dirs()

    csv_files = sorted(RAW_DIR.glob("*/*/*/*.csv"))

    if not csv_files:
        print("No OHLCV CSV files found.")
        return

    all_rows = []

    for file_path in csv_files:
        print(f"Processing: {file_path}")

        try:
            rows = process_file(file_path)
            all_rows.extend(rows)
            print(f"  generated windows: {len(rows)}")
        except Exception as error:
            print(f"  ERROR: {error}")

    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "image_id",
            "pair",
            "timeframe",
            "year",
            "start_datetime",
            "end_datetime",
            "clean_image_path",
            "preview_image_path",
            "label_path",
            "ob_count",
            "fvg_count",
            "object_count",
            "status",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print("")
    print("Auto-label v5 finished.")
    print(f"Total generated windows : {len(all_rows)}")
    print(f"Clean images            : {CLEAN_IMAGE_DIR}")
    print(f"Preview images          : {PREVIEW_IMAGE_DIR}")
    print(f"YOLO labels             : {YOLO_LABEL_DIR}")
    print(f"Report                  : {REPORT_PATH}")

if __name__ == "__main__":
    main()
