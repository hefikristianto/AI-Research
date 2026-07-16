from pathlib import Path
import csv
from datetime import datetime
from typing import List, Optional
import pandas as pd


PAIRING_CSV = Path("ai/detection/postprocessing/reports/ob_fvg_pairs_v2.csv")
AUTO_LABEL_REPORT = Path("ai/datasets/annotation/auto_labels_v5_medium/reports/auto_label_report.csv")
RAW_OHLCV_ROOT = Path("ai/datasets/raw/ohlcv")

OUTPUT_DIR = Path("ai/detection/validation/reports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "ob_fvg_direction_validation_v1.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "ob_fvg_direction_validation_summary_v1.md"

WINDOW_SIZE = 100

# Toleransi index sekitar deteksi YOLO.
SEARCH_RADIUS = 2

# Definisi impulse sederhana.
MIN_IMPULSE_BODY_RATIO = 0.45


def normalize_image_id(file_name: str) -> str:
    return Path(file_name).stem


def load_auto_label_metadata() -> pd.DataFrame:
    df = pd.read_csv(AUTO_LABEL_REPORT)
    df["image_id"] = df["image_id"].astype(str)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"])
    df["end_datetime"] = pd.to_datetime(df["end_datetime"])
    return df


def load_pairs() -> pd.DataFrame:
    df = pd.read_csv(PAIRING_CSV)
    df["image_id"] = df["file"].apply(normalize_image_id)
    return df


def find_ohlcv_file(pair: str, timeframe: str, year: int) -> Path:
    folder = RAW_OHLCV_ROOT / pair / timeframe / str(year)

    if not folder.exists():
        raise FileNotFoundError(f"OHLCV folder not found: {folder}")

    candidates = list(folder.glob("*.csv"))

    if not candidates:
        raise FileNotFoundError(f"No OHLCV CSV found in: {folder}")

    if len(candidates) > 1:
        # Ambil file pertama, tapi urutkan biar stabil.
        candidates = sorted(candidates)

    return candidates[0]


def load_ohlcv(pair: str, timeframe: str, year: int) -> pd.DataFrame:
    path = find_ohlcv_file(pair, timeframe, year)

    # MT5 export biasanya tab-separated.
    df = pd.read_csv(path, sep="\t")

    # Normalize column names.
    df.columns = [col.strip().replace("<", "").replace(">", "").upper() for col in df.columns]

    required = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE"]

    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f"Missing columns {missing} in {path}. Found columns: {list(df.columns)}")

    df["DATETIME"] = pd.to_datetime(df["DATE"].astype(str) + " " + df["TIME"].astype(str))

    for col in ["OPEN", "HIGH", "LOW", "CLOSE"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["DATETIME", "OPEN", "HIGH", "LOW", "CLOSE"]).reset_index(drop=True)

    return df


def get_window(df: pd.DataFrame, start_dt, end_dt) -> pd.DataFrame:
    window = df[(df["DATETIME"] >= start_dt) & (df["DATETIME"] <= end_dt)].copy()
    window = window.reset_index(drop=True)

    if len(window) > WINDOW_SIZE:
        window = window.iloc[:WINDOW_SIZE].copy().reset_index(drop=True)

    return window


def x_to_index(x: float, window_len: int) -> int:
    if window_len <= 1:
        return 0

    idx = round(x * (window_len - 1))
    return max(0, min(window_len - 1, idx))


def candle_direction(row) -> str:
    if row["CLOSE"] > row["OPEN"]:
        return "bullish"

    if row["CLOSE"] < row["OPEN"]:
        return "bearish"

    return "neutral"


def body_ratio(row) -> float:
    candle_range = row["HIGH"] - row["LOW"]

    if candle_range == 0:
        return 0.0

    body = abs(row["CLOSE"] - row["OPEN"])
    return body / candle_range


def find_best_ob_index(window: pd.DataFrame, approx_idx: int) -> int:
    start = max(0, approx_idx - SEARCH_RADIUS)
    end = min(len(window) - 1, approx_idx + SEARCH_RADIUS)

    best_idx = approx_idx
    best_score = -1

    for idx in range(start, end + 1):
        row = window.iloc[idx]
        score = body_ratio(row)

        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx


def infer_ohlcv_direction(window: pd.DataFrame, ob_idx: int) -> str:
    if len(window) < 3:
        return "unknown"

    ob_idx = max(0, min(len(window) - 2, ob_idx))

    ob = window.iloc[ob_idx]
    next_candle = window.iloc[ob_idx + 1]

    ob_dir = candle_direction(ob)
    impulse_dir = candle_direction(next_candle)
    impulse_body_ratio = body_ratio(next_candle)

    if impulse_body_ratio < MIN_IMPULSE_BODY_RATIO:
        return "uncertain"

    # Bullish OB-FVG:
    # OB candle bearish, impulse candle bullish.
    if ob_dir == "bearish" and impulse_dir == "bullish":
        return "bullish_candidate"

    # Bearish OB-FVG:
    # OB candle bullish, impulse candle bearish.
    if ob_dir == "bullish" and impulse_dir == "bearish":
        return "bearish_candidate"

    return "uncertain"


