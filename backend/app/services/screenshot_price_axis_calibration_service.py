from __future__ import annotations

import importlib
import math
import os
import re
import threading
from statistics import median
from typing import Any
from typing import Protocol

from PIL import Image
from PIL import ImageOps
from PIL import ImageStat


class PriceAxisOCRProvider(Protocol):
    """Small adapter boundary for replaceable OCR engines."""

    def extract(
        self,
        image: Image.Image,
    ) -> dict[str, Any]: ...


class OptionalTesseractPriceAxisOCRProvider:
    """Use pytesseract when locally available, otherwise fail closed."""

    ENGINE = "PYTESSERACT"
    SUPPORTED_PREPROCESSING_PROFILES = {
        "RAW_RGB",
        "GRAYSCALE_AUTOCONTRAST_2X",
        "GRAYSCALE_INVERT_AUTOCONTRAST_2X",
        "GRAYSCALE_FOOTER_TRIM_AUTOCONTRAST_2X",
    }
    LIGHT_BACKGROUND_MINIMUM = 220
    DARK_FOOTER_MAXIMUM_MEAN = 80.0
    MINIMUM_FOOTER_HEIGHT_RATIO = 0.025
    _OCR_LOCK = threading.RLock()

    def __init__(
        self,
        *,
        preprocessing_profile: str = "RAW_RGB",
        tesseract_cmd: str | None = None,
    ) -> None:
        profile = str(preprocessing_profile).upper()
        if profile not in self.SUPPORTED_PREPROCESSING_PROFILES:
            raise ValueError(
                "Profil preprocessing OCR tidak didukung: "
                f"{preprocessing_profile}"
            )

        self.preprocessing_profile = profile
        self.tesseract_cmd = (
            str(tesseract_cmd).strip()
            if tesseract_cmd
            else str(
                os.getenv("AI_TDSS_TESSERACT_CMD", "")
            ).strip()
        ) or None

    @classmethod
    def _footer_trim_bottom(
        cls,
        image: Image.Image,
    ) -> int:
        """Return a safe lower OCR boundary for bright charts.

        TradingView can append a dark navigation/status footer below an
        otherwise bright chart. Including that footer in global
        autocontrast suppresses the faint gray price ticks. The crop is
        applied only when the upper image has a bright dominant tone and
        a sufficiently tall, contiguous dark band reaches the bottom.
        """

        grayscale = image.convert("L")
        width, height = grayscale.size
        if width < 1 or height < 2:
            return height

        upper_height = max(1, round(height * 0.80))
        histogram = grayscale.crop(
            (0, 0, width, upper_height)
        ).histogram()
        dominant_tone = max(
            range(len(histogram)),
            key=histogram.__getitem__,
        )
        if dominant_tone < cls.LIGHT_BACKGROUND_MINIMUM:
            return height

        footer_start = height
        for y_pixel in range(height - 1, -1, -1):
            row_mean = ImageStat.Stat(
                grayscale.crop((0, y_pixel, width, y_pixel + 1))
            ).mean[0]
            if row_mean > cls.DARK_FOOTER_MAXIMUM_MEAN:
                break
            footer_start = y_pixel

        minimum_footer_height = max(
            8,
            round(height * cls.MINIMUM_FOOTER_HEIGHT_RATIO),
        )
        if height - footer_start < minimum_footer_height:
            return height

        return footer_start

    def _ocr_input_region(
        self,
        image: Image.Image,
    ) -> tuple[Image.Image, tuple[int, int, int, int]]:
        width, height = image.size
        bottom = height
        if self.preprocessing_profile == (
            "GRAYSCALE_FOOTER_TRIM_AUTOCONTRAST_2X"
        ):
            bottom = self._footer_trim_bottom(image)

        region = (0, 0, width, bottom)
        return image.crop(region), region

    def _prepare_image(
        self,
        image: Image.Image,
    ) -> tuple[Image.Image, float]:
        if self.preprocessing_profile == "RAW_RGB":
            return image.convert("RGB"), 1.0

        prepared = ImageOps.autocontrast(
            image.convert("L")
        )
        if self.preprocessing_profile == (
            "GRAYSCALE_INVERT_AUTOCONTRAST_2X"
        ):
            prepared = ImageOps.invert(prepared)

        scale = 2.0
        prepared = prepared.resize(
            (
                max(1, round(prepared.width * scale)),
                max(1, round(prepared.height * scale)),
            ),
            Image.Resampling.LANCZOS,
        )
        return prepared, scale

    def extract(
        self,
        image: Image.Image,
    ) -> dict[str, Any]:
        try:
            pytesseract = importlib.import_module(
                "pytesseract"
            )
        except (ImportError, ModuleNotFoundError):
            return {
                "status": "OCR_UNAVAILABLE",
                "engine": self.ENGINE,
                "preprocessing_profile": self.preprocessing_profile,
                "reason_code": "OCR_BACKEND_UNAVAILABLE",
                "observations": [],
            }

        ocr_input, ocr_input_region = self._ocr_input_region(image)
        prepared, coordinate_scale = self._prepare_image(ocr_input)
        coordinate_left = float(ocr_input_region[0])
        coordinate_top = float(ocr_input_region[1])

        version: str | None = None
        try:
            with self._OCR_LOCK:
                previous_tesseract_cmd = (
                    pytesseract.pytesseract.tesseract_cmd
                )
                if self.tesseract_cmd:
                    pytesseract.pytesseract.tesseract_cmd = (
                        self.tesseract_cmd
                    )

                try:
                    version = str(
                        pytesseract.get_tesseract_version()
                    )
                    data = pytesseract.image_to_data(
                        prepared,
                        config=(
                            "--oem 1 --psm 11 "
                            "-c tessedit_char_whitelist="
                            "0123456789.,-%"
                        ),
                        output_type=pytesseract.Output.DICT,
                    )
                finally:
                    pytesseract.pytesseract.tesseract_cmd = (
                        previous_tesseract_cmd
                    )
        except Exception as error:
            return {
                "status": "OCR_ERROR",
                "engine": self.ENGINE,
                "preprocessing_profile": self.preprocessing_profile,
                "tesseract_version": version,
                "tesseract_cmd": self.tesseract_cmd,
                "reason_code": "OCR_EXECUTION_FAILED",
                "error": str(error),
                "observations": [],
            }

        observations: list[dict[str, Any]] = []
        texts = data.get("text", [])

        for index, raw_text in enumerate(texts):
            text = str(raw_text or "").strip()
            if not text:
                continue

            try:
                confidence = float(
                    data.get("conf", [])[index]
                )
                left = int(data.get("left", [])[index])
                top = int(data.get("top", [])[index])
                width = int(data.get("width", [])[index])
                height = int(data.get("height", [])[index])
            except (IndexError, TypeError, ValueError):
                continue

            observations.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "left": coordinate_left + left / coordinate_scale,
                    "top": coordinate_top + top / coordinate_scale,
                    "width": width / coordinate_scale,
                    "height": height / coordinate_scale,
                }
            )

        return {
            "status": "OCR_COMPLETE",
            "engine": self.ENGINE,
            "preprocessing_profile": self.preprocessing_profile,
            "tesseract_version": version,
            "tesseract_cmd": self.tesseract_cmd,
            "reason_code": None,
            "ocr_input_region": list(ocr_input_region),
            "observations": observations,
        }


