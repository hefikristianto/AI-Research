from __future__ import annotations

import sys
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from unittest.mock import patch

from PIL import Image


ultralytics_stub = types.ModuleType("ultralytics")
ultralytics_stub.YOLO = object

with patch.dict(
    sys.modules,
    {"ultralytics": ultralytics_stub},
):
    from app.services.yolo_detection_service import (  # noqa: E402
        YOLODetectionService,
    )


class RecordingModel:
    def __init__(self) -> None:
        self.confidence_thresholds: list[float] = []
        self.active_calls = 0
        self.maximum_active_calls = 0
        self._state_lock = Lock()

    def predict(self, **kwargs):
        with self._state_lock:
            self.active_calls += 1
            self.maximum_active_calls = max(
                self.maximum_active_calls,
                self.active_calls,
            )

        time.sleep(0.01)

        with self._state_lock:
            self.confidence_thresholds.append(
                kwargs["conf"]
            )
            self.active_calls -= 1

        return []


class YOLODetectionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = YOLODetectionService(
            confidence_threshold=0.05,
            image_size=640,
        )
        self.model = RecordingModel()
        self.service._model = self.model

    def test_request_override_does_not_mutate_default(self) -> None:
        result = self.service.predict(
            Image.new("RGB", (8, 8)),
            confidence_threshold=0.25,
        )

        self.assertEqual(
            result["confidence_threshold"],
            0.25,
        )
        self.assertEqual(
            self.service.confidence_threshold,
            0.05,
        )
        self.assertEqual(
            self.model.confidence_thresholds,
            [0.25],
        )

    def test_concurrent_overrides_remain_isolated(self) -> None:
        thresholds = [
            0.11,
            0.22,
            0.33,
            0.44,
            0.55,
            0.66,
            0.77,
            0.88,
        ]

        def run_prediction(threshold: float) -> float:
            result = self.service.predict(
                Image.new("RGB", (8, 8)),
                confidence_threshold=threshold,
            )
            return result["confidence_threshold"]

        with ThreadPoolExecutor(
            max_workers=len(thresholds)
        ) as executor:
            observed_thresholds = list(
                executor.map(
                    run_prediction,
                    thresholds,
                )
            )

        self.assertEqual(
            observed_thresholds,
            thresholds,
        )
        self.assertCountEqual(
            self.model.confidence_thresholds,
            thresholds,
        )
        self.assertEqual(
            self.model.maximum_active_calls,
            1,
        )
        self.assertEqual(
            self.service.confidence_threshold,
            0.05,
        )


if __name__ == "__main__":
    unittest.main()
