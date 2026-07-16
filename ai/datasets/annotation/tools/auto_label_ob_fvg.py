from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import csv
import math

RAW_DIR = Path("ai/datasets/raw/ohlcv")
OUTPUT_DIR = Path("ai/datasets/annotation/auto_labels")

CLEAN_IMAGE_DIR = OUTPUT_DIR / "images" / "clean"
PREVIEW_IMAGE_DIR = OUTPUT_DIR / "images" / "preview"
YOLO_LABEL_DIR = OUTPUT_DIR / "labels" / "yolo"
REPORT_PATH = OUTPUT_DIR / "reports" / "auto_label_report.csv"

WINDOW_SIZE = 100
STEP_SIZE = 100

# Untuk test awal biar tidak langsung bikin ribuan file.
# Nanti kalau rule sudah oke, ubah ke 50 atau None.
MAX_WINDOWS_PER_FILE = 5

IMAGE_WIDTH = 640
IMAGE_HEIGHT = 640

PLOT_LEFT = 40
PLOT_RIGHT = 30
PLOT_TOP = 30
PLOT_BOTTOM = 40

CLASS_ORDER_BLOCK = 0
CLASS_FVG = 1

MIN_GAP_RANGE_MULTIPLIER = 0.18
MIN_IMPULSE_BODY_MULTIPLIER = 1.60

MAX_FVG_PER_IMAGE = 2
MAX_OB_PER_IMAGE = 2

MIN_IMPULSE_RANGE_MULTIPLIER = 1.30
MIN_BODY_TO_RANGE_RATIO = 0.55
MAX_GAP_RANGE_MULTIPLIER = 1.20
MAX_OB_RANGE_MULTIPLIER = 2.20
MIN_OB_BODY_MULTIPLIER = 0.35
FVG_FORWARD_FILL_CHECK = 6
FVG_MIN_REMAINING_RATIO = 0.35
OB_MAX_LOOKBACK = 2
EDGE_CANDLE_SKIP = 3


CANDLE_BULL = (25, 150, 90)
CANDLE_BEAR = (210, 65, 65)
WICK_COLOR = (35, 35, 35)
BACKGROUND = (255, 255, 255)

OB_BOX = (155, 80, 220)
FVG_BOX = (40, 120, 230)

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

