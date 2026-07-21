from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class LiveSessionRiskService:
    SESSION_SCORES = {
        "GBPUSD": {
            "ASIA": 0.55,
            "LONDON": 1.00,
            "LONDON_NEW_YORK_OVERLAP": 1.00,
            "NEW_YORK": 0.85,
            "OFF_PEAK": 0.40,
        },
        "XAUUSD": {
            "ASIA": 0.45,
            "LONDON": 0.85,
            "LONDON_NEW_YORK_OVERLAP": 1.00,
            "NEW_YORK": 0.95,
            "OFF_PEAK": 0.35,
        },
    }

    @staticmethod
    def _normalize_direction(
        value: Any,
    ) -> str:
        direction = str(
            value or "unknown"
        ).lower()

        if direction.startswith("bullish"):
            return "bullish"

        if direction.startswith("bearish"):
            return "bearish"

        return "unknown"

    @staticmethod
    def _classify_session(
        utc_hour: int,
    ) -> str:
        if 0 <= utc_hour < 7:
            return "ASIA"

        if 7 <= utc_hour < 13:
            return "LONDON"

        if 13 <= utc_hour < 16:
            return (
                "LONDON_NEW_YORK_OVERLAP"
            )

        if 16 <= utc_hour < 22:
            return "NEW_YORK"

        return "OFF_PEAK"

    @classmethod
    def _session_context(
        cls,
        pair: str,
        chart_end_datetime: str,
        market_utc_offset_hours: float,
        datetime_source: str = (
            "CHART_END_DATETIME"
        ),
        original_chart_end_datetime: (
            str | None
        ) = None,
    ) -> dict[str, Any]:
        market_timestamp = datetime.fromisoformat(
            str(chart_end_datetime).replace(
                "Z",
                "+00:00",
            )
        )

        if market_timestamp.tzinfo is not None:
            market_timestamp = (
                market_timestamp
                .replace(tzinfo=None)
            )

        utc_timestamp = (
            market_timestamp
            - timedelta(
                hours=market_utc_offset_hours
            )
        )

        session = cls._classify_session(
            int(utc_timestamp.hour)
        )

        pair_scores = (
            cls.SESSION_SCORES.get(
                pair,
                {
                    "ASIA": 0.50,
                    "LONDON": 0.85,
                    "LONDON_NEW_YORK_OVERLAP": (
                        1.00
                    ),
                    "NEW_YORK": 0.85,
                    "OFF_PEAK": 0.40,
                },
            )
        )

        session_score = float(
            pair_scores.get(
                session,
                0.50,
            )
        )

        return {
            "status": "COMPLETE",
            "pair": pair,
            "market_datetime": (
                market_timestamp.isoformat()
            ),
            "evaluation_datetime_source": (
                datetime_source
            ),
            "chart_end_datetime": (
                original_chart_end_datetime
                or chart_end_datetime
            ),
            "analysis_target_datetime": (
                chart_end_datetime
                if datetime_source
                == "ANALYSIS_TARGET_OVERRIDE"
                else None
            ),
            "market_utc_offset_hours": (
                market_utc_offset_hours
            ),
            "resolved_utc_datetime": (
                utc_timestamp.isoformat()
            ),
            "utc_hour": int(
                utc_timestamp.hour
            ),
            "session": session,
            "session_score": (
                session_score
            ),
            "timezone_assumption_provisional": (
                True
            ),
            "timezone_warning": (
                "Offset waktu data broker harus "
                "dikonfirmasi sebelum produksi."
            ),
        }

    @staticmethod
    def _extract_liquidity_levels(
        market_structure: dict[str, Any],
        side: str,
    ) -> list[float]:
        levels: list[float] = []

        for liquidity in (
            market_structure.get(
                "recent_liquidity",
                [],
            )
        ):
            if liquidity.get("side") != side:
                continue

            try:
                levels.append(
                    float(
                        liquidity["level"]
                    )
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

        return sorted(set(levels))

    @classmethod
    def _calculate_risk_reward(
        cls,
        setup_direction: str,
        market_structure: dict[str, Any],
        ohlcv_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        zone = market_structure.get(
            "zone",
            {},
        )

        if zone.get("status") != "MAPPED":
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    "Harga zona belum berhasil "
                    "dipetakan."
                ),
            }

        try:
            zone_low = float(
                zone["zone_low"]
            )

            zone_high = float(
                zone["zone_high"]
            )

            zone_mid = float(
                zone["zone_mid"]
            )

            current_close = float(
                ohlcv_metrics[
                    "current_close"
                ]
            )

            atr = float(
                ohlcv_metrics["atr14"]
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    "Data harga atau ATR "
                    f"tidak lengkap: {error}"
                ),
            }

        buffer_size = max(
            atr * 0.25,
            abs(zone_mid) * 0.00005,
        )

        target_source = (
            "FALLBACK_FIXED_2R"
        )

        target_liquidity_level = None

        if setup_direction == "bullish":
            entry = zone_mid

            stop_loss = (
                zone_low - buffer_size
            )

            target_levels = [
                level
                for level
                in cls._extract_liquidity_levels(
                    market_structure,
                    "buy_side",
                )
                if level > entry
            ]

            if target_levels:
                take_profit = min(
                    target_levels
                )

                target_liquidity_level = (
                    take_profit
                )

                target_source = (
                    "NEAREST_BUY_SIDE_"
                    "LIQUIDITY"
                )

            else:
                risk_distance = (
                    entry - stop_loss
                )

                take_profit = (
                    entry
                    + risk_distance * 2.0
                )

            order_type = "BUY_LIMIT"

            entry_side_valid = (
                entry < current_close
            )

        elif setup_direction == "bearish":
            entry = zone_mid

            stop_loss = (
                zone_high + buffer_size
            )

            target_levels = [
                level
                for level
                in cls._extract_liquidity_levels(
                    market_structure,
                    "sell_side",
                )
                if level < entry
            ]

            if target_levels:
                take_profit = max(
                    target_levels
                )

                target_liquidity_level = (
                    take_profit
                )

                target_source = (
                    "NEAREST_SELL_SIDE_"
                    "LIQUIDITY"
                )

            else:
                risk_distance = (
                    stop_loss - entry
                )

                take_profit = (
                    entry
                    - risk_distance * 2.0
                )

            order_type = "SELL_LIMIT"

            entry_side_valid = (
                entry > current_close
            )

        else:
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    "Arah setup tidak dikenali."
                ),
            }

        if setup_direction == "bullish":
            risk_distance = (
                entry - stop_loss
            )

            reward_distance = (
                take_profit - entry
            )

        else:
            risk_distance = (
                stop_loss - entry
            )

            reward_distance = (
                entry - take_profit
            )

        if risk_distance <= 0:
            return {
                "status": "INVALID",
                "reason": (
                    "Risk distance tidak valid."
                ),
            }

        risk_reward_ratio = (
            reward_distance
            / risk_distance
        )

        if atr > 0:
            entry_distance_atr = (
                abs(
                    current_close - entry
                )
                / atr
            )

        else:
            entry_distance_atr = None

        if setup_direction == "bullish":
            current_price_invalidated = (
                current_close < stop_loss
            )

        else:
            current_price_invalidated = (
                current_close > stop_loss
            )

        zone_invalidated = bool(
            zone.get(
                "invalidated",
                False,
            )
            or current_price_invalidated
        )

        mapping_provisional = bool(
            zone.get(
                "mapping_provisional",
                zone.get("mapping_mode")
                != (
                    "CANONICAL_OHLCV_"
                    "CANDLE_ANCHORED"
                ),
            )
        )

        rr_valid = (
            risk_reward_ratio >= 1.50
            and reward_distance > 0
            and entry_side_valid
            and not zone_invalidated
        )

        return {
            "status": "COMPLETE",
            "setup_direction": (
                setup_direction
            ),
            "order_type": order_type,
            "current_close": (
                current_close
            ),
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_distance": (
                risk_distance
            ),
            "reward_distance": (
                reward_distance
            ),
            "risk_reward_ratio": (
                risk_reward_ratio
            ),
            "minimum_required_rr": 1.50,
            "rr_valid": rr_valid,
            "entry_side_valid": (
                entry_side_valid
            ),
            "entry_distance_atr": (
                entry_distance_atr
            ),
            "stop_buffer_atr": 0.25,
            "target_source": (
                target_source
            ),
            "target_liquidity_level": (
                target_liquidity_level
            ),
            "zone_status": zone.get(
                "zone_status"
            ),
            "zone_invalidated": (
                zone_invalidated
            ),
            "price_mapping_provisional": (
                mapping_provisional
            ),
            "price_mapping_mode": (
                zone.get("mapping_mode")
            ),
        }

    def analyze(
        self,
        pair: str,
        chart_end_datetime: str,
        setup_direction: str,
        market_structure: dict[str, Any],
        ohlcv_metrics: dict[str, Any],
        market_utc_offset_hours: float,
        analysis_datetime: str | None = None,
        analysis_datetime_source: str = (
            "CHART_END_DATETIME"
        ),
    ) -> dict[str, Any]:
        pair = pair.upper().strip()

        setup_direction = (
            self._normalize_direction(
                setup_direction
            )
        )

        session = self._session_context(
            pair=pair,
            chart_end_datetime=(
                analysis_datetime
                or chart_end_datetime
            ),
            market_utc_offset_hours=(
                market_utc_offset_hours
            ),
            datetime_source=(
                analysis_datetime_source
                if analysis_datetime
                else "CHART_END_DATETIME"
            ),
            original_chart_end_datetime=(
                chart_end_datetime
            ),
        )

        risk_reward = (
            self._calculate_risk_reward(
                setup_direction=(
                    setup_direction
                ),
                market_structure=(
                    market_structure
                ),
                ohlcv_metrics=(
                    ohlcv_metrics
                ),
            )
        )

        return {
            "status": (
                "SESSION_RISK_COMPLETE"
            ),
            "pair": pair,
            "setup_direction": (
                setup_direction
            ),
            "session": session,
            "risk_reward": risk_reward,
        }
