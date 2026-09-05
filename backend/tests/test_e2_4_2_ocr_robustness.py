from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from PIL import ImageDraw

from ai.scripts.benchmark_e2_4_price_axis_ocr import build_summary
from ai.scripts.benchmark_e2_4_price_axis_ocr import run
from ai.scripts.benchmark_e2_4_price_axis_ocr import selected_ocr_pass
from ai.scripts.benchmark_e2_4_price_axis_ocr import validate_contract
from ai.scripts.benchmark_e2_4_price_axis_ocr import validate_manifest
from ai.scripts.build_e2_4_external_ocr_fixture_pack import build_pack
from app.services.screenshot_price_axis_calibration_service import (
    OptionalTesseractPriceAxisOCRProvider,
)
from app.services.screenshot_price_axis_calibration_service import (
    ScreenshotPriceAxisCalibrationService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
E242_CONTRACT = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_4_2_ocr_robustness.json"
)
E242_DEVELOPMENT_RESULT = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_4_2_development_result.json"
)
E242_BENCHMARK_RUNNER = (
    PROJECT_ROOT / "ai" / "scripts" / "benchmark_e2_4_price_axis_ocr.py"
)
E242_CALIBRATION_SERVICE = (
    PROJECT_ROOT
    / "backend"
    / "app"
    / "services"
    / "screenshot_price_axis_calibration_service.py"
)


class _AdaptiveFakeProvider:
    def __init__(self, passes: list[dict[str, object]]) -> None:
        self.passes = passes

    def extract(self, image: Image.Image) -> dict[str, object]:
        return {
            "status": "OCR_COMPLETE",
            "engine": "FAKE_ADAPTIVE_OCR",
            "preprocessing_profile": (
                "ADAPTIVE_WIDE_FOOTER2_TIGHT_GRAY3"
            ),
            "tesseract_version": "5.5.3",
            "observations": self.passes[0]["observations"],
            "passes": self.passes,
        }


