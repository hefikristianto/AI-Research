from __future__ import annotations

from math import hypot
from typing import Any


class OBFVGPairingService:
    def __init__(
        self,
        max_x_distance: float = 0.12,
        max_y_distance: float = 0.20,
    ) -> None:
        self.max_x_distance = max_x_distance
        self.max_y_distance = max_y_distance

    @staticmethod
    def _normalized_box(
        detection: dict[str, Any],
    ) -> dict[str, float]:
        box = detection.get(
            "bbox_normalized",
            {},
        )

        return {
            "x": float(box.get("x", 0.0)),
            "y": float(box.get("y", 0.0)),
            "width": float(
                box.get("width", 0.0)
            ),
            "height": float(
                box.get("height", 0.0)
            ),
        }

    @staticmethod
    def _infer_direction(
        ob_box: dict[str, float],
        fvg_box: dict[str, float],
    ) -> str:
        # Koordinat y gambar meningkat ke bawah.
        # FVG di atas OB diasumsikan bullish.
        # FVG di bawah OB diasumsikan bearish.
        if fvg_box["y"] < ob_box["y"]:
            return "bullish_candidate"

        return "bearish_candidate"

    def pair(
        self,
        detections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        order_blocks = [
            detection
            for detection in detections
            if detection.get("class_name")
            == "order_block"
        ]

        fair_value_gaps = [
            detection
            for detection in detections
            if detection.get("class_name")
            == "fair_value_gap"
        ]

        candidates: list[
            dict[str, Any]
        ] = []

        for ob in order_blocks:
            ob_box = self._normalized_box(ob)

            for fvg in fair_value_gaps:
                fvg_box = self._normalized_box(
                    fvg
                )

                x_distance = abs(
                    ob_box["x"]
                    - fvg_box["x"]
                )

                y_distance = abs(
                    ob_box["y"]
                    - fvg_box["y"]
                )

                if (
                    x_distance
                    > self.max_x_distance
                ):
                    continue

                if (
                    y_distance
                    > self.max_y_distance
                ):
                    continue

                spatial_distance = hypot(
                    x_distance,
                    y_distance,
                )

                confidence_average = (
                    float(
                        ob.get(
                            "confidence",
                            0.0,
                        )
                    )
                    + float(
                        fvg.get(
                            "confidence",
                            0.0,
                        )
                    )
                ) / 2.0

                spatial_score = max(
                    0.0,
                    1.0
                    - (
                        x_distance
                        / self.max_x_distance
                        * 0.60
                    )
                    - (
                        y_distance
                        / self.max_y_distance
                        * 0.40
                    ),
                )

                preliminary_score = (
                    confidence_average
                    * 0.45
                    + spatial_score
                    * 0.55
                )

                candidates.append(
                    {
                        "ob_detection_id": (
                            ob.get(
                                "detection_id"
                            )
                        ),
                        "fvg_detection_id": (
                            fvg.get(
                                "detection_id"
                            )
                        ),
                        "direction": (
                            self._infer_direction(
                                ob_box,
                                fvg_box,
                            )
                        ),
                        "ob_confidence": float(
                            ob.get(
                                "confidence",
                                0.0,
                            )
                        ),
                        "fvg_confidence": float(
                            fvg.get(
                                "confidence",
                                0.0,
                            )
                        ),
                        "average_confidence": (
                            confidence_average
                        ),
                        "x_distance": (
                            x_distance
                        ),
                        "y_distance": (
                            y_distance
                        ),
                        "spatial_distance": (
                            spatial_distance
                        ),
                        "spatial_score": (
                            spatial_score
                        ),
                        "preliminary_score": (
                            preliminary_score
                        ),
                        "ob_bbox": ob_box,
                        "fvg_bbox": fvg_box,
                    }
                )

        candidates.sort(
            key=lambda item: item[
                "preliminary_score"
            ],
            reverse=True,
        )

        used_ob: set[int] = set()
        used_fvg: set[int] = set()

        selected_pairs: list[
            dict[str, Any]
        ] = []

        for candidate in candidates:
            ob_id = candidate[
                "ob_detection_id"
            ]

            fvg_id = candidate[
                "fvg_detection_id"
            ]

            if ob_id in used_ob:
                continue

            if fvg_id in used_fvg:
                continue

            used_ob.add(ob_id)
            used_fvg.add(fvg_id)

            candidate["pair_id"] = len(
                selected_pairs
            )

            selected_pairs.append(
                candidate
            )

        return {
            "total_order_blocks": len(
                order_blocks
            ),
            "total_fair_value_gaps": len(
                fair_value_gaps
            ),
            "candidate_combinations": len(
                candidates
            ),
            "total_pairs": len(
                selected_pairs
            ),
            "pairs": selected_pairs,
            "pairing_status": (
                "PAIRS_FOUND"
                if selected_pairs
                else "NO_VALID_PAIR"
            ),
            "max_x_distance": (
                self.max_x_distance
            ),
            "max_y_distance": (
                self.max_y_distance
            ),
        }
