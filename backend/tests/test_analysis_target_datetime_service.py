from __future__ import annotations

import unittest
from pathlib import Path

from app.services.analysis_target_datetime_service import (
    AnalysisTargetDatetimeService,
)
from app.services.live_session_risk_service import (
    LiveSessionRiskService,
)


class AnalysisTargetDatetimeServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AnalysisTargetDatetimeService()

    def test_default_preserves_legacy_chart_end_clock(self) -> None:
        result = self.service.resolve(
            chart_end_datetime="2023-01-02T04:00:00",
            timeframe="H4",
            analysis_target_datetime=None,
        )

        self.assertEqual(result["status"], "LEGACY_CHART_END_DEFAULT")
        self.assertEqual(result["datetime_source"], "CHART_END_DATETIME")
        self.assertEqual(result["effective_datetime"], "2023-01-02T04:00:00")
        self.assertFalse(result["override_requested"])
        self.assertFalse(result["anti_lookahead_validated"])

    def test_h4_london_target_is_valid_after_closed_candle(self) -> None:
        result = self.service.resolve(
            chart_end_datetime="2023-01-02T04:00:00",
            timeframe="H4",
            analysis_target_datetime="2023-01-02T09:00:00",
        )

        self.assertEqual(result["status"], "ANALYSIS_TARGET_VALIDATED")
        self.assertEqual(result["datetime_source"], "ANALYSIS_TARGET_OVERRIDE")
        self.assertEqual(
            result["expected_chart_end_close_datetime"],
            "2023-01-02T08:00:00",
        )
        self.assertEqual(result["target_delay_after_close_minutes"], 60.0)
        self.assertTrue(result["anti_lookahead_validated"])

    def test_target_before_close_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "mendahului waktu close"):
            self.service.resolve(
                chart_end_datetime="2023-01-02T04:00:00",
                timeframe="H4",
                analysis_target_datetime="2023-01-02T07:59:59",
            )

    def test_target_beyond_one_candle_freshness_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "batas freshness"):
            self.service.resolve(
                chart_end_datetime="2023-01-02T04:00:00",
                timeframe="H4",
                analysis_target_datetime="2023-01-02T12:00:01",
            )

    def test_timezone_basis_must_match_ohlcv_clock(self) -> None:
        with self.assertRaisesRegex(ValueError, "basis timezone"):
            self.service.resolve(
                chart_end_datetime="2023-01-02T04:00:00",
                timeframe="H4",
                analysis_target_datetime="2023-01-02T09:00:00Z",
            )

    def test_validated_target_changes_only_session_clock(self) -> None:
        clock = self.service.resolve(
            chart_end_datetime="2023-01-02T04:00:00",
            timeframe="H4",
            analysis_target_datetime="2023-01-02T09:00:00",
        )
        session = LiveSessionRiskService._session_context(
            pair="GBPUSD",
            chart_end_datetime=clock["effective_datetime"],
            market_utc_offset_hours=0.0,
            datetime_source=clock["datetime_source"],
            original_chart_end_datetime=clock["chart_end_datetime"],
        )

        self.assertEqual(session["session"], "LONDON")
        self.assertEqual(session["evaluation_datetime_source"], "ANALYSIS_TARGET_OVERRIDE")
        self.assertEqual(session["chart_end_datetime"], "2023-01-02T04:00:00")
        self.assertEqual(session["analysis_target_datetime"], "2023-01-02T09:00:00")

    def test_full_endpoint_keeps_override_optional_and_session_only(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "api"
            / "full_analysis.py"
        )
        source = source_path.read_text(encoding="utf-8-sig")
        self.assertIn(
            "analysis_target_datetime: str | None = Query(\n        default=None,",
            source,
        )

        htf_start = source.index("htf_volatility_service.analyze(")
        session_start = source.index("session_risk_service.analyze(")
        htf_call = source[htf_start:session_start]
        session_call = source[session_start:source.index("except Exception", session_start)]
        self.assertNotIn("analysis_datetime=", htf_call)
        self.assertIn("analysis_datetime=", session_call)
        self.assertIn("analysis_datetime_source=", session_call)


if __name__ == "__main__":
    unittest.main()
