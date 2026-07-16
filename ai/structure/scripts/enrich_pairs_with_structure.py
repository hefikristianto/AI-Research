from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_detector_module(script_path: Path):
    spec = importlib.util.spec_from_file_location(
        "market_structure_detector",
        script_path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Gagal memuat module: {script_path}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module



def safe_index(
    value: object,
    fallback: object = 0,
) -> int:
    try:
        if pd.isna(value):
            raise ValueError

        return int(float(value))

    except (TypeError, ValueError):
        try:
            if pd.isna(fallback):
                return 0

            return int(float(fallback))

        except (TypeError, ValueError):
            return 0

def normalize_direction(value: object) -> str:
    text = str(value).lower().strip()

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

    expected = (
        root
        / pair
        / timeframe
        / str(year)
        / f"{pair}_{timeframe}_{year}_RAW.csv"
    )

    if expected.exists():
        return expected

    candidates = list(
        (
            root
            / pair
            / timeframe
            / str(year)
        ).glob("*.csv")
    )

    if not candidates:
        raise FileNotFoundError(
            f"OHLCV tidak ditemukan untuk "
            f"{pair} {timeframe} {year}"
        )

    return candidates[0]


def find_nearest_index(
    dataframe: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> int:
    difference = (
        dataframe["datetime"] - timestamp
    ).abs()

    return int(
        difference.idxmin()
    )


def calculate_zone_status(
    window: pd.DataFrame,
    ob_index: int,
    fvg_index: int,
    direction: str,
) -> dict:
    if (
        ob_index < 0
        or ob_index >= len(window)
        or fvg_index < 0
        or fvg_index >= len(window)
    ):
        return {
            "zone_status": "unknown",
            "zone_fresh": False,
            "zone_mitigated": False,
            "zone_touch_count": 0,
            "zone_score": 0.50,
        }

    ob_candle = window.iloc[ob_index]

    zone_low = float(
        ob_candle["low"]
    )

    zone_high = float(
        ob_candle["high"]
    )

    future = window.iloc[
        fvg_index + 1:
    ]

    touch_count = 0

    for _, candle in future.iterrows():
        overlap = (
            candle["low"] <= zone_high
            and candle["high"] >= zone_low
        )

        if overlap:
            touch_count += 1

    if touch_count == 0:
        status = "fresh"
        score = 1.00
        fresh = True
        mitigated = False

    elif touch_count == 1:
        status = "partially_mitigated"
        score = 0.65
        fresh = False
        mitigated = True

    else:
        status = "mitigated"
        score = 0.25
        fresh = False
        mitigated = True

    return {
        "zone_status": status,
        "zone_fresh": fresh,
        "zone_mitigated": mitigated,
        "zone_touch_count": touch_count,
        "zone_score": score,
        "zone_low": zone_low,
        "zone_high": zone_high,
    }


def evaluate_setup(
    row: pd.Series,
    detector,
    ohlcv_root: Path,
) -> dict:
    pair = str(row["pair"]).upper()
    timeframe = str(
        row["timeframe"]
    ).upper()

    year = int(row["year"])

    direction = normalize_direction(
        row["direction"]
    )

    source_path = resolve_ohlcv_path(
        root=ohlcv_root,
        pair=pair,
        timeframe=timeframe,
        year=year,
    )

    dataframe = detector.load_ohlcv(
        source_path
    )

    start_datetime = pd.to_datetime(
        row["start_datetime"],
        errors="coerce",
    )

    end_datetime = pd.to_datetime(
        row["end_datetime"],
        errors="coerce",
    )

    if (
        pd.isna(start_datetime)
        or pd.isna(end_datetime)
    ):
        raise ValueError(
            f"Datetime tidak valid untuk "
            f"{row.get('image_id', 'unknown')}"
        )

    start_index = find_nearest_index(
        dataframe,
        start_datetime,
    )

    end_index = find_nearest_index(
        dataframe,
        end_datetime,
    )

    context_start = max(
        0,
        start_index - 50,
    )

    context_end = min(
        len(dataframe),
        end_index + 31,
    )

    context = dataframe.iloc[
        context_start:context_end
    ].copy().reset_index(drop=True)

    context["index"] = np.arange(
        len(context)
    )

    context["atr"] = detector.calculate_atr(
        context
    )

    context = detector.detect_swings(
        context,
        left=3,
        right=3,
    )

    liquidity = detector.detect_equal_levels(
        context,
        tolerance_atr=0.20,
        lookback_swings=8,
    )

    sweeps = detector.detect_sweeps(
        context,
        liquidity,
        max_bars_after_level=30,
    )

    structure = detector.detect_structure_breaks(
        context
    )

    confirmed_sweeps = (
        detector.link_sweeps_to_structure(
            sweeps,
            structure,
            max_confirmation_bars=20,
        )
    )

    setup_start_local = (
        start_index - context_start
    )

    setup_end_local = (
        end_index - context_start
    )

    matched_ob = safe_index(
        row.get("matched_ob_idx"),
        row.get("approx_ob_idx", 0),
    )

    matched_fvg = safe_index(
        row.get("matched_fvg_idx"),
        matched_ob + 2,
    )

    ob_local = (
        setup_start_local
        + matched_ob
    )

    fvg_local = (
        setup_start_local
        + matched_fvg
    )

    expected_sweep = (
        "bullish_candidate"
        if direction == "bullish"
        else "bearish_candidate"
    )

    relevant_sweeps = confirmed_sweeps.copy()

    if not relevant_sweeps.empty:
        relevant_sweeps = relevant_sweeps[
            (
                relevant_sweeps[
                    "sweep_direction"
                ]
                == expected_sweep
            )
            & (
                relevant_sweeps[
                    "sweep_index"
                ]
                <= fvg_local
            )
            & (
                relevant_sweeps[
                    "sweep_index"
                ]
                >= max(
                    0,
                    ob_local - 30,
                )
            )
        ]

    liquidity_present = (
        not relevant_sweeps.empty
    )

    confirmed_liquidity = False
    sweep_distance = np.nan
    penetration_atr = 0.0
    confirmation_type = None

    if liquidity_present:
        relevant_sweeps = (
            relevant_sweeps
            .sort_values(
                "sweep_index",
                ascending=False,
            )
        )

        nearest = (
            relevant_sweeps.iloc[0]
        )

        confirmed_liquidity = bool(
            nearest["confirmed"]
        )

        sweep_distance = int(
            fvg_local
            - nearest["sweep_index"]
        )

        penetration_atr = float(
            nearest["penetration_atr"]
        )

        confirmation_type = (
            nearest[
                "confirmation_type"
            ]
        )

    expected_structure_direction = direction

    relevant_structure = structure.copy()

    if not relevant_structure.empty:
        relevant_structure = (
            relevant_structure[
                (
                    relevant_structure[
                        "direction"
                    ]
                    == expected_structure_direction
                )
                & (
                    relevant_structure[
                        "event_index"
                    ]
                    >= max(
                        0,
                        ob_local - 10,
                    )
                )
                & (
                    relevant_structure[
                        "event_index"
                    ]
                    <= min(
                        len(context) - 1,
                        fvg_local + 20,
                    )
                )
            ]
        )

    bos_present = False
    choch_present = False
    structure_alignment = False

    if not relevant_structure.empty:
        bos_present = bool(
            (
                relevant_structure[
                    "event_type"
                ]
                == "BOS"
            ).any()
        )

        choch_present = bool(
            (
                relevant_structure[
                    "event_type"
                ]
                == "CHOCH"
            ).any()
        )

        structure_alignment = True

    zone_result = calculate_zone_status(
        window=context,
        ob_index=ob_local,
        fvg_index=fvg_local,
        direction=direction,
    )

    liquidity_score = 0.0

    if liquidity_present:
        liquidity_score += 0.45

    if confirmed_liquidity:
        liquidity_score += 0.35

    if penetration_atr >= 0.05:
        liquidity_score += 0.20

    liquidity_score = min(
        liquidity_score,
        1.0,
    )

    structure_score = 0.0

    if structure_alignment:
        structure_score += 0.45

    if bos_present:
        structure_score += 0.25

    if choch_present:
        structure_score += 0.30

    structure_score = min(
        structure_score,
        1.0,
    )

    market_context_score = (
        0.40 * liquidity_score
        + 0.35 * structure_score
        + 0.25
        * zone_result["zone_score"]
    )

    return {
        "ohlcv_path_v5": str(
            source_path
        ),
        "liquidity_present_v5": (
            liquidity_present
        ),
        "liquidity_confirmed_v5": (
            confirmed_liquidity
        ),
        "liquidity_score_v5": (
            liquidity_score
        ),
        "sweep_distance_v5": (
            sweep_distance
        ),
        "penetration_atr_v5": (
            penetration_atr
        ),
        "confirmation_type_v5": (
            confirmation_type
        ),
        "bos_present_v5": (
            bos_present
        ),
        "choch_present_v5": (
            choch_present
        ),
        "structure_alignment_v5": (
            structure_alignment
        ),
        "market_structure_score_v5": (
            structure_score
        ),
        "zone_status_v5": (
            zone_result[
                "zone_status"
            ]
        ),
        "zone_fresh_v5": (
            zone_result[
                "zone_fresh"
            ]
        ),
        "zone_mitigated_v5": (
            zone_result[
                "zone_mitigated"
            ]
        ),
        "zone_touch_count_v5": (
            zone_result[
                "zone_touch_count"
            ]
        ),
        "zone_score_v5": (
            zone_result[
                "zone_score"
            ]
        ),
        "zone_low_v5": (
            zone_result.get(
                "zone_low",
                np.nan,
            )
        ),
        "zone_high_v5": (
            zone_result.get(
                "zone_high",
                np.nan,
            )
        ),
        "market_context_score_v5": (
            market_context_score
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "scoring_v4_results.csv"
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
            "ai/structure/reports/"
            "pairs_structure_enriched.csv"
        ),
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
            )

            result[
                "structure_error_v5"
            ] = ""

        except Exception as error:
            result = {
                "liquidity_present_v5": False,
                "liquidity_confirmed_v5": False,
                "liquidity_score_v5": 0.0,
                "bos_present_v5": False,
                "choch_present_v5": False,
                "structure_alignment_v5": False,
                "market_structure_score_v5": 0.0,
                "zone_status_v5": "error",
                "zone_fresh_v5": False,
                "zone_mitigated_v5": False,
                "zone_touch_count_v5": 0,
                "zone_score_v5": 0.0,
                "zone_low_v5": np.nan,
                "zone_high_v5": np.nan,
                "market_context_score_v5": 0.0,
                "structure_error_v5": str(
                    error
                ),
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

    print("")
    print(
        "Structure enrichment selesai"
    )
    print(
        f"Total setups       : "
        f"{len(enriched)}"
    )
    print(
        f"Liquidity present  : "
        f"{enriched['liquidity_present_v5'].sum()}"
    )
    print(
        f"Confirmed sweep    : "
        f"{enriched['liquidity_confirmed_v5'].sum()}"
    )
    print(
        f"BOS present        : "
        f"{enriched['bos_present_v5'].sum()}"
    )
    print(
        f"CHoCH present      : "
        f"{enriched['choch_present_v5'].sum()}"
    )
    print(
        f"Fresh zones        : "
        f"{enriched['zone_fresh_v5'].sum()}"
    )
    print(
        f"Average context    : "
        f"{enriched['market_context_score_v5'].mean():.4f}"
    )
    print(
        f"Errors             : "
        f"{enriched['structure_error_v5'].ne('').sum()}"
    )
    print(
        f"Output             : "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()