def validate_row(pair_row, meta_row, ohlcv_cache):
    pair = meta_row["pair"]
    timeframe = meta_row["timeframe"]
    year = int(meta_row["year"])
    start_dt = meta_row["start_datetime"]
    end_dt = meta_row["end_datetime"]

    cache_key = (pair, timeframe, year)

    if cache_key not in ohlcv_cache:
        ohlcv_cache[cache_key] = load_ohlcv(pair, timeframe, year)

    df = ohlcv_cache[cache_key]
    window = get_window(df, start_dt, end_dt)

    if window.empty:
        return {
            "ohlcv_status": "window_not_found",
            "ohlcv_direction": "unknown",
            "direction_match": "false",
            "window_candles": 0,
            "ob_idx": "",
            "fvg_idx": "",
            "ob_candle_direction": "",
            "impulse_candle_direction": "",
            "impulse_body_ratio": "",
        }

    ob_x = float(pair_row["ob_x"])
    fvg_x = float(pair_row["fvg_x"])

    approx_ob_idx = x_to_index(ob_x, len(window))
    fvg_idx = x_to_index(fvg_x, len(window))

    ob_idx = find_best_ob_index(window, approx_ob_idx)

    ohlcv_direction = infer_ohlcv_direction(window, ob_idx)
    visual_direction = pair_row["direction"]

    direction_match = str(ohlcv_direction == visual_direction).lower()

    ob = window.iloc[ob_idx]
    impulse = window.iloc[min(ob_idx + 1, len(window) - 1)]

    return {
        "ohlcv_status": "ok",
        "ohlcv_direction": ohlcv_direction,
        "direction_match": direction_match,
        "window_candles": len(window),
        "ob_idx": ob_idx,
        "fvg_idx": fvg_idx,
        "ob_candle_direction": candle_direction(ob),
        "impulse_candle_direction": candle_direction(impulse),
        "impulse_body_ratio": f"{body_ratio(impulse):.6f}",
    }


def main():
    meta_df = load_auto_label_metadata()
    pairs_df = load_pairs()

    merged = pairs_df.merge(
        meta_df,
        on="image_id",
        how="left",
        suffixes=("", "_meta"),
    )

    missing_meta = merged[merged["pair"].isna()]

    if not missing_meta.empty:
        print("Warning: some pairs have no metadata match:")
        print(missing_meta[["file", "image_id"]].to_string(index=False))

    ohlcv_cache = {}
    rows = []

    for _, row in merged.iterrows():
        base = row.to_dict()

        if pd.isna(row.get("pair")):
            base.update({
                "ohlcv_status": "metadata_not_found",
                "ohlcv_direction": "unknown",
                "direction_match": "false",
                "window_candles": 0,
                "ob_idx": "",
                "fvg_idx": "",
                "ob_candle_direction": "",
                "impulse_candle_direction": "",
                "impulse_body_ratio": "",
            })
            rows.append(base)
            continue

        try:
            validation = validate_row(row, row, ohlcv_cache)
            base.update(validation)
        except Exception as exc:
            base.update({
                "ohlcv_status": f"error: {exc}",
                "ohlcv_direction": "unknown",
                "direction_match": "false",
                "window_candles": 0,
                "ob_idx": "",
                "fvg_idx": "",
                "ob_candle_direction": "",
                "impulse_candle_direction": "",
                "impulse_body_ratio": "",
            })

        rows.append(base)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUTPUT_CSV, index=False)

    total = len(out_df)
    ok = (out_df["ohlcv_status"] == "ok").sum()
    matched = (out_df["direction_match"] == "true").sum()
    uncertain = (out_df["ohlcv_direction"] == "uncertain").sum()
    bullish = (out_df["ohlcv_direction"] == "bullish_candidate").sum()
    bearish = (out_df["ohlcv_direction"] == "bearish_candidate").sum()

    summary = []
    summary.append("# OB-FVG Direction Validation v1")
    summary.append("")
    summary.append("## Purpose")
    summary.append("")
    summary.append("This report validates visual OB-FVG direction estimates using OHLCV candle structure.")
    summary.append("")
    summary.append("## Method")
    summary.append("")
    summary.append("- Match prediction filename to auto-label metadata.")
    summary.append("- Load the corresponding OHLCV window.")
    summary.append("- Convert YOLO normalized x-coordinate into approximate candle index.")
    summary.append("- Validate direction using OB candle and next impulse candle.")
    summary.append("")
    summary.append("## Result")
    summary.append("")
    summary.append(f"- Total pairs: {total}")
    summary.append(f"- OHLCV windows loaded successfully: {ok}")
    summary.append(f"- Direction matches: {matched}")
    summary.append(f"- Direction match rate: {(matched / total * 100) if total else 0:.2f}%")
    summary.append(f"- Bullish candidates by OHLCV: {bullish}")
    summary.append(f"- Bearish candidates by OHLCV: {bearish}")
    summary.append(f"- Uncertain candidates: {uncertain}")
    summary.append("")
    summary.append("## Notes")
    summary.append("")
    summary.append("This is an initial validation method. It uses the nearest candle around the detected OB x-coordinate and the next candle as the impulse candle. Future versions should use a wider local search and validate the full OB-FVG three-candle structure.")
    summary.append("")
    summary.append("## Output")
    summary.append("")
    summary.append(f"- CSV: {OUTPUT_CSV}")

    OUTPUT_SUMMARY.write_text("\n".join(summary), encoding="utf-8")

    print("OHLCV direction validation finished.")
    print(f"Total pairs       : {total}")
    print(f"OHLCV ok          : {ok}")
    print(f"Direction matches : {matched}")
    print(f"Match rate        : {(matched / total * 100) if total else 0:.2f}%")
    print(f"Bullish OHLCV     : {bullish}")
    print(f"Bearish OHLCV     : {bearish}")
    print(f"Uncertain         : {uncertain}")
    print(f"CSV report        : {OUTPUT_CSV}")
    print(f"Summary report    : {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
