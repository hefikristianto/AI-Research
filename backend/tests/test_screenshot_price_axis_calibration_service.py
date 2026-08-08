from __future__ import annotations

import unittest

from PIL import Image

from app.services.screenshot_price_axis_calibration_service import (
    ScreenshotPriceAxisCalibrationService,
)


class _FakeOCRProvider:
    def __init__(
        self,
        observations: list[dict[str, object]],
        *,
        status: str = "OCR_COMPLETE",
        reason_code: str | None = None,
    ) -> None:
        self.observations = observations
        self.status = status
        self.reason_code = reason_code

    def extract(self, image: Image.Image) -> dict[str, object]:
        return {
            "status": self.status,
            "engine": "FAKE_OCR",
            "reason_code": self.reason_code,
            "observations": self.observations,
        }


class ScreenshotPriceAxisCalibrationServiceTest(unittest.TestCase):
    @staticmethod
    def _observation(
        text: str,
        y_center: float,
        confidence: float = 95.0,
    ) -> dict[str, object]:
        return {
            "text": text,
            "confidence": confidence,
            "left": 5,
            "top": y_center - 5,
            "width": 60,
            "height": 10,
        }

    @staticmethod
    def _image() -> Image.Image:
        return Image.new("RGB", (1000, 500), color=(15, 15, 15))

    @staticmethod
    def _geometry() -> dict[str, object]:
        return {
            "status": "DETECTED",
            "plot_right_pixel": 850,
            "plot_right_normalized": 0.85,
        }

    def test_parses_dot_comma_and_comma_dot_price_formats(self) -> None:
        service = ScreenshotPriceAxisCalibrationService

        self.assertEqual(
            service.parse_price_label("1.27150", "GBPUSD"),
            1.27150,
        )
        self.assertEqual(
            service.parse_price_label("1,27150", "GBPUSD"),
            1.27150,
        )
        self.assertEqual(
            service.parse_price_label("4.027,10", "XAUUSD"),
            4027.10,
        )
        self.assertEqual(
            service.parse_price_label("4,027.10", "XAUUSD"),
            4027.10,
        )
        self.assertEqual(
            service.parse_price_label("4,027", "XAUUSD"),
            4027.0,
        )

    def test_calibrates_linear_axis_and_maps_pixel_price(self) -> None:
        provider = _FakeOCRProvider(
            [
                self._observation("1.28000", 50),
                self._observation("1.27500", 150),
                self._observation("1.27000", 250),
                self._observation("1.26500", 350),
                self._observation("1.29999", 210),
            ]
        )
        service = ScreenshotPriceAxisCalibrationService(provider)

        result = service.calibrate(
            self._image(),
            pair="GBPUSD",
            plot_geometry=self._geometry(),
        )

        self.assertEqual(result["status"], "CALIBRATED")
        self.assertEqual(result["valid_tick_count"], 5)
        self.assertEqual(result["inlier_tick_count"], 4)
        self.assertEqual(result["rejected_tick_count"], 1)
        self.assertEqual(result["axis_region_method"], "PLOT_RIGHT_EDGE")
        self.assertFalse(result["entry_price_authorized"])
        self.assertFalse(result["production_decision_changed"])
        self.assertAlmostEqual(
            service.price_at_y(result, 250),
            1.27000,
            places=6,
        )

    def test_fails_closed_when_fewer_than_three_ticks_are_valid(self) -> None:
        service = ScreenshotPriceAxisCalibrationService(
            _FakeOCRProvider(
                [
                    self._observation("1.28000", 50),
                    self._observation("1.27500", 150),
                ]
            )
        )

        result = service.calibrate(
            self._image(),
            pair="GBPUSD",
            plot_geometry=self._geometry(),
        )

        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(
            result["reason_code"],
            "INSUFFICIENT_VALID_PRICE_TICKS",
        )
        self.assertTrue(result["mapping_provisional"])
        self.assertFalse(result["entry_price_authorized"])

    def test_fails_closed_for_percent_and_declared_log_axis(self) -> None:
        percent_service = ScreenshotPriceAxisCalibrationService(
            _FakeOCRProvider(
                [
                    self._observation("2.0%", 50),
                    self._observation("1.0%", 150),
                    self._observation("0.0%", 250),
                ]
            )
        )

        percent = percent_service.calibrate(
            self._image(),
            pair="GBPUSD",
            plot_geometry=self._geometry(),
        )
        logarithmic = percent_service.calibrate(
            self._image(),
            pair="GBPUSD",
            plot_geometry=self._geometry(),
            declared_scale_mode="LOG",
        )

        self.assertEqual(
            percent["reason_code"],
            "PERCENT_PRICE_AXIS_DETECTED",
        )
        self.assertEqual(
            logarithmic["reason_code"],
            "LOG_PRICE_AXIS_UNSUPPORTED",
        )

    def test_fails_closed_for_ascending_or_cropped_axis(self) -> None:
        ascending = ScreenshotPriceAxisCalibrationService.fit_ticks(
            [
                {"text": "1.26000", "price": 1.26, "y": 50},
                {"text": "1.26500", "price": 1.265, "y": 150},
                {"text": "1.27000", "price": 1.27, "y": 250},
            ],
            image_height=500,
            pair="GBPUSD",
        )
        cropped = ScreenshotPriceAxisCalibrationService.fit_ticks(
            [
                {"text": "1.27000", "price": 1.270, "y": 100},
                {"text": "1.26990", "price": 1.2699, "y": 120},
                {"text": "1.26980", "price": 1.2698, "y": 140},
            ],
            image_height=1000,
            pair="GBPUSD",
        )

        self.assertEqual(
            ascending["reason_code"],
            "PRICE_AXIS_NOT_MONOTONIC_DESCENDING",
        )
        self.assertEqual(
            cropped["reason_code"],
            "PRICE_AXIS_CROPPED_OR_TOO_NARROW",
        )

    def test_fails_closed_when_ocr_backend_is_unavailable(self) -> None:
        service = ScreenshotPriceAxisCalibrationService(
            _FakeOCRProvider(
                [],
                status="OCR_UNAVAILABLE",
                reason_code="OCR_BACKEND_UNAVAILABLE",
            )
        )

        result = service.calibrate(
            self._image(),
            pair="GBPUSD",
            plot_geometry=self._geometry(),
        )

        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(
            result["reason_code"],
            "OCR_BACKEND_UNAVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