def detect_fvg(window: pd.DataFrame):
    zones = []

    avg_range = (window["high"] - window["low"]).mean()
    avg_body = (window["close"] - window["open"]).abs().mean()

    if avg_range <= 0 or avg_body <= 0:
        return zones

    # Skip pinggir window supaya zona tidak muncul dari candle yang konteksnya kepotong.
    start_i = EDGE_CANDLE_SKIP
    end_i = len(window) - 2 - EDGE_CANDLE_SKIP

    for i in range(start_i, end_i):
        c1 = window.iloc[i]
        c2 = window.iloc[i + 1]
        c3 = window.iloc[i + 2]

        c2_range = c2["high"] - c2["low"]
        c2_body = abs(c2["close"] - c2["open"])

        if c2_range <= 0:
            continue

        body_ratio = c2_body / c2_range

        # Candle tengah harus impulsif dan body-nya dominan.
        if c2_body < avg_body * MIN_IMPULSE_BODY_MULTIPLIER:
            continue

        if c2_range < avg_range * MIN_IMPULSE_RANGE_MULTIPLIER:
            continue

        if body_ratio < MIN_BODY_TO_RANGE_RATIO:
            continue

        # Bullish FVG:
        # high candle 1 < low candle 3
        if c1["high"] < c3["low"] and c2["close"] > c2["open"]:
            gap_low = c1["high"]
            gap_high = c3["low"]
            gap_size = gap_high - gap_low

            if gap_size < avg_range * MIN_GAP_RANGE_MULTIPLIER:
                continue

            # Skip gap ekstrem yang biasanya muncul karena wick/spike tidak natural.
            if gap_size > avg_range * MAX_GAP_RANGE_MULTIPLIER:
                continue

            # Cek apakah FVG langsung keisi setelah terbentuk.
            future = window.iloc[i + 3 : min(len(window), i + 3 + FVG_FORWARD_FILL_CHECK)]
            if not future.empty:
                lowest_after = future["low"].min()
                remaining = max(0, gap_high - max(lowest_after, gap_low))
                remaining_ratio = remaining / gap_size

                if remaining_ratio < FVG_MIN_REMAINING_RATIO:
                    continue

            zones.append(
                {
                    "type": "bullish_fvg",
                    "class_id": CLASS_FVG,
                    "start_idx": i,
                    "mid_idx": i + 1,
                    "end_idx": i + 2,
                    "price_low": gap_low,
                    "price_high": gap_high,
                    "score": (gap_size / avg_range) + body_ratio,
                }
            )

        # Bearish FVG:
        # low candle 1 > high candle 3
        if c1["low"] > c3["high"] and c2["close"] < c2["open"]:
            gap_low = c3["high"]
            gap_high = c1["low"]
            gap_size = gap_high - gap_low

            if gap_size < avg_range * MIN_GAP_RANGE_MULTIPLIER:
                continue

            # Skip gap ekstrem yang biasanya muncul karena wick/spike tidak natural.
            if gap_size > avg_range * MAX_GAP_RANGE_MULTIPLIER:
                continue

            # Cek apakah FVG langsung keisi setelah terbentuk.
            future = window.iloc[i + 3 : min(len(window), i + 3 + FVG_FORWARD_FILL_CHECK)]
            if not future.empty:
                highest_after = future["high"].max()
                remaining = max(0, min(highest_after, gap_high) - gap_low)
                filled_ratio = remaining / gap_size

                # Untuk bearish FVG, kalau harga balik mengisi sebagian besar gap, skip.
                if filled_ratio > (1 - FVG_MIN_REMAINING_RATIO):
                    continue

            zones.append(
                {
                    "type": "bearish_fvg",
                    "class_id": CLASS_FVG,
                    "start_idx": i,
                    "mid_idx": i + 1,
                    "end_idx": i + 2,
                    "price_low": gap_low,
                    "price_high": gap_high,
                    "score": (gap_size / avg_range) + body_ratio,
                }
            )

    zones = sorted(zones, key=lambda item: item["score"], reverse=True)
    zones = zones[:MAX_FVG_PER_IMAGE * 3]
    zones = post_filter_fvg_pairs(window, zones)
    return zones[:MAX_FVG_PER_IMAGE]


def post_filter_fvg_pairs(window: pd.DataFrame, fvg_zones: list):
    # Ambil hanya FVG yang clean:
    # - searah displacement
    # - hindari multiple nested FVG yang saling nempel
    if not fvg_zones:
        return []

    bullish = [z for z in fvg_zones if z["type"] == "bullish_fvg"]
    bearish = [z for z in fvg_zones if z["type"] == "bearish_fvg"]

    def select_best(zones):
        if not zones:
            return []
        zones = sorted(zones, key=lambda z: (z["score"], -z["start_idx"]), reverse=True)

        selected = []
        for z in zones:
            overlap = False
            for s in selected:
                if abs(z["mid_idx"] - s["mid_idx"]) <= 2:
                    overlap = True
                    break
            if not overlap:
                selected.append(z)
        return selected[:1]

    result = []
    result.extend(select_best(bullish))
    result.extend(select_best(bearish))
    return result




