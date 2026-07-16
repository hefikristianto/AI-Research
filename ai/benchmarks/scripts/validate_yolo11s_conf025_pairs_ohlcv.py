from pathlib import Path
import pandas as pd


PAIRING_CSV = Path("ai/benchmarks/reports/yolo11s_pairing_conf025/yolo11s_conf025_ob_fvg_pairs_v2.csv")
AUTO_LABEL_REPORT = Path("ai/datasets/annotation/auto_labels_v5_medium/reports/auto_label_report.csv")
RAW_OHLCV_ROOT = Path("ai/datasets/raw/ohlcv")

OUTPUT_DIR = Path("ai/benchmarks/reports/yolo11s_pairing_conf025")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "yolo11s_ohlcv_validation.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "yolo11s_ohlcv_validation_summary.md"

WINDOW_SIZE = 100

SEARCH_RADIUS = 6
MIN_IMPULSE_BODY_RATIO = 0.35
MIN_IMPULSE_RANGE_MULTIPLIER = 1.10


def normalize_image_id(file_name: str) -> str:
    return Path(file_name).stem


def candle_direction(row) -> str:
    if row["CLOSE"] > row["OPEN"]:
        return "bullish"
    if row["CLOSE"] < row["OPEN"]:
        return "bearish"
    return "neutral"


def candle_body(row) -> float:
    return abs(row["CLOSE"] - row["OPEN"])


def candle_range(row) -> float:
    return max(row["HIGH"] - row["LOW"], 0.0)


def body_ratio(row) -> float:
    rng = candle_range(row)
    if rng == 0:
        return 0.0
    return candle_body(row) / rng


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

    candidates = sorted(folder.glob("*.csv"))

    if not candidates:
        raise FileNotFoundError(f"No OHLCV CSV found in: {folder}")

    return candidates[0]


def load_ohlcv(pair: str, timeframe: str, year: int) -> pd.DataFrame:
    path = find_ohlcv_file(pair, timeframe, year)

    df = pd.read_csv(path, sep="\t")
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


def avg_range_around(window: pd.DataFrame, idx: int, lookback: int = 10) -> float:
    start = max(0, idx - lookback)
    end = min(len(window), idx)

    if end <= start:
        return float(window["HIGH"].sub(window["LOW"]).mean())

    ranges = window.iloc[start:end]["HIGH"] - window.iloc[start:end]["LOW"]
    avg = float(ranges.mean())

    if avg <= 0:
        avg = float(window["HIGH"].sub(window["LOW"]).mean())

    return avg if avg > 0 else 1e-9


