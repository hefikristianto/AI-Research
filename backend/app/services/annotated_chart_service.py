from __future__ import annotations

import base64
import hashlib
from io import BytesIO
from typing import Any

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


class AnnotatedChartService:
    COLORS = {
        "order_block": (14, 165, 233),
        "fair_value_gap": (168, 85, 247),
    }
    DEFAULT_COLOR = (245, 158, 11)
    DECISION_COLORS = {
        "BUY": (16, 185, 129),
        "SELL": (239, 68, 68),
        "WATCHLIST": (245, 158, 11),
        "NO_TRADE": (82, 82, 91),
    }

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(minimum, min(value, maximum))

    @classmethod
    def _box_coordinates(
        cls,
        detection: dict[str, Any],
        width: int,
        height: int,
    ) -> tuple[float, float, float, float] | None:
        bbox = detection.get("bbox_pixel")

        if not isinstance(bbox, dict):
            return None

        try:
            x1 = float(bbox["x1"])
            y1 = float(bbox["y1"])
            x2 = float(bbox["x2"])
            y2 = float(bbox["y2"])
        except (KeyError, TypeError, ValueError):
            return None

        x1 = cls._clamp(x1, 0.0, float(width - 1))
        y1 = cls._clamp(y1, 0.0, float(height - 1))
        x2 = cls._clamp(x2, 0.0, float(width - 1))
        y2 = cls._clamp(y2, 0.0, float(height - 1))

        if x2 <= x1 or y2 <= y1:
            return None

        return x1, y1, x2, y2

    @staticmethod
    def _label_text(
        detection: dict[str, Any],
    ) -> str:
        class_name = str(
            detection.get("class_name", "zone")
        )
        display_name = class_name.replace(
            "_",
            " ",
        ).upper()

        try:
            confidence = float(
                detection.get("confidence", 0.0)
            )
        except (TypeError, ValueError):
            confidence = 0.0

        return f"{display_name} {confidence:.0%}"

    @staticmethod
    def _label_x(
        x1: float,
        text_width: int,
        canvas_width: int,
    ) -> float:
        maximum = max(
            0.0,
            float(
                canvas_width
                - text_width
                - 9
            ),
        )
        return max(
            0.0,
            min(x1, maximum),
        )

    @classmethod
    def render(
        cls,
        image: Image.Image,
        detections: list[Any],
        decision: str | None = None,
        execution_status: str | None = None,
    ) -> dict[str, Any]:
        canvas = image.convert("RGB").copy()
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()
        stroke_width = max(
            2,
            min(canvas.size) // 240,
        )
        rendered_detections = 0

        for detection in detections:
            if not isinstance(detection, dict):
                continue

            coordinates = cls._box_coordinates(
                detection,
                width=canvas.width,
                height=canvas.height,
            )

            if coordinates is None:
                continue

            class_name = str(
                detection.get("class_name", "")
            )
            color = cls.COLORS.get(
                class_name,
                cls.DEFAULT_COLOR,
            )
            draw.rectangle(
                coordinates,
                outline=color,
                width=stroke_width,
            )

            label = cls._label_text(detection)
            text_bounds = draw.textbbox(
                (0, 0),
                label,
                font=font,
            )
            text_width = text_bounds[2] - text_bounds[0]
            text_height = text_bounds[3] - text_bounds[1]
            x1, y1, _, _ = coordinates
            label_x = cls._label_x(
                x1=x1,
                text_width=text_width,
                canvas_width=canvas.width,
            )
            label_y = max(0.0, y1 - text_height - 6)

            draw.rectangle(
                (
                    label_x,
                    label_y,
                    min(
                        float(canvas.width - 1),
                        label_x + text_width + 8,
                    ),
                    label_y + text_height + 6,
                ),
                fill=color,
            )
            draw.text(
                (label_x + 4, label_y + 3),
                label,
                fill=(255, 255, 255),
                font=font,
            )
            rendered_detections += 1

        if decision:
            normalized_decision = str(decision).upper()
            banner_text = normalized_decision

            if execution_status:
                banner_text += (
                    " | "
                    + str(execution_status).replace(
                        "_",
                        " ",
                    )
                )

            banner_color = cls.DECISION_COLORS.get(
                normalized_decision,
                cls.DEFAULT_COLOR,
            )
            text_bounds = draw.textbbox(
                (0, 0),
                banner_text,
                font=font,
            )
            banner_width = min(
                canvas.width,
                text_bounds[2] - text_bounds[0] + 20,
            )
            banner_height = (
                text_bounds[3] - text_bounds[1] + 12
            )
            draw.rectangle(
                (0, 0, banner_width, banner_height),
                fill=banner_color,
            )
            draw.text(
                (10, 6),
                banner_text,
                fill=(255, 255, 255),
                font=font,
            )

        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
        encoded = base64.b64encode(
            image_bytes
        ).decode("ascii")

        return {
            "status": "RENDERED",
            "media_type": "image/png",
            "encoding": "base64_data_url",
            "data_url": (
                "data:image/png;base64," + encoded
            ),
            "sha256": hashlib.sha256(
                image_bytes
            ).hexdigest(),
            "width": canvas.width,
            "height": canvas.height,
            "rendered_detections": rendered_detections,
        }
