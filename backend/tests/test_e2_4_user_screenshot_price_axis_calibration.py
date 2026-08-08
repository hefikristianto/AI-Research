from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_4_user_screenshot_price_axis_calibration.json"
)


class E24UserScreenshotPriceAxisCalibrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8")
        )

    def test_experiment_is_telemetry_only_and_fail_closed(self) -> None:
        integration = self.contract["integration_boundary"]
        calibration = self.contract["calibration_contract"]

        self.assertEqual(
            integration["api_mode"],
            "OPT_IN_TELEMETRY_ONLY",
        )
        self.assertFalse(integration["entry_price_authorized"])
        self.assertFalse(integration["may_replace_canonical_ohlcv"])
        self.assertFalse(
            integration["may_change_buy_sell_watchlist_no_trade"]
        )
        self.assertGreaterEqual(
            calibration["minimum_valid_ocr_ticks"],
            3,
        )
        self.assertTrue(
            calibration[
                "price_must_decrease_as_pixel_y_increases"
            ]
        )

    def test_holdout_and_high_risk_remain_locked(self) -> None:
        holdout = self.contract["holdout_access"]

        self.assertFalse(holdout["frozen_2024_allowed"])
        self.assertFalse(holdout["final_2025_allowed"])
        self.assertFalse(self.contract["high_risk_policy_changed"])
        self.assertFalse(self.contract["production_default_changed"])
        self.assertFalse(self.contract["training_performed"])

    def test_cnn_and_yolo_inputs_remain_separate(self) -> None:
        integration = self.contract["integration_boundary"]

        self.assertIn("CANDLE_CROP", integration["cnn_input"])
        self.assertEqual(
            integration["yolo_input"],
            "FULL_DETECTED_PLOT_UNCHANGED",
        )

    def test_api_keeps_calibration_opt_in_and_out_of_decision_calls(
        self,
    ) -> None:
        api_path = (
            PROJECT_ROOT
            / "backend"
            / "app"
            / "api"
            / "full_analysis.py"
        )
        schema_path = (
            PROJECT_ROOT
            / "backend"
            / "app"
            / "schemas"
            / "full_analysis.py"
        )
        source = api_path.read_text(encoding="utf-8-sig")
        schema = schema_path.read_text(encoding="utf-8-sig")

        self.assertIn(
            "screenshot_price_axis_calibration: bool = Query(\n"
            "        default=False,",
            source,
        )
        self.assertIn(
            "price_axis_calibration: dict[str, Any]",
            schema,
        )

        decision_start = source.index(
            "execution_gate_service.evaluate("
        )
        decision_end = source.index(
            "if include_annotated_chart:",
            decision_start,
        )

        self.assertNotIn(
            "price_axis_calibration_result",
            source[decision_start:decision_end],
        )


if __name__ == "__main__":
    unittest.main()
