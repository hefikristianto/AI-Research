from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai.scripts.audit_decision_coverage import (
    ensure_resume_compatible,
    multipart_body,
    persist_review_artifacts,
    request_analysis,
    run,
    select_samples,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.status = 200
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class DecisionCoverageAuditScriptTest(unittest.TestCase):
    def test_select_samples_filters_and_samples_deterministically(self) -> None:
        rows = [
            {
                "image_id": f"GBPUSD_M5_2025_{index}",
                "file_name": f"sample_{index}.png",
                "pair": "GBPUSD",
                "timeframe": "M5",
                "year": "2025",
                "end_datetime": f"2025-01-01 00:{index:02d}:00",
            }
            for index in range(5)
        ]
        rows.append(
            {
                "image_id": "XAUUSD_M5_2025_0",
                "file_name": "xau.png",
                "pair": "XAUUSD",
                "timeframe": "M5",
                "year": "2025",
                "end_datetime": "2025-01-01 00:00:00",
            }
        )

        first = select_samples(
            rows,
            images_root=Path("charts"),
            year=2025,
            pairs=["GBPUSD"],
            timeframes=["M5"],
            sample_size=2,
            seed=17,
        )
        second = select_samples(
            rows,
            images_root=Path("charts"),
            year=2025,
            pairs=["GBPUSD"],
            timeframes=["M5"],
            sample_size=2,
            seed=17,
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertTrue(all(row["pair"] == "GBPUSD" for row in first))

        targeted = select_samples(
            rows,
            images_root=Path("charts"),
            year=2025,
            pairs=["GBPUSD"],
            timeframes=["M5"],
            sample_size=0,
            seed=17,
            image_ids=["GBPUSD_M5_2025_3"],
        )
        self.assertEqual(
            [row["image_id"] for row in targeted],
            ["GBPUSD_M5_2025_3"],
        )

        with self.assertRaisesRegex(
            ValueError,
            "Image ID tidak ditemukan",
        ):
            select_samples(
                rows,
                images_root=Path("charts"),
                year=2025,
                pairs=["GBPUSD"],
                timeframes=["M5"],
                sample_size=0,
                seed=17,
                image_ids=["MISSING_CASE"],
            )

    def test_request_uses_batch_flag_and_multipart_image(self) -> None:
        payload = {
            "recommendation": {"decision": "NO_TRADE"},
            "pipeline_status": "COMPLETE",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "sample.png"
            image_path.write_bytes(b"fake-png")
            sample = {
                "image_path": str(image_path),
                "pair": "GBPUSD",
                "timeframe": "M5",
                "chart_datetime": "2025-01-03 09:15:00",
            }

            with patch(
                "ai.scripts.audit_decision_coverage.urlopen",
                return_value=_FakeResponse(payload),
            ) as mocked_urlopen:
                result, status = request_analysis(
                    base_url="http://127.0.0.1:8000",
                    sample=sample,
                    confidence_threshold=0.25,
                    chart_candles=100,
                    context_candles=300,
                    utc_offset=0.0,
                    include_annotated_chart=False,
                    timeout_seconds=30.0,
                )

            request = mocked_urlopen.call_args.args[0]
            self.assertIn("include_annotated_chart=false", request.full_url)
            self.assertIn(b"fake-png", request.data)
            self.assertEqual(status, 200)
            self.assertEqual(result, payload)

    def test_multipart_body_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "chart.png"
            image_path.write_bytes(b"chart-bytes")
            body, media_type = multipart_body(
                image_path=image_path,
                boundary="BOUNDARY",
            )

        self.assertEqual(media_type, "image/png")
        self.assertIn(b"chart-bytes", body)
        self.assertIn(b'filename="chart.png"', body)

    def test_resume_rejects_changed_sample(self) -> None:
        existing = {
            "year": 2025,
            "pairs": ["GBPUSD"],
            "timeframes": ["M5"],
            "sample_digest_sha256": "first",
            "confidence_threshold": 0.25,
            "chart_candles": 100,
            "context_candles": 300,
            "utc_offset": 0.0,
        }
        current = dict(existing)
        current["sample_digest_sha256"] = "second"

        with self.assertRaisesRegex(ValueError, "sample_digest_sha256"):
            ensure_resume_compatible(existing, current)

        old_schema = dict(existing)
        old_schema["schema_version"] = 1
        new_schema = dict(existing)
        new_schema["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema_version"):
            ensure_resume_compatible(old_schema, new_schema)

    def test_review_pack_saves_response_and_verified_png(self) -> None:
        image_bytes = b"diagnostic-png"
        encoded = base64.b64encode(
            image_bytes
        ).decode("ascii")
        payload = {
            "pipeline_status": "COMPLETE",
            "annotated_chart": {
                "status": "RENDERED",
                "data_url": (
                    "data:image/png;base64,"
                    + encoded
                ),
                "sha256": hashlib.sha256(
                    image_bytes
                ).hexdigest(),
            },
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            result = persist_review_artifacts(
                output_dir,
                {"image_id": "GBPUSD/M5 CASE"},
                payload,
            )

            response_path = (
                output_dir
                / result["response_json_path"]
            )
            annotated_path = (
                output_dir
                / result["annotated_chart_path"]
            )
            self.assertTrue(response_path.exists())
            self.assertEqual(
                annotated_path.read_bytes(),
                image_bytes,
            )
            self.assertEqual(
                result[
                    "annotated_chart_sha256_verified"
                ],
                1,
            )
            self.assertEqual(
                result["review_artifact_error"],
                "",
            )

    def test_run_writes_resumable_rows_and_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            metadata_path = root / "metadata.csv"
            images_root = root / "charts"
            image_dir = images_root / "GBPUSD" / "M5" / "2025"
            image_dir.mkdir(parents=True)
            image_path = image_dir / "sample.png"
            image_path.write_bytes(b"fake-png")

            with metadata_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "image_id",
                        "file_name",
                        "pair",
                        "timeframe",
                        "year",
                        "end_datetime",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "image_id": "GBPUSD_M5_2025_SAMPLE",
                        "file_name": image_path.name,
                        "pair": "GBPUSD",
                        "timeframe": "M5",
                        "year": "2025",
                        "end_datetime": "2025-01-03 09:15:00",
                    }
                )

            output_dir = root / "audit"
            args = SimpleNamespace(
                base_url="http://127.0.0.1:8000",
                metadata=metadata_path,
                images_root=images_root,
                year=2025,
                pairs=["GBPUSD"],
                timeframes=["M5"],
                sample_size=0,
                image_ids=None,
                seed=42,
                confidence_threshold=0.25,
                chart_candles=100,
                context_candles=300,
                utc_offset=0.0,
                timeout_seconds=30.0,
                max_errors=5,
                output_dir=output_dir,
                resume=False,
                include_annotated_chart=False,
                review_pack=False,
                skip_health_check=False,
            )
            payload = {
                "pipeline_status": "COMPLETE",
                "regime": {"label": "bullish", "confidence": 0.7},
                "detection": {"total": 0, "class_counts": {}},
                "pairing": {
                    "total_pairs": 0,
                    "pairing_status": "NO_VALID_PAIR",
                },
                "recommendation": {
                    "decision": "NO_TRADE",
                    "internal_decision": "WAIT",
                    "execution_status": "NO_SETUP",
                    "final_decision_ready": False,
                    "actionable": False,
                    "blockers": ["NO_VALID_SETUP"],
                    "warnings": [],
                    "reasons": ["NO_VALID_SETUP"],
                },
            }

            with (
                patch(
                    "ai.scripts.audit_decision_coverage.check_health"
                ) as mocked_health,
                patch(
                    "ai.scripts.audit_decision_coverage.request_analysis",
                    return_value=(payload, 200),
                ),
            ):
                with redirect_stdout(io.StringIO()):
                    result = run(args)

            self.assertEqual(result, 0)
            mocked_health.assert_called_once()
            self.assertTrue(
                (output_dir / "decision_coverage_rows.csv").exists()
            )
            self.assertTrue(
                (output_dir / "decision_coverage_summary.json").exists()
            )
            self.assertTrue(
                (output_dir / "decision_coverage_summary.md").exists()
            )

            summary = json.loads(
                (output_dir / "decision_coverage_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                summary["coverage"]["no_trade"]["count"],
                1,
            )
            self.assertFalse(
                summary["run_configuration"]["training_performed"]
            )


if __name__ == "__main__":
    unittest.main()
