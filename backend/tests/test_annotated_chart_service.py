from __future__ import annotations

import base64
import unittest
from io import BytesIO

from PIL import Image

from app.services.annotated_chart_service import (
    AnnotatedChartService,
)


class AnnotatedChartServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.image = Image.new(
            "RGB",
            (120, 80),
            color=(255, 255, 255),
        )

    @staticmethod
    def _decode_data_url(data_url: str) -> Image.Image:
        _, encoded = data_url.split(",", maxsplit=1)
        return Image.open(
            BytesIO(base64.b64decode(encoded))
        )

    def test_renders_box_and_decision_banner(
        self,
    ) -> None:
        result = AnnotatedChartService.render(
            image=self.image,
            detections=[
                {
                    "class_name": "order_block",
                    "confidence": 0.82,
                    "bbox_pixel": {
                        "x1": 10,
                        "y1": 20,
                        "x2": 60,
                        "y2": 55,
                    },
                }
            ],
            decision="WATCHLIST",
            execution_status="REVIEW",
        )

        self.assertEqual(result["status"], "RENDERED")
        self.assertEqual(result["rendered_detections"], 1)
        self.assertTrue(
            result["data_url"].startswith(
                "data:image/png;base64,"
            )
        )
        rendered = self._decode_data_url(
            result["data_url"]
        )
        self.assertEqual(rendered.size, self.image.size)
        self.assertNotEqual(
            rendered.convert("RGB").getpixel((10, 20)),
            (255, 255, 255),
        )

    def test_skips_malformed_detection(self) -> None:
        result = AnnotatedChartService.render(
            image=self.image,
            detections=[
                None,
                {
                    "class_name": "fair_value_gap",
                    "bbox_pixel": {"x1": "invalid"},
                },
            ],
        )

        self.assertEqual(result["rendered_detections"], 0)
