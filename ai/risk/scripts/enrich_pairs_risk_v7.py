from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_detector_module(path: Path):
    spec = importlib.util.spec_from_file_location(
        "market_structure_detector",
        path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Gagal memuat detector: {path}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def normalize_direction(value: object) -> str:
    text = str(value).strip().lower()

    if "bull" in text or text in {"buy", "long"}:
        return "bullish"

    if "bear" in text or text in {"sell", "short"}:
        return "bearish"

    return "uncertain"


def resolve_ohlcv_path(
    root: Path,
    pair: str,
    timeframe: str,
    year: int,
) -> Path:
    pair = pair.upper()
    timeframe = timeframe.upper()

    folder = (
        root
        / pair
        / timeframe
        / str(year)
    )

    expected = (
        folder
        / f"{pair}_{timeframe}_{year}_RAW.csv"
    )

    if expected.exists():
        return expected

    candidates = sorted(
        folder.glob("*.csv")
    )

    if not candidates:
        raise FileNotFoundError(
            f"OHLCV tidak ditemukan: "
            f"{pair} {timeframe} {year}"
        )

    return candidates[0]


def classify_rr(rr: float | None) -> tuple[str, float]:
    if rr is None or not np.isfinite(rr):
        return "target_missing", 0.50

    if rr >= 3.0:
        return "excellent", 1.00

    if rr >= 2.0:
        return "strong", 0.90

    if rr >= 1.5:
        return "feasible", 0.70

    if rr >= 1.0:
        return "weak", 0.40

    return "poor", 0.10


def find_unswept_targets(
    history: pd.DataFrame,
    liquidity: pd.DataFrame,
) -> pd.DataFrame:
    if liquidity.empty:
        return liquidity.copy()

    rows = []

    for _, level_row in liquidity.iterrows():
        level = float(
            level_row["level"]
        )

        second_index = int(
            level_row["second_index"]
        )

        future = history.iloc[
            second_index + 1:
        ]

        liquidity_type = str(
            level_row["liquidity_type"]
        )

        if liquidity_type == "buy_side":
            swept = bool(
                (future["high"] > level).any()
            )

        else:
            swept = bool(
                (future["low"] < level).any()
            )

        if not swept:
            result = level_row.to_dict()
            result["target_unswept_v7"] = True
            rows.append(result)

    return pd.DataFrame(rows)


def choose_target(
    liquidity: pd.DataFrame,
    direction: str,
    entry: float,
    current_atr: float,
    max_target_atr: float = 6.0,
) -> dict:
    if liquidity.empty:
        return {
            "target_price_v7": np.nan,
            "target_type_v7": "missing",
            "target_distance_v7": np.nan,
            "target_distance_atr_v7": np.nan,
        }

    maximum_distance = (
        max_target_atr * current_atr
    )

    if direction == "bullish":
        candidates = liquidity[
            (
                liquidity["liquidity_type"]
                == "buy_side"
            )
            & (
                liquidity["level"] > entry
            )
            & (
                liquidity["level"]
                <= entry + maximum_distance
            )
        ].copy()

        if candidates.empty:
            return {
                "target_price_v7": np.nan,
                "target_type_v7": "missing",
                "target_distance_v7": np.nan,
                "target_distance_atr_v7": np.nan,
            }

        candidates["distance"] = (
            candidates["level"] - entry
        )

    elif direction == "bearish":
        candidates = liquidity[
            (
                liquidity["liquidity_type"]
                == "sell_side"
            )
            & (
                liquidity["level"] < entry
            )
            & (
                liquidity["level"]
                >= entry - maximum_distance
            )
        ].copy()

        if candidates.empty:
            return {
                "target_price_v7": np.nan,
                "target_type_v7": "missing",
                "target_distance_v7": np.nan,
                "target_distance_atr_v7": np.nan,
            }

        candidates["distance"] = (
            entry - candidates["level"]
        )

    else:
        return {
            "target_price_v7": np.nan,
            "target_type_v7": "missing",
            "target_distance_v7": np.nan,
            "target_distance_atr_v7": np.nan,
        }

    nearest = (
        candidates
        .sort_values("distance")
        .iloc[0]
    )

    distance = float(
        nearest["distance"]
    )

    return {
        "target_price_v7": float(
            nearest["level"]
        ),
        "target_type_v7": str(
            nearest["liquidity_type"]
        ),
        "target_distance_v7": distance,
        "target_distance_atr_v7": (
            distance
            / max(current_atr, 1e-12)
        ),
    }


def evaluate_setup(
    row: pd.Series,
    detector,
    ohlcv_root: Path,
    atr_buffer: float,
) -> dict:
    pair = str(row["pair"]).upper()
    timeframe = str(
        row["timeframe"]
    ).upper()

    year = int(
        float(row["year"])
    )

    direction = normalize_direction(
        row["direction"]
    )

    end_datetime = pd.to_datetime(
        row["end_datetime"],
        errors="coerce",
    )

    if pd.isna(end_datetime):
        raise ValueError(
            "end_datetime tidak valid"
        )

    zone_low = pd.to_numeric(
        row.get("zone_low_v5"),
        errors="coerce",
    )

    zone_high = pd.to_numeric(
        row.get("zone_high_v5"),
        errors="coerce",
    )

    if (
        pd.isna(zone_low)
        or pd.isna(zone_high)
        or zone_high <= zone_low
    ):
        raise ValueError(
            "Level zona tidak valid"
        )

    source_path = resolve_ohlcv_path(
        ohlcv_root,
        pair,
        timeframe,
        year,
    )

    dataframe = detector.load_ohlcv(
        source_path
    )

    # Anti-lookahead:
    # hanya candle sampai waktu setup.
    history = dataframe[
        dataframe["datetime"]
        <= end_datetime
    ].copy().reset_index(drop=True)

    if len(history) < 50:
        raise ValueError(
            "History candle terlalu sedikit"
        )

    history["index"] = np.arange(
        len(history)
    )

    history["atr"] = (
        detector.calculate_atr(
            history
        )
    )

    history = detector.detect_swings(
        history,
        left=3,
        right=3,
    )

    liquidity = detector.detect_equal_levels(
        history,
        tolerance_atr=0.20,
        lookback_swings=8,
    )

    unswept = find_unswept_targets(
        history,
        liquidity,
    )

    latest = history.iloc[-1]

    current_close = float(
        latest["close"]
    )

    current_atr = float(
        latest["atr"]
    )

    if (
        not np.isfinite(current_atr)
        or current_atr <= 0
    ):
        raise ValueError(
            "ATR tidak valid"
        )

    entry = float(
        (zone_low + zone_high) / 2.0
    )

    if direction == "bullish":
        stop_loss = float(
            zone_low
            - atr_buffer * current_atr
        )

        invalidated = bool(
            current_close < stop_loss
        )

        entry_relation = (
            "above_zone"
            if current_close > zone_high
            else (
                "inside_zone"
                if current_close >= zone_low
                else "below_zone"
            )
        )

    elif direction == "bearish":
        stop_loss = float(
            zone_high
            + atr_buffer * current_atr
        )

        invalidated = bool(
            current_close > stop_loss
        )

        entry_relation = (
            "below_zone"
            if current_close < zone_low
            else (
                "inside_zone"
                if current_close <= zone_high
                else "above_zone"
            )
        )

    else:
        raise ValueError(
            "Direction tidak valid"
        )

    raw_risk_distance = abs(
        entry - stop_loss
    )

    minimum_risk_distance = (
        0.75 * current_atr
    )

    risk_distance = max(
        raw_risk_distance,
        minimum_risk_distance,
    )

    if direction == "bullish":
        stop_loss = (
            entry - risk_distance
        )
    else:
        stop_loss = (
            entry + risk_distance
        )

    target_result = choose_target(
        liquidity=unswept,
        direction=direction,
        entry=entry,
        current_atr=current_atr,
        max_target_atr=6.0,
    )

    target_price = target_result[
        "target_price_v7"
    ]

    if invalidated:
        target_price = np.nan
        target_result[
            "target_type_v7"
        ] = "invalidated"

        reward_distance = np.nan
        rr_ratio = np.nan

    elif (
        np.isfinite(target_price)
        and risk_distance > 0
    ):
        reward_distance = abs(
            target_price - entry
        )

        rr_ratio = (
            reward_distance
            / risk_distance
        )

    else:
        reward_distance = np.nan
        rr_ratio = np.nan

    rr_category, rr_score = classify_rr(
        rr_ratio
    )

    distance_to_entry = abs(
        current_close - entry
    )

    distance_to_entry_atr = (
        distance_to_entry
        / current_atr
    )

    if distance_to_entry_atr <= 0.50:
        entry_distance_score = 1.00
        entry_feasibility = "near"

    elif distance_to_entry_atr <= 1.00:
        entry_distance_score = 0.75
        entry_feasibility = "reachable"

    elif distance_to_entry_atr <= 2.00:
        entry_distance_score = 0.45
        entry_feasibility = "far"

    else:
        entry_distance_score = 0.20
        entry_feasibility = "very_far"

    if invalidated:
        rr_score = 0.0
        entry_distance_score = 0.0
        entry_feasibility = "invalidated"

    feasibility_score = (
        0.75 * rr_score
        + 0.25 * entry_distance_score
    )

    return {
        "rr_ohlcv_path_v7": str(
            source_path
        ),
        "current_close_v7": current_close,
        "atr_v7": current_atr,
        "zone_low_rr_v7": float(
            zone_low
        ),
        "zone_high_rr_v7": float(
            zone_high
        ),
        "entry_price_v7": entry,
        "stop_loss_v7": stop_loss,
        "target_price_v7": target_price,
        "target_type_v7": target_result[
            "target_type_v7"
        ],
        "target_distance_atr_v7": (
            target_result.get(
                "target_distance_atr_v7",
                np.nan,
            )
        ),
        "raw_risk_distance_v7": (
            raw_risk_distance
        ),
        "minimum_risk_distance_v7": (
            minimum_risk_distance
        ),
        "risk_distance_v7": risk_distance,
        "reward_distance_v7": (
            reward_distance
        ),
        "rr_ratio_v7": rr_ratio,
        "rr_category_v7": rr_category,
        "rr_score_v7": rr_score,
        "entry_relation_v7": (
            entry_relation
        ),
        "distance_to_entry_v7": (
            distance_to_entry
        ),
        "distance_to_entry_atr_v7": (
            distance_to_entry_atr
        ),
        "entry_feasibility_v7": (
            entry_feasibility
        ),
        "entry_distance_score_v7": (
            entry_distance_score
        ),
        "zone_invalidated_v7": invalidated,
        "unswept_targets_v7": int(
            len(unswept)
        ),
        "risk_feasibility_score_v7": (
            feasibility_score
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "scoring_v6_1_results.csv"
        ),
    )

    parser.add_argument(
        "--detector-script",
        type=Path,
        default=Path(
            "ai/structure/scripts/"
            "detect_market_structure.py"
        ),
    )

    parser.add_argument(
        "--ohlcv-root",
        type=Path,
        default=Path(
            "ai/datasets/raw/ohlcv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/risk/reports/"
            "pairs_risk_v7.csv"
        ),
    )

    parser.add_argument(
        "--atr-buffer",
        type=float,
        default=0.15,
    )

    args = parser.parse_args()

    detector = load_detector_module(
        args.detector_script
    )

    dataframe = pd.read_csv(
        args.input
    )

    results = []

    for index, row in dataframe.iterrows():
        image_id = row.get(
            "image_id",
            f"row_{index}",
        )

        print(
            f"[{index + 1}/{len(dataframe)}] "
            f"{image_id}"
        )

        try:
            result = evaluate_setup(
                row=row,
                detector=detector,
                ohlcv_root=args.ohlcv_root,
                atr_buffer=args.atr_buffer,
            )

            result["risk_error_v7"] = ""

        except Exception as error:
            result = {
                "current_close_v7": np.nan,
                "atr_v7": np.nan,
                "entry_price_v7": np.nan,
                "stop_loss_v7": np.nan,
                "target_price_v7": np.nan,
                "target_type_v7": "error",
                "risk_distance_v7": np.nan,
                "reward_distance_v7": np.nan,
                "rr_ratio_v7": np.nan,
                "rr_category_v7": "error",
                "rr_score_v7": 0.50,
                "entry_relation_v7": "error",
                "distance_to_entry_v7": np.nan,
                "distance_to_entry_atr_v7": np.nan,
                "entry_feasibility_v7": "error",
                "entry_distance_score_v7": 0.50,
                "zone_invalidated_v7": False,
                "unswept_targets_v7": 0,
                "risk_feasibility_score_v7": 0.50,
                "risk_error_v7": str(error),
            }

        results.append(result)

    enriched = pd.concat(
        [
            dataframe.reset_index(
                drop=True
            ),
            pd.DataFrame(results),
        ],
        axis=1,
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    enriched.to_csv(
        args.output,
        index=False,
    )

    valid_rr = pd.to_numeric(
        enriched["rr_ratio_v7"],
        errors="coerce",
    ).dropna()

    print("")
    print("Risk enrichment v7 selesai")
    print(
        f"Total setups       : "
        f"{len(enriched)}"
    )
    print(
        f"Valid targets      : "
        f"{enriched['target_price_v7'].notna().sum()}"
    )
    print(
        f"Missing targets    : "
        f"{enriched['target_price_v7'].isna().sum()}"
    )
    print(
        f"RR >= 2            : "
        f"{(valid_rr >= 2.0).sum()}"
    )
    print(
        f"RR 1.5 - 2         : "
        f"{((valid_rr >= 1.5) & (valid_rr < 2.0)).sum()}"
    )
    print(
        f"RR < 1.5           : "
        f"{(valid_rr < 1.5).sum()}"
    )
    print(
        f"Invalidated zones  : "
        f"{enriched['zone_invalidated_v7'].astype(str).str.lower().eq('true').sum()}"
    )
    print(
        f"Average RR         : "
        f"{valid_rr.mean():.4f}"
        if not valid_rr.empty
        else "Average RR         : unavailable"
    )
    print(
        f"Errors             : "
        f"{enriched['risk_error_v7'].ne('').sum()}"
    )
    print(
        f"Output             : "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()







