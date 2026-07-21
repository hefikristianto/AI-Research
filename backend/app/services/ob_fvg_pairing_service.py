from __future__ import annotations

from math import hypot
from typing import Any


class OBFVGPairingService:
    MAX_REJECTION_DETAILS = 50

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
        rejected_combinations = 0
        rejection_counts = {
            "X_DISTANCE_EXCEEDS_MAX": 0,
            "Y_DISTANCE_EXCEEDS_MAX": 0,
        }
        rejections: list[dict[str, Any]] = []

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

                rejection_reasons: list[str] = []

                if (
                    x_distance
                    > self.max_x_distance
                ):
                    rejection_reasons.append(
                        "X_DISTANCE_EXCEEDS_MAX"
                    )

                if (
                    y_distance
                    > self.max_y_distance
                ):
                    rejection_reasons.append(
                        "Y_DISTANCE_EXCEEDS_MAX"
                    )

                if rejection_reasons:
                    rejected_combinations += 1

                    for reason in rejection_reasons:
                        rejection_counts[reason] += 1

                    if (
                        len(rejections)
                        < self.MAX_REJECTION_DETAILS
                    ):
                        rejections.append(
                            {
                                "ob_detection_id": ob.get(
                                    "detection_id"
                                ),
                                "fvg_detection_id": fvg.get(
                                    "detection_id"
                                ),
                                "x_distance": x_distance,
                                "y_distance": y_distance,
                                "reasons": rejection_reasons,
                            }
                        )

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
            "evaluated_combinations": (
                len(order_blocks)
                * len(fair_value_gaps)
            ),
            "rejected_combinations": (
                rejected_combinations
            ),
            "rejection_counts": (
                rejection_counts
            ),
            "rejections": rejections,
            "rejection_details_truncated": (
                rejected_combinations
                > len(rejections)
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