def detect_local_ob_fvg(window: pd.DataFrame, center_idx: int):
    """
    Cari struktur OB-FVG lokal di sekitar center_idx.

    Bullish:
    i bearish OB
    i+1 bullish impulse
    high(i) < low(i+2)

    Bearish:
    i bullish OB
    i+1 bearish impulse
    low(i) > high(i+2)
    """

    if len(window) < 3:
        return None

    start = max(0, center_idx - SEARCH_RADIUS)
    end = min(len(window) - 3, center_idx + SEARCH_RADIUS)

    candidates = []

    for i in range(start, end + 1):
        c1 = window.iloc[i]
        c2 = window.iloc[i + 1]
        c3 = window.iloc[i + 2]

        c1_dir = candle_direction(c1)
        c2_dir = candle_direction(c2)

        c2_body_ratio = body_ratio(c2)
        c2_range = candle_range(c2)
        avg_rng = avg_range_around(window, i)

        impulse_ok = (
            c2_body_ratio >= MIN_IMPULSE_BODY_RATIO
            and c2_range >= avg_rng * MIN_IMPULSE_RANGE_MULTIPLIER
        )

        if not impulse_ok:
            continue

        # Bullish OB-FVG
        if c1_dir == "bearish" and c2_dir == "bullish" and c1["HIGH"] < c3["LOW"]:
            gap_size = c3["LOW"] - c1["HIGH"]
            score = (
                c2_body_ratio * 0.45
                + min(c2_range / avg_rng, 3.0) / 3.0 * 0.35
                + min(gap_size / avg_rng, 2.0) / 2.0 * 0.20
            )

            candidates.append({
                "direction": "bullish_candidate",
                "ob_idx": i,
                "impulse_idx": i + 1,
                "fvg_idx": i + 2,
                "ob_candle_direction": c1_dir,
                "impulse_candle_direction": c2_dir,
                "impulse_body_ratio": c2_body_ratio,
                "gap_size": gap_size,
                "local_score": score,
                "distance_from_prediction": abs(i - center_idx),
            })

        # Bearish OB-FVG
        if c1_dir == "bullish" and c2_dir == "bearish" and c1["LOW"] > c3["HIGH"]:
            gap_size = c1["LOW"] - c3["HIGH"]
            score = (
                c2_body_ratio * 0.45
                + min(c2_range / avg_rng, 3.0) / 3.0 * 0.35
                + min(gap_size / avg_rng, 2.0) / 2.0 * 0.20
            )

            candidates.append({
                "direction": "bearish_candidate",
                "ob_idx": i,
                "impulse_idx": i + 1,
                "fvg_idx": i + 2,
                "ob_candle_direction": c1_dir,
                "impulse_candle_direction": c2_dir,
                "impulse_body_ratio": c2_body_ratio,
                "gap_size": gap_size,
                "local_score": score,
                "distance_from_prediction": abs(i - center_idx),
            })

    if not candidates:
        return None

    # Prioritas:
    # 1. Dekat dengan prediksi YOLO
    # 2. Struktur lokal kuat
    candidates.sort(
        key=lambda c: (
            c["distance_from_prediction"],
            -c["local_score"],
        )
    )

    return candidates[0]


