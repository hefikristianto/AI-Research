from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle


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


def read_mt5_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        sep=r"\s+",
        engine="python",
    )

    df = df.rename(columns=COLUMN_MAP)

    required = [
        "date",
        "time",
        "open",
        "high",
        "low",
        "close",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Kolom wajib tidak ditemukan pada {path}: {missing}"
        )

    df["datetime"] = pd.to_datetime(
        df["date"].astype(str)
        + " "
        + df["time"].astype(str),
        format="%Y.%m.%d %H:%M:%S",
        errors="coerce",
    )

    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "datetime",
            "open",
            "high",
            "low",
            "close",
        ]
    )

    valid = (
        (df["high"] >= df[["open", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
        & (df["high"] >= df["low"])
        & (df["open"] > 0)
        & (df["high"] > 0)
        & (df["low"] > 0)
        & (df["close"] > 0)
    )

    df = df.loc[valid].copy()

    df = (
        df.sort_values("datetime")
        .drop_duplicates(
            subset=["datetime"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return df



def sanitize_window_outliers(
    window: pd.DataFrame,
    range_multiplier: float = 8.0,
) -> tuple[pd.DataFrame, int]:
    """
    Membatasi wick ekstrem tanpa mengubah nilai open dan close.

    Candle dianggap outlier jika:
        high - low > median candle range * range_multiplier

    Nilai high dan low kemudian dibatasi berdasarkan body candle
    dan batas wick maksimum. Open dan close tetap dipertahankan.
    """
    cleaned = window.copy()

    candle_range = (
        cleaned["high"] - cleaned["low"]
    ).astype(float)

    positive_ranges = candle_range.loc[
        candle_range > 0
    ]

    if positive_ranges.empty:
        return cleaned, 0

    median_range = float(
        positive_ranges.median()
    )

    if not np.isfinite(median_range) or median_range <= 0:
        return cleaned, 0

    maximum_range = (
        median_range * range_multiplier
    )

    outlier_mask = (
        candle_range > maximum_range
    )

    corrected_count = int(
        outlier_mask.sum()
    )

    if corrected_count == 0:
        return cleaned, 0

    for index in cleaned.index[outlier_mask]:
        open_price = float(
            cleaned.at[index, "open"]
        )

        close_price = float(
            cleaned.at[index, "close"]
        )

        original_high = float(
            cleaned.at[index, "high"]
        )

        original_low = float(
            cleaned.at[index, "low"]
        )

        body_high = max(
            open_price,
            close_price,
        )

        body_low = min(
            open_price,
            close_price,
        )

        body_size = (
            body_high - body_low
        )

        allowed_total_range = max(
            maximum_range,
            body_size * 1.10,
        )

        available_wick_range = max(
            allowed_total_range - body_size,
            median_range,
        )

        upper_wick_limit = (
            available_wick_range / 2.0
        )

        lower_wick_limit = (
            available_wick_range / 2.0
        )

        cleaned.at[index, "high"] = min(
            original_high,
            body_high + upper_wick_limit,
        )

        cleaned.at[index, "low"] = max(
            original_low,
            body_low - lower_wick_limit,
        )

        cleaned.at[index, "high"] = max(
            cleaned.at[index, "high"],
            body_high,
        )

        cleaned.at[index, "low"] = min(
            cleaned.at[index, "low"],
            body_low,
        )

    return cleaned, corrected_count


def render_candlestick(
    window: pd.DataFrame,
    output_path: Path,
    image_size: int,
    dpi: int,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    width_inches = image_size / dpi

    fig, ax = plt.subplots(
        figsize=(width_inches, width_inches),
        dpi=dpi,
    )

    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    opens = window["open"].to_numpy(dtype=float)
    highs = window["high"].to_numpy(dtype=float)
    lows = window["low"].to_numpy(dtype=float)
    closes = window["close"].to_numpy(dtype=float)

    x_positions = np.arange(len(window))

    candle_width = 0.62

    full_range = float(
        np.nanmax(highs) - np.nanmin(lows)
    )

    minimum_body = max(
        full_range * 0.0015,
        float(np.nanmean(closes)) * 1e-7,
    )

    for index, x_value in enumerate(x_positions):
        bullish = closes[index] >= opens[index]

        body_color = (
            "#22a06b"
            if bullish
            else "#d64545"
        )

        wick_color = "#2b2b2b"

        ax.vlines(
            x=x_value,
            ymin=lows[index],
            ymax=highs[index],
            color=wick_color,
            linewidth=0.65,
        )

        body_bottom = min(
            opens[index],
            closes[index],
        )

        body_height = abs(
            closes[index] - opens[index]
        )

        if body_height < minimum_body:
            body_height = minimum_body
            body_bottom -= minimum_body / 2.0

        rectangle = Rectangle(
            (
                x_value - candle_width / 2.0,
                body_bottom,
            ),
            candle_width,
            body_height,
            facecolor=body_color,
            edgecolor=body_color,
            linewidth=0.45,
        )

        ax.add_patch(rectangle)

    price_min = float(np.nanmin(lows))
    price_max = float(np.nanmax(highs))

    price_padding = max(
        (price_max - price_min) * 0.05,
        abs(price_max) * 1e-6,
    )

    ax.set_xlim(
        -1,
        len(window),
    )

    ax.set_ylim(
        price_min - price_padding,
        price_max + price_padding,
    )

    ax.set_xticks([])
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.subplots_adjust(
        left=0,
        right=1,
        top=1,
        bottom=0,
    )

    fig.savefig(
        output_path,
        dpi=dpi,
        bbox_inches=None,
        pad_inches=0,
        facecolor="white",
    )

    plt.close(fig)


def resolve_source_path(
    source_value: str,
    project_root: Path,
) -> Path:
    source_path = Path(source_value)

    if source_path.is_absolute():
        return source_path

    return project_root / source_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Render market regime CNN dataset "
            "dari selected manifest."
        )
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "ai/datasets/classification/"
            "market_regime/"
            "market_regime_selected_manifest.csv"
        ),
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            "ai/datasets/classification/"
            "market_regime"
        ),
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "ai/classification/reports/"
            "market_regime_render_report.json"
        ),
    )

    parser.add_argument(
        "--image-size",
        type=int,
        default=224,
    )

    parser.add_argument(
        "--dpi",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Jumlah maksimum gambar. "
            "Gunakan 0 untuk seluruh manifest."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    args = parser.parse_args()

    project_root = Path.cwd()

    if not args.manifest.exists():
        raise FileNotFoundError(
            f"Manifest tidak ditemukan: {args.manifest}"
        )

    manifest = pd.read_csv(args.manifest)

    required_columns = {
        "sample_id",
        "split",
        "label",
        "source_file",
        "start_index",
        "end_index",
    }

    missing = required_columns - set(manifest.columns)

    if missing:
        raise ValueError(
            f"Kolom manifest kurang: {sorted(missing)}"
        )

    if args.limit > 0:
        manifest = manifest.head(args.limit).copy()

    cache: dict[str, pd.DataFrame] = {}

    rendered = 0
    skipped_existing = 0
    corrected_candles = 0
    corrected_windows = 0
    failed: list[dict] = []

    total = len(manifest)

    for row_number, row in enumerate(
        manifest.itertuples(index=False),
        start=1,
    ):
        output_path = (
            args.output_root
            / str(row.split)
            / str(row.label)
            / f"{row.sample_id}.png"
        )

        if output_path.exists() and not args.overwrite:
            skipped_existing += 1
            continue

        try:
            source_path = resolve_source_path(
                str(row.source_file),
                project_root,
            )

            cache_key = str(source_path)

            if cache_key not in cache:
                cache[cache_key] = read_mt5_ohlcv(
                    source_path
                )

            dataframe = cache[cache_key]

            start_index = int(row.start_index)
            end_index = int(row.end_index)

            window = dataframe.iloc[
                start_index:end_index + 1
            ].copy()

            window, window_corrected = (
                sanitize_window_outliers(
                    window=window,
                    range_multiplier=8.0,
                )
            )

            if window_corrected > 0:
                corrected_candles += (
                    window_corrected
                )
                corrected_windows += 1

            expected_size = (
                end_index - start_index + 1
            )

            if len(window) != expected_size:
                raise ValueError(
                    f"Window hanya {len(window)} row, "
                    f"seharusnya {expected_size}"
                )

            render_candlestick(
                window=window,
                output_path=output_path,
                image_size=args.image_size,
                dpi=args.dpi,
            )

            rendered += 1

        except Exception as exc:
            failed.append(
                {
                    "sample_id": str(row.sample_id),
                    "source_file": str(row.source_file),
                    "error": str(exc),
                }
            )

        if (
            row_number == 1
            or row_number % 250 == 0
            or row_number == total
        ):
            print(
                f"[{row_number}/{total}] "
                f"rendered={rendered}, "
                f"existing={skipped_existing}, "
                f"failed={len(failed)}, "
                f"corrected_windows={corrected_windows}, "
                f"corrected_candles={corrected_candles}"
            )

    distribution = (
        manifest.groupby(["split", "label"])
        .size()
        .unstack(fill_value=0)
        .to_dict(orient="index")
    )

    report = {
        "configuration": {
            "manifest": str(args.manifest),
            "output_root": str(args.output_root),
            "image_size": args.image_size,
            "dpi": args.dpi,
            "limit": args.limit,
            "overwrite": args.overwrite,
        },
        "result": {
            "requested": total,
            "rendered": rendered,
            "skipped_existing": skipped_existing,
            "failed": len(failed),
            "corrected_windows": corrected_windows,
            "corrected_candles": corrected_candles,
        },
        "distribution": distribution,
        "failed_samples": failed,
    }

    args.report.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.report.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            default=str,
        )

    print("")
    print("Render selesai")
    print(f"Rendered : {rendered}")
    print(f"Existing : {skipped_existing}")
    print(f"Failed            : {len(failed)}")
    print(f"Corrected windows : {corrected_windows}")
    print(f"Corrected candles : {corrected_candles}")
    print(f"Report            : {args.report}")


if __name__ == "__main__":
    main()