def find_order_block_for_fvg(window: pd.DataFrame, fvg_zone: dict):
    i = fvg_zone["start_idx"]

    avg_range = (window["high"] - window["low"]).mean()
    avg_body = (window["close"] - window["open"]).abs().mean()

    if avg_range <= 0 or avg_body <= 0:
        return None

    # Cari parent OB lebih terstruktur:
    # fokus ke 1-3 candle sebelum FVG, pilih candle lawan arah
    # dengan body paling kuat, bukan sekadar nearest random candle.
    search_start = max(0, i - 3)
    search_end = i

    candidates = []

    for j in range(search_start, search_end + 1):
        candle = window.iloc[j]
        candle_range = candle["high"] - candle["low"]
        candle_body = abs(candle["close"] - candle["open"])

        if candle_range <= 0:
            continue

        body_ratio = candle_body / candle_range if candle_range > 0 else 0

        if candle_body < avg_body * 0.30:
            continue

        if candle_range > avg_range * 2.5:
            continue

        # Bullish FVG -> parent OB harus bearish
        if fvg_zone["type"] == "bullish_fvg" and candle["close"] < candle["open"]:
            candidates.append({
                "type": "bullish_ob",
                "class_id": CLASS_ORDER_BLOCK,
                "idx": j,
                "price_low": candle["low"],
                "price_high": candle["high"],
                "score": body_ratio + candle_body / avg_body
            })

        # Bearish FVG -> parent OB harus bullish
        if fvg_zone["type"] == "bearish_fvg" and candle["close"] > candle["open"]:
            candidates.append({
                "type": "bearish_ob",
                "class_id": CLASS_ORDER_BLOCK,
                "idx": j,
                "price_low": candle["low"],
                "price_high": candle["high"],
                "score": body_ratio + candle_body / avg_body
            })

    if not candidates:
        return None

    # Pilih candidate OB terbaik:
    # skor tertinggi, lalu paling dekat ke FVG
    candidates = sorted(
        candidates,
        key=lambda x: (x["score"], x["idx"]),
        reverse=True
    )
    return candidates[0]


def detect_ob_from_fvg(window: pd.DataFrame, fvg_zones):
    ob_zones = []
    used_indices = set()

    for fvg_zone in fvg_zones:
        ob = find_order_block_for_fvg(window, fvg_zone)

        if not ob:
            continue

        key = (ob["idx"], ob["type"])

        if key in used_indices:
            continue

        used_indices.add(key)
        ob_zones.append(ob)

    ob_zones = sorted(ob_zones, key=lambda item: item["score"], reverse=True)
    return ob_zones[:MAX_OB_PER_IMAGE]

def zone_to_pixels(zone: dict, total_candles: int, price_min: float, price_max: float):
    cw = candle_width(total_candles)

    if zone["class_id"] == CLASS_FVG:
        x1 = index_to_x(zone["start_idx"], total_candles) - cw // 2
        x2 = index_to_x(zone["end_idx"], total_candles) + cw // 2
    else:
        x_center = index_to_x(zone["idx"], total_candles)
        x1 = x_center - cw // 2
        x2 = x_center + cw // 2

    y_top = price_to_y(zone["price_high"], price_min, price_max)
    y_bottom = price_to_y(zone["price_low"], price_min, price_max)

    return int(x1), int(y_top), int(x2), int(y_bottom)

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
    # ai/datasets/raw/ohlcv/{PAIR}/{TIMEFRAME}/{YEAR}/{FILE}.csv
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

        fvg_zones = detect_fvg(window)
        ob_zones = detect_ob_from_fvg(window, fvg_zones)

        zones = ob_zones + fvg_zones

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
                "fvg_count": len(fvg_zones),
                "ob_count": len(ob_zones),
                "object_count": object_count,
                "status": "auto_labeled",
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
            "fvg_count",
            "ob_count",
            "object_count",
            "status",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print("")
    print("Auto-label finished.")
    print(f"Total generated images : {len(all_rows)}")
    print(f"Clean images           : {CLEAN_IMAGE_DIR}")
    print(f"Preview images         : {PREVIEW_IMAGE_DIR}")
    print(f"YOLO labels            : {YOLO_LABEL_DIR}")
    print(f"Report                 : {REPORT_PATH}")

if __name__ == "__main__":
    main()
