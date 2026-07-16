from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_ohlcv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"OHLCV tidak ditemukan: {path}"
        )

    dataframe = pd.read_csv(
        path,
        sep=r"\s+|,",
        engine="python",
    )

    dataframe.columns = [
        str(column)
        .replace("<", "")
        .replace(">", "")
        .strip()
        .lower()
        for column in dataframe.columns
    ]

    aliases = {
        "date": "date",
        "time": "time",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "tickvol": "tick_volume",
        "tick_volume": "tick_volume",
        "vol": "volume",
        "volume": "volume",
        "spread": "spread",
    }

    dataframe = dataframe.rename(
        columns={
            column: aliases.get(
                column,
                column,
            )
            for column in dataframe.columns
        }
    )

    required = {
        "open",
        "high",
        "low",
        "close",
    }

    missing = required - set(
        dataframe.columns
    )

    if missing:
        raise ValueError(
            f"Kolom OHLCV kurang: {sorted(missing)}"
        )

    if (
        "date" in dataframe.columns
        and "time" in dataframe.columns
    ):
        dataframe["datetime"] = pd.to_datetime(
            dataframe["date"].astype(str)
            + " "
            + dataframe["time"].astype(str),
            errors="coerce",
        )

    elif "datetime" in dataframe.columns:
        dataframe["datetime"] = pd.to_datetime(
            dataframe["datetime"],
            errors="coerce",
        )

    else:
        dataframe["datetime"] = pd.RangeIndex(
            start=0,
            stop=len(dataframe),
        )

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
    ]

    for column in numeric_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe = dataframe.dropna(
        subset=numeric_columns
    ).reset_index(drop=True)

    return dataframe