class E242OCRRobustnessTest(unittest.TestCase):
    @staticmethod
    def _observation(
        text: str,
        y_center: float,
        *,
        confidence: float = 95.0,
    ) -> dict[str, object]:
        return {
            "text": text,
            "confidence": confidence,
            "left": 230.0,
            "top": y_center - 5.0,
            "width": 45.0,
            "height": 10.0,
        }

    @classmethod
    def _pass(
        cls,
        pass_id: str,
        observations: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "pass_id": pass_id,
            "status": "OCR_COMPLETE",
            "preprocessing_profile": pass_id,
            "ocr_input_region": (
                [0, 0, 280, 500]
                if pass_id == "WIDE_FOOTER_TRIM_GRAY2"
                else [220, 0, 280, 500]
            ),
            "observations": observations,
            "rejected_observations": [],
            "filled_background_rejection_count": 0,
        }

    def test_repository_contract_is_frozen_after_windows_verification(
        self,
    ) -> None:
        contract = json.loads(E242_CONTRACT.read_text(encoding="utf-8"))

        self.assertEqual(validate_contract(contract), [])
        self.assertEqual(
            contract["status"],
            "IMPLEMENTATION_FROZEN_AWAITING_HOLDOUT",
        )
        implementation_freeze = contract["implementation_freeze"]
        self.assertEqual(
            implementation_freeze["freeze_id"],
            "E2_4_2_FREEZE_20260905_01",
        )
        self.assertEqual(
            implementation_freeze["source_commit"],
            "32cd3015f694ae9fc36bd545d160f6b6c5c1a1fd",
        )
        self.assertEqual(
            implementation_freeze[
                "windows_development_result_zip_sha256"
            ],
            (
                "07d99c4d83d1a36ec12cb1c92c44caa"
                "5f1f17896a42a20f3c03964efd27e9713"
            ),
        )
        source_paths = {
            "calibration_service": (
                E242_CALIBRATION_SERVICE,
                "calibration_service_source_sha256",
            ),
            "benchmark_runner": (
                E242_BENCHMARK_RUNNER,
                "benchmark_runner_source_sha256",
            ),
        }
        for source_id, (source_path, runtime_hash_key) in (
            source_paths.items()
        ):
            canonical_bytes = source_path.read_bytes().replace(
                b"\r\n",
                b"\n",
            )
            self.assertEqual(
                hashlib.sha256(canonical_bytes).hexdigest(),
                implementation_freeze["canonical_lf_source_sha256"][
                    source_id
                ],
            )
            windows_bytes = canonical_bytes.replace(b"\n", b"\r\n")
            self.assertEqual(
                hashlib.sha256(windows_bytes).hexdigest(),
                implementation_freeze[runtime_hash_key],
            )
        self.assertEqual(
            contract["evidence_roles"]["reused_e2_4_1_fixtures"],
            "DEVELOPMENT_REGRESSION_ONLY",
        )
        self.assertFalse(
            contract["evidence_roles"][
                "development_metrics_may_pass_freeze"
            ]
        )
        self.assertTrue(
            contract["evidence_roles"]["fresh_external_holdout_required"]
        )
        self.assertFalse(
            contract["output_contract"]["production_promotion_possible"]
        )
        development_result = json.loads(
            E242_DEVELOPMENT_RESULT.read_text(encoding="utf-8")
        )
        self.assertTrue(development_result["implementation_frozen"])
        self.assertFalse(
            development_result["windows_development_verification_pending"]
        )
        self.assertFalse(development_result["freeze_evaluated"])
        self.assertFalse(development_result["benchmark_pass"])
        self.assertIsNone(development_result["selected_production_profile"])
        profile = contract["ocr_engine"]["profiles"][0]
        self.assertAlmostEqual(
            profile["tight_pass"][
                "outer_axis_region_relative_start_ratio"
            ],
            OptionalTesseractPriceAxisOCRProvider
            .ADAPTIVE_TIGHT_INPUT_START_RATIO,
        )
        rejection = profile["filled_background_rejection"]
        self.assertEqual(
            rejection["minimum_rgb_mode_distance"],
            OptionalTesseractPriceAxisOCRProvider
            .FILLED_BACKGROUND_MINIMUM_RGB_DISTANCE,
        )
        self.assertEqual(
            rejection["minimum_local_mode_coverage"],
            OptionalTesseractPriceAxisOCRProvider
            .FILLED_BACKGROUND_MINIMUM_MODE_COVERAGE,
        )
        self.assertEqual(
            rejection["observation_padding_pixels"],
            OptionalTesseractPriceAxisOCRProvider
            .FILLED_BACKGROUND_OBSERVATION_PADDING,
        )

    def test_external_builder_requires_freeze_before_e2_4_2_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image_path = root / "holdout.png"
            Image.new("RGB", (1000, 500), color="white").save(image_path)
            annotations = {
                "schema_version": 1,
                "experiment_id": "E2.4.2",
                "fixture_set_id": "UNIT_TEST_E242_HOLDOUT",
                "trading_outcome_data_used": False,
                "fixtures": [
                    {
                        "fixture_id": "E242_HOLDOUT_001",
                        "source_image_path": str(image_path),
                        "pair": "GBPUSD",
                        "timeframe": "M5",
                        "platform": "TRADINGVIEW",
                        "theme": "LIGHT",
                        "locale": "DOT_DECIMAL",
                        "scale_mode": "LINEAR",
                        "variant": "VALID",
                        "expected_status": "CALIBRATED",
                        "expected_reason_codes": [],
                        "expected_axis_region": [720, 0, 1000, 500],
                        "expected_plot_right_pixel": 718,
                        "ground_truth_ticks": [
                            {
                                "text": "1.28000",
                                "price": 1.28,
                                "y_center": 100.0,
                            },
                            {
                                "text": "1.27000",
                                "price": 1.27,
                                "y_center": 250.0,
                            },
                            {
                                "text": "1.26000",
                                "price": 1.26,
                                "y_center": 400.0,
                            },
                        ],
                        "tick_metric_eligible": True,
                    }
                ],
            }
            annotations_path = root / "annotations.json"
            annotations_path.write_text(
                json.dumps(annotations),
                encoding="utf-8",
            )

            contract = json.loads(E242_CONTRACT.read_text(encoding="utf-8"))
            development_contract = dict(contract)
            development_contract[
                "status"
            ] = "PREREGISTERED_DEVELOPMENT_REMEDIATION"
            development_contract.pop("implementation_freeze")
            development_contract_path = root / "development_contract.json"
            development_contract_path.write_text(
                json.dumps(development_contract),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "sebelum implementation freeze",
            ):
                build_pack(
                    annotations_path=annotations_path,
                    output_dir=root / "pack",
                    contract_path=development_contract_path,
                )

            freeze_id = contract["implementation_freeze"]["freeze_id"]
            annotations.update(
                {
                    "evidence_role": "FRESH_EXTERNAL_HOLDOUT",
                    "captured_after_implementation_freeze": True,
                    "capture_started_at_utc": (
                        "2026-09-06T00:00:00+00:00"
                    ),
                    "implementation_freeze_id": freeze_id,
                }
            )
            annotations_path.write_text(
                json.dumps(annotations),
                encoding="utf-8",
            )

            manifest_path = build_pack(
                annotations_path=annotations_path,
                output_dir=root / "pack",
                contract_path=E242_CONTRACT,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(
                manifest_path.name,
                "e2_4_2_fixture_manifest.json",
            )
            self.assertEqual(manifest["experiment_id"], "E2.4.2")
            self.assertEqual(
                manifest["evidence_role"],
                "FRESH_EXTERNAL_HOLDOUT",
            )
            self.assertEqual(
                manifest["implementation_freeze_id"],
                freeze_id,
            )
            self.assertEqual(
                validate_manifest(manifest, contract, manifest_path),
                [],
            )
            mismatched_contract = json.loads(
                E242_CONTRACT.read_text(encoding="utf-8")
            )
            mismatched_contract["implementation_freeze"][
                "calibration_service_source_sha256"
            ] = "0" * 64
            mismatched_contract_path = root / "mismatched_contract.json"
            mismatched_contract_path.write_text(
                json.dumps(mismatched_contract),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "Frozen source SHA berubah",
            ):
                run(
                    SimpleNamespace(
                        contract=mismatched_contract_path,
                        fixture_manifest=manifest_path,
                        output_dir=root / "benchmark",
                        profile_ids=None,
                        tesseract_cmd=None,
                        limit=0,
                        resume=False,
                        fail_fast=True,
                        progress_every=10,
                    )
                )

    def test_filled_background_rejection_removes_price_badge_only(
        self,
    ) -> None:
        source = Image.new("RGB", (280, 120), color=(0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.rectangle((220, 65, 279, 85), fill=(119, 136, 153))
        observations = [
            self._observation("1.28000", 25.0),
            self._observation("1.27555", 75.0),
        ]

        accepted, rejected = (
            OptionalTesseractPriceAxisOCRProvider
            ._reject_filled_background_observations(
                source,
                observations,
            )
        )

        self.assertEqual(
            [observation["text"] for observation in accepted],
            ["1.28000"],
        )
        self.assertEqual(
            [observation["text"] for observation in rejected],
            ["1.27555"],
        )
        self.assertEqual(
            rejected[0]["rejection_reason"],
            "FILLED_BACKGROUND",
        )

    def test_adaptive_service_selects_calibrated_tight_pass(self) -> None:
        wide = self._pass(
            "WIDE_FOOTER_TRIM_GRAY2",
            [
                self._observation("71.28000", 100.0),
                self._observation("71.27000", 250.0),
                self._observation("71.26000", 400.0),
            ],
        )
        tight = self._pass(
            "TIGHT_GRAY3",
            [
                self._observation("1.28000", 100.0),
                self._observation("1.27000", 250.0),
                self._observation("1.26000", 400.0),
            ],
        )
        service = ScreenshotPriceAxisCalibrationService(
            _AdaptiveFakeProvider([wide, tight])
        )

        result = service.calibrate(
            Image.new("RGB", (1000, 500), color="black"),
            pair="GBPUSD",
        )

        self.assertEqual(result["status"], "CALIBRATED")
        self.assertEqual(result["ocr_selected_pass_id"], "TIGHT_GRAY3")
        self.assertEqual(result["ocr_pass_count"], 2)
        self.assertEqual(result["axis_region"], [940, 0, 1000, 500])
        self.assertFalse(result["entry_price_authorized"])
        self.assertFalse(result["production_decision_changed"])

        selected = selected_ocr_pass(
            _AdaptiveFakeProvider([wide, tight]).extract(
                Image.new("RGB", (280, 500))
            ),
            result,
        )
        self.assertEqual(selected["pass_id"], "TIGHT_GRAY3")
        self.assertEqual(len(selected["observations"]), 3)

    def test_percent_evidence_in_any_pass_preempts_calibration(self) -> None:
        wide = self._pass(
            "WIDE_FOOTER_TRIM_GRAY2",
            [
                self._observation("1.28000", 100.0),
                self._observation("1.27000", 250.0),
                self._observation("1.26000", 400.0),
            ],
        )
        tight = self._pass(
            "TIGHT_GRAY3",
            [
                self._observation("+2.0%", 100.0),
                self._observation("+1.0%", 250.0),
                self._observation("0.0%", 400.0),
            ],
        )
        service = ScreenshotPriceAxisCalibrationService(
            _AdaptiveFakeProvider([wide, tight])
        )

        result = service.calibrate(
            Image.new("RGB", (1000, 500), color="black"),
            pair="GBPUSD",
            declared_scale_mode="LINEAR",
        )

        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["reason_code"], "PERCENT_PRICE_AXIS_DETECTED")
        self.assertEqual(result["ocr_selected_pass_id"], "TIGHT_GRAY3")
        self.assertFalse(result["entry_price_authorized"])

    def test_development_target_pass_cannot_be_reported_as_freeze_pass(
        self,
    ) -> None:
        contract = json.loads(E242_CONTRACT.read_text(encoding="utf-8"))
        pairs = ["GBPUSD", "XAUUSD"]
        platforms = ["TRADINGVIEW", "MT5"]
        themes = ["LIGHT", "DARK", "CUSTOM"]
        timeframes = ["M5", "M15", "H1", "H4"]
        locales = ["DOT_DECIMAL", "COMMA_DECIMAL"]
        rows: list[dict[str, object]] = []
        for index in range(32):
            fail_closed = index % 4 == 0
            rows.append(
                {
                    "request_status": "SUCCESS",
                    "fixture_id": f"FIXTURE_{index:03d}",
                    "fixture_source": "EXTERNAL_REVIEWED",
                    "external_reviewed": 1,
                    "pair": pairs[index % len(pairs)],
                    "platform": platforms[(index // 2) % len(platforms)],
                    "theme": themes[index % len(themes)],
                    "timeframe": timeframes[index % len(timeframes)],
                    "locale": locales[index % len(locales)],
                    "tick_metric_eligible": 0 if fail_closed else 1,
                    "tick_true_positive": 0 if fail_closed else 3,
                    "tick_false_positive": 0,
                    "tick_false_negative": 0,
                    "exact_text_match_count": 0 if fail_closed else 3,
                    "axis_region_contains_expected": 1,
                    "expected_status": (
                        "FAIL_CLOSED" if fail_closed else "CALIBRATED"
                    ),
                    "expected_status_match": 1,
                    "fail_closed_correct": 1 if fail_closed else 0,
                    "false_calibration": 0,
                    "mapping_point_count": 0 if fail_closed else 3,
                    "mapping_absolute_error_sum": 0.0,
                    "mapping_normalized_absolute_error_sum": 0.0,
                    "mapping_pixel_absolute_error_sum": 0.0,
                    "entry_price_authorized": 0,
                    "production_decision_changed": 0,
                    "telemetry_boundary_valid": 1,
                    "tesseract_version": "5.5.3",
                    "latency_ms": 1.0,
                    "profile_id": (
                        "ADAPTIVE_WIDE_FOOTER2_TIGHT_GRAY3_PSM11"
                    ),
                    "calibration_status": (
                        "FAIL_CLOSED" if fail_closed else "CALIBRATED"
                    ),
                    "calibration_reason_code": (
                        "TEST_NEGATIVE" if fail_closed else None
                    ),
                }
            )

        summary = build_summary(
            rows,
            contract,
            "UNIT_TEST_DEVELOPMENT",
            {"experiment_id": "E2.4.2"},
            evidence_role="DEVELOPMENT_REGRESSION_ONLY",
        )

        self.assertTrue(summary["technical_gate_pass"])
        self.assertFalse(summary["freeze_evaluated"])
        self.assertFalse(summary["benchmark_pass"])
        self.assertFalse(summary["production_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
