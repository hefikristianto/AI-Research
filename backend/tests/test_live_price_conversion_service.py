from __future__ import annotations

import unittest
import sys
import types
from unittest.mock import patch

pandas_stub = types.ModuleType("pandas")
pandas_stub.DataFrame = object

with patch.dict(
    sys.modules,
    {"pandas": pandas_stub},
):
    from app.services.live_price_conversion_service import (
        CanonicalOHLCVPriceConversionService,
    )


class _Validator:
    @staticmethod
    def x_to_index(x_value: float, window_len: int) -> int:
        return round(x_value * (window_len - 1))


class LivePriceConversionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = object.__new__(
            CanonicalOHLCVPriceConversionService
        )
        self.service.validator = _Validator()
        self.geometry = {
            "status": "DETECTED",
            "plot_left_normalized": 0.05,
            "plot_right_normalized": 0.95,
        }

    def test_plot_aware_mapping_is_opt_in(self) -> None:
        legacy = self.service._index_mapping(
            x_value=0.91,
            window_len=100,
            plot_geometry=self.geometry,
            use_plot_geometry=False,
        )
        calibrated = self.service._index_mapping(
            x_value=0.91,
            window_len=100,
            plot_geometry=self.geometry,
            use_plot_geometry=True,
        )

        self.assertEqual(legacy["selected_index"], 90)
        self.assertEqual(legacy["index_mode"], "FULL_IMAGE")
        self.assertFalse(legacy["calibration_applied"])
        self.assertEqual(calibrated["selected_index"], 95)
        self.assertEqual(calibrated["legacy_index"], 90)
        self.assertEqual(calibrated["plot_aware_index"], 95)
        self.assertEqual(calibrated["index_mode"], "PLOT_AWARE")
        self.assertTrue(calibrated["calibration_applied"])

    def test_fallback_geometry_preserves_legacy_mapping(self) -> None:
        result = self.service._index_mapping(
            x_value=0.91,
            window_len=100,
            plot_geometry={
                "status": "FALLBACK",
                "plot_left_normalized": 0.0,
                "plot_right_normalized": 1.0,
            },
            use_plot_geometry=True,
        )

        self.assertEqual(result["selected_index"], 90)
        self.assertIsNone(result["plot_aware_index"])
        self.assertFalse(result["calibration_applied"])


if __name__ == "__main__":
    unittest.main()
