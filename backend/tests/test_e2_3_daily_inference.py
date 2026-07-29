from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from ai.scripts.build_e2_3_daily_manifest import MANIFEST_FIELDS, manifest_digest
from ai.scripts.render_e2_3_daily_snapshots import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    RENDER_FIELDS,
)
from ai.scripts.run_e2_3_daily_inference import (
    DEFAULT_CONTRACT,
    DEFAULT_MANIFEST_RESULT,
    validate_full_analysis_response,
    validate_inference_contract,
    run,
)


class E23DailyInferenceTest(unittest.TestCase):
    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _response(
        *,
        chart_datetime: str,
        target_datetime: str,
    ) -> dict[str, object]:
        return {
            "filename": "sample.png",
            "content_type": "image/png",
            "width": IMAGE_WIDTH,
            "height": IMAGE_HEIGHT,
            "metadata": {
                "pair": "GBPUSD",
                "timeframe": "M5",
                "chart_datetime": chart_datetime,
            },
            "ohlcv_context": {
                "status": "LOADED",
                "chart_end_datetime": chart_datetime,
            },
            "analysis_clock": {
                "status": "ANALYSIS_TARGET_VALIDATED",
                "datetime_source": "ANALYSIS_TARGET_OVERRIDE",
                "anti_lookahead_validated": True,
                "effective_datetime": target_datetime,
            },
            "chart_geometry": {"status": "DETECTED"},
            "regime": {
                "label": "bullish",
                "confidence": 0.71,
            },
            "detection": {
                "total": 2,
                "confidence_threshold": 0.25,
                "model_path": "fixture/best.pt",
            },
            "pairing": {"total_pairs": 1},
            "price_conversion": {
                "status": "MAPPED",
                "plot_aware_mapping_requested": True,
                "mapping_index_mode": "PLOT_AWARE",
                "mapping_confidence": 0.91,
                "mapping_provisional": False,
                "mapping_calibration_applied": True,
            },
            "execution_gate": {
                "decision": "WAIT",
                "execution_status": "REVIEW",
                "final_decision_ready": False,
                "advanced_score": 0.57,
                "session_score": 0.61,
                "risk_reward_ratio": 1.42,
                "entry_distance_atr": 1.1,
                "blockers": [],
                "warnings": ["SESSION_BELOW_TRADE_CANDIDATE"],
            },
            "recommendation": {
                "decision": "WATCHLIST",
                "internal_decision": "WAIT",
            },
            "annotated_chart": {
                "status": "SKIPPED",
                "rendered_detections": 0,
            },
            "pipeline_status": "FIXTURE_COMPLETE",
        }

    def _write_fixture(self, root: Path) -> SimpleNamespace:
        experiment_dir = root / "experiment"
        input_dir = experiment_dir / "input"
        render_dir = experiment_dir / "render"
        image_relative = "images/GBPUSD/M5/2023/sample.png"
        image_path = experiment_dir / image_relative
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "white").save(image_path)
        image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()

        chart_start = datetime(2023, 1, 2, 0, 0)
        chart_end = chart_start + timedelta(minutes=5 * 99)
        target = chart_end + timedelta(minutes=5)
        source_hash = "a" * 64
        row = {field: "" for field in MANIFEST_FIELDS}
        row.update(
            {
                "schema_version": 1,
                "experiment_id": "E2.3",
                "event_id": "GBPUSD_20230102_LONDON",
                "daily_group_id": "GBPUSD_20230102",
                "snapshot_id": "GBPUSD_20230102_LONDON_M5",
                "evaluation_split": "POLICY_SELECTION",
                "pair": "GBPUSD",
                "year": 2023,
                "trading_date_utc": "2023-01-02",
                "slot": "LONDON",
                "target_session": "LONDON",
                "analysis_target_utc_datetime": target.isoformat() + "Z",
                "analysis_target_market_datetime": target.isoformat(),
                "market_utc_offset_hours": 0.0,
                "source_timestamp_semantics": "MT5_BAR_OPEN_TIME",
                "timezone_assumption": "SOURCE_TIMESTAMPS_ARE_UTC_PROVISIONAL",
                "closed_candle_rule": "BAR_OPEN_PLUS_TIMEFRAME_DURATION_LTE_TARGET",
                "timeframe": "M5",
                "timeframe_minutes": 5,
                "chart_candles": 100,
                "context_candles": 300,
                "chart_start_datetime": chart_start.isoformat(),
                "chart_end_open_datetime": chart_end.isoformat(),
                "chart_end_close_datetime": target.isoformat(),
                "ohlcv_cutoff_datetime": chart_end.isoformat(),
                "staleness_minutes": 0.0,
                "available_history_candles": 300,
                "resolved_bar_session": "LONDON",
                "session_alignment_status": "ALIGNED",
                "anti_lookahead_verified": 1,
                "plot_aware_mapping": 1,
                "mapping_fallback": "FULL_IMAGE",
                "planned_image_path": image_relative,
                "source_paths": "fixture.csv",
                "source_sha256s": source_hash,
                "status": "READY",
                "event_ready": 1,
                "max_candidates_per_tier_per_day": 1,
            }
        )
        digest = manifest_digest([row])

        manifest = input_dir / "daily_snapshot_manifest.csv"
        manifest.parent.mkdir(parents=True)
        with manifest.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerow(row)

        self._write_json(
            input_dir / "daily_manifest_summary.json",
            {
                "snapshot_rows": 1,
                "manifest_digest_sha256": digest,
            },
        )
        self._write_json(
            input_dir / "run_config.json",
            {
                "training_performed": False,
                "inference_performed": False,
                "manifest_digest_sha256": digest,
                "git_commit": "fixture",
                "git_dirty": False,
                "pair": "GBPUSD",
                "years": [2023],
                "source_files": [
                    {"path": "fixture.csv", "sha256": source_hash}
                ],
            },
        )

        manifest_result = root / "manifest_result.json"
        self._write_json(
            manifest_result,
            {
                "decision_status": "VALIDATED_FOR_RENDERING",
                "manifest": {
                    "sha256": digest,
                    "git_commit": "fixture",
                    "git_dirty": False,
                    "pair": "GBPUSD",
                    "years": [2023],
                    "snapshot_rows": 1,
                    "ready_snapshot_rows": 1,
                    "source_files": 1,
                },
                "render_authorization": {"expected_render_count": 1},
            },
        )

        render_dir.mkdir(parents=True)
        render_row = {field: "" for field in RENDER_FIELDS}
        render_row.update(
            {
                "snapshot_id": row["snapshot_id"],
                "event_id": row["event_id"],
                "evaluation_split": row["evaluation_split"],
                "pair": "GBPUSD",
                "year": 2023,
                "slot": "LONDON",
                "timeframe": "M5",
                "manifest_status": "READY",
                "render_status": "RENDERED",
                "image_path": image_relative,
                "image_sha256": image_hash,
                "width": IMAGE_WIDTH,
                "height": IMAGE_HEIGHT,
                "chart_start_datetime": row["chart_start_datetime"],
                "chart_end_open_datetime": row["chart_end_open_datetime"],
                "analysis_target_market_datetime": row[
                    "analysis_target_market_datetime"
                ],
                "source_paths": "fixture.csv",
                "source_sha256s": source_hash,
                "manifest_digest_sha256": digest,
            }
        )
        with (
            render_dir / "daily_snapshot_render_rows.csv"
        ).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=RENDER_FIELDS)
            writer.writeheader()
            writer.writerow(render_row)
        self._write_json(
            render_dir / "daily_snapshot_render_summary.json",
            {
                "stage": "DAILY_SNAPSHOT_RENDER",
                "training_performed": False,
                "inference_performed": False,
                "manifest_digest_sha256": digest,
                "manifest_ready_rows": 1,
                "cumulative_audit_rows": 1,
                "render_status_counts": {"RENDERED": 1},
                "complete_for_reviewed_manifest": True,
            },
        )

        contract = root / "inference_contract.json"
        self._write_json(
            contract,
            {
                "schema_version": 1,
                "experiment_id": "E2.3",
                "stage": "DAILY_INFERENCE_CACHE",
                "decision_status": "PREREGISTERED_FOR_DEVELOPMENT_INFERENCE",
                "training_performed": False,
                "policy_evaluation_performed": False,
                "reviewed_manifest": {
                    "sha256": digest,
                    "ready_snapshot_rows": 1,
                    "canonical_width": IMAGE_WIDTH,
                    "canonical_height": IMAGE_HEIGHT,
                },
                "request_contract": {
                    "endpoint": "/api/analysis/full",
                    "confidence_threshold": 0.25,
                    "chart_candles": 100,
                    "context_candles": 300,
                    "market_utc_offset_hours": 0.0,
                    "include_annotated_chart": False,
                    "plot_aware_mapping": True,
                    "chart_datetime_field": "chart_end_open_datetime",
                    "analysis_target_datetime_field": (
                        "analysis_target_market_datetime"
                    ),
                },
                "development": {
                    "allowed_splits": [
                        "POLICY_DEVELOPMENT",
                        "POLICY_SELECTION",
                    ],
                    "allowed_years": [2020, 2021, 2022, 2023],
                },
                "frozen_holdout": {
                    "year": 2024,
                    "inference_allowed_before_policy_freeze": False,
                },
                "final_temporal_test": {
                    "year": 2025,
                    "locked": True,
                },
                "guardrails": {
                    "one_inference_per_snapshot": True,
                    "standard_and_high_risk_reuse_same_response": True,
                    "raw_response_is_not_ground_truth": True,
                    "request_failure_is_not_no_trade": True,
                    "response_contract_failure_is_not_no_trade": True,
                    "high_risk_threshold_selection_allowed": False,
                    "holdout_inspection_allowed": False,
                    "final_2025_inference_allowed": False,
                },
            },
        )
        return SimpleNamespace(
            experiment_dir=experiment_dir,
            base_url="http://127.0.0.1:8000",
            contract=contract,
            manifest_result=manifest_result,
            years=[2023],
            timeframes=None,
            slots=None,
            snapshot_ids=None,
            limit=None,
            resume=False,
            timeout_seconds=30.0,
            max_errors=1,
            checkpoint_every=1,
            progress_every=1,
            skip_health_check=True,
            fail_fast=True,
            manifest_row=row,
        )

    def test_runner_writes_and_reuses_one_validated_response(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            args = self._write_fixture(Path(temporary_directory))
            calls: list[dict[str, object]] = []

            def request(**kwargs: object) -> tuple[dict[str, object], int]:
                calls.append(kwargs)
                self.assertEqual(
                    kwargs["analysis_target_datetime"],
                    args.manifest_row["analysis_target_market_datetime"],
                )
                self.assertTrue(kwargs["plot_aware_mapping"])
                self.assertFalse(kwargs["include_annotated_chart"])
                return (
                    self._response(
                        chart_datetime=args.manifest_row[
                            "chart_end_open_datetime"
                        ],
                        target_datetime=args.manifest_row[
                            "analysis_target_market_datetime"
                        ],
                    ),
                    200,
                )

            first = run(args, request_function=request)
            self.assertEqual(first["exit_code"], 0)
            self.assertEqual(len(calls), 1)
            inference_row = next(iter(first["inference_rows"].values()))
            self.assertEqual(inference_row["request_status"], "SUCCESS")
            self.assertEqual(inference_row["cache_status"], "WRITTEN")
            self.assertTrue(
                (
                    args.experiment_dir
                    / inference_row["response_path"]
                ).is_file()
            )

            args.resume = True

            def must_not_run(**kwargs: object) -> tuple[dict[str, object], int]:
                raise AssertionError(f"Unexpected second inference: {kwargs}")

            second = run(args, request_function=must_not_run)
            reused = next(iter(second["inference_rows"].values()))
            self.assertEqual(reused["cache_status"], "REUSED")
            self.assertEqual(len(calls), 1)

    def test_response_rejects_wrong_analysis_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            args = self._write_fixture(Path(temporary_directory))
            payload = self._response(
                chart_datetime=args.manifest_row["chart_end_open_datetime"],
                target_datetime="2023-01-03T09:00:00",
            )
            with self.assertRaisesRegex(ValueError, "Jam efektif sesi"):
                validate_full_analysis_response(payload, args.manifest_row)

    def test_runner_rejects_frozen_holdout_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            args = self._write_fixture(Path(temporary_directory))
            args.years = [2024]
            with self.assertRaisesRegex(ValueError, "Frozen holdout 2024"):
                run(args)

    def test_repository_inference_contract_keeps_holdouts_locked(self) -> None:
        contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        manifest_result = json.loads(
            DEFAULT_MANIFEST_RESULT.read_text(encoding="utf-8")
        )
        request = validate_inference_contract(contract, manifest_result)

        self.assertTrue(request["plot_aware_mapping"])
        self.assertFalse(request["include_annotated_chart"])
        self.assertEqual(
            contract["reviewed_manifest"]["ready_snapshot_rows"],
            10230,
        )
        self.assertFalse(
            contract["frozen_holdout"][
                "inference_allowed_before_policy_freeze"
            ]
        )
        self.assertTrue(contract["final_temporal_test"]["locked"])


if __name__ == "__main__":
    unittest.main()
