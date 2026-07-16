from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


COLUMN_MAP = {
    "<DATE>": "date",
    "<TIME>": "time",
    "<OPEN>": "open",
    "<HIGH>": "high",
    "<LOW>": "low",
    "<CLOSE>": "close",
    "<TICKVOL>": "tick_volume",
    "<VOL>": "volume",
    "<SPREAD>": "spread",
}

SPLIT_BY_YEAR = {
    2020: "train",
    2021: "train",
    2022: "train",
    2023: "train",
    2024: "valid",
    2025: "test",
}


@dataclass
class RegimeFeatures:
    normalized_slope: float
    return_atr: float
    directional_efficiency: float
    structure_score: float
    volatility_ratio: float
    regime_score: float
    confidence: float
    label: str


def read_mt5_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        sep=r"\s+",
        engine="python",
        dtype=str,
    )

    df = df.rename(columns=COLUMN_MAP)

    required = ["date", "time", "open", "high", "low", "close"]
    missing = [column for column in required if column not in df.columns]

    if missing:
        raise ValueError(
            f"Kolom wajib tidak ditemukan pada {path.name}: {missing}"
        )

    df["datetime"] = pd.to_datetime(
        df["date"] + " " + df["time"],
        format="%Y.%m.%d %H:%M:%S",
        errors="coerce",
    )

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "volume",
        "spread",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(
        subset=["datetime", "open", "high", "low", "close"]
    )

    valid_ohlc = (
        (df["high"] >= df[["open", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
        & (df["high"] >= df["low"])
        & (df["open"] > 0)
        & (df["high"] > 0)
        & (df["low"] > 0)
        & (df["close"] > 0)
    )

    df = df.loc[valid_ohlc].copy()

    df = (
        df.sort_values("datetime")
        .drop_duplicates(subset=["datetime"], keep="last")
        .reset_index(drop=True)
    )

    return df


def calculate_atr(window: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = window["close"].shift(1)

    true_range = pd.concat(
        [
            window["high"] - window["low"],
            (window["high"] - previous_close).abs(),
            (window["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.rolling(
        window=period,
        min_periods=period,
    ).mean()


def calculate_structure_score(close: np.ndarray) -> float:
    if len(close) < 10:
        return 0.0

    lookback = min(5, max(2, len(close) // 20))

    rolling_high = (
        pd.Series(close)
        .rolling(lookback, min_periods=lookback)
        .max()
        .dropna()
        .to_numpy()
    )

    rolling_low = (
        pd.Series(close)
        .rolling(lookback, min_periods=lookback)
        .min()
        .dropna()
        .to_numpy()
    )

    if len(rolling_high) < 2 or len(rolling_low) < 2:
        return 0.0

    higher_high = np.mean(np.diff(rolling_high) > 0)
    lower_high = np.mean(np.diff(rolling_high) < 0)

    higher_low = np.mean(np.diff(rolling_low) > 0)
    lower_low = np.mean(np.diff(rolling_low) < 0)

    bullish_structure = (higher_high + higher_low) / 2.0
    bearish_structure = (lower_high + lower_low) / 2.0

    return float(
        np.clip(
            bullish_structure - bearish_structure,
            -1.0,
            1.0,
        )
    )


def extract_regime_features(
    window: pd.DataFrame,
    sideways_threshold: float,
) -> RegimeFeatures:
    close = window["close"].to_numpy(dtype=np.float64)
    high = window["high"].to_numpy(dtype=np.float64)
    low = window["low"].to_numpy(dtype=np.float64)

    atr_series = calculate_atr(window)
    atr = float(atr_series.iloc[-1])

    if not np.isfinite(atr) or atr <= 0:
        atr = float(np.mean(high - low))

    if not np.isfinite(atr) or atr <= 0:
        atr = max(float(np.mean(close)) * 1e-6, 1e-9)

    x = np.arange(len(close), dtype=np.float64)

    slope = float(np.polyfit(x, close, 1)[0])
    normalized_slope = float(
        np.clip((slope * len(close)) / atr, -6.0, 6.0)
    )

    net_change = float(close[-1] - close[0])
    return_atr = float(np.clip(net_change / atr, -6.0, 6.0))

    total_path = float(np.abs(np.diff(close)).sum())

    directional_efficiency = (
        abs(net_change) / total_path
        if total_path > 0
        else 0.0
    )

    directional_efficiency = float(
        np.clip(directional_efficiency, 0.0, 1.0)
    )

    structure_score = calculate_structure_score(close)

    candle_range = high - low
    recent_volatility = float(np.mean(candle_range[-20:]))
    full_volatility = float(np.mean(candle_range))

    volatility_ratio = (
        recent_volatility / full_volatility
        if full_volatility > 0
        else 1.0
    )

    volatility_ratio = float(
        np.clip(volatility_ratio, 0.0, 5.0)
    )

    slope_component = np.tanh(normalized_slope / 2.5)
    return_component = np.tanh(return_atr / 3.0)

    regime_score = float(
        0.45 * slope_component
        + 0.30 * return_component
        + 0.15 * structure_score
        + 0.10
        * np.sign(net_change)
        * directional_efficiency
    )

    directional_strength = (
        0.55 * abs(regime_score)
        + 0.45 * directional_efficiency
    )

    confidence = float(
        np.clip(directional_strength, 0.0, 1.0)
    )

    if (
        abs(regime_score) < sideways_threshold
        or directional_efficiency < 0.12
    ):
        label = "sideways"
    elif regime_score > 0:
        label = "bullish"
    else:
        label = "bearish"

    return RegimeFeatures(
        normalized_slope=normalized_slope,
        return_atr=return_atr,
        directional_efficiency=directional_efficiency,
        structure_score=structure_score,
        volatility_ratio=volatility_ratio,
        regime_score=regime_score,
        confidence=confidence,
        label=label,
    )


def parse_file_metadata(path: Path) -> tuple[str, str, int]:
    match = re.match(
        r"(?P<pair>[A-Z]+)_(?P<timeframe>M5|M15|H1|H4)_(?P<year>\d{4})_RAW\.csv",
        path.name,
    )

    if not match:
        raise ValueError(
            f"Nama file tidak sesuai pola dataset: {path.name}"
        )

    return (
        match.group("pair"),
        match.group("timeframe"),
        int(match.group("year")),
    )


def build_manifest(
    input_root: Path,
    output_csv: Path,
    output_summary: Path,
    window_size: int,
    stride: int,
    sideways_threshold: float,
    minimum_confidence: float,
) -> None:
    records: list[dict] = []
    skipped_files: list[dict] = []

    csv_files = sorted(input_root.rglob("*_RAW.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"Tidak ada file OHLCV di {input_root}"
        )

    for file_path in csv_files:
        try:
            pair, timeframe, year = parse_file_metadata(file_path)
        except ValueError:
            continue

        if year not in SPLIT_BY_YEAR:
            continue

        print(
            f"Processing {pair} {timeframe} {year}: "
            f"{file_path.name}"
        )

        try:
            df = read_mt5_ohlcv(file_path)
        except Exception as exc:
            skipped_files.append(
                {
                    "file": str(file_path),
                    "reason": str(exc),
                }
            )
            print(f"  SKIP: {exc}")
            continue

        if len(df) < window_size:
            skipped_files.append(
                {
                    "file": str(file_path),
                    "reason": (
                        f"Jumlah row {len(df)} "
                        f"lebih kecil dari window {window_size}"
                    ),
                }
            )
            continue

        split = SPLIT_BY_YEAR[year]

        for start_index in range(
            0,
            len(df) - window_size + 1,
            stride,
        ):
            end_index = start_index + window_size
            window = df.iloc[start_index:end_index].copy()

            features = extract_regime_features(
                window=window,
                sideways_threshold=sideways_threshold,
            )

            include_for_training = (
                features.label == "sideways"
                or features.confidence >= minimum_confidence
            )

            sample_id = (
                f"{pair.lower()}_"
                f"{timeframe.lower()}_"
                f"{year}_"
                f"{window.iloc[0]['datetime']:%Y%m%d_%H%M%S}_"
                f"{start_index:06d}"
            )

            records.append(
                {
                    "sample_id": sample_id,
                    "split": split,
                    "pair": pair,
                    "timeframe": timeframe,
                    "year": year,
                    "source_file": str(file_path),
                    "start_index": start_index,
                    "end_index": end_index - 1,
                    "start_datetime": window.iloc[0]["datetime"],
                    "end_datetime": window.iloc[-1]["datetime"],
                    "window_size": window_size,
                    "label": features.label,
                    "confidence": round(features.confidence, 6),
                    "regime_score": round(features.regime_score, 6),
                    "normalized_slope": round(
                        features.normalized_slope,
                        6,
                    ),
                    "return_atr": round(
                        features.return_atr,
                        6,
                    ),
                    "directional_efficiency": round(
                        features.directional_efficiency,
                        6,
                    ),
                    "structure_score": round(
                        features.structure_score,
                        6,
                    ),
                    "volatility_ratio": round(
                        features.volatility_ratio,
                        6,
                    ),
                    "include_for_training": include_for_training,
                }
            )

    if not records:
        raise RuntimeError(
            "Manifest kosong. Periksa path dan format dataset."
        )

    manifest = pd.DataFrame(records)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)

    manifest.to_csv(output_csv, index=False)

    included = manifest.loc[
        manifest["include_for_training"] == True
    ].copy()

    split_distribution = (
        included.groupby(["split", "label"])
        .size()
        .unstack(fill_value=0)
        .reindex(
            index=["train", "valid", "test"],
            fill_value=0,
        )
    )

    pair_distribution = (
        included.groupby(["pair", "label"])
        .size()
        .unstack(fill_value=0)
    )

    timeframe_distribution = (
        included.groupby(["timeframe", "label"])
        .size()
        .unstack(fill_value=0)
    )

    summary = {
        "configuration": {
            "input_root": str(input_root),
            "window_size": window_size,
            "stride": stride,
            "sideways_threshold": sideways_threshold,
            "minimum_confidence": minimum_confidence,
            "split_rule": {
                "train": "2020-2023",
                "valid": "2024",
                "test": "2025",
            },
        },
        "totals": {
            "all_windows": int(len(manifest)),
            "included_windows": int(len(included)),
            "excluded_windows": int(
                len(manifest) - len(included)
            ),
        },
        "split_distribution": split_distribution.to_dict(
            orient="index"
        ),
        "pair_distribution": pair_distribution.to_dict(
            orient="index"
        ),
        "timeframe_distribution": (
            timeframe_distribution.to_dict(orient="index")
        ),
        "skipped_files": skipped_files,
    }

    with output_summary.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(summary, file, indent=2, default=str)

    print("")
    print("Manifest selesai dibuat")
    print(f"Output CSV    : {output_csv}")
    print(f"Output summary: {output_summary}")
    print("")
    print("Distribusi split:")
    print(split_distribution)
    print("")
    print(
        f"Total window   : {len(manifest)}"
    )
    print(
        f"Included       : {len(included)}"
    )
    print(
        f"Excluded       : {len(manifest) - len(included)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate manifest label bullish, bearish, "
            "dan sideways dari OHLCV MT5."
        )
    )

    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("ai/datasets/raw/ohlcv"),
    )

    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path(
            "ai/datasets/classification/"
            "market_regime/market_regime_manifest.csv"
        ),
    )

    parser.add_argument(
        "--output-summary",
        type=Path,
        default=Path(
            "ai/classification/reports/"
            "market_regime_manifest_summary.json"
        ),
    )

    parser.add_argument(
        "--window-size",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--stride",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--sideways-threshold",
        type=float,
        default=0.18,
    )

    parser.add_argument(
        "--minimum-confidence",
        type=float,
        default=0.22,
    )

    args = parser.parse_args()

    build_manifest(
        input_root=args.input_root,
        output_csv=args.output_csv,
        output_summary=args.output_summary,
        window_size=args.window_size,
        stride=args.stride,
        sideways_threshold=args.sideways_threshold,
        minimum_confidence=args.minimum_confidence,
    )


if __name__ == "__main__":
    main()
