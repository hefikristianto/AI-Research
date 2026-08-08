from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.services.screenshot_price_axis_calibration_service import (
    OptionalTesseractPriceAxisOCRProvider,
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
        self.assertEqual(
            result["axis_region_method"],
            "PLOT_RIGHT_EDGE_CAPPED_TO_RIGHT_STRIP",
        )
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

    def test_ignores_low_confidence_percent_noise(self) -> None:
        service = ScreenshotPriceAxisCalibrationService(
            _FakeOCRProvider(
                [
                    self._observation("1.28000", 50),
                    self._observation("1.27500", 150),
                    self._observation("1.27000", 250),
                    {
                        **self._observation(
                            "8855500808%0805580080",
                            210,
                            confidence=0.0,
                        ),
                        "height": 1,
                    },
                ]
            )
        )

        result = service.calibrate(
            self._image(),
            pair="GBPUSD",
            plot_geometry=self._geometry(),
        )

        self.assertEqual(result["status"], "CALIBRATED")
        self.assertEqual(result["percent_label_observation_count"], 0)

    def test_requires_three_valid_percent_labels_for_axis_detection(
        self,
    ) -> None:
        service = ScreenshotPriceAxisCalibrationService(
            _FakeOCRProvider(
                [
                    self._observation("1.28000", 50),
                    self._observation("1.27500", 150),
                    self._observation("1.27000", 250),
                    self._observation("+0.20%", 350),
                ]
            )
        )

        result = service.calibrate(
            self._image(),
            pair="GBPUSD",
            plot_geometry=self._geometry(),
        )

        self.assertEqual(result["status"], "CALIBRATED")
        self.assertEqual(result["percent_label_observation_count"], 1)

    def test_repeated_well_formed_percent_labels_are_structural_evidence(
        self,
    ) -> None:
        service = ScreenshotPriceAxisCalibrationService(
            _FakeOCRProvider(
                [
                    self._observation("2.0%", 50, confidence=15.0),
                    self._observation("1.0%", 150, confidence=15.0),
                    self._observation("0.0%", 250, confidence=15.0),
                ]
            )
        )

        result = service.calibrate(
            self._image(),
            pair="GBPUSD",
            plot_geometry=self._geometry(),
        )

        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["reason_code"], "PERCENT_PRICE_AXIS_DETECTED")
        self.assertEqual(result["percent_label_observation_count"], 3)

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

    def test_registered_preprocessing_profiles_preserve_contract(self) -> None:
        image = Image.new("RGB", (120, 60), color=(15, 15, 15))

        raw = OptionalTesseractPriceAxisOCRProvider(
            preprocessing_profile="RAW_RGB"
        )
        enlarged = OptionalTesseractPriceAxisOCRProvider(
            preprocessing_profile="GRAYSCALE_AUTOCONTRAST_2X"
        )
        inverted = OptionalTesseractPriceAxisOCRProvider(
            preprocessing_profile=(
                "GRAYSCALE_INVERT_AUTOCONTRAST_2X"
            )
        )
        footer_trimmed = OptionalTesseractPriceAxisOCRProvider(
            preprocessing_profile=(
                "GRAYSCALE_FOOTER_TRIM_AUTOCONTRAST_2X"
            )
        )

        raw_image, raw_scale = raw._prepare_image(image)
        enlarged_image, enlarged_scale = enlarged._prepare_image(image)
        inverted_image, inverted_scale = inverted._prepare_image(image)
        footer_image, footer_scale = footer_trimmed._prepare_image(image)

        self.assertEqual(raw_image.size, image.size)
        self.assertEqual(raw_scale, 1.0)
        self.assertEqual(enlarged_image.size, (240, 120))
        self.assertEqual(inverted_image.size, (240, 120))
        self.assertEqual(footer_image.size, (240, 120))
        self.assertEqual(enlarged_scale, 2.0)
        self.assertEqual(inverted_scale, 2.0)
        self.assertEqual(footer_scale, 2.0)

        with self.assertRaisesRegex(ValueError, "tidak didukung"):
            OptionalTesseractPriceAxisOCRProvider(
                preprocessing_profile="UNREGISTERED"
            )

    def test_footer_trim_profile_removes_dark_footer_only_on_bright_chart(
        self,
    ) -> None:
        provider = OptionalTesseractPriceAxisOCRProvider(
            preprocessing_profile=(
                "GRAYSCALE_FOOTER_TRIM_AUTOCONTRAST_2X"
            )
        )
        bright = Image.new("RGB", (200, 200), color="white")
        for y_pixel in range(180, 200):
            for x_pixel in range(200):
                bright.putpixel((x_pixel, y_pixel), (15, 15, 15))
        dark = Image.new("RGB", (200, 200), color=(15, 15, 15))

        bright_input, bright_region = provider._ocr_input_region(bright)
        dark_input, dark_region = provider._ocr_input_region(dark)

        self.assertEqual(bright_input.size, (200, 180))
        self.assertEqual(bright_region, (0, 0, 200, 180))
        self.assertEqual(dark_input.size, dark.size)
        self.assertEqual(dark_region, (0, 0, 200, 200))

    def test_tesseract_profile_restores_coordinates_and_global_command(
        self,
    ) -> None:
        tesseract_state = SimpleNamespace(tesseract_cmd="tesseract-default")
        fake_module = SimpleNamespace(
            pytesseract=tesseract_state,
            Output=SimpleNamespace(DICT="DICT"),
            get_tesseract_version=lambda: "5.5.0",
            image_to_data=lambda *args, **kwargs: {
                "text": ["1.27500"],
                "conf": ["96"],
                "left": [20],
                "top": [40],
                "width": [120],
                "height": [24],
            },
        )
        provider = OptionalTesseractPriceAxisOCRProvider(
            preprocessing_profile="GRAYSCALE_AUTOCONTRAST_2X",
            tesseract_cmd="C:/OCR/tesseract.exe",
        )

        with patch(
            "app.services.screenshot_price_axis_calibration_service."
            "importlib.import_module",
            return_value=fake_module,
        ):
            result = provider.extract(
                Image.new("RGB", (100, 60), color="white")
            )

        self.assertEqual(result["status"], "OCR_COMPLETE")
        self.assertEqual(result["tesseract_version"], "5.5.0")
        self.assertEqual(result["observations"][0]["left"], 10.0)
        self.assertEqual(result["observations"][0]["top"], 20.0)
        self.assertEqual(result["observations"][0]["width"], 60.0)
        self.assertEqual(result["observations"][0]["height"], 12.0)
        self.assertEqual(tesseract_state.tesseract_cmd, "tesseract-default")


if __name__ == "__main__":
    unittest.main()
