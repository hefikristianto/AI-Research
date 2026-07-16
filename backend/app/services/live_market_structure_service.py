from __future__ import annotations

from typing import Any

import pandas as pd


class LiveMarketStructureService:
    def __init__(
        self,
        swing_strength: int = 2,
        liquidity_tolerance_atr: float = 0.15,
    ) -> None:
        self.swing_strength = swing_strength
        self.liquidity_tolerance_atr = (
            liquidity_tolerance_atr
        )

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

    def _detect_swings(
        self,
        dataframe: pd.DataFrame,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        strength = self.swing_strength
        window = strength * 2 + 1

        rolling_high = (
            dataframe["high"]
            .rolling(
                window=window,
                center=True,
            )
            .max()
        )

        rolling_low = (
            dataframe["low"]
            .rolling(
                window=window,
                center=True,
            )
            .min()
        )

        high_mask = (
            dataframe["high"].eq(
                rolling_high
            )
            & dataframe["high"].gt(
                dataframe["high"].shift(1)
            )
            & dataframe["high"].ge(
                dataframe["high"].shift(-1)
            )
        )

        low_mask = (
            dataframe["low"].eq(
                rolling_low
            )
            & dataframe["low"].lt(
                dataframe["low"].shift(1)
            )
            & dataframe["low"].le(
                dataframe["low"].shift(-1)
            )
        )

        swing_highs: list[
            dict[str, Any]
        ] = []

        swing_lows: list[
            dict[str, Any]
        ] = []

        for index in dataframe.index[
            high_mask.fillna(False)
        ]:
            row = dataframe.loc[index]

            swing_highs.append(
                {
                    "index": int(index),
                    "datetime": (
                        row["datetime"]
                        .isoformat()
                    ),
                    "price": float(
                        row["high"]
                    ),
                    "type": "swing_high",
                }
            )

        for index in dataframe.index[
            low_mask.fillna(False)
        ]:
            row = dataframe.loc[index]

            swing_lows.append(
                {
                    "index": int(index),
                    "datetime": (
                        row["datetime"]
                        .isoformat()
                    ),
                    "price": float(
                        row["low"]
                    ),
                    "type": "swing_low",
                }
            )

        return swing_highs, swing_lows

    @staticmethod
    def _infer_market_bias(
        swing_highs: list[
            dict[str, Any]
        ],
        swing_lows: list[
            dict[str, Any]
        ],
    ) -> str:
        if (
            len(swing_highs) < 2
            or len(swing_lows) < 2
        ):
            return "neutral"

        previous_high = swing_highs[-2][
            "price"
        ]

        latest_high = swing_highs[-1][
            "price"
        ]

        previous_low = swing_lows[-2][
            "price"
        ]

        latest_low = swing_lows[-1][
            "price"
        ]

        if (
            latest_high > previous_high
            and latest_low > previous_low
        ):
            return "bullish"

        if (
            latest_high < previous_high
            and latest_low < previous_low
        ):
            return "bearish"

        return "neutral"

    @staticmethod
    def _cluster_liquidity(
        swings: list[dict[str, Any]],
        side: str,
        tolerance: float,
    ) -> list[dict[str, Any]]:
        clusters: list[
            dict[str, Any]
        ] = []

        for swing in swings:
            selected_cluster = None

            for cluster in clusters:
                if abs(
                    float(swing["price"])
                    - float(cluster["level"])
                ) <= tolerance:
                    selected_cluster = cluster
                    break

            if selected_cluster is None:
                clusters.append(
                    {
                        "side": side,
                        "level": float(
                            swing["price"]
                        ),
                        "touches": 1,
                        "swing_indices": [
                            int(
                                swing["index"]
                            )
                        ],
                        "datetimes": [
                            swing["datetime"]
                        ],
                    }
                )

                continue

            selected_cluster[
                "swing_indices"
            ].append(
                int(swing["index"])
            )

            selected_cluster[
                "datetimes"
            ].append(
                swing["datetime"]
            )

            selected_cluster[
                "touches"
            ] += 1

            prices = [
                float(
                    item["price"]
                )
                for item in swings
                if int(item["index"])
                in selected_cluster[
                    "swing_indices"
                ]
            ]

            selected_cluster[
                "level"
            ] = sum(prices) / len(
                prices
            )

        confirmed = [
            cluster
            for cluster in clusters
            if cluster["touches"] >= 2
        ]

        for cluster in confirmed:
            cluster["last_index"] = max(
                cluster["swing_indices"]
            )

            cluster[
                "last_datetime"
            ] = cluster["datetimes"][-1]

        confirmed.sort(
            key=lambda item: item[
                "last_index"
            ],
            reverse=True,
        )

        return confirmed

    @staticmethod
    def _detect_sweeps(
        dataframe: pd.DataFrame,
        liquidity_levels: list[
            dict[str, Any]
        ],
        atr_series: pd.Series,
    ) -> list[dict[str, Any]]:
        sweeps: list[
            dict[str, Any]
        ] = []

        for liquidity in liquidity_levels:
            level = float(
                liquidity["level"]
            )

            start_index = int(
                liquidity["last_index"]
            ) + 1

            future = dataframe.loc[
                dataframe.index
                >= start_index
            ]

            for index, row in (
                future.iterrows()
            ):
                atr = float(
                    atr_series.loc[index]
                )

                margin = max(
                    atr * 0.03,
                    abs(level) * 0.000001,
                )

                if (
                    liquidity["side"]
                    == "buy_side"
                    and float(row["high"])
                    > level + margin
                    and float(row["close"])
                    < level
                ):
                    sweeps.append(
                        {
                            "side": "buy_side",
                            "level": level,
                            "index": int(index),
                            "datetime": (
                                row["datetime"]
                                .isoformat()
                            ),
                            "penetration": float(
                                row["high"]
                                - level
                            ),
                            "confirmation_direction": (
                                "bearish"
                            ),
                        }
                    )
                    break

                if (
                    liquidity["side"]
                    == "sell_side"
                    and float(row["low"])
                    < level - margin
                    and float(row["close"])
                    > level
                ):
                    sweeps.append(
                        {
                            "side": "sell_side",
                            "level": level,
                            "index": int(index),
                            "datetime": (
                                row["datetime"]
                                .isoformat()
                            ),
                            "penetration": float(
                                level
                                - row["low"]
                            ),
                            "confirmation_direction": (
                                "bullish"
                            ),
                        }
                    )
                    break

        sweeps.sort(
            key=lambda item: item[
                "index"
            ]
        )

        return sweeps

    @staticmethod
    def _detect_break_events(
        dataframe: pd.DataFrame,
        swing_highs: list[
            dict[str, Any]
        ],
        swing_lows: list[
            dict[str, Any]
        ],
    ) -> list[dict[str, Any]]:
        raw_events: list[
            dict[str, Any]
        ] = []

        for swing in swing_highs:
            future = dataframe.loc[
                dataframe.index
                > int(swing["index"])
            ]

            broken = future[
                future["close"]
                > float(swing["price"])
            ]

            if broken.empty:
                continue

            break_index = int(
                broken.index[0]
            )

            break_row = dataframe.loc[
                break_index
            ]

            raw_events.append(
                {
                    "index": break_index,
                    "datetime": (
                        break_row[
                            "datetime"
                        ].isoformat()
                    ),
                    "direction": "bullish",
                    "broken_level": float(
                        swing["price"]
                    ),
                    "source_swing_index": int(
                        swing["index"]
                    ),
                }
            )

        for swing in swing_lows:
            future = dataframe.loc[
                dataframe.index
                > int(swing["index"])
            ]

            broken = future[
                future["close"]
                < float(swing["price"])
            ]

            if broken.empty:
                continue

            break_index = int(
                broken.index[0]
            )

            break_row = dataframe.loc[
                break_index
            ]

            raw_events.append(
                {
                    "index": break_index,
                    "datetime": (
                        break_row[
                            "datetime"
                        ].isoformat()
                    ),
                    "direction": "bearish",
                    "broken_level": float(
                        swing["price"]
                    ),
                    "source_swing_index": int(
                        swing["index"]
                    ),
                }
            )

        raw_events.sort(
            key=lambda item: (
                item["index"],
                item["source_swing_index"],
            )
        )

        deduplicated: list[
            dict[str, Any]
        ] = []

        used_keys: set[
            tuple[int, str]
        ] = set()

        for event in raw_events:
            key = (
                int(event["index"]),
                str(event["direction"]),
            )

            if key in used_keys:
                continue

            used_keys.add(key)
            deduplicated.append(event)

        previous_direction = None

        for event in deduplicated:
            if previous_direction is None:
                event["event_type"] = "BOS"

            elif (
                event["direction"]
                == previous_direction
            ):
                event["event_type"] = "BOS"

            else:
                event[
                    "event_type"
                ] = "CHoCH"

            previous_direction = event[
                "direction"
            ]

        return deduplicated

    @staticmethod
    def _normalize_setup_direction(
        setup: dict[str, Any] | None,
    ) -> str:
        if not setup:
            return "unknown"

        direction = str(
            setup.get(
                "setup_direction",
                setup.get(
                    "direction",
                    "unknown",
                ),
            )
        ).lower()

        if direction.startswith(
            "bullish"
        ):
            return "bullish"

        if direction.startswith(
            "bearish"
        ):
            return "bearish"

        return "unknown"

    @staticmethod
    def _map_zone_to_price(
        chart_window: pd.DataFrame,
        setup: dict[str, Any] | None,
        atr: float,
    ) -> dict[str, Any]:
        if not setup:
            return {
                "status": "NO_SETUP",
                "mapping_mode": (
                    "approximate_full_image_linear"
                ),
            }

        box = setup.get(
            "ob_bbox",
            {},
        )

        if not box:
            return {
                "status": "NO_OB_BOX",
                "mapping_mode": (
                    "approximate_full_image_linear"
                ),
            }

        box_x = float(
            box.get("x", 0.0)
        )

        box_y = float(
            box.get("y", 0.0)
        )

        box_height = float(
            box.get("height", 0.0)
        )

        y_top = max(
            0.0,
            box_y - box_height / 2.0,
        )

        y_bottom = min(
            1.0,
            box_y + box_height / 2.0,
        )

        chart_high = float(
            chart_window["high"].max()
        )

        chart_low = float(
            chart_window["low"].min()
        )

        price_range = (
            chart_high - chart_low
        )

        if price_range <= 0:
            return {
                "status": "INVALID_PRICE_RANGE",
                "mapping_mode": (
                    "approximate_full_image_linear"
                ),
            }

        zone_high = (
            chart_high
            - y_top * price_range
        )

        zone_low = (
            chart_high
            - y_bottom * price_range
        )

        origin_index = int(
            round(
                box_x
                * max(
                    len(chart_window) - 1,
                    0,
                )
            )
        )

        origin_index = max(
            0,
            min(
                origin_index,
                len(chart_window) - 1,
            ),
        )

        future = chart_window.iloc[
            origin_index + 1:
        ]

        touch_mask = (
            future["high"].ge(zone_low)
            & future["low"].le(zone_high)
        )

        touch_count = int(
            touch_mask.sum()
        )

        setup_direction = (
            LiveMarketStructureService
            ._normalize_setup_direction(
                setup
            )
        )

        invalidation_buffer = (
            atr * 0.10
        )

        if setup_direction == "bullish":
            invalidated = bool(
                (
                    future["close"]
                    < (
                        zone_low
                        - invalidation_buffer
                    )
                ).any()
            )

        elif setup_direction == "bearish":
            invalidated = bool(
                (
                    future["close"]
                    > (
                        zone_high
                        + invalidation_buffer
                    )
                ).any()
            )

        else:
            invalidated = False

        fresh = (
            touch_count == 0
            and not invalidated
        )

        mitigated = (
            touch_count > 0
            and not invalidated
        )

        if invalidated:
            zone_status = "invalidated"

        elif fresh:
            zone_status = "fresh"

        elif mitigated:
            zone_status = "mitigated"

        else:
            zone_status = "unknown"

        return {
            "status": "MAPPED",
            "mapping_mode": (
                "approximate_full_image_linear"
            ),
            "mapping_warning": (
                "Harga zona masih menggunakan "
                "pemetaan linear seluruh tinggi "
                "gambar. Kalibrasi plot-area "
                "diperlukan untuk produksi."
            ),
            "chart_high": chart_high,
            "chart_low": chart_low,
            "zone_low": zone_low,
            "zone_high": zone_high,
            "zone_mid": (
                zone_low + zone_high
            ) / 2.0,
            "origin_candle_offset": (
                origin_index
            ),
            "touch_count": touch_count,
            "fresh": fresh,
            "mitigated": mitigated,
            "invalidated": invalidated,
            "zone_status": zone_status,
        }

    def analyze(
        self,
        context_window: pd.DataFrame,
        chart_candles: int,
        best_setup: dict[str, Any] | None,
        ohlcv_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        required_columns = {
            "datetime",
            "open",
            "high",
            "low",
            "close",
        }

        missing_columns = (
            required_columns
            - set(context_window.columns)
        )

        if missing_columns:
            raise ValueError(
                "Kolom market structure "
                "tidak lengkap: "
                + ", ".join(
                    sorted(missing_columns)
                )
            )

        dataframe = (
            context_window
            .copy()
            .reset_index(drop=True)
        )

        chart_window = (
            dataframe
            .tail(chart_candles)
            .copy()
            .reset_index(drop=True)
        )

        atr_series = self._calculate_atr(
            dataframe
        )

        current_atr = float(
            atr_series.iloc[-1]
        )

        swing_highs, swing_lows = (
            self._detect_swings(
                dataframe
            )
        )

        market_bias = (
            self._infer_market_bias(
                swing_highs,
                swing_lows,
            )
        )

        liquidity_tolerance = max(
            current_atr
            * self.liquidity_tolerance_atr,
            float(
                dataframe["close"].iloc[-1]
            )
            * 0.000001,
        )

        buy_side_liquidity = (
            self._cluster_liquidity(
                swings=swing_highs,
                side="buy_side",
                tolerance=(
                    liquidity_tolerance
                ),
            )
        )

        sell_side_liquidity = (
            self._cluster_liquidity(
                swings=swing_lows,
                side="sell_side",
                tolerance=(
                    liquidity_tolerance
                ),
            )
        )

        all_liquidity = (
            buy_side_liquidity
            + sell_side_liquidity
        )

        sweeps = self._detect_sweeps(
            dataframe=dataframe,
            liquidity_levels=all_liquidity,
            atr_series=atr_series,
        )

        break_events = (
            self._detect_break_events(
                dataframe=dataframe,
                swing_highs=swing_highs,
                swing_lows=swing_lows,
            )
        )

        setup_direction = (
            self._normalize_setup_direction(
                best_setup
            )
        )

        latest_break = (
            break_events[-1]
            if break_events
            else None
        )

        structure_direction = (
            latest_break["direction"]
            if latest_break
            else market_bias
        )

        if setup_direction == "unknown":
            structure_alignment = (
                "unknown"
            )

        elif (
            structure_direction
            == "neutral"
        ):
            structure_alignment = (
                "neutral"
            )

        elif (
            setup_direction
            == structure_direction
        ):
            structure_alignment = (
                "aligned"
            )

        else:
            structure_alignment = (
                "conflict"
            )

        latest_sweep = (
            sweeps[-1]
            if sweeps
            else None
        )

        if latest_sweep is None:
            sweep_score = 0.50

        elif (
            latest_sweep[
                "confirmation_direction"
            ]
            == setup_direction
        ):
            sweep_score = 1.00

        else:
            sweep_score = 0.00

        if structure_alignment == "aligned":
            alignment_score = 1.00

        elif structure_alignment == "neutral":
            alignment_score = 0.50

        elif structure_alignment == "unknown":
            alignment_score = 0.50

        else:
            alignment_score = 0.00

        zone_result = (
            self._map_zone_to_price(
                chart_window=chart_window,
                setup=best_setup,
                atr=current_atr,
            )
        )

        zone_status = zone_result.get(
            "zone_status",
            "unknown",
        )

        if zone_status == "fresh":
            zone_score = 1.00

        elif zone_status == "mitigated":
            zone_score = 0.50

        elif zone_status == "invalidated":
            zone_score = 0.00

        else:
            zone_score = 0.50

        market_structure_score = (
            alignment_score * 0.45
            + sweep_score * 0.25
            + zone_score * 0.30
        )

        return {
            "status": "STRUCTURE_COMPLETE",
            "candles_analyzed": len(
                dataframe
            ),
            "chart_candles": len(
                chart_window
            ),
            "current_atr": current_atr,
            "ohlcv_trend": (
                ohlcv_metrics.get(
                    "trend",
                    "unknown",
                )
            ),
            "market_bias": market_bias,
            "structure_direction": (
                structure_direction
            ),
            "setup_direction": (
                setup_direction
            ),
            "structure_alignment": (
                structure_alignment
            ),
            "alignment_score": (
                alignment_score
            ),
            "swing_high_count": len(
                swing_highs
            ),
            "swing_low_count": len(
                swing_lows
            ),
            "recent_swing_highs": (
                swing_highs[-5:]
            ),
            "recent_swing_lows": (
                swing_lows[-5:]
            ),
            "buy_side_liquidity_count": (
                len(
                    buy_side_liquidity
                )
            ),
            "sell_side_liquidity_count": (
                len(
                    sell_side_liquidity
                )
            ),
            "recent_liquidity": (
                sorted(
                    all_liquidity,
                    key=lambda item: item[
                        "last_index"
                    ],
                    reverse=True,
                )[:10]
            ),
            "sweep_count": len(sweeps),
            "latest_sweep": latest_sweep,
            "bos_present": any(
                event["event_type"]
                == "BOS"
                for event in break_events
            ),
            "choch_present": any(
                event["event_type"]
                == "CHoCH"
                for event in break_events
            ),
            "recent_break_events": (
                break_events[-10:]
            ),
            "latest_break": latest_break,
            "zone": zone_result,
            "sweep_score": sweep_score,
            "zone_score": zone_score,
            "market_structure_score": (
                market_structure_score
            ),
            "scoring_integration": (
                "NOT_APPLIED_YET"
            ),
        }
