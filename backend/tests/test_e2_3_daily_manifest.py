from __future__ import annotations

import copy
import csv
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from ai.scripts.build_e2_3_daily_manifest import (
    build_manifest_rows,
    build_summary,
    manifest_digest,
    mark_duplicate_windows,
    mark_event_readiness,
    read_json,
    read_mt5_datetimes,
    run,
    select_closed_window,
    validate_contracts,
    validate_manifest_rows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_3_daily_manifest.json"
)
MAPPING_DECISION_PATH = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_2_plot_mapping_decision.json"
)


class E23DailyManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = read_json(CONFIG_PATH)
        self.mapping_decision = read_json(MAPPING_DECISION_PATH)

    @staticmethod
    def _write_mt5_file(path: Path, timestamps: list[datetime]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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
                    "<VOL>",
                    "<SPREAD>",
                ]
            )
            for timestamp in timestamps:
                writer.writerow(
                    [
                        timestamp.strftime("%Y.%m.%d"),
                        timestamp.strftime("%H:%M:%S"),
                        "1.20000",
                        "1.20100",
                        "1.19900",
                        "1.20050",
                        "100",
                        "0",
                        "10",
                    ]
                )

    def _write_complete_fixture(self, raw_root: Path) -> None:
        target = datetime(2023, 1, 2, 9, 0)
        final = datetime(2023, 1, 3, 14, 0)

        for timeframe, minutes in self.config["timeframe_minutes"].items():
            duration = timedelta(minutes=int(minutes))
            current = target - (330 * duration)
            timestamps: list[datetime] = []
            while current <= final:
                timestamps.append(current)
                current += duration

            for year in sorted({value.year for value in timestamps}):
                path = (
                    raw_root
                    / "GBPUSD"
                    / timeframe
                    / str(year)
                    / f"GBPUSD_{timeframe}_{year}_RAW.csv"
                )
                self._write_mt5_file(
                    path,
                    [value for value in timestamps if value.year == year],
                )

    def test_contract_accepts_development_years_and_rejects_final_year(self) -> None:
        self.assertEqual(
            validate_contracts(
                self.config,
                self.mapping_decision,
                [2020, 2021, 2022, 2023, 2024],
            ),
            [],
        )

        errors = validate_contracts(
            self.config,
            self.mapping_decision,
            [2025],
        )
        self.assertTrue(any("belum diizinkan" in error for error in errors))
        self.assertTrue(any("masih terkunci" in error for error in errors))

        drifted = copy.deepcopy(self.mapping_decision)
        drifted["selected_policy"][
            "e2_3_canonical_experiment_mapping"
        ] = "FULL_IMAGE"
        errors = validate_contracts(self.config, drifted, [2023])
        self.assertTrue(any("PLOT_AWARE" in error for error in errors))

        drifted_config = copy.deepcopy(self.config)
        drifted_config["time_policy"]["slots"][0]["utc_time"] = "10:00:00"
        errors = validate_contracts(
            drifted_config,
            self.mapping_decision,
            [2023],
        )
        self.assertTrue(any("09:00" in error for error in errors))

    def test_mt5_parser_rejects_duplicate_timestamps(self) -> None:
        timestamp = datetime(2023, 1, 2, 8, 55)
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "sample.csv"
            self._write_mt5_file(path, [timestamp])
            self.assertEqual(read_mt5_datetimes(path), [timestamp])

            self._write_mt5_file(path, [timestamp, timestamp])
            with self.assertRaisesRegex(ValueError, "duplikat"):
                read_mt5_datetimes(path)

            path.write_text(
                "<DATE>\t<TIME>\n2023.01.02\t08:55:00\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "OHLCV minimum"):
                read_mt5_datetimes(path)

    def test_closed_window_excludes_candle_that_opens_at_target(self) -> None:
        target = datetime(2023, 1, 2, 9, 0)
        timestamps = [
            target - timedelta(minutes=5 * offset)
            for offset in range(8, -1, -1)
        ]

        result = select_closed_window(
            timestamps,
            target_market_datetime=target,
            timeframe_minutes=5,
            chart_candles=3,
            context_candles=5,
            maximum_staleness_minutes=5,
        )

        self.assertEqual(result["status"], "READY")
        self.assertEqual(
            result["chart_end_open_datetime"],
            datetime(2023, 1, 2, 8, 55),
        )
        self.assertEqual(result["chart_end_close_datetime"], target)
        self.assertNotEqual(result["chart_end_open_datetime"], target)
        self.assertTrue(result["anti_lookahead_verified"])

    def test_h4_cutoff_is_separate_from_london_analysis_target(self) -> None:
        target = datetime(2023, 1, 2, 9, 0)
        timestamps = [
            datetime(2022, 11, 1, 0, 0) + timedelta(hours=4 * index)
            for index in range(380)
        ]

        result = select_closed_window(
            timestamps,
            target_market_datetime=target,
            timeframe_minutes=240,
            chart_candles=100,
            context_candles=300,
            maximum_staleness_minutes=240,
        )

        self.assertEqual(result["status"], "READY")
        self.assertEqual(
            result["chart_end_open_datetime"],
            datetime(2023, 1, 2, 4, 0),
        )
        self.assertEqual(
            result["chart_end_close_datetime"],
            datetime(2023, 1, 2, 8, 0),
        )
        self.assertEqual(result["staleness_minutes"], 60.0)

    def test_duplicate_window_invalidates_only_the_later_event(self) -> None:
        rows = [
            {
                "snapshot_id": "first_M5",
                "event_id": "first",
                "pair": "GBPUSD",
                "timeframe": "M5",
                "chart_start_datetime": "2023-01-02T00:40:00",
                "chart_end_open_datetime": "2023-01-02T08:55:00",
                "status": "READY",
                "anti_lookahead_verified": 1,
                "event_ready": 0,
            },
            {
                "snapshot_id": "second_M5",
                "event_id": "second",
                "pair": "GBPUSD",
                "timeframe": "M5",
                "chart_start_datetime": "2023-01-02T00:40:00",
                "chart_end_open_datetime": "2023-01-02T08:55:00",
                "status": "READY",
                "anti_lookahead_verified": 1,
                "event_ready": 0,
            },
        ]

        mark_duplicate_windows(rows)
        mark_event_readiness(rows, expected_timeframes={"M5"})

        self.assertEqual(rows[0]["status"], "READY")
        self.assertEqual(rows[0]["event_ready"], 1)
        self.assertEqual(rows[1]["status"], "DUPLICATE_WINDOW")
        self.assertEqual(rows[1]["duplicate_of_snapshot_id"], "first_M5")
        self.assertEqual(rows[1]["event_ready"], 0)

    def test_complete_fixture_builds_deterministic_ready_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_root = root / "raw"
            self._write_complete_fixture(raw_root)

            first_rows, _ = build_manifest_rows(
                self.config,
                raw_root=raw_root,
                years=[2023],
            )
            second_rows, _ = build_manifest_rows(
                self.config,
                raw_root=raw_root,
                years=[2023],
            )

        self.assertEqual(len(first_rows), 16)
        self.assertEqual(manifest_digest(first_rows), manifest_digest(second_rows))
        self.assertEqual(
            validate_manifest_rows(
                first_rows,
                expected_timeframes={"M5", "M15", "H1", "H4"},
            ),
            [],
        )
        self.assertTrue(all(row["status"] == "READY" for row in first_rows))
        self.assertTrue(all(row["event_ready"] == 1 for row in first_rows))
        self.assertTrue(
            all(row["anti_lookahead_verified"] == 1 for row in first_rows)
        )
        self.assertEqual(
            sum(
                row["session_alignment_status"]
                == "TARGET_OVERRIDE_REQUIRED"
                for row in first_rows
            ),
            4,
        )
        self.assertTrue(
            all(not Path(row["source_paths"].split("|")[0]).is_absolute()
                for row in first_rows)
        )

        summary = build_summary(first_rows)
        self.assertEqual(summary["trading_days"], 2)
        self.assertEqual(summary["events"], 4)
        self.assertEqual(summary["ready_events"], 4)
        self.assertEqual(summary["ready_event_rate"], 1.0)

    def test_run_writes_manifest_summary_and_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            raw_root = root / "raw"
            output_dir = root / "output"
            self._write_complete_fixture(raw_root)
            args = SimpleNamespace(
                config=CONFIG_PATH,
                mapping_decision=MAPPING_DECISION_PATH,
                raw_root=raw_root,
                years=[2023],
                output_dir=output_dir,
            )

            with redirect_stdout(StringIO()):
                result = run(args)

            manifest_path = output_dir / "daily_snapshot_manifest.csv"
            summary_path = output_dir / "daily_manifest_summary.json"
            run_config_path = output_dir / "run_config.json"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(run_config_path.exists())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            run_config = json.loads(run_config_path.read_text(encoding="utf-8"))

        self.assertEqual(
            summary["manifest_digest_sha256"],
            manifest_digest(result["rows"]),
        )
        self.assertEqual(
            run_config["manifest_digest_sha256"],
            summary["manifest_digest_sha256"],
        )
        self.assertEqual(run_config["years"], [2023])
        self.assertFalse(run_config["training_performed"])
        self.assertFalse(run_config["inference_performed"])
        self.assertTrue(run_config["source_files"])


if __name__ == "__main__":
    unittest.main()