def calculate_atr(
    dataframe: pd.DataFrame,
    period: int = 14,
) -> pd.Series:
    previous_close = (
        dataframe["close"].shift(1)
    )

    true_range = pd.concat(
        [
            dataframe["high"]
            - dataframe["low"],
            (
                dataframe["high"]
                - previous_close
            ).abs(),
            (
                dataframe["low"]
                - previous_close
            ).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.rolling(
        period,
        min_periods=1,
    ).mean()


def detect_swings(
    dataframe: pd.DataFrame,
    left: int,
    right: int,
) -> pd.DataFrame:
    output = dataframe.copy()

    output["swing_high"] = False
    output["swing_low"] = False

    highs = output["high"].to_numpy()
    lows = output["low"].to_numpy()

    for index in range(
        left,
        len(output) - right,
    ):
        high_window = highs[
            index - left:
            index + right + 1
        ]

        low_window = lows[
            index - left:
            index + right + 1
        ]

        current_high = highs[index]
        current_low = lows[index]

        if current_high == np.max(high_window):
            if np.sum(
                high_window == current_high
            ) == 1:
                output.loc[
                    index,
                    "swing_high",
                ] = True

        if current_low == np.min(low_window):
            if np.sum(
                low_window == current_low
            ) == 1:
                output.loc[
                    index,
                    "swing_low",
                ] = True

    return output


def detect_equal_levels(
    dataframe: pd.DataFrame,
    tolerance_atr: float,
    lookback_swings: int,
) -> pd.DataFrame:
    swings_high = dataframe[
        dataframe["swing_high"]
    ].copy()

    swings_low = dataframe[
        dataframe["swing_low"]
    ].copy()

    liquidity_rows = []

    high_records = swings_high.to_dict(
        orient="records"
    )

    for index, current in enumerate(
        high_records
    ):
        previous_candidates = high_records[
            max(
                0,
                index - lookback_swings,
            ):
            index
        ]

        for previous in reversed(
            previous_candidates
        ):
            tolerance = (
                max(
                    current["atr"],
                    previous["atr"],
                )
                * tolerance_atr
            )

            distance = abs(
                current["high"]
                - previous["high"]
            )

            if distance <= tolerance:
                liquidity_rows.append(
                    {
                        "liquidity_type": (
                            "buy_side"
                        ),
                        "level": float(
                            (
                                current["high"]
                                + previous["high"]
                            )
                            / 2.0
                        ),
                        "first_index": int(
                            previous["index"]
                        ),
                        "second_index": int(
                            current["index"]
                        ),
                        "distance": float(
                            distance
                        ),
                        "tolerance": float(
                            tolerance
                        ),
                    }
                )
                break

    low_records = swings_low.to_dict(
        orient="records"
    )

    for index, current in enumerate(
        low_records
    ):
        previous_candidates = low_records[
            max(
                0,
                index - lookback_swings,
            ):
            index
        ]

        for previous in reversed(
            previous_candidates
        ):
            tolerance = (
                max(
                    current["atr"],
                    previous["atr"],
                )
                * tolerance_atr
            )

            distance = abs(
                current["low"]
                - previous["low"]
            )

            if distance <= tolerance:
                liquidity_rows.append(
                    {
                        "liquidity_type": (
                            "sell_side"
                        ),
                        "level": float(
                            (
                                current["low"]
                                + previous["low"]
                            )
                            / 2.0
                        ),
                        "first_index": int(
                            previous["index"]
                        ),
                        "second_index": int(
                            current["index"]
                        ),
                        "distance": float(
                            distance
                        ),
                        "tolerance": float(
                            tolerance
                        ),
                    }
                )
                break

    return pd.DataFrame(
        liquidity_rows
    )


def detect_sweeps(
    dataframe: pd.DataFrame,
    liquidity: pd.DataFrame,
    max_bars_after_level: int,
) -> pd.DataFrame:
    sweep_rows = []

    if liquidity.empty:
        return pd.DataFrame(
            sweep_rows
        )

    for _, level_row in liquidity.iterrows():
        start_index = int(
            level_row["second_index"]
        ) + 1

        end_index = min(
            len(dataframe),
            start_index
            + max_bars_after_level,
        )

        level = float(
            level_row["level"]
        )

        for candle_index in range(
            start_index,
            end_index,
        ):
            candle = dataframe.iloc[
                candle_index
            ]

            if (
                level_row["liquidity_type"]
                == "buy_side"
            ):
                swept = (
                    candle["high"] > level
                    and candle["close"] < level
                )

                direction = (
                    "bearish_candidate"
                )

                penetration = (
                    candle["high"] - level
                )

            else:
                swept = (
                    candle["low"] < level
                    and candle["close"] > level
                )

                direction = (
                    "bullish_candidate"
                )

                penetration = (
                    level - candle["low"]
                )

            if swept:
                sweep_rows.append(
                    {
                        "liquidity_type": (
                            level_row[
                                "liquidity_type"
                            ]
                        ),
                        "liquidity_level": level,
                        "liquidity_first_index": int(
                            level_row[
                                "first_index"
                            ]
                        ),
                        "liquidity_second_index": int(
                            level_row[
                                "second_index"
                            ]
                        ),
                        "sweep_index": candle_index,
                        "sweep_datetime": str(
                            candle["datetime"]
                        ),
                        "sweep_direction": direction,
                        "penetration": float(
                            penetration
                        ),
                        "sweep_close": float(
                            candle["close"]
                        ),
                        "atr": float(
                            candle["atr"]
                        ),
                        "penetration_atr": float(
                            penetration
                            / max(
                                candle["atr"],
                                1e-12,
                            )
                        ),
                    }
                )
                break

    return pd.DataFrame(
        sweep_rows
    )


def detect_structure_breaks(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    events = []

    last_swing_high = None
    last_swing_low = None
    current_trend = "unknown"

    for index, candle in (
        dataframe.iterrows()
    ):
        if candle["swing_high"]:
            last_swing_high = {
                "index": index,
                "price": float(
                    candle["high"]
                ),
            }

        if candle["swing_low"]:
            last_swing_low = {
                "index": index,
                "price": float(
                    candle["low"]
                ),
            }

        bullish_break = (
            last_swing_high is not None
            and index
            > last_swing_high["index"]
            and candle["close"]
            > last_swing_high["price"]
        )

        bearish_break = (
            last_swing_low is not None
            and index
            > last_swing_low["index"]
            and candle["close"]
            < last_swing_low["price"]
        )

        if bullish_break:
            event_type = (
                "BOS"
                if current_trend
                in {"bullish", "unknown"}
                else "CHOCH"
            )

            events.append(
                {
                    "event_index": index,
                    "event_datetime": str(
                        candle["datetime"]
                    ),
                    "event_type": event_type,
                    "direction": "bullish",
                    "broken_level": (
                        last_swing_high[
                            "price"
                        ]
                    ),
                    "source_swing_index": (
                        last_swing_high[
                            "index"
                        ]
                    ),
                    "close": float(
                        candle["close"]
                    ),
                }
            )

            current_trend = "bullish"
            last_swing_high = None

        elif bearish_break:
            event_type = (
                "BOS"
                if current_trend
                in {"bearish", "unknown"}
                else "CHOCH"
            )

            events.append(
                {
                    "event_index": index,
                    "event_datetime": str(
                        candle["datetime"]
                    ),
                    "event_type": event_type,
                    "direction": "bearish",
                    "broken_level": (
                        last_swing_low[
                            "price"
                        ]
                    ),
                    "source_swing_index": (
                        last_swing_low[
                            "index"
                        ]
                    ),
                    "close": float(
                        candle["close"]
                    ),
                }
            )

            current_trend = "bearish"
            last_swing_low = None

    return pd.DataFrame(events)


def link_sweeps_to_structure(
    sweeps: pd.DataFrame,
    structure: pd.DataFrame,
    max_confirmation_bars: int,
) -> pd.DataFrame:
    if sweeps.empty:
        return sweeps.copy()

    output = sweeps.copy()

    output["confirmation_type"] = None
    output["confirmation_direction"] = None
    output["confirmation_index"] = np.nan
    output["confirmation_distance"] = np.nan
    output["confirmed"] = False

    if structure.empty:
        return output

    for row_index, sweep in (
        output.iterrows()
    ):
        expected_direction = (
            "bullish"
            if sweep["sweep_direction"]
            == "bullish_candidate"
            else "bearish"
        )

        candidates = structure[
            (
                structure["event_index"]
                > sweep["sweep_index"]
            )
            & (
                structure["event_index"]
                <= (
                    sweep["sweep_index"]
                    + max_confirmation_bars
                )
            )
            & (
                structure["direction"]
                == expected_direction
            )
        ]

        if candidates.empty:
            continue

        confirmation = (
            candidates.iloc[0]
        )

        output.loc[
            row_index,
            "confirmation_type",
        ] = confirmation["event_type"]

        output.loc[
            row_index,
            "confirmation_direction",
        ] = confirmation["direction"]

        output.loc[
            row_index,
            "confirmation_index",
        ] = int(
            confirmation["event_index"]
        )

        output.loc[
            row_index,
            "confirmation_distance",
        ] = int(
            confirmation["event_index"]
            - sweep["sweep_index"]
        )

        output.loc[
            row_index,
            "confirmed",
        ] = True

    return output


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--ohlcv",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "ai/structure/reports/latest"
        ),
    )

    parser.add_argument(
        "--swing-left",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--swing-right",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--equal-tolerance-atr",
        type=float,
        default=0.20,
    )

    parser.add_argument(
        "--lookback-swings",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--max-sweep-bars",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--max-confirmation-bars",
        type=int,
        default=20,
    )

    args = parser.parse_args()

    dataframe = load_ohlcv(
        args.ohlcv
    )

    dataframe["index"] = np.arange(
        len(dataframe)
    )

    dataframe["atr"] = calculate_atr(
        dataframe
    )

    dataframe = detect_swings(
        dataframe,
        left=args.swing_left,
        right=args.swing_right,
    )

    liquidity = detect_equal_levels(
        dataframe,
        tolerance_atr=(
            args.equal_tolerance_atr
        ),
        lookback_swings=(
            args.lookback_swings
        ),
    )

    sweeps = detect_sweeps(
        dataframe,
        liquidity,
        max_bars_after_level=(
            args.max_sweep_bars
        ),
    )

    structure = detect_structure_breaks(
        dataframe
    )

    confirmed_sweeps = (
        link_sweeps_to_structure(
            sweeps,
            structure,
            max_confirmation_bars=(
                args.max_confirmation_bars
            ),
        )
    )

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    swing_output = dataframe[
        [
            "index",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "atr",
            "swing_high",
            "swing_low",
        ]
    ]

    swing_output.to_csv(
        args.output_dir
        / "swings.csv",
        index=False,
    )

    liquidity.to_csv(
        args.output_dir
        / "liquidity_levels.csv",
        index=False,
    )

    structure.to_csv(
        args.output_dir
        / "structure_events.csv",
        index=False,
    )

    confirmed_sweeps.to_csv(
        args.output_dir
        / "liquidity_sweeps.csv",
        index=False,
    )

    summary = {
        "ohlcv_source": str(
            args.ohlcv
        ),
        "candles": int(
            len(dataframe)
        ),
        "swing_highs": int(
            dataframe[
                "swing_high"
            ].sum()
        ),
        "swing_lows": int(
            dataframe[
                "swing_low"
            ].sum()
        ),
        "liquidity_levels": int(
            len(liquidity)
        ),
        "liquidity_sweeps": int(
            len(confirmed_sweeps)
        ),
        "confirmed_sweeps": int(
            confirmed_sweeps[
                "confirmed"
            ].sum()
        )
        if not confirmed_sweeps.empty
        else 0,
        "structure_events": int(
            len(structure)
        ),
        "bos_events": int(
            (
                structure[
                    "event_type"
                ]
                == "BOS"
            ).sum()
        )
        if not structure.empty
        else 0,
        "choch_events": int(
            (
                structure[
                    "event_type"
                ]
                == "CHOCH"
            ).sum()
        )
        if not structure.empty
        else 0,
        "parameters": {
            "swing_left": (
                args.swing_left
            ),
            "swing_right": (
                args.swing_right
            ),
            "equal_tolerance_atr": (
                args.equal_tolerance_atr
            ),
            "lookback_swings": (
                args.lookback_swings
            ),
            "max_sweep_bars": (
                args.max_sweep_bars
            ),
            "max_confirmation_bars": (
                args.max_confirmation_bars
            ),
        },
    }

    (
        args.output_dir
        / "structure_summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print("Market Structure Detection selesai")
    print(
        f"Candles          : "
        f"{summary['candles']}"
    )
    print(
        f"Swing highs      : "
        f"{summary['swing_highs']}"
    )
    print(
        f"Swing lows       : "
        f"{summary['swing_lows']}"
    )
    print(
        f"Liquidity levels : "
        f"{summary['liquidity_levels']}"
    )
    print(
        f"Sweeps           : "
        f"{summary['liquidity_sweeps']}"
    )
    print(
        f"Confirmed sweeps : "
        f"{summary['confirmed_sweeps']}"
    )
    print(
        f"BOS              : "
        f"{summary['bos_events']}"
    )
    print(
        f"CHoCH            : "
        f"{summary['choch_events']}"
    )
    print(
        f"Output           : "
        f"{args.output_dir}"
    )


if __name__ == "__main__":
    main()
