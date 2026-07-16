from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


HTF_MAP = {
    "M5": "M15",
    "M15": "H1",
    "H1": "H4",
    "H4": None,
}


def normalize_direction(value: object) -> str:
    text = str(value).strip().lower()

    if "bull" in text or text in {"buy", "long"}:
        return "bullish"

    if "bear" in text or text in {"sell", "short"}:
        return "bearish"

    return "uncertain"


def load_ohlcv(path: Path) -> pd.DataFrame:
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

    rename_map = {
        "tickvol": "tick_volume",
        "vol": "volume",
    }

    dataframe = dataframe.rename(
        columns=rename_map
    )

    required = {
        "date",
        "time",
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

    dataframe["datetime"] = pd.to_datetime(
        dataframe["date"].astype(str)
        + " "
        + dataframe["time"].astype(str),
        errors="coerce",
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
    ]:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe = (
        dataframe
        .dropna(
            subset=[
                "datetime",
                "open",
                "high",
                "low",
                "close",
            ]
        )
        .sort_values("datetime")
        .reset_index(drop=True)
    )

    return dataframe


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
        min_periods=period,
    ).mean()


def determine_htf_trend(
    dataframe: pd.DataFrame,
    end_datetime: pd.Timestamp,
) -> dict:
    history = dataframe[
        dataframe["datetime"]
        <= end_datetime
    ].copy()

    if len(history) < 210:
        return {
            "htf_trend_v6": "neutral",
            "htf_trend_score_raw_v6": 0.50,
            "htf_ema50_v6": np.nan,
            "htf_ema200_v6": np.nan,
            "htf_slope_v6": 0.0,
        }

    history["ema50"] = (
        history["close"]
        .ewm(
            span=50,
            adjust=False,
        )
        .mean()
    )

    history["ema200"] = (
        history["close"]
        .ewm(
            span=200,
            adjust=False,
        )
        .mean()
    )

    latest = history.iloc[-1]

    ema50 = float(
        latest["ema50"]
    )

    ema200 = float(
        latest["ema200"]
    )

    close = float(
        latest["close"]
    )

    previous_ema50 = float(
        history.iloc[-11]["ema50"]
    )

    slope = (
        ema50 - previous_ema50
    ) / max(
        abs(previous_ema50),
        1e-12,
    )

    if (
        close > ema50 > ema200
        and slope > 0
    ):
        trend = "bullish"
        raw_score = 1.0

    elif (
        close < ema50 < ema200
        and slope < 0
    ):
        trend = "bearish"
        raw_score = 1.0

    else:
        trend = "neutral"
        raw_score = 0.50

    return {
        "htf_trend_v6": trend,
        "htf_trend_score_raw_v6": raw_score,
        "htf_ema50_v6": ema50,
        "htf_ema200_v6": ema200,
        "htf_slope_v6": float(slope),
    }


def calculate_htf_alignment(
    setup_direction: str,
    htf_trend: str,
) -> float:
    if (
        setup_direction == "uncertain"
        or htf_trend == "neutral"
    ):
        return 0.50

    if setup_direction == htf_trend:
        return 1.00

    return 0.00


def calculate_volatility_context(
    dataframe: pd.DataFrame,
    end_datetime: pd.Timestamp,
) -> dict:
    history = dataframe[
        dataframe["datetime"]
        <= end_datetime
    ].copy()

    history["atr"] = calculate_atr(
        history
    )

    atr_history = (
        history["atr"]
        .dropna()
        .tail(250)
    )

    if len(atr_history) < 30:
        return {
            "atr_v6": np.nan,
            "atr_percentile_v6": 0.50,
            "volatility_regime_v6": "unknown",
            "volatility_score_v6": 0.50,
        }

    current_atr = float(
        atr_history.iloc[-1]
    )

    percentile = float(
        (
            atr_history
            <= current_atr
        ).mean()
    )

    if percentile < 0.20:
        regime = "low"
        score = 0.35

    elif percentile <= 0.80:
        regime = "normal"
        score = 1.00

    elif percentile <= 0.95:
        regime = "high"
        score = 0.65

    else:
        regime = "extreme"
        score = 0.25

    return {
        "atr_v6": current_atr,
        "atr_percentile_v6": percentile,
        "volatility_regime_v6": regime,
        "volatility_score_v6": score,
    }