class ScreenshotPriceAxisCalibrationService:
    """Fit a guarded linear pixel-y to price mapping from OCR ticks."""

    MAPPING_MODE = "SCREENSHOT_PRICE_AXIS_LINEAR"
    MINIMUM_VALID_TICKS = 3
    MINIMUM_OCR_CONFIDENCE = 0.50
    MINIMUM_PERCENT_LABEL_CONFIDENCE = 0.10
    MINIMUM_VERTICAL_COVERAGE = 0.12
    MINIMUM_AXIS_WIDTH_RATIO = 0.035
    FALLBACK_AXIS_START_RATIO = 0.72
    MAXIMUM_NORMALIZED_RMSE = 0.08
    MAXIMUM_NORMALIZED_RESIDUAL = 0.20
    PRELIMINARY_INLIER_RESIDUAL_RATIO = 0.30
    MINIMUM_R_SQUARED = 0.995
    MINIMUM_Y_SEPARATION_PIXELS = 3.0
    PERCENT_LABEL_PATTERN = re.compile(
        r"^[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)%$"
    )

    PAIR_PRICE_RANGES = {
        "GBPUSD": (0.50, 3.00),
        "XAUUSD": (100.0, 10000.0),
    }

    def __init__(
        self,
        ocr_provider: PriceAxisOCRProvider | None = None,
    ) -> None:
        self.ocr_provider = (
            ocr_provider
            or OptionalTesseractPriceAxisOCRProvider()
        )

    @classmethod
    def not_requested(cls) -> dict[str, Any]:
        return {
            "status": "NOT_REQUESTED",
            "mapping_mode": cls.MAPPING_MODE,
            "mapping_provisional": True,
            "entry_price_authorized": False,
            "production_decision_changed": False,
            "reason_code": "E2_4_OPT_IN_NOT_REQUESTED",
        }

    @classmethod
    def _fail(
        cls,
        reason_code: str,
        **telemetry: Any,
    ) -> dict[str, Any]:
        return {
            "status": "FAIL_CLOSED",
            "mapping_mode": cls.MAPPING_MODE,
            "mapping_provisional": True,
            "entry_price_authorized": False,
            "production_decision_changed": False,
            "reason_code": reason_code,
            **telemetry,
        }

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0

        if confidence > 1.0:
            confidence /= 100.0

        return max(0.0, min(1.0, confidence))

    @classmethod
    def _valid_percent_label_count(
        cls,
        observations: list[Any],
    ) -> int:
        count = 0
        for observation in observations:
            if not isinstance(observation, dict):
                continue
            confidence = cls._normalize_confidence(
                observation.get("confidence")
            )
            if confidence < cls.MINIMUM_PERCENT_LABEL_CONFIDENCE:
                continue
            compact = (
                str(observation.get("text", ""))
                .strip()
                .replace("\u00a0", "")
                .replace(" ", "")
            )
            if cls.PERCENT_LABEL_PATTERN.fullmatch(compact):
                count += 1
        return count

    @classmethod
    def _price_candidates(
        cls,
        text: str,
    ) -> list[float]:
        compact = (
            str(text)
            .strip()
            .replace("\u00a0", "")
            .replace(" ", "")
            .replace("'", "")
        )

        if "%" in compact:
            return []

        compact = re.sub(
            r"[^0-9,\.\-]",
            "",
            compact,
        )

        if not compact or compact in {"-", ".", ","}:
            return []

        candidates: list[str] = []
        comma = compact.rfind(",")
        dot = compact.rfind(".")

        if comma >= 0 and dot >= 0:
            decimal_separator = (
                "," if comma > dot else "."
            )
            thousands_separator = (
                "." if decimal_separator == "," else ","
            )
            candidates.append(
                compact
                .replace(thousands_separator, "")
                .replace(decimal_separator, ".")
            )
        elif comma >= 0 or dot >= 0:
            separator = "," if comma >= 0 else "."
            candidates.append(compact.replace(separator, "."))
            candidates.append(compact.replace(separator, ""))
        else:
            candidates.append(compact)

        parsed: list[float] = []
        for candidate in candidates:
            try:
                value = float(candidate)
            except ValueError:
                continue

            if math.isfinite(value) and value not in parsed:
                parsed.append(value)

        return parsed

    @classmethod
    def parse_price_label(
        cls,
        text: str,
        pair: str,
    ) -> float | None:
        pair_key = str(pair or "").upper()
        price_range = cls.PAIR_PRICE_RANGES.get(pair_key)
        if price_range is None:
            return None

        lower, upper = price_range
        candidates = cls._price_candidates(text)
        plausible = [
            candidate
            for candidate in candidates
            if lower <= candidate <= upper
        ]

        if len(plausible) != 1:
            return None

        return plausible[0]

    @staticmethod
    def _decimal_places(text: str) -> int | None:
        compact = (
            str(text)
            .strip()
            .replace("\u00a0", "")
            .replace(" ", "")
        )
        comma = compact.rfind(",")
        dot = compact.rfind(".")
        separator_index = max(comma, dot)

        if separator_index < 0:
            return 0

        suffix = re.sub(
            r"\D",
            "",
            compact[separator_index + 1 :],
        )
        return len(suffix) if suffix else None

    @classmethod
    def _axis_region(
        cls,
        image: Image.Image,
        plot_geometry: dict[str, Any] | None,
    ) -> tuple[tuple[int, int, int, int], str]:
        width, height = image.size
        geometry = (
            plot_geometry
            if isinstance(plot_geometry, dict)
            else {}
        )
        method = "RIGHT_STRIP_FALLBACK"
        fallback_left = round(width * cls.FALLBACK_AXIS_START_RATIO)
        left = fallback_left

        if geometry.get("status") == "DETECTED":
            raw_right = geometry.get("plot_right_pixel")
            if raw_right is None:
                try:
                    raw_right = round(
                        float(
                            geometry["plot_right_normalized"]
                        )
                        * width
                    )
                except (KeyError, TypeError, ValueError):
                    raw_right = None

            if raw_right is not None:
                candidate = int(raw_right) + 2
                candidate_width_ratio = (
                    width - candidate
                ) / max(1, width)
                if (
                    cls.MINIMUM_AXIS_WIDTH_RATIO
                    <= candidate_width_ratio
                    <= 0.35
                ):
                    left = min(candidate, fallback_left)
                    method = (
                        "PLOT_RIGHT_EDGE"
                        if candidate <= fallback_left
                        else "PLOT_RIGHT_EDGE_CAPPED_TO_RIGHT_STRIP"
                    )

        left = max(0, min(width - 1, left))
        return (left, 0, width, height), method

    @staticmethod
    def _linear_fit(
        ticks: list[dict[str, Any]],
    ) -> tuple[float, float]:
        mean_y = sum(tick["y"] for tick in ticks) / len(ticks)
        mean_price = (
            sum(tick["price"] for tick in ticks) / len(ticks)
        )
        denominator = sum(
            (tick["y"] - mean_y) ** 2
            for tick in ticks
        )
        if denominator <= 0.0:
            raise ValueError("Tick Y tidak memiliki variasi.")

        slope = sum(
            (tick["y"] - mean_y)
            * (tick["price"] - mean_price)
            for tick in ticks
        ) / denominator
        intercept = mean_price - slope * mean_y
        return slope, intercept

    @staticmethod
    def _r_squared(
        ticks: list[dict[str, Any]],
        slope: float,
        intercept: float,
        *,
        log_price: bool = False,
    ) -> float:
        values = [
            math.log(tick["price"])
            if log_price
            else tick["price"]
            for tick in ticks
        ]
        mean_value = sum(values) / len(values)
        residual = sum(
            (
                value
                - (slope * tick["y"] + intercept)
            )
            ** 2
            for tick, value in zip(ticks, values)
        )
        total = sum(
            (value - mean_value) ** 2
            for value in values
        )
        if total <= 0.0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - residual / total))

    @classmethod
    def _deduplicate_ticks(
        cls,
        ticks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []

        for tick in sorted(ticks, key=lambda item: item["y"]):
            if (
                selected
                and abs(tick["y"] - selected[-1]["y"])
                < cls.MINIMUM_Y_SEPARATION_PIXELS
            ):
                if tick["confidence"] > selected[-1]["confidence"]:
                    selected[-1] = tick
                continue
            selected.append(tick)

        return selected

    @classmethod
    def fit_ticks(
        cls,
        ticks: list[dict[str, Any]],
        *,
        image_height: int,
        pair: str,
        axis_region: tuple[int, int, int, int] | None = None,
        axis_region_method: str | None = None,
        ocr_engine: str | None = None,
    ) -> dict[str, Any]:
        normalized: list[dict[str, Any]] = []
        for tick in ticks:
            try:
                y_value = float(tick["y"])
                price_value = float(tick["price"])
            except (KeyError, TypeError, ValueError):
                continue

            confidence = cls._normalize_confidence(
                tick.get("confidence", 1.0)
            )
            if (
                not math.isfinite(y_value)
                or not math.isfinite(price_value)
                or confidence < cls.MINIMUM_OCR_CONFIDENCE
            ):
                continue

            normalized.append(
                {
                    **tick,
                    "y": y_value,
                    "price": price_value,
                    "confidence": confidence,
                }
            )

        normalized = cls._deduplicate_ticks(normalized)
        telemetry = {
            "pair": str(pair).upper(),
            "ocr_engine": ocr_engine,
            "valid_tick_count": len(normalized),
            "required_tick_count": cls.MINIMUM_VALID_TICKS,
            "axis_region": list(axis_region) if axis_region else None,
            "axis_region_method": axis_region_method,
        }

        if len(normalized) < cls.MINIMUM_VALID_TICKS:
            return cls._fail("INSUFFICIENT_VALID_PRICE_TICKS", **telemetry)

        y_values = [tick["y"] for tick in normalized]
        vertical_coverage = (
            max(y_values) - min(y_values)
        ) / max(1, image_height - 1)
        telemetry["vertical_coverage"] = vertical_coverage

        if vertical_coverage < cls.MINIMUM_VERTICAL_COVERAGE:
            return cls._fail("PRICE_AXIS_CROPPED_OR_TOO_NARROW", **telemetry)

        slopes = [
            (right["price"] - left["price"])
            / (right["y"] - left["y"])
            for index, left in enumerate(normalized)
            for right in normalized[index + 1 :]
            if abs(right["y"] - left["y"])
            >= cls.MINIMUM_Y_SEPARATION_PIXELS
        ]
        if not slopes:
            return cls._fail("PRICE_AXIS_Y_VARIATION_REQUIRED", **telemetry)

        robust_slope = float(median(slopes))
        if robust_slope >= 0.0:
            return cls._fail("PRICE_AXIS_NOT_MONOTONIC_DESCENDING", **telemetry)

        robust_intercept = float(
            median(
                tick["price"] - robust_slope * tick["y"]
                for tick in normalized
            )
        )
        ordered_prices = [
            tick["price"]
            for tick in sorted(normalized, key=lambda item: item["y"])
        ]
        price_deltas = [
            abs(right - left)
            for left, right in zip(
                ordered_prices,
                ordered_prices[1:],
            )
            if abs(right - left) > 0.0
        ]
        if not price_deltas:
            return cls._fail("PRICE_TICK_STEP_INVALID", **telemetry)

        price_step = float(median(price_deltas))
        preliminary_threshold = (
            price_step
            * cls.PRELIMINARY_INLIER_RESIDUAL_RATIO
        )
        preliminary_inliers = [
            tick
            for tick in normalized
            if abs(
                tick["price"]
                - (
                    robust_slope * tick["y"]
                    + robust_intercept
                )
            )
            <= preliminary_threshold
        ]

        if len(preliminary_inliers) < cls.MINIMUM_VALID_TICKS:
            return cls._fail("ROBUST_PRICE_FIT_HAS_TOO_FEW_INLIERS", **telemetry)

        try:
            slope, intercept = cls._linear_fit(preliminary_inliers)
        except ValueError:
            return cls._fail("PRICE_AXIS_Y_VARIATION_REQUIRED", **telemetry)

        if slope >= 0.0:
            return cls._fail("PRICE_AXIS_NOT_MONOTONIC_DESCENDING", **telemetry)

        final_threshold = price_step * cls.MAXIMUM_NORMALIZED_RESIDUAL
        inliers = [
            tick
            for tick in normalized
            if abs(
                tick["price"]
                - (slope * tick["y"] + intercept)
            )
            <= final_threshold
        ]
        if len(inliers) < cls.MINIMUM_VALID_TICKS:
            return cls._fail("LINEAR_PRICE_FIT_HAS_TOO_FEW_INLIERS", **telemetry)

        slope, intercept = cls._linear_fit(inliers)
        ordered_inliers = sorted(inliers, key=lambda item: item["y"])
        if any(
            left["price"] <= right["price"]
            for left, right in zip(
                ordered_inliers,
                ordered_inliers[1:],
            )
        ):
            return cls._fail("PRICE_TICKS_NOT_STRICTLY_MONOTONIC", **telemetry)

        residuals = [
            tick["price"] - (slope * tick["y"] + intercept)
            for tick in inliers
        ]
        rmse = math.sqrt(
            sum(residual**2 for residual in residuals)
            / len(residuals)
        )
        maximum_residual = max(abs(residual) for residual in residuals)
        normalized_rmse = rmse / price_step
        normalized_maximum_residual = maximum_residual / price_step
        linear_r_squared = cls._r_squared(
            inliers,
            slope,
            intercept,
        )

        log_ticks = [
            {**tick, "price": math.log(tick["price"])}
            for tick in inliers
            if tick["price"] > 0.0
        ]
        log_r_squared = 0.0
        if len(log_ticks) == len(inliers):
            log_slope, log_intercept = cls._linear_fit(log_ticks)
            log_r_squared = cls._r_squared(
                inliers,
                log_slope,
                log_intercept,
                log_price=True,
            )

        telemetry.update(
            {
                "inlier_tick_count": len(inliers),
                "rejected_tick_count": len(normalized) - len(inliers),
                "price_tick_step": price_step,
                "linear_r_squared": linear_r_squared,
                "log_r_squared": log_r_squared,
                "rmse_price": rmse,
                "maximum_residual_price": maximum_residual,
                "normalized_rmse": normalized_rmse,
                "normalized_maximum_residual": normalized_maximum_residual,
            }
        )

        if (
            log_r_squared >= cls.MINIMUM_R_SQUARED
            and log_r_squared > linear_r_squared + 0.02
        ):
            return cls._fail("LOG_PRICE_AXIS_SUSPECTED", **telemetry)

        if (
            linear_r_squared < cls.MINIMUM_R_SQUARED
            or normalized_rmse > cls.MAXIMUM_NORMALIZED_RMSE
            or normalized_maximum_residual
            > cls.MAXIMUM_NORMALIZED_RESIDUAL
        ):
            return cls._fail("LINEAR_PRICE_FIT_VALIDATION_FAILED", **telemetry)

        decimal_places = [
            cls._decimal_places(str(tick.get("text", "")))
            for tick in inliers
            if tick.get("text") is not None
        ]
        decimal_places = [
            value for value in decimal_places if value is not None
        ]
        decimal_precision_consistent = (
            not decimal_places
            or max(decimal_places) - min(decimal_places) <= 1
        )
        telemetry["decimal_places"] = decimal_places
        telemetry["decimal_precision_consistent"] = (
            decimal_precision_consistent
        )
        if not decimal_precision_consistent:
            return cls._fail("INCONSISTENT_PRICE_DECIMAL_PRECISION", **telemetry)

        public_ticks = [
            {
                "text": tick.get("text"),
                "y": tick["y"],
                "price": tick["price"],
                "confidence": tick["confidence"],
                "residual_price": (
                    tick["price"]
                    - (slope * tick["y"] + intercept)
                ),
            }
            for tick in ordered_inliers
        ]

        return {
            "status": "CALIBRATED",
            "mapping_mode": cls.MAPPING_MODE,
            "mapping_provisional": False,
            "entry_price_authorized": False,
            "production_decision_changed": False,
            "reason_code": None,
            **telemetry,
            "slope_price_per_pixel": slope,
            "intercept_price": intercept,
            "price_at_image_top": intercept,
            "price_at_image_bottom": (
                slope * max(0, image_height - 1) + intercept
            ),
            "ticks": public_ticks,
        }

    def calibrate(
        self,
        image: Image.Image,
        *,
        pair: str | None,
        plot_geometry: dict[str, Any] | None = None,
        declared_scale_mode: str = "AUTO",
    ) -> dict[str, Any]:
        pair_key = str(pair or "").upper()
        if pair_key not in self.PAIR_PRICE_RANGES:
            return self._fail(
                "SUPPORTED_PAIR_METADATA_REQUIRED",
                pair=pair_key or None,
            )

        scale_mode = str(declared_scale_mode or "AUTO").upper()
        if scale_mode in {"LOG", "LOGARITHMIC"}:
            return self._fail(
                "LOG_PRICE_AXIS_UNSUPPORTED",
                pair=pair_key,
                declared_scale_mode=scale_mode,
            )
        if scale_mode in {"PERCENT", "PERCENTAGE"}:
            return self._fail(
                "PERCENT_PRICE_AXIS_UNSUPPORTED",
                pair=pair_key,
                declared_scale_mode=scale_mode,
            )
        if scale_mode not in {"AUTO", "LINEAR"}:
            return self._fail(
                "UNKNOWN_PRICE_AXIS_SCALE_MODE",
                pair=pair_key,
                declared_scale_mode=scale_mode,
            )

        canvas = image.convert("RGB")
        width, height = canvas.size
        if width < 96 or height < 96:
            return self._fail(
                "IMAGE_TOO_SMALL_FOR_PRICE_AXIS_OCR",
                pair=pair_key,
                image_width=width,
                image_height=height,
            )

        axis_region, axis_region_method = self._axis_region(
            canvas,
            plot_geometry,
        )
        left, top, right, bottom = axis_region
        axis_width_ratio = (right - left) / max(1, width)
        if axis_width_ratio < self.MINIMUM_AXIS_WIDTH_RATIO:
            return self._fail(
                "PRICE_AXIS_REGION_TOO_NARROW",
                pair=pair_key,
                axis_region=list(axis_region),
                axis_region_method=axis_region_method,
                axis_width_ratio=axis_width_ratio,
            )

        ocr_result = self.ocr_provider.extract(
            canvas.crop(axis_region)
        )
        ocr_status = str(ocr_result.get("status", "OCR_ERROR"))
        ocr_engine = ocr_result.get("engine")
        preprocessing_profile = ocr_result.get(
            "preprocessing_profile"
        )
        tesseract_version = ocr_result.get(
            "tesseract_version"
        )
        if ocr_status != "OCR_COMPLETE":
            return self._fail(
                str(
                    ocr_result.get("reason_code")
                    or "PRICE_AXIS_OCR_FAILED"
                ),
                pair=pair_key,
                ocr_status=ocr_status,
                ocr_engine=ocr_engine,
                ocr_preprocessing_profile=preprocessing_profile,
                tesseract_version=tesseract_version,
                ocr_error=ocr_result.get("error"),
                axis_region=list(axis_region),
                axis_region_method=axis_region_method,
            )

        raw_observations = ocr_result.get("observations") or []
        percent_label_observation_count = (
            self._valid_percent_label_count(raw_observations)
        )
        if (
            percent_label_observation_count
            >= self.MINIMUM_VALID_TICKS
        ):
            return self._fail(
                "PERCENT_PRICE_AXIS_DETECTED",
                pair=pair_key,
                ocr_status=ocr_status,
                ocr_engine=ocr_engine,
                ocr_preprocessing_profile=preprocessing_profile,
                tesseract_version=tesseract_version,
                percent_label_observation_count=(
                    percent_label_observation_count
                ),
                axis_region=list(axis_region),
                axis_region_method=axis_region_method,
            )

        ticks: list[dict[str, Any]] = []
        for observation in raw_observations:
            if not isinstance(observation, dict):
                continue

            confidence = self._normalize_confidence(
                observation.get("confidence")
            )
            if confidence < self.MINIMUM_OCR_CONFIDENCE:
                continue

            text = str(observation.get("text", "")).strip()
            price = self.parse_price_label(text, pair_key)
            if price is None:
                continue

            try:
                local_top = float(observation["top"])
                token_height = float(observation.get("height", 0.0))
            except (KeyError, TypeError, ValueError):
                continue

            ticks.append(
                {
                    "text": text,
                    "price": price,
                    "confidence": confidence,
                    "y": top + local_top + token_height / 2.0,
                }
            )

        result = self.fit_ticks(
            ticks,
            image_height=height,
            pair=pair_key,
            axis_region=axis_region,
            axis_region_method=axis_region_method,
            ocr_engine=str(ocr_engine) if ocr_engine else None,
        )
        result.update(
            {
                "image_width": width,
                "image_height": height,
                "axis_width_ratio": axis_width_ratio,
                "declared_scale_mode": scale_mode,
                "ocr_status": ocr_status,
                "ocr_preprocessing_profile": preprocessing_profile,
                "tesseract_version": tesseract_version,
                "ocr_observation_count": len(raw_observations),
                "percent_label_observation_count": (
                    percent_label_observation_count
                ),
            }
        )
        return result

    @staticmethod
    def price_at_y(
        calibration: dict[str, Any],
        y_pixel: float,
    ) -> float:
        if calibration.get("status") != "CALIBRATED":
            raise ValueError("Kalibrasi sumbu harga belum valid.")

        return (
            float(calibration["slope_price_per_pixel"])
            * float(y_pixel)
            + float(calibration["intercept_price"])
        )
