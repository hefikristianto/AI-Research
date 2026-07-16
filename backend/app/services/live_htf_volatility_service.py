from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.ohlcv_context_service import (
    OHLCVContextService,
)


class LiveHTFVolatilityService:
    HTF_MAP = {
        "M5": [
            "M15",
            "H1",
            "H4",
        ],
        "M15": [
            "H1",
            "H4",
        ],
        "H1": [
            "H4",
        ],
        "H4": [],
    }

    HTF_WEIGHTS = {
        "M15": 0.20,
        "H1": 0.35,
        "H4": 0.45,
    }

    @staticmethod
    def _normalize_direction(
        value: Any,
    ) -> str:
        direction = str(
            value or "unknown"
        ).lower()

        if direction.startswith(
            "bullish"
        ):
            return "bullish"

        if direction.startswith(
            "bearish"
        ):
            return "bearish"

        if direction in {
            "neutral",
            "sideways",
        }:
            return "neutral"

        return "unknown"

    @staticmethod
    def _calculate_atr(
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
            window=period,
            min_periods=1,
        ).mean()

    @classmethod
    def _analyze_volatility(
        cls,
        dataframe: pd.DataFrame,
    ) -> dict[str, Any]:
        if dataframe.empty:
            return {
                "status": "NO_DATA",
                "regime": "UNKNOWN",
                "score": 0.50,
            }

        atr_series = cls._calculate_atr(
            dataframe
        )

        atr_history = (
            atr_series
            .dropna()
            .tail(100)
        )

        current_atr = float(
            atr_series.iloc[-1]
        )

        current_close = float(
            dataframe["close"].iloc[-1]
        )

        median_atr = float(
            atr_history.median()
        )

        mean_atr = float(
            atr_history.mean()
        )

        if median_atr > 0:
            atr_ratio = (
                current_atr
                / median_atr
            )
        else:
            atr_ratio = 1.0

        if current_close != 0:
            atr_percentage = (
                current_atr
                / abs(current_close)
                * 100.0
            )
        else:
            atr_percentage = 0.0

        if len(atr_history) > 0:
            volatility_percentile = float(
                (
                    atr_history
                    <= current_atr
                ).sum()
                / len(atr_history)
            )
        else:
            volatility_percentile = 0.50

        if atr_ratio < 0.75:
            regime = "LOW"
            suitability_score = 0.40

        elif atr_ratio < 1.25:
            regime = "NORMAL"
            suitability_score = 1.00

        elif atr_ratio < 1.75:
            regime = "HIGH"
            suitability_score = 0.70

        else:
            regime = "EXTREME"
            suitability_score = 0.20

        return {
            "status": "COMPLETE",
            "regime": regime,
            "current_atr": current_atr,
            "median_atr_100": median_atr,
            "mean_atr_100": mean_atr,
            "atr_ratio_to_median": (
                atr_ratio
            ),
            "atr_percentage": (
                atr_percentage
            ),
            "percentile_100": (
                volatility_percentile
            ),
            "samples": len(
                atr_history
            ),
            "score": suitability_score,
        }

    @staticmethod
    def _alignment_value(
        setup_direction: str,
        trend: str,
    ) -> tuple[str, float]:
        if trend == setup_direction:
            return "aligned", 1.00

        if trend in {
            "neutral",
            "unknown",
        }:
            return "neutral", 0.50

        return "conflict", 0.00

    def analyze(
        self,
        pair: str,
        base_timeframe: str,
        chart_end_datetime: str,
        base_context_window: pd.DataFrame,
        base_metrics: dict[str, Any],
        setup_direction: str,
        ohlcv_service: (
            OHLCVContextService
        ),
    ) -> dict[str, Any]:
        pair = pair.upper().strip()

        base_timeframe = (
            base_timeframe
            .upper()
            .strip()
        )

        setup_direction = (
            self._normalize_direction(
                setup_direction
            )
        )

        higher_timeframes = (
            self.HTF_MAP.get(
                base_timeframe,
                [],
            )
        )

        volatility = (
            self._analyze_volatility(
                base_context_window
            )
        )

        base_trend = (
            self._normalize_direction(
                base_metrics.get(
                    "trend",
                    "unknown",
                )
            )
        )

        timeframe_results: list[
            dict[str, Any]
        ] = []

        for timeframe in higher_timeframes:
            try:
                (
                    _,
                    summary,
                ) = ohlcv_service.load_context(
                    pair=pair,
                    timeframe=timeframe,
                    window_start_datetime=None,
                    chart_datetime=(
                        chart_end_datetime
                    ),
                    chart_candles=100,
                    context_candles=300,
                )

                trend = (
                    self._normalize_direction(
                        summary.get(
                            "metrics",
                            {},
                        ).get(
                            "trend",
                            "unknown",
                        )
                    )
                )

                (
                    alignment,
                    alignment_value,
                ) = self._alignment_value(
                    setup_direction=(
                        setup_direction
                    ),
                    trend=trend,
                )

                timeframe_results.append(
                    {
                        "timeframe": (
                            timeframe
                        ),
                        "status": "LOADED",
                        "trend": trend,
                        "alignment": (
                            alignment
                        ),
                        "alignment_value": (
                            alignment_value
                        ),
                        "base_weight": float(
                            self.HTF_WEIGHTS.get(
                                timeframe,
                                1.0,
                            )
                        ),
                        "chart_end_datetime": (
                            summary.get(
                                "chart_end_datetime"
                            )
                        ),
                        "context_candles": (
                            summary.get(
                                "context_candles"
                            )
                        ),
                        "atr14": (
                            summary.get(
                                "metrics",
                                {},
                            ).get("atr14")
                        ),
                        "ema50": (
                            summary.get(
                                "metrics",
                                {},
                            ).get("ema50")
                        ),
                        "ema200": (
                            summary.get(
                                "metrics",
                                {},
                            ).get("ema200")
                        ),
                    }
                )

            except Exception as error:
                timeframe_results.append(
                    {
                        "timeframe": (
                            timeframe
                        ),
                        "status": "ERROR",
                        "error": str(error),
                        "base_weight": float(
                            self.HTF_WEIGHTS.get(
                                timeframe,
                                1.0,
                            )
                        ),
                    }
                )

        loaded_results = [
            item
            for item in timeframe_results
            if item.get("status")
            == "LOADED"
        ]

        total_weight = sum(
            float(
                item["base_weight"]
            )
            for item in loaded_results
        )

        if (
            loaded_results
            and total_weight > 0
        ):
            weighted_alignment = sum(
                float(
                    item[
                        "alignment_value"
                    ]
                )
                * float(
                    item["base_weight"]
                )
                for item
                in loaded_results
            )

            htf_alignment_score = (
                weighted_alignment
                / total_weight
            )

        else:
            htf_alignment_score = 0.50

        trend_weights = {
            "bullish": 0.0,
            "bearish": 0.0,
            "neutral": 0.0,
            "unknown": 0.0,
        }

        for item in loaded_results:
            trend = str(
                item.get(
                    "trend",
                    "unknown",
                )
            )

            trend_weights[
                trend
                if trend
                in trend_weights
                else "unknown"
            ] += float(
                item["base_weight"]
            )

        if loaded_results:
            sorted_trends = sorted(
                trend_weights.items(),
                key=lambda item: item[1],
                reverse=True,
            )

            if (
                len(sorted_trends) >= 2
                and sorted_trends[0][1]
                == sorted_trends[1][1]
            ):
                htf_consensus = "mixed"

            else:
                htf_consensus = (
                    sorted_trends[0][0]
                )

        else:
            htf_consensus = (
                "not_available"
            )

        if not higher_timeframes:
            htf_status = (
                "NO_HIGHER_TIMEFRAME"
            )

        elif loaded_results:
            htf_status = "LOADED"

        else:
            htf_status = "UNAVAILABLE"

        return {
            "status": (
                "HTF_VOLATILITY_COMPLETE"
            ),
            "pair": pair,
            "base_timeframe": (
                base_timeframe
            ),
            "chart_end_datetime": (
                chart_end_datetime
            ),
            "setup_direction": (
                setup_direction
            ),
            "base_trend": base_trend,
            "higher_timeframe_status": (
                htf_status
            ),
            "requested_higher_timeframes": (
                higher_timeframes
            ),
            "loaded_higher_timeframes": (
                len(loaded_results)
            ),
            "higher_timeframes": (
                timeframe_results
            ),
            "htf_consensus": (
                htf_consensus
            ),
            "htf_alignment_score": (
                htf_alignment_score
            ),
            "volatility": volatility,
            "anti_lookahead": True,
        }