def validate_row(row, ohlcv_cache):
    pair = row["pair"]
    timeframe = row["timeframe"]
    year = int(row["year"])
    start_dt = row["start_datetime"]
    end_dt = row["end_datetime"]

    cache_key = (pair, timeframe, year)

    if cache_key not in ohlcv_cache:
        ohlcv_cache[cache_key] = load_ohlcv(pair, timeframe, year)

    df = ohlcv_cache[cache_key]
    window = get_window(df, start_dt, end_dt)

    if window.empty:
        return {
            "ohlcv_status": "window_not_found",
            "ohlcv_direction_v2": "unknown",
            "direction_match_v2": "false",
            "window_candles": 0,
            "approx_ob_idx": "",
            "matched_ob_idx": "",
            "matched_impulse_idx": "",
            "matched_fvg_idx": "",
            "ob_candle_direction_v2": "",
            "impulse_candle_direction_v2": "",
            "impulse_body_ratio_v2": "",
            "gap_size_v2": "",
            "local_structure_score": "",
            "distance_from_prediction": "",
        }

    ob_x = float(row["ob_x"])
    approx_ob_idx = x_to_index(ob_x, len(window))

    detected = detect_local_ob_fvg(window, approx_ob_idx)

    if detected is None:
        return {
            "ohlcv_status": "ok",
            "ohlcv_direction_v2": "uncertain",
            "direction_match_v2": "false",
            "window_candles": len(window),
            "approx_ob_idx": approx_ob_idx,
            "matched_ob_idx": "",
            "matched_impulse_idx": "",
            "matched_fvg_idx": "",
            "ob_candle_direction_v2": "",
            "impulse_candle_direction_v2": "",
            "impulse_body_ratio_v2": "",
            "gap_size_v2": "",
            "local_structure_score": "",
            "distance_from_prediction": "",
        }

    ohlcv_direction = detected["direction"]
    visual_direction = row["direction"]

    return {
        "ohlcv_status": "ok",
        "ohlcv_direction_v2": ohlcv_direction,
        "direction_match_v2": str(ohlcv_direction == visual_direction).lower(),
        "window_candles": len(window),
        "approx_ob_idx": approx_ob_idx,
        "matched_ob_idx": detected["ob_idx"],
        "matched_impulse_idx": detected["impulse_idx"],
        "matched_fvg_idx": detected["fvg_idx"],
        "ob_candle_direction_v2": detected["ob_candle_direction"],
        "impulse_candle_direction_v2": detected["impulse_candle_direction"],
        "impulse_body_ratio_v2": f'{detected["impulse_body_ratio"]:.6f}',
        "gap_size_v2": f'{detected["gap_size"]:.6f}',
        "local_structure_score": f'{detected["local_score"]:.6f}',
        "distance_from_prediction": detected["distance_from_prediction"],
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

    ohlcv_cache = {}
    rows = []

    for _, row in merged.iterrows():
        base = row.to_dict()

        if pd.isna(row.get("pair")):
            base.update({
                "ohlcv_status": "metadata_not_found",
                "ohlcv_direction_v2": "unknown",
                "direction_match_v2": "false",
                "window_candles": 0,
                "approx_ob_idx": "",
                "matched_ob_idx": "",
                "matched_impulse_idx": "",
                "matched_fvg_idx": "",
                "ob_candle_direction_v2": "",
                "impulse_candle_direction_v2": "",
                "impulse_body_ratio_v2": "",
                "gap_size_v2": "",
                "local_structure_score": "",
                "distance_from_prediction": "",
            })
            rows.append(base)
            continue

        try:
            validation = validate_row(row, ohlcv_cache)
            base.update(validation)
        except Exception as exc:
            base.update({
                "ohlcv_status": f"error: {exc}",
                "ohlcv_direction_v2": "unknown",
                "direction_match_v2": "false",
                "window_candles": 0,
                "approx_ob_idx": "",
                "matched_ob_idx": "",
                "matched_impulse_idx": "",
                "matched_fvg_idx": "",
                "ob_candle_direction_v2": "",
                "impulse_candle_direction_v2": "",
                "impulse_body_ratio_v2": "",
                "gap_size_v2": "",
                "local_structure_score": "",
                "distance_from_prediction": "",
            })

        rows.append(base)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUTPUT_CSV, index=False)

    total = len(out_df)
    ok = (out_df["ohlcv_status"] == "ok").sum()
    matched = (out_df["direction_match_v2"] == "true").sum()
    uncertain = (out_df["ohlcv_direction_v2"] == "uncertain").sum()
    bullish = (out_df["ohlcv_direction_v2"] == "bullish_candidate").sum()
    bearish = (out_df["ohlcv_direction_v2"] == "bearish_candidate").sum()

    summary = []
    summary.append("# YOLO11s Conf025 OB-FVG OHLCV Validation")
    summary.append("")
    summary.append("## Purpose")
    summary.append("")
    summary.append("This report validates visual OB-FVG direction estimates using local OHLCV OB-FVG structure search.")
    summary.append("")
    summary.append("## Method")
    summary.append("")
    summary.append("- Match prediction filename to auto-label metadata.")
    summary.append("- Load the corresponding OHLCV window.")
    summary.append("- Convert YOLO normalized x-coordinate into approximate candle index.")
    summary.append("- Search local candles around the predicted OB location.")
    summary.append("- Validate bullish/bearish OB-FVG structure using three-candle logic.")
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
    summary.append("This v2 validation improves v1 by searching for a complete local OB-FVG structure around the YOLO-predicted region instead of checking only the nearest candle and the next impulse candle.")
    summary.append("")
    summary.append("## Output")
    summary.append("")
    summary.append(f"- CSV: {OUTPUT_CSV}")

    OUTPUT_SUMMARY.write_text("\n".join(summary), encoding="utf-8")

    print("OHLCV direction validation v2 finished.")
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



