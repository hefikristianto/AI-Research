from __future__ import annotations

import unittest

from PIL import Image
from PIL import ImageDraw

from app.services.chart_plot_geometry_service import (
    ChartPlotGeometryService,
)


class ChartPlotGeometryServiceTest(unittest.TestCase):
    @staticmethod
    def _chart(
        background: tuple[int, int, int],
        foreground: tuple[int, int, int],
    ) -> Image.Image:
        image = Image.new(
            "RGB",
            (200, 100),
            color=background,
        )
        draw = ImageDraw.Draw(image)

        for x in range(20, 181, 2):
            top = 25 + (x % 17)
            bottom = 75 - (x % 13)
            draw.line(
                (x, top, x, bottom),
                fill=foreground,
                width=2,
            )

        return image

    def test_detects_same_plot_bounds_across_themes(self) -> None:
        for background, foreground in (
            ((255, 255, 255), (15, 118, 90)),
            ((5, 5, 5), (240, 240, 240)),
        ):
            with self.subTest(background=background):
                result = ChartPlotGeometryService.analyze(
                    self._chart(background, foreground)
                )

                self.assertEqual(result["status"], "DETECTED")
                self.assertEqual(result["plot_left_pixel"], 20)
                self.assertIn(
                    result["plot_right_pixel"],
                    {180, 181},
                )
                self.assertAlmostEqual(
                    result["plot_left_normalized"],
                    0.10,
                )
                self.assertGreater(result["confidence"], 0.50)

    def test_falls_back_when_foreground_touches_image_edges(self) -> None:
        image = Image.new(
            "RGB",
            (200, 100),
            color=(255, 255, 255),
        )
        ImageDraw.Draw(image).rectangle(
            (0, 30, 199, 70),
            fill=(0, 0, 0),
        )

        result = ChartPlotGeometryService.analyze(image)

        self.assertEqual(result["status"], "FALLBACK")
        self.assertEqual(result["method"], "FULL_IMAGE")
        self.assertEqual(
            result["reason"],
            "GEOMETRY_VALIDATION_FAILED",
        )


if __name__ == "__main__":
    unittest.main()
