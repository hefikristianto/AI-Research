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
    DEFAULT_RESULT,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    read_manifest,
    run,
    validate_reviewed_manifest,
)
from app.services.chart_plot_geometry_service import (
    ChartPlotGeometryService,
)


class E23SnapshotRendererTest(unittest.TestCase):
    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _write_source(path: Path) -> list[datetime]:
        path.parent.mkdir(parents=True, exist_ok=True)
        start = datetime(2023, 1, 2, 0, 0)
        timestamps = [start + timedelta(minutes=5 * index) for index in range(100)]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(
                [
                    "<DATE>",
                    "<TIME>",
                    "<OPEN>",
                    "<HIGH>",
                    "<LOW>",
                    "<CLOSE>",
                    "<TICKVOL>",
                ]
            )
            for index, timestamp in enumerate(timestamps):
                open_price = 1.20 + index * 0.0001
                close_price = open_price + (0.00005 if index % 2 == 0 else -0.00005)
                writer.writerow(
                    [
                        timestamp.strftime("%Y.%m.%d"),
                        timestamp.strftime("%H:%M:%S"),
                        f"{open_price:.5f}",
                        f"{max(open_price, close_price) + 0.0001:.5f}",
                        f"{min(open_price, close_price) - 0.0001:.5f}",
                        f"{close_price:.5f}",
                        "100",
                    ]
                )
        return timestamps

    def _write_fixture(self, root: Path) -> SimpleNamespace:
        raw_root = root / "raw"
        relative_source = "GBPUSD/M5/2023/GBPUSD_M5_2023_RAW.csv"
        source = raw_root / relative_source
        timestamps = self._write_source(source)
        source_hash = self._sha256(source)

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
                "analysis_target_utc_datetime": "2023-01-02T08:20:00Z",
                "analysis_target_market_datetime": "2023-01-02T08:20:00",
                "market_utc_offset_hours": 0.0,
                "source_timestamp_semantics": "MT5_BAR_OPEN_TIME",
                "timezone_assumption": "SOURCE_TIMESTAMPS_ARE_UTC_PROVISIONAL",
                "closed_candle_rule": "BAR_OPEN_PLUS_TIMEFRAME_DURATION_LTE_TARGET",
                "timeframe": "M5",
                "timeframe_minutes": 5,
                "chart_candles": 100,
                "context_candles": 300,
                "chart_start_datetime": timestamps[0].isoformat(),
                "chart_end_open_datetime": timestamps[-1].isoformat(),
                "chart_end_close_datetime": (timestamps[-1] + timedelta(minutes=5)).isoformat(),
                "ohlcv_cutoff_datetime": timestamps[-1].isoformat(),
                "staleness_minutes": 0.0,
                "available_history_candles": 300,
                "resolved_bar_session": "LONDON",
                "session_alignment_status": "ALIGNED",
                "anti_lookahead_verified": 1,
                "plot_aware_mapping": 1,
                "mapping_fallback": "FULL_IMAGE",
                "planned_image_path": "images/GBPUSD/M5/2023/sample.png",
                "source_paths": relative_source,
                "source_sha256s": source_hash,
                "status": "READY",
                "event_ready": 1,
                "max_candidates_per_tier_per_day": 1,
            }
        )
        digest = manifest_digest([row])

        input_dir = root / "input"
        input_dir.mkdir()
        manifest = input_dir / "daily_snapshot_manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerow(row)

        summary = input_dir / "daily_manifest_summary.json"
        summary.write_text(
            json.dumps(
                {
                    "snapshot_rows": 1,
                    "manifest_digest_sha256": digest,
                }
            ),
            encoding="utf-8",
        )
        manifest_run_config = input_dir / "run_config.json"
        manifest_run_config.write_text(
            json.dumps(
                {
                    "training_performed": False,
                    "inference_performed": False,
                    "manifest_digest_sha256": digest,
                    "git_commit": "fixture",
                    "git_dirty": False,
                    "pair": "GBPUSD",
                    "years": [2023],
                    "source_files": [
                        {"path": relative_source, "sha256": source_hash}
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = root / "result.json"
        result.write_text(
            json.dumps(
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
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(
            manifest=manifest,
            manifest_summary=summary,
            manifest_run_config=manifest_run_config,
            manifest_result=result,
            raw_root=raw_root,
            output_dir=root / "output",
            years=None,
            timeframes=None,
            slots=None,
            limit=None,
            resume=False,
            force=False,
            fail_fast=True,
        )

    def test_renderer_is_deterministic_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            args = self._write_fixture(Path(temporary_directory))
            first = run(args)
            image_path = args.output_dir / "images/GBPUSD/M5/2023/sample.png"
            first_hash = self._sha256(image_path)
            with Image.open(image_path) as image:
                self.assertEqual(image.size, (IMAGE_WIDTH, IMAGE_HEIGHT))
                geometry = ChartPlotGeometryService().analyze(image.convert("RGB"))
            self.assertEqual(geometry["status"], "DETECTED")
            self.assertGreater(geometry["confidence"], 0.90)

            args.resume = True
            second = run(args)
            self.assertEqual(self._sha256(image_path), first_hash)
            self.assertEqual(
                second["audit_rows"]["GBPUSD_20230102_LONDON_M5"]["render_status"],
                "REUSED",
            )
            summary = json.loads(first["summary_path"].read_text(encoding="utf-8"))
            self.assertEqual(summary["manifest_ready_rows"], 1)
            self.assertFalse(summary["training_performed"])
            self.assertFalse(summary["inference_performed"])

    def test_review_digest_rejects_changed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            args = self._write_fixture(Path(temporary_directory))
            rows = read_manifest(args.manifest)
            rows[0]["slot"] = "LONDON_NEW_YORK_OVERLAP"
            with self.assertRaisesRegex(ValueError, "Digest CSV"):
                validate_reviewed_manifest(
                    rows,
                    json.loads(args.manifest_summary.read_text(encoding="utf-8")),
                    json.loads(args.manifest_run_config.read_text(encoding="utf-8")),
                    json.loads(args.manifest_result.read_text(encoding="utf-8")),
                )

    def test_repository_review_result_is_internally_consistent(self) -> None:
        result = json.loads(DEFAULT_RESULT.read_text(encoding="utf-8"))
        manifest = result["manifest"]
        authorization = result["render_authorization"]
        status_counts = result["status_counts"]

        self.assertEqual(result["decision_status"], "VALIDATED_FOR_RENDERING")
        self.assertEqual(
            sum(status_counts.values()),
            manifest["snapshot_rows"],
        )
        self.assertEqual(
            status_counts["READY"],
            authorization["expected_render_count"],
        )
        self.assertEqual(manifest["years"], [2020, 2021, 2022, 2023, 2024])
        self.assertNotIn(2025, manifest["years"])
        self.assertEqual(authorization["canonical_width"], IMAGE_WIDTH)
        self.assertEqual(authorization["canonical_height"], IMAGE_HEIGHT)
        self.assertEqual(len(manifest["sha256"]), 64)
        self.assertEqual(len(result["review_archive"]["sha256"]), 64)
        self.assertFalse(result["guardrails"]["high_risk_policy_selected"])
        self.assertFalse(result["guardrails"]["final_2025_unlocked"])


if __name__ == "__main__":
    unittest.main()
