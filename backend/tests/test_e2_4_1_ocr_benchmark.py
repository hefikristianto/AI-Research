from __future__ import annotations

import codecs
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from ai.scripts.benchmark_e2_4_price_axis_ocr import (
    DEFAULT_CONTRACT,
    match_ticks,
    run,
    validate_contract,
    validate_manifest,
)
from ai.scripts.build_e2_4_external_ocr_fixture_pack import (
    build_pack,
)
from ai.scripts.generate_e2_4_synthetic_ocr_fixtures import (
    run as generate_fixtures,
)


class _FakePriceAxisProvider:
    def extract(self, image: Image.Image) -> dict[str, object]:
        return {
            "status": "OCR_COMPLETE",
            "engine": "FAKE_TEST_OCR",
            "preprocessing_profile": "RAW_RGB",
            "tesseract_version": "5.5.0",
            "observations": [
                {
                    "text": text,
                    "confidence": 99.0,
                    "left": 10.0,
                    "top": y_center - 10.0,
                    "width": 90.0,
                    "height": 20.0,
                }
                for text, y_center in (
                    ("1.28000", 100.0),
                    ("1.27000", 250.0),
                    ("1.26000", 400.0),
                )
            ],
        }


class E241OCRBenchmarkTest(unittest.TestCase):
    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _args(
        fixture_manifest: Path,
        output_dir: Path,
        *,
        resume: bool = False,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            contract=DEFAULT_CONTRACT,
            fixture_manifest=fixture_manifest,
            output_dir=output_dir,
            profile_ids=["RAW_RGB_PSM11"],
            tesseract_cmd=None,
            limit=0,
            resume=resume,
            fail_fast=True,
            progress_every=100,
        )

    def _write_external_fixture(self, root: Path) -> Path:
        image_path = root / "images" / "external.png"
        image_path.parent.mkdir(parents=True)
        image = Image.new("RGB", (1000, 500), color="white")
        image.save(image_path)
        fixture = {
            "fixture_id": "EXT_GBPUSD_TRADINGVIEW_LIGHT_M5_001",
            "fixture_source": "EXTERNAL_REVIEWED",
            "external_reviewed": True,
            "image_path": "images/external.png",
            "image_sha256": self._sha256(image_path),
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
                {"text": "1.28000", "price": 1.28, "y_center": 100.0},
                {"text": "1.27000", "price": 1.27, "y_center": 250.0},
                {"text": "1.26000", "price": 1.26, "y_center": 400.0},
            ],
            "tick_metric_eligible": True,
            "outcome_data_used": False,
        }
        manifest = {
            "schema_version": 1,
            "experiment_id": "E2.4.1",
            "fixture_set_id": "UNIT_TEST_EXTERNAL_V1",
            "trading_outcome_data_used": False,
            "production_decision_changed": False,
            "fixtures": [fixture],
        }
        manifest_path = root / "fixture_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return manifest_path

    def test_repository_contract_preserves_locked_boundaries(self) -> None:
        contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(validate_contract(contract), [])
        self.assertFalse(contract["training_performed"])
        self.assertFalse(contract["model_inference_performed"])
        self.assertFalse(contract["production_decision_changed"])
        self.assertFalse(any(contract["holdout_access"].values()))
        self.assertFalse(
            contract["output_contract"]["production_promotion_possible"]
        )
        profiles = {
            profile["profile_id"]: profile
            for profile in contract["ocr_engine"]["profiles"]
        }
        self.assertEqual(len(profiles), 4)
        self.assertEqual(
            profiles[
                "GRAY_FOOTER_TRIM_AUTOCONTRAST_2X_PSM11"
            ]["preprocessing_profile"],
            "GRAYSCALE_FOOTER_TRIM_AUTOCONTRAST_2X",
        )
        self.assertTrue(
            profiles[
                "GRAY_FOOTER_TRIM_AUTOCONTRAST_2X_PSM11"
            ]["candidate_added_after_partial_review"]
        )
        percent_contract = contract["matching_contract"][
            "percent_axis_detection"
        ]
        self.assertEqual(percent_contract["minimum_well_formed_labels"], 3)
        self.assertEqual(percent_contract["minimum_label_confidence"], 0.1)
        self.assertTrue(
            percent_contract[
                "malformed_percent_tokens_are_not_axis_evidence"
            ]
        )

    def test_generator_creates_hashed_smoke_fixture_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = generate_fixtures(
                SimpleNamespace(
                    contract=DEFAULT_CONTRACT,
                    output_dir=root / "fixtures",
                )
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))

            self.assertEqual(validate_manifest(manifest, contract, manifest_path), [])
            self.assertEqual(len(manifest["fixtures"]), 32)
            self.assertEqual(
                sum(
                    fixture["expected_status"] == "CALIBRATED"
                    for fixture in manifest["fixtures"]
                ),
                24,
            )
            self.assertEqual(
                sum(
                    fixture["expected_status"] == "FAIL_CLOSED"
                    for fixture in manifest["fixtures"]
                ),
                8,
            )
            self.assertFalse(manifest["trading_outcome_data_used"])
            for fixture in manifest["fixtures"]:
                image_path = manifest_path.parent / fixture["image_path"]
                self.assertEqual(self._sha256(image_path), fixture["image_sha256"])

    def test_one_to_one_tick_matching_does_not_double_count(self) -> None:
        ground = [
            {"text": "1.28000", "price": 1.28, "y_center": 100.0},
        ]
        detected = [
            {"text": "1.28000", "price": 1.28, "y_center": 99.0},
            {"text": "1.28000", "price": 1.28, "y_center": 101.0},
        ]
        result = match_ticks(
            ground,
            detected,
            maximum_y_error=12.0,
            maximum_price_error=0.00001,
        )
        self.assertEqual(result["true_positive"], 1)
        self.assertEqual(result["false_positive"], 1)
        self.assertEqual(result["false_negative"], 0)

    def test_runner_persists_verified_raw_evidence_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = self._write_external_fixture(root / "fixtures")
            output_dir = root / "output"
            factory_calls = 0

            def factory(*args: object) -> _FakePriceAxisProvider:
                nonlocal factory_calls
                factory_calls += 1
                return _FakePriceAxisProvider()

            first = run(
                self._args(manifest_path, output_dir),
                provider_factory=factory,
            )
            self.assertEqual(factory_calls, 1)
            self.assertFalse(first["benchmark_pass"])
            self.assertFalse(first["production_promotion_allowed"])

            rows_path = output_dir / "e2_4_1_ocr_benchmark_rows.csv"
            rows_text = rows_path.read_text(encoding="utf-8")
            self.assertIn("CALIBRATED", rows_text)
            self.assertIn("FAKE_TEST_OCR", rows_text)
            report_path = (
                output_dir / "e2_4_1_ocr_benchmark_summary.md"
            )
            self.assertTrue(
                report_path.read_bytes().startswith(codecs.BOM_UTF8)
            )
            report_text = report_path.read_text(encoding="utf-8-sig")
            self.assertIn("## Synthetic smoke results", report_text)
            self.assertIn(
                "## External reviewed gate results",
                report_text,
            )
            raw_files = list((output_dir / "raw").glob("*.json"))
            self.assertEqual(len(raw_files), 1)

            def forbidden_factory(*args: object) -> _FakePriceAxisProvider:
                raise AssertionError("Resume seharusnya tidak menjalankan OCR.")

            second = run(
                self._args(manifest_path, output_dir, resume=True),
                provider_factory=forbidden_factory,
            )
            self.assertEqual(second["task_count"], 1)

            raw_files[0].write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "raw response SHA berubah"):
                run(
                    self._args(manifest_path, output_dir, resume=True),
                    provider_factory=forbidden_factory,
                )

    def test_manifest_rejects_trade_outcome_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = self._write_external_fixture(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["fixtures"][0]["win_rate"] = 0.99
            contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))

            errors = validate_manifest(manifest, contract, manifest_path)
            self.assertTrue(any("outcome terlarang" in error for error in errors))

    def test_external_builder_copies_and_hashes_reviewed_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_manifest = self._write_external_fixture(root / "source")
            source = json.loads(source_manifest.read_text(encoding="utf-8"))
            annotation = source["fixtures"][0]
            annotation["source_image_path"] = str(
                source_manifest.parent / annotation.pop("image_path")
            )
            annotation.pop("image_sha256")
            annotation.pop("fixture_source")
            annotation.pop("external_reviewed")
            annotations = {
                "schema_version": 1,
                "experiment_id": "E2.4.1",
                "fixture_set_id": "UNIT_TEST_EXTERNAL_PACK_V1",
                "trading_outcome_data_used": False,
                "fixtures": [annotation],
            }
            annotations_path = root / "annotations.json"
            annotations_path.write_text(
                json.dumps(annotations),
                encoding="utf-8",
            )

            manifest_path = build_pack(
                annotations_path=annotations_path,
                output_dir=root / "pack",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            fixture = manifest["fixtures"][0]
            copied = manifest_path.parent / fixture["image_path"]

            self.assertTrue(copied.is_file())
            self.assertEqual(self._sha256(copied), fixture["image_sha256"])
            self.assertTrue(fixture["external_reviewed"])
            self.assertFalse(manifest["trading_outcome_data_used"])


if __name__ == "__main__":
    unittest.main()
