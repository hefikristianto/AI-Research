from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

RAW_OHLCV_ROOT = (
    PROJECT_ROOT
    / "ai"
    / "datasets"
    / "raw"
    / "ohlcv"
)


class OHLCVContextService:
    REQUIRED_COLUMNS = {
        "open",
        "high",
        "low",
        "close",
    }

    @staticmethod
    def _clean_column_name(
        column: Any,
    ) -> str:
        name = str(column)

        name = name.replace(
            "\ufeff",
            "",
        )

        name = name.strip().lower()

        name = re.sub(
            r"[<>\[\]\{\}\(\)]",
            "",
            name,
        )

        name = re.sub(
            r"[^a-z0-9]+",
            "_",
            name,
        )

        return name.strip("_")

    @staticmethod
    def _normalize_timestamp(
        value: str | pd.Timestamp,
    ) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)

        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_localize(
                None
            )

        return timestamp

    @classmethod
    def _read_csv(
        cls,
        path: Path,
    ) -> pd.DataFrame:
        attempts: list[
            tuple[str, str | None]
        ] = [
            ("utf-8-sig", r"\s+"),
            ("utf-8", r"\s+"),
            ("cp1252", r"\s+"),
            ("utf-8-sig", "\t"),
            ("utf-8", "\t"),
            ("cp1252", "\t"),
            ("utf-8-sig", None),
            ("utf-8", None),
            ("cp1252", None),
            ("utf-8-sig", ","),
            ("utf-8", ","),
            ("utf-8-sig", ";"),
            ("utf-8", ";"),
        ]

        errors: list[str] = []

        for encoding, separator in attempts:
            try:
                if separator is None:
                    dataframe = pd.read_csv(
                        path,
                        sep=None,
                        engine="python",
                        encoding=encoding,
                    )

                else:
                    dataframe = pd.read_csv(
                        path,
                        sep=separator,
                        engine="python",
                        encoding=encoding,
                    )

                if len(dataframe.columns) <= 1:
                    errors.append(
                        f"{encoding} {separator!r}: "
                        "hanya satu kolom"
                    )
                    continue

                cleaned_columns = [
                    cls._clean_column_name(
                        column
                    )
                    for column in dataframe.columns
                ]

                expected = {
                    "date",
                    "time",
                    "open",
                    "high",
                    "low",
                    "close",
                }

                if expected.issubset(
                    set(cleaned_columns)
                ):
                    return dataframe

                errors.append(
                    f"{encoding} {separator!r}: "
                    f"kolom={cleaned_columns}"
                )

            except Exception as error:
                errors.append(
                    f"{encoding} {separator!r}: "
                    f"{error}"
                )

        raise ValueError(
            "CSV OHLCV gagal dibaca sebagai "
            "format MT5. Percobaan terakhir: "
            + " | ".join(
                errors[-6:]
            )
        )

    @classmethod
    def _standardize_columns(
        cls,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        dataframe = dataframe.copy()

        dataframe.columns = [
            cls._clean_column_name(
                column
            )
            for column in dataframe.columns
        ]

        rename_map = {
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "tick_volume": "tickvol",
            "tickvolume": "tickvol",
            "tick_vol": "tickvol",
            "realvolume": "real_volume",
        }

        dataframe = dataframe.rename(
            columns=rename_map
        )

        if (
            "date" not in dataframe.columns
            or "time" not in dataframe.columns
        ):
            raise ValueError(
                "Kolom DATE dan TIME tidak "
                "ditemukan setelah normalisasi. "
                f"Kolom terbaca: "
                f"{list(dataframe.columns)}"
            )

        missing_columns = (
            cls.REQUIRED_COLUMNS
            - set(dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Kolom harga OHLCV tidak lengkap: "
                + ", ".join(
                    sorted(missing_columns)
                )
                + ". Kolom terbaca: "
                + str(
                    list(dataframe.columns)
                )
            )

        combined_datetime = (
            dataframe["date"]
            .astype(str)
            .str.strip()
            + " "
            + dataframe["time"]
            .astype(str)
            .str.strip()
        )

        datetime_series = pd.to_datetime(
            combined_datetime,
            format="%Y.%m.%d %H:%M:%S",
            errors="coerce",
        )

        if datetime_series.notna().mean() < 0.80:
            fallback_series = pd.to_datetime(
                combined_datetime,
                errors="coerce",
            )

            if (
                fallback_series.notna().mean()
                > datetime_series.notna().mean()
            ):
                datetime_series = (
                    fallback_series
                )

        valid_datetime_ratio = float(
            datetime_series.notna().mean()
        )

        if valid_datetime_ratio < 0.80:
            raise ValueError(
                "Nilai DATE dan TIME ditemukan, "
                "tetapi gagal dikonversi. "
                f"Rasio valid: "
                f"{valid_datetime_ratio:.2%}. "
                f"Contoh nilai: "
                f"{combined_datetime.head(3).tolist()}"
            )

        dataframe["datetime"] = (
            datetime_series
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "tickvol",
            "vol",
            "volume",
            "real_volume",
            "spread",
        ]

        for column in numeric_columns:
            if column not in dataframe.columns:
                continue

            values = (
                dataframe[column]
                .astype(str)
                .str.strip()
                .str.replace(
                    " ",
                    "",
                    regex=False,
                )
                .str.replace(
                    ",",
                    ".",
                    regex=False,
                )
            )

            dataframe[column] = pd.to_numeric(
                values,
                errors="coerce",
            )

        if "tickvol" in dataframe.columns:
            dataframe["volume"] = dataframe[
                "tickvol"
            ]

        elif "volume" not in dataframe.columns:
            if "vol" in dataframe.columns:
                dataframe["volume"] = dataframe[
                    "vol"
                ]

            elif (
                "real_volume"
                in dataframe.columns
            ):
                dataframe["volume"] = dataframe[
                    "real_volume"
                ]

        dataframe = dataframe.dropna(
            subset=[
                "datetime",
                "open",
                "high",
                "low",
                "close",
            ]
        )

        dataframe = (
            dataframe
            .sort_values("datetime")
            .drop_duplicates(
                subset=["datetime"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        if dataframe.empty:
            raise ValueError(
                "Dataset OHLCV kosong setelah "
                "normalisasi."
            )

        return dataframe

    @staticmethod
    def _candidate_years(
        window_start_datetime: str | None,
        chart_datetime: str | None,
    ) -> list[int]:
        if chart_datetime:
            year = pd.Timestamp(
                chart_datetime
            ).year

            return sorted(
                {
                    year - 1,
                    year,
                }
            )

        if window_start_datetime:
            year = pd.Timestamp(
                window_start_datetime
            ).year

            return sorted(
                {
                    year,
                    year + 1,
                }
            )

        return []

    @staticmethod
    def _build_path(
        pair: str,
        timeframe: str,
        year: int,
    ) -> Path:
        return (
            RAW_OHLCV_ROOT
            / pair
            / timeframe
            / str(year)
            / (
                f"{pair}_{timeframe}_"
                f"{year}_RAW.csv"
            )
        )

    def _load_data(
        self,
        pair: str,
        timeframe: str,
        years: list[int],
    ) -> tuple[
        pd.DataFrame,
        list[str],
    ]:
        dataframes: list[pd.DataFrame] = []
        source_paths: list[str] = []

        attempted_paths: list[str] = []

        for year in years:
            path = self._build_path(
                pair=pair,
                timeframe=timeframe,
                year=year,
            )

            attempted_paths.append(
                str(path)
            )

            if not path.exists():
                continue

            raw_dataframe = self._read_csv(
                path
            )

            dataframe = (
                self._standardize_columns(
                    raw_dataframe
                )
            )

            dataframes.append(dataframe)
            source_paths.append(str(path))

        if not dataframes:
            raise FileNotFoundError(
                "File OHLCV tidak ditemukan "
                "atau gagal dimuat. Path: "
                + " | ".join(
                    attempted_paths
                )
            )

        combined = pd.concat(
            dataframes,
            ignore_index=True,
        )

        combined = (
            combined
            .sort_values("datetime")
            .drop_duplicates(
                subset=["datetime"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        return combined, source_paths

    @staticmethod
    def _calculate_metrics(
        dataframe: pd.DataFrame,
    ) -> dict[str, Any]:
        close = dataframe["close"]
        high = dataframe["high"]
        low = dataframe["low"]

        previous_close = close.shift(1)

        true_range = pd.concat(
            [
                high - low,
                (
                    high
                    - previous_close
                ).abs(),
                (
                    low
                    - previous_close
                ).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr14 = true_range.rolling(
            window=14,
            min_periods=1,
        ).mean()

        ema50 = close.ewm(
            span=50,
            adjust=False,
        ).mean()

        ema200 = close.ewm(
            span=200,
            adjust=False,
        ).mean()

        latest_ema50 = float(
            ema50.iloc[-1]
        )

        latest_ema200 = float(
            ema200.iloc[-1]
        )

        if len(ema50) >= 6:
            ema50_slope = float(
                ema50.iloc[-1]
                - ema50.iloc[-6]
            )

        else:
            ema50_slope = 0.0

        if (
            latest_ema50
            > latest_ema200
            and ema50_slope > 0
        ):
            trend = "bullish"

        elif (
            latest_ema50
            < latest_ema200
            and ema50_slope < 0
        ):
            trend = "bearish"

        else:
            trend = "neutral"

        momentum_lookback = min(
            5,
            len(close) - 1,
        )

        if momentum_lookback > 0:
            momentum_value = float(
                close.iloc[-1]
                - close.iloc[
                    -1
                    - momentum_lookback
                ]
            )

        else:
            momentum_value = 0.0

        if momentum_value > 0:
            momentum_direction = "bullish"

        elif momentum_value < 0:
            momentum_direction = "bearish"

        else:
            momentum_direction = "neutral"

        latest = dataframe.iloc[-1]

        metrics: dict[str, Any] = {
            "current_datetime": (
                latest["datetime"]
                .isoformat()
            ),
            "current_open": float(
                latest["open"]
            ),
            "current_high": float(
                latest["high"]
            ),
            "current_low": float(
                latest["low"]
            ),
            "current_close": float(
                latest["close"]
            ),
            "atr14": float(
                atr14.iloc[-1]
            ),
            "ema50": latest_ema50,
            "ema200": latest_ema200,
            "ema50_slope": ema50_slope,
            "trend": trend,
            "momentum_5": momentum_value,
            "momentum_direction": (
                momentum_direction
            ),
        }

        if "volume" in dataframe.columns:
            volume_value = latest[
                "volume"
            ]

            if pd.notna(volume_value):
                metrics["current_volume"] = (
                    float(volume_value)
                )

        if "spread" in dataframe.columns:
            spread_value = latest[
                "spread"
            ]

            if pd.notna(spread_value):
                metrics["current_spread"] = (
                    float(spread_value)
                )

        return metrics

    def load_context(
        self,
        pair: str,
        timeframe: str,
        window_start_datetime: str | None,
        chart_datetime: str | None,
        chart_candles: int = 100,
        context_candles: int = 300,
    ) -> tuple[
        pd.DataFrame,
        dict[str, Any],
    ]:
        pair = pair.upper().strip()
        timeframe = timeframe.upper().strip()

        years = self._candidate_years(
            window_start_datetime=(
                window_start_datetime
            ),
            chart_datetime=chart_datetime,
        )

        if not years:
            raise ValueError(
                "Waktu chart belum tersedia."
            )

        dataframe, source_paths = (
            self._load_data(
                pair=pair,
                timeframe=timeframe,
                years=years,
            )
        )

        if chart_datetime:
            requested_end = (
                self._normalize_timestamp(
                    chart_datetime
                )
            )

            end_position = int(
                dataframe["datetime"]
                .searchsorted(
                    requested_end,
                    side="right",
                )
                - 1
            )

            if end_position < 0:
                raise ValueError(
                    "Tidak ada candle sebelum "
                    "chart_datetime."
                )

            chart_start_position = max(
                0,
                end_position
                - chart_candles
                + 1,
            )

        elif window_start_datetime:
            requested_start = (
                self._normalize_timestamp(
                    window_start_datetime
                )
            )

            chart_start_position = int(
                dataframe["datetime"]
                .searchsorted(
                    requested_start,
                    side="left",
                )
            )

            if chart_start_position >= len(
                dataframe
            ):
                raise ValueError(
                    "Waktu awal chart berada "
                    "di luar dataset OHLCV."
                )

            end_position = min(
                chart_start_position
                + chart_candles
                - 1,
                len(dataframe) - 1,
            )

        else:
            raise ValueError(
                "window_start_datetime atau "
                "chart_datetime diperlukan."
            )

        context_start_position = max(
            0,
            end_position
            - context_candles
            + 1,
        )

        chart_window = dataframe.iloc[
            chart_start_position:
            end_position + 1
        ].copy()

        context_window = dataframe.iloc[
            context_start_position:
            end_position + 1
        ].copy()

        if chart_window.empty:
            raise ValueError(
                "Chart window OHLCV kosong."
            )

        if context_window.empty:
            raise ValueError(
                "OHLCV context kosong."
            )

        metrics = self._calculate_metrics(
            context_window
        )

        summary = {
            "status": "LOADED",
            "pair": pair,
            "timeframe": timeframe,
            "source_paths": source_paths,
            "source_columns": [
                column
                for column
                in context_window.columns
            ],
            "anti_lookahead": True,
            "requested_chart_candles": (
                chart_candles
            ),
            "resolved_chart_candles": len(
                chart_window
            ),
            "context_candles": len(
                context_window
            ),
            "chart_start_datetime": (
                chart_window[
                    "datetime"
                ].iloc[0].isoformat()
            ),
            "chart_end_datetime": (
                chart_window[
                    "datetime"
                ].iloc[-1].isoformat()
            ),
            "context_start_datetime": (
                context_window[
                    "datetime"
                ].iloc[0].isoformat()
            ),
            "context_end_datetime": (
                context_window[
                    "datetime"
                ].iloc[-1].isoformat()
            ),
            "metrics": metrics,
        }

        return context_window, summary
