from __future__ import annotations

from statistics import median
from typing import Any

from PIL import Image


class ChartPlotGeometryService:
    """Estimate the horizontal candle plot bounds without assuming colors."""

    DIFFERENCE_THRESHOLD = 24
    MINIMUM_SPAN_RATIO = 0.55
    MAXIMUM_SPAN_RATIO = 0.98
    MINIMUM_MARGIN_RATIO = 0.01
    MAXIMUM_MARGIN_RATIO = 0.20
    MINIMUM_ACTIVE_COLUMN_RATIO = 0.10

    @staticmethod
    def _background_color(
        image: Image.Image,
    ) -> tuple[int, int, int]:
        width, height = image.size
        stride = max(
            1,
            min(width, height) // 128,
        )
        samples: list[tuple[int, int, int]] = []

        for x in range(0, width, stride):
            samples.append(image.getpixel((x, 0)))
            samples.append(
                image.getpixel((x, height - 1))
            )

        for y in range(0, height, stride):
            samples.append(image.getpixel((0, y)))
            samples.append(
                image.getpixel((width - 1, y))
            )

        return tuple(
            int(median(pixel[channel] for pixel in samples))
            for channel in range(3)
        )

    @classmethod
    def _is_foreground(
        cls,
        pixel: tuple[int, int, int],
        background: tuple[int, int, int],
    ) -> bool:
        return max(
            abs(pixel[channel] - background[channel])
            for channel in range(3)
        ) >= cls.DIFFERENCE_THRESHOLD

    @staticmethod
    def _fallback(
        *,
        reason: str,
        width: int,
        height: int,
        background: tuple[int, int, int] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "FALLBACK",
            "method": "FULL_IMAGE",
            "reason": reason,
            "image_width": width,
            "image_height": height,
            "background_rgb": (
                list(background)
                if background is not None
                else None
            ),
            "plot_left_pixel": 0,
            "plot_right_pixel": max(0, width - 1),
            "plot_left_normalized": 0.0,
            "plot_right_normalized": 1.0,
            "active_columns": 0,
            "active_column_ratio": 0.0,
            "confidence": 0.0,
        }

    @classmethod
    def analyze(
        cls,
        image: Image.Image,
    ) -> dict[str, Any]:
        canvas = image.convert("RGB")
        width, height = canvas.size

        if width < 64 or height < 64:
            return cls._fallback(
                reason="IMAGE_TOO_SMALL",
                width=width,
                height=height,
            )

        background = cls._background_color(canvas)
        minimum_foreground_pixels = max(
            2,
            round(height * 0.004),
        )
        active_columns: list[int] = []
        pixels = canvas.load()

        for x in range(width):
            foreground_pixels = 0

            for y in range(height):
                if cls._is_foreground(
                    pixels[x, y],
                    background,
                ):
                    foreground_pixels += 1

                    if (
                        foreground_pixels
                        >= minimum_foreground_pixels
                    ):
                        active_columns.append(x)
                        break

        if not active_columns:
            return cls._fallback(
                reason="NO_FOREGROUND_COLUMNS",
                width=width,
                height=height,
                background=background,
            )

        left = min(active_columns)
        right = max(active_columns)
        denominator = max(1, width - 1)
        left_margin_ratio = left / denominator
        right_margin_ratio = (
            denominator - right
        ) / denominator
        span_ratio = (
            right - left
        ) / denominator
        active_column_ratio = (
            len(active_columns) / width
        )

        valid_geometry = (
            cls.MINIMUM_SPAN_RATIO
            <= span_ratio
            <= cls.MAXIMUM_SPAN_RATIO
            and cls.MINIMUM_MARGIN_RATIO
            <= left_margin_ratio
            <= cls.MAXIMUM_MARGIN_RATIO
            and cls.MINIMUM_MARGIN_RATIO
            <= right_margin_ratio
            <= cls.MAXIMUM_MARGIN_RATIO
            and active_column_ratio
            >= cls.MINIMUM_ACTIVE_COLUMN_RATIO
        )

        if not valid_geometry:
            result = cls._fallback(
                reason="GEOMETRY_VALIDATION_FAILED",
                width=width,
                height=height,
                background=background,
            )
            result.update(
                {
                    "candidate_left_pixel": left,
                    "candidate_right_pixel": right,
                    "candidate_span_ratio": span_ratio,
                    "candidate_left_margin_ratio": (
                        left_margin_ratio
                    ),
                    "candidate_right_margin_ratio": (
                        right_margin_ratio
                    ),
                    "active_columns": len(active_columns),
                    "active_column_ratio": active_column_ratio,
                }
            )
            return result

        symmetry_score = max(
            0.0,
            1.0
            - abs(
                left_margin_ratio
                - right_margin_ratio
            )
            / max(
                left_margin_ratio
                + right_margin_ratio,
                0.01,
            ),
        )
        density_score = min(
            1.0,
            active_column_ratio / 0.30,
        )
        confidence = (
            symmetry_score * 0.60
            + density_score * 0.40
        )

        return {
            "status": "DETECTED",
            "method": "BACKGROUND_CONTRAST_BOUNDS",
            "reason": None,
            "image_width": width,
            "image_height": height,
            "background_rgb": list(background),
            "difference_threshold": cls.DIFFERENCE_THRESHOLD,
            "minimum_foreground_pixels_per_column": (
                minimum_foreground_pixels
            ),
            "plot_left_pixel": left,
            "plot_right_pixel": right,
            "plot_left_normalized": left / width,
            "plot_right_normalized": right / width,
            "plot_span_ratio": span_ratio,
            "left_margin_ratio": left_margin_ratio,
            "right_margin_ratio": right_margin_ratio,
            "active_columns": len(active_columns),
            "active_column_ratio": active_column_ratio,
            "confidence": confidence,
        }
