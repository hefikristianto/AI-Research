from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class AnalysisTargetDatetimeService:
    """Validate the experiment clock without changing the OHLCV cutoff."""

    TIMEFRAME_MINUTES = {
        "M5": 5,
        "M15": 15,
        "H1": 60,
        "H4": 240,
    }

    @staticmethod
    def _parse(value: str, *, field: str) -> datetime:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field} wajib diisi.")

        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(
                f"{field} harus berupa ISO-8601 datetime yang valid."
            ) from error

        return parsed

    @staticmethod
    def _is_aware(value: datetime) -> bool:
        return value.tzinfo is not None and value.utcoffset() is not None

    @classmethod
    def resolve(
        cls,
        *,
        chart_end_datetime: str,
        timeframe: str,
        analysis_target_datetime: str | None,
    ) -> dict[str, Any]:
        normalized_timeframe = str(timeframe or "").upper().strip()
        if normalized_timeframe not in cls.TIMEFRAME_MINUTES:
            raise ValueError(
                "Timeframe analysis target tidak didukung. "
                "Gunakan M5, M15, H1, atau H4."
            )

        chart_end = cls._parse(
            chart_end_datetime,
            field="chart_end_datetime",
        )

        if analysis_target_datetime is None:
            return {
                "status": "LEGACY_CHART_END_DEFAULT",
                "override_requested": False,
                "effective_datetime": chart_end.isoformat(),
                "datetime_source": "CHART_END_DATETIME",
                "chart_end_datetime": chart_end.isoformat(),
                "analysis_target_datetime": None,
                "anti_lookahead_validated": False,
                "timeframe": normalized_timeframe,
            }

        target = cls._parse(
            analysis_target_datetime,
            field="analysis_target_datetime",
        )

        if cls._is_aware(chart_end) != cls._is_aware(target):
            raise ValueError(
                "analysis_target_datetime harus memakai basis timezone yang "
                "sama dengan chart_datetime/OHLCV. Untuk manifest E2.3, "
                "gunakan analysis_target_market_datetime tanpa suffix Z."
            )

        duration = timedelta(minutes=cls.TIMEFRAME_MINUTES[normalized_timeframe])
        expected_close = chart_end + duration
        maximum_target = expected_close + duration

        if target < expected_close:
            raise ValueError(
                "analysis_target_datetime mendahului waktu close candle "
                "terakhir dan berisiko look-ahead."
            )

        if target > maximum_target:
            raise ValueError(
                "analysis_target_datetime melebihi batas freshness satu "
                "candle setelah close terakhir."
            )

        return {
            "status": "ANALYSIS_TARGET_VALIDATED",
            "override_requested": True,
            "effective_datetime": target.isoformat(),
            "datetime_source": "ANALYSIS_TARGET_OVERRIDE",
            "chart_end_datetime": chart_end.isoformat(),
            "analysis_target_datetime": target.isoformat(),
            "expected_chart_end_close_datetime": expected_close.isoformat(),
            "maximum_allowed_target_datetime": maximum_target.isoformat(),
            "target_delay_after_close_minutes": round(
                (target - expected_close).total_seconds() / 60.0,
                6,
            ),
            "anti_lookahead_validated": True,
            "timeframe": normalized_timeframe,
        }