def calculate_session_context(
    timestamp: pd.Timestamp,
    time_shift_hours: float,
) -> dict:
    shifted = (
        timestamp
        + pd.Timedelta(
            hours=time_shift_hours
        )
    )

    hour = shifted.hour

    if 7 <= hour < 13:
        session = "asia"
        score = 0.55

    elif 13 <= hour < 19:
        session = "london"
        score = 1.00

    elif 19 <= hour < 24:
        session = "new_york"
        score = 1.00

    else:
        session = "off_session"
        score = 0.35

    return {
        "session_datetime_v6": str(
            shifted
        ),
        "session_v6": session,
        "session_score_v6": score,
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "scoring_v5_1_results.csv"
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
            "pairs_context_v6.csv"
        ),
    )

    parser.add_argument(
        "--time-shift-hours",
        type=float,
        default=0.0,
        help=(
            "Perubahan jam dari timestamp MT5 "
            "ke zona waktu analisis. Default 0 "
            "karena timezone broker belum dikunci."
        ),
    )

    args = parser.parse_args()

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
            pair = str(
                row["pair"]
            ).upper()

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

            htf = HTF_MAP.get(
                timeframe,
            )

            local_path = resolve_ohlcv_path(
                args.ohlcv_root,
                pair,
                timeframe,
                year,
            )

            local_dataframe = load_ohlcv(
                local_path
            )

            if htf is None:
                htf_path = None

                trend_result = {
                    "htf_trend_v6": "neutral",
                    "htf_trend_score_raw_v6": 0.50,
                    "htf_ema50_v6": np.nan,
                    "htf_ema200_v6": np.nan,
                    "htf_slope_v6": 0.0,
                }

                htf_alignment = 0.50

            else:
                htf_path = resolve_ohlcv_path(
                    args.ohlcv_root,
                    pair,
                    htf,
                    year,
                )

                htf_dataframe = load_ohlcv(
                    htf_path
                )

                trend_result = determine_htf_trend(
                    htf_dataframe,
                    end_datetime,
                )

                htf_alignment = (
                    calculate_htf_alignment(
                        direction,
                        trend_result[
                            "htf_trend_v6"
                        ],
                    )
                )

            volatility_result = (
                calculate_volatility_context(
                    local_dataframe,
                    end_datetime,
                )
            )

            session_result = (
                calculate_session_context(
                    end_datetime,
                    args.time_shift_hours,
                )
            )

            result = {
                "htf_timeframe_v6": htf,
                "htf_ohlcv_path_v6": (
                    str(htf_path)
                    if htf_path is not None
                    else ""
                ),
                **trend_result,
                "htf_alignment_v6": (
                    htf_alignment
                ),
                **volatility_result,
                **session_result,
                "context_error_v6": "",
            }

        except Exception as error:
            result = {
                "htf_timeframe_v6": "",
                "htf_trend_v6": "unknown",
                "htf_trend_score_raw_v6": 0.50,
                "htf_alignment_v6": 0.50,
                "htf_ema50_v6": np.nan,
                "htf_ema200_v6": np.nan,
                "htf_slope_v6": 0.0,
                "atr_v6": np.nan,
                "atr_percentile_v6": 0.50,
                "volatility_regime_v6": "unknown",
                "volatility_score_v6": 0.50,
                "session_v6": "unknown",
                "session_score_v6": 0.50,
                "context_error_v6": str(
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
    print("Context enrichment v6 selesai")
    print(
        f"Total setups      : "
        f"{len(enriched)}"
    )
    print(
        f"HTF aligned       : "
        f"{(enriched['htf_alignment_v6'] == 1.0).sum()}"
    )
    print(
        f"HTF conflict      : "
        f"{(enriched['htf_alignment_v6'] == 0.0).sum()}"
    )
    print(
        f"HTF neutral       : "
        f"{(enriched['htf_alignment_v6'] == 0.5).sum()}"
    )
    print("")
    print("Session:")
    print(
        enriched["session_v6"]
        .value_counts()
        .to_string()
    )
    print("")
    print("Volatility:")
    print(
        enriched[
            "volatility_regime_v6"
        ]
        .value_counts()
        .to_string()
    )
    print("")
    print(
        f"Errors            : "
        f"{enriched['context_error_v6'].ne('').sum()}"
    )
    print(f"Output            : {args.output}")


if __name__ == "__main__":
    main()

