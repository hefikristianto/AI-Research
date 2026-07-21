from __future__ import annotations

import unittest

from app.services.ob_fvg_pairing_service import (
    OBFVGPairingService,
)


class OBFVGPairingServiceTest(unittest.TestCase):
    @staticmethod
    def _detection(
        detection_id: int,
        class_name: str,
        x: float,
        y: float,
    ) -> dict[str, object]:
        return {
            "detection_id": detection_id,
            "class_name": class_name,
            "confidence": 0.80,
            "bbox_normalized": {
                "x": x,
                "y": y,
                "width": 0.05,
                "height": 0.05,
            },
        }

    def test_reports_each_pairing_rejection_reason(self) -> None:
        service = OBFVGPairingService(
            max_x_distance=0.12,
            max_y_distance=0.20,
        )
        result = service.pair(
            [
                self._detection(1, "order_block", 0.50, 0.50),
                self._detection(2, "fair_value_gap", 0.55, 0.40),
                self._detection(3, "fair_value_gap", 0.80, 0.45),
                self._detection(4, "fair_value_gap", 0.55, 0.80),
                self._detection(5, "fair_value_gap", 0.80, 0.80),
            ]
        )

        self.assertEqual(result["evaluated_combinations"], 4)
        self.assertEqual(result["candidate_combinations"], 1)
        self.assertEqual(result["rejected_combinations"], 3)
        self.assertEqual(result["total_pairs"], 1)
        self.assertEqual(
            result["rejection_counts"],
            {
                "X_DISTANCE_EXCEEDS_MAX": 2,
                "Y_DISTANCE_EXCEEDS_MAX": 2,
            },
        )
        self.assertFalse(result["rejection_details_truncated"])
        self.assertEqual(len(result["rejections"]), 3)


if __name__ == "__main__":
    unittest.main()
