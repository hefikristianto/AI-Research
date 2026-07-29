from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from ai.scripts.audit_decision_coverage import (
        AuditRequestError,
        check_health,
        request_analysis,
    )
    from ai.scripts.render_e2_3_daily_snapshots import (
        file_sha256,
        read_json,
        read_manifest,
        read_render_rows,
        validate_reviewed_manifest,
    )
except ModuleNotFoundError:
    from audit_decision_coverage import (  # type: ignore[no-redef]
        AuditRequestError,
        check_health,
        request_analysis,
    )
    from render_e2_3_daily_snapshots import (  # type: ignore[no-redef]
        file_sha256,
        read_json,
        read_manifest,
        read_render_rows,
        validate_reviewed_manifest,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_3_daily_inference.json"
)
DEFAULT_MANIFEST_RESULT = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_3_daily_manifest_result.json"
)

RUNNER_VERSION = "1.0.0"
DEVELOPMENT_SPLITS = {
    "POLICY_DEVELOPMENT",
    "POLICY_SELECTION",
}
DEVELOPMENT_YEARS = {2020, 2021, 2022, 2023}
SAFE_SNAPSHOT_ID = re.compile(r"^[A-Za-z0-9._-]+$")

INFERENCE_FIELDS = [
    "snapshot_id",
    "event_id",
    "daily_group_id",
    "evaluation_split",
    "pair",
    "year",
    "trading_date_utc",
    "slot",
    "timeframe",
    "chart_datetime",
    "analysis_target_datetime",
    "image_path",
    "image_sha256",
    "manifest_digest_sha256",
    "inference_contract_sha256",
    "request_status",
    "cache_status",
    "http_status",
    "latency_ms",
    "response_path",
    "response_sha256",
    "pipeline_status",
    "analysis_clock_status",
    "analysis_clock_validated",
    "public_decision",
    "internal_decision",
    "execution_status",
    "final_decision_ready",
    "detection_count",
    "pair_count",
    "regime_label",
    "regime_confidence",
    "mapping_status",
    "mapping_mode",
    "mapping_confidence",
    "mapping_provisional",
    "mapping_calibration_applied",
    "advanced_score",
    "session_score",
    "risk_reward_ratio",
    "entry_distance_atr",
    "blockers_json",
    "warnings_json",
    "yolo_model_path",
    "error",
    "inferred_at_utc",
]


RequestFunction = Callable[..., tuple[dict[str, Any], int]]
HealthFunction = Callable[[str, float], None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a resumable raw inference cache for the reviewed E2.3 "
            "daily snapshots. The runner performs no training and does not "
            "select a high-risk policy."
        )
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help=(
            "E2.3 run root containing input/, images/, and render/. "
            "Inference artifacts are written below this directory."
        ),
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Running local AI-TDSS backend URL.",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="Frozen E2.3 development-inference contract.",
    )
    parser.add_argument(
        "--manifest-result",
        type=Path,
        default=DEFAULT_MANIFEST_RESULT,
    )
    parser.add_argument(
        "--year",
        dest="years",
        action="append",
        type=int,
        help=(
            "Development year to process. Repeat as needed. "
            "Default: 2020, 2021, 2022, and 2023."
        ),
    )
    parser.add_argument(
        "--timeframe",
        dest="timeframes",
        action="append",
        choices=["M5", "M15", "H1", "H4"],
    )
    parser.add_argument(
        "--slot",
        dest="slots",
        action="append",
        choices=["LONDON", "LONDON_NEW_YORK_OVERLAP"],
    )
    parser.add_argument(
        "--snapshot-id",
        dest="snapshot_ids",
        action="append",
        help="Run one exact reviewed snapshot. Repeat as needed.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Reuse verified responses and retry failed or unfinished snapshots."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=300.0,
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=5,
        help="Stop after this many consecutive request errors; 0 disables.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1,
    )
    parser.add_argument("--skip-health-check", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    return parser.parse_args()


def _argument(args: argparse.Namespace, name: str, default: Any) -> Any:
    return getattr(args, name, default)


def validate_args(args: argparse.Namespace) -> None:
    years = set(_argument(args, "years", None) or DEVELOPMENT_YEARS)
    if 2025 in years:
        raise ValueError(
            "Final temporal test 2025 masih terkunci dan tidak boleh diinferensi."
        )
    if 2024 in years:
        raise ValueError(
            "Frozen holdout 2024 belum boleh diinferensi sebelum kebijakan "
            "Standard/High Risk dibekukan."
        )
    unsupported = years.difference(DEVELOPMENT_YEARS)
    if unsupported:
        raise ValueError(
            "Tahun inference development tidak didukung: "
            + ", ".join(str(value) for value in sorted(unsupported))
        )

    limit = _argument(args, "limit", None)
    if limit is not None and int(limit) < 1:
        raise ValueError("--limit harus minimal 1.")
    if float(_argument(args, "timeout_seconds", 300.0)) <= 0:
        raise ValueError("--timeout-seconds harus lebih dari nol.")
    if int(_argument(args, "max_errors", 5)) < 0:
        raise ValueError("--max-errors tidak boleh negatif.")
    if int(_argument(args, "checkpoint_every", 10)) < 1:
        raise ValueError("--checkpoint-every harus minimal 1.")
    if int(_argument(args, "progress_every", 1)) < 1:
        raise ValueError("--progress-every harus minimal 1.")


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> str:
    encoded = (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    _write_bytes_atomic(path, encoded)
    return hashlib.sha256(encoded).hexdigest()


def read_inference_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != INFERENCE_FIELDS:
            raise ValueError("Checkpoint inference memakai schema yang berbeda.")
        rows: dict[str, dict[str, str]] = {}
        for raw in reader:
            snapshot_id = str(raw.get("snapshot_id", ""))
            if not snapshot_id or snapshot_id in rows:
                raise ValueError("Checkpoint inference memiliki snapshot_id invalid.")
            rows[snapshot_id] = dict(raw)
    return rows


def write_inference_rows(
    path: Path,
    rows: dict[str, dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=INFERENCE_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows[key] for key in sorted(rows))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def validate_inference_contract(
    contract: dict[str, Any],
    manifest_result: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    reviewed = contract.get("reviewed_manifest", {})
    request = contract.get("request_contract", {})
    development = contract.get("development", {})
    holdout = contract.get("frozen_holdout", {})
    final_test = contract.get("final_temporal_test", {})
    guardrails = contract.get("guardrails", {})

    if contract.get("schema_version") != 1:
        errors.append("Inference contract schema_version harus 1.")
    if contract.get("experiment_id") != "E2.3":
        errors.append("Inference contract harus untuk E2.3.")
    if contract.get("stage") != "DAILY_INFERENCE_CACHE":
        errors.append("Stage inference contract tidak valid.")
    if contract.get("decision_status") != (
        "PREREGISTERED_FOR_DEVELOPMENT_INFERENCE"
    ):
        errors.append("Inference development belum dipreregistrasikan.")
    if contract.get("training_performed") is not False:
        errors.append("Inference contract tidak boleh melakukan training.")
    if contract.get("policy_evaluation_performed") is not False:
        errors.append("Runner cache tidak boleh memilih kebijakan.")

    reviewed_result = manifest_result.get("manifest", {})
    if reviewed.get("sha256") != reviewed_result.get("sha256"):
        errors.append("Digest manifest pada inference contract tidak cocok.")
    if int(reviewed.get("ready_snapshot_rows", -1)) != int(
        reviewed_result.get("ready_snapshot_rows", -2)
    ):
        errors.append("Jumlah READY inference contract tidak cocok.")
    if request != {
        "endpoint": "/api/analysis/full",
        "confidence_threshold": 0.25,
        "chart_candles": 100,
        "context_candles": 300,
        "market_utc_offset_hours": 0.0,
        "include_annotated_chart": False,
        "plot_aware_mapping": True,
        "chart_datetime_field": "chart_end_open_datetime",
        "analysis_target_datetime_field": "analysis_target_market_datetime",
    }:
        errors.append("Parameter full-analysis inference berubah.")
    if set(development.get("allowed_splits", [])) != DEVELOPMENT_SPLITS:
        errors.append("Split development inference berubah.")
    if set(development.get("allowed_years", [])) != DEVELOPMENT_YEARS:
        errors.append("Tahun development inference berubah.")
    if holdout.get("year") != 2024 or (
        holdout.get("inference_allowed_before_policy_freeze") is not False
    ):
        errors.append("Frozen holdout 2024 tidak terkunci.")
    if final_test.get("year") != 2025 or final_test.get("locked") is not True:
        errors.append("Final temporal test 2025 tidak terkunci.")
    if not all(
        guardrails.get(name) is expected
        for name, expected in {
            "one_inference_per_snapshot": True,
            "standard_and_high_risk_reuse_same_response": True,
            "raw_response_is_not_ground_truth": True,
            "request_failure_is_not_no_trade": True,
            "response_contract_failure_is_not_no_trade": True,
            "high_risk_threshold_selection_allowed": False,
            "holdout_inspection_allowed": False,
            "final_2025_inference_allowed": False,
        }.items()
    ):
        errors.append("Guardrail inference contract berubah.")

    if errors:
        raise ValueError("Inference contract INVALID:\n- " + "\n- ".join(errors))
    return request


def validate_render_contract(
    *,
    manifest_rows: list[dict[str, Any]],
    manifest_digest_sha256: str,
    render_rows: dict[str, dict[str, str]],
    render_summary: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    errors: list[str] = []
    reviewed = contract["reviewed_manifest"]
    expected_ready = int(reviewed["ready_snapshot_rows"])
    ready_ids = {
        str(row["snapshot_id"])
        for row in manifest_rows
        if row["status"] == "READY"
    }
    counts = render_summary.get("render_status_counts", {})

    if render_summary.get("stage") != "DAILY_SNAPSHOT_RENDER":
        errors.append("Render summary stage tidak valid.")
    if render_summary.get("training_performed") is not False:
        errors.append("Renderer tercatat melakukan training.")
    if render_summary.get("inference_performed") is not False:
        errors.append("Renderer tercatat melakukan inference.")
    if render_summary.get("manifest_digest_sha256") != manifest_digest_sha256:
        errors.append("Digest render summary berbeda dari manifest.")
    if render_summary.get("complete_for_reviewed_manifest") is not True:
        errors.append("Render 10.230 snapshot belum lengkap.")
    if int(render_summary.get("manifest_ready_rows", -1)) != expected_ready:
        errors.append("Jumlah READY pada render summary tidak cocok.")
    if int(render_summary.get("cumulative_audit_rows", -1)) != expected_ready:
        errors.append("Jumlah audit render belum sama dengan jumlah READY.")
    if int(counts.get("FAILED", 0)) != 0:
        errors.append("Render summary masih memiliki kegagalan.")
    if len(ready_ids) != expected_ready:
        errors.append("Jumlah READY manifest berbeda dari inference contract.")
    if set(render_rows) != ready_ids:
        errors.append("Audit render tidak tepat mencakup seluruh row READY.")

    accepted = {"RENDERED", "REUSED"}
    if any(
        row.get("render_status") not in accepted
        or row.get("manifest_digest_sha256") != manifest_digest_sha256
        for row in render_rows.values()
    ):
        errors.append("Audit render memiliki status atau lineage yang tidak valid.")

    if errors:
        raise ValueError("Completed render INVALID:\n- " + "\n- ".join(errors))


def select_development_rows(
    manifest_rows: list[dict[str, Any]],
    *,
    years: list[int] | None,
    timeframes: list[str] | None,
    slots: list[str] | None,
    snapshot_ids: list[str] | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    selected_years = set(years or sorted(DEVELOPMENT_YEARS))
    selected = [
        dict(row)
        for row in manifest_rows
        if row["status"] == "READY"
        and row["evaluation_split"] in DEVELOPMENT_SPLITS
        and int(row["year"]) in selected_years
    ]
    if timeframes:
        values = set(timeframes)
        selected = [row for row in selected if row["timeframe"] in values]
    if slots:
        values = set(slots)
        selected = [row for row in selected if row["slot"] in values]
    if snapshot_ids:
        requested = set(snapshot_ids)
        selected = [row for row in selected if row["snapshot_id"] in requested]
        found = {str(row["snapshot_id"]) for row in selected}
        missing = requested.difference(found)
        if missing:
            raise ValueError(
                "Snapshot ID tidak ditemukan pada population development READY: "
                + ", ".join(sorted(missing))
            )
    selected.sort(key=lambda row: str(row["snapshot_id"]))
    if limit is not None:
        selected = selected[: int(limit)]
    if not selected:
        raise ValueError("Tidak ada snapshot development READY yang cocok.")
    return selected


def _safe_experiment_path(experiment_dir: Path, relative_value: str) -> Path:
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Path artifact tidak aman: {relative_value}")
    root = experiment_dir.resolve()
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError(f"Path artifact keluar dari experiment dir: {relative_value}")
    return target


def attach_verified_images(
    rows: list[dict[str, Any]],
    *,
    experiment_dir: Path,
    render_rows: dict[str, dict[str, str]],
    manifest_digest_sha256: str,
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    reviewed = contract["reviewed_manifest"]
    expected_width = int(reviewed["canonical_width"])
    expected_height = int(reviewed["canonical_height"])
    verified: list[dict[str, Any]] = []

    for raw in rows:
        row = dict(raw)
        snapshot_id = str(row["snapshot_id"])
        render = render_rows.get(snapshot_id)
        if render is None:
            raise ValueError(f"{snapshot_id}: audit render tidak ditemukan.")
        if render.get("image_path") != row["planned_image_path"]:
            raise ValueError(f"{snapshot_id}: image path berbeda dari manifest.")
        if render.get("manifest_digest_sha256") != manifest_digest_sha256:
            raise ValueError(f"{snapshot_id}: lineage render berbeda.")
        if int(render.get("width", -1)) != expected_width or int(
            render.get("height", -1)
        ) != expected_height:
            raise ValueError(f"{snapshot_id}: dimensi render tidak kanonis.")
        expected_hash = str(render.get("image_sha256", ""))
        if len(expected_hash) != 64:
            raise ValueError(f"{snapshot_id}: SHA256 render tidak lengkap.")

        image_path = _safe_experiment_path(
            experiment_dir,
            str(row["planned_image_path"]),
        )
        if not image_path.is_file():
            raise FileNotFoundError(f"{snapshot_id}: PNG tidak ditemukan: {image_path}")
        if file_sha256(image_path) != expected_hash:
            raise ValueError(f"{snapshot_id}: SHA256 PNG berbeda dari audit render.")

        row["_image_path"] = image_path
        row["_image_sha256"] = expected_hash
        verified.append(row)
    return verified


def _datetime_equal(left: Any, right: Any) -> bool:
    try:
        first = datetime.fromisoformat(str(left).replace("Z", "+00:00"))
        second = datetime.fromisoformat(str(right).replace("Z", "+00:00"))
    except ValueError:
        return False
    return first == second


def validate_full_analysis_response(
    payload: dict[str, Any],
    manifest_row: dict[str, Any],
) -> None:
    errors: list[str] = []
    metadata = payload.get("metadata")
    context = payload.get("ohlcv_context")
    clock = payload.get("analysis_clock")
    detection = payload.get("detection")
    annotated = payload.get("annotated_chart")
    price_conversion = payload.get("price_conversion")

    if not isinstance(metadata, dict):
        errors.append("metadata response tidak tersedia.")
        metadata = {}
    if metadata.get("pair") != manifest_row["pair"]:
        errors.append("Pair response berbeda dari manifest.")
    if metadata.get("timeframe") != manifest_row["timeframe"]:
        errors.append("Timeframe response berbeda dari manifest.")
    if not _datetime_equal(
        metadata.get("chart_datetime"),
        manifest_row["chart_end_open_datetime"],
    ):
        errors.append("chart_datetime response berbeda dari cutoff manifest.")

    if not isinstance(context, dict) or context.get("status") != "LOADED":
        errors.append("OHLCV context response tidak berstatus LOADED.")
        context = {}
    if not _datetime_equal(
        context.get("chart_end_datetime"),
        manifest_row["chart_end_open_datetime"],
    ):
        errors.append("OHLCV chart_end_datetime berbeda dari manifest.")

    if not isinstance(clock, dict):
        errors.append("analysis_clock response tidak tersedia.")
        clock = {}
    if clock.get("status") != "ANALYSIS_TARGET_VALIDATED":
        errors.append("analysis target tidak berstatus tervalidasi.")
    if clock.get("datetime_source") != "ANALYSIS_TARGET_OVERRIDE":
        errors.append("analysis target override tidak diterapkan.")
    if clock.get("anti_lookahead_validated") is not True:
        errors.append("anti-lookahead analysis target tidak tervalidasi.")
    if not _datetime_equal(
        clock.get("effective_datetime"),
        manifest_row["analysis_target_market_datetime"],
    ):
        errors.append("Jam efektif sesi berbeda dari analysis target manifest.")

    if not isinstance(detection, dict) or float(
        detection.get("confidence_threshold", -1.0)
    ) != 0.25:
        errors.append("Threshold YOLO response bukan baseline 0.25.")
    if not isinstance(annotated, dict) or annotated.get("status") != "SKIPPED":
        errors.append("Batch inference tidak boleh membawa annotated chart.")
    if isinstance(price_conversion, dict) and price_conversion.get(
        "status"
    ) == "MAPPED":
        if price_conversion.get("plot_aware_mapping_requested") is not True:
            errors.append("Mapped setup tidak memakai permintaan plot-aware.")
    if not str(payload.get("pipeline_status", "")).strip():
        errors.append("pipeline_status response kosong.")
    if int(payload.get("width", -1)) != 691 or int(payload.get("height", -1)) != 482:
        errors.append("Dimensi gambar pada response tidak kanonis.")

    if errors:
        raise ValueError("Full-analysis response INVALID: " + "; ".join(errors))


def _response_relative_path(row: dict[str, Any]) -> str:
    snapshot_id = str(row["snapshot_id"])
    if not SAFE_SNAPSHOT_ID.fullmatch(snapshot_id):
        raise ValueError(f"snapshot_id tidak aman untuk cache: {snapshot_id}")
    return (
        Path("inference")
        / "responses"
        / str(row["evaluation_split"])
        / str(row["year"])
        / str(row["timeframe"])
        / f"{snapshot_id}.json"
    ).as_posix()


def _request_parameters(
    row: dict[str, Any],
    request_contract: dict[str, Any],
) -> dict[str, Any]:
    return {
        "confidence_threshold": request_contract["confidence_threshold"],
        "pair": row["pair"],
        "timeframe": row["timeframe"],
        "chart_datetime": row["chart_end_open_datetime"],
        "analysis_target_datetime": row["analysis_target_market_datetime"],
        "chart_candles": request_contract["chart_candles"],
        "context_candles": request_contract["context_candles"],
        "market_utc_offset_hours": request_contract[
            "market_utc_offset_hours"
        ],
        "include_annotated_chart": request_contract[
            "include_annotated_chart"
        ],
        "plot_aware_mapping": request_contract["plot_aware_mapping"],
    }


def build_response_envelope(
    *,
    row: dict[str, Any],
    payload: dict[str, Any],
    request_parameters: dict[str, Any],
    http_status: int,
    latency_ms: float,
    manifest_digest_sha256: str,
    inference_contract_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "DAILY_INFERENCE_CACHE",
        "runner_version": RUNNER_VERSION,
        "snapshot_id": row["snapshot_id"],
        "evaluation_split": row["evaluation_split"],
        "manifest_digest_sha256": manifest_digest_sha256,
        "inference_contract_sha256": inference_contract_sha256,
        "image_path": row["planned_image_path"],
        "image_sha256": row["_image_sha256"],
        "request": request_parameters,
        "http_status": http_status,
        "latency_ms": round(float(latency_ms), 3),
        "received_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_performed": False,
        "response": payload,
    }


def validate_response_envelope(
    envelope: dict[str, Any],
    *,
    row: dict[str, Any],
    request_parameters: dict[str, Any],
    manifest_digest_sha256: str,
    inference_contract_sha256: str,
) -> dict[str, Any]:
    errors: list[str] = []
    if envelope.get("schema_version") != 1:
        errors.append("schema envelope berbeda.")
    if envelope.get("stage") != "DAILY_INFERENCE_CACHE":
        errors.append("stage envelope berbeda.")
    if envelope.get("snapshot_id") != row["snapshot_id"]:
        errors.append("snapshot_id envelope berbeda.")
    if envelope.get("evaluation_split") != row["evaluation_split"]:
        errors.append("split envelope berbeda.")
    if envelope.get("manifest_digest_sha256") != manifest_digest_sha256:
        errors.append("manifest digest envelope berbeda.")
    if envelope.get("inference_contract_sha256") != inference_contract_sha256:
        errors.append("contract digest envelope berbeda.")
    if envelope.get("image_path") != row["planned_image_path"]:
        errors.append("image path envelope berbeda.")
    if envelope.get("image_sha256") != row["_image_sha256"]:
        errors.append("image digest envelope berbeda.")
    if envelope.get("request") != request_parameters:
        errors.append("parameter request envelope berbeda.")
    if envelope.get("training_performed") is not False:
        errors.append("envelope tidak boleh mencatat training.")
    if int(envelope.get("http_status", 0)) != 200:
        errors.append("HTTP status envelope bukan 200.")
    payload = envelope.get("response")
    if not isinstance(payload, dict):
        errors.append("payload response envelope bukan object.")
        payload = {}
    if errors:
        raise ValueError("Cached response envelope INVALID: " + "; ".join(errors))
    validate_full_analysis_response(payload, row)
    return payload


def _json_list(value: Any) -> str:
    if not isinstance(value, list):
        value = []
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_success_row(
    *,
    row: dict[str, Any],
    payload: dict[str, Any],
    envelope: dict[str, Any],
    response_path: str,
    response_sha256: str,
    cache_status: str,
    manifest_digest_sha256: str,
    inference_contract_sha256: str,
) -> dict[str, Any]:
    recommendation = payload.get("recommendation") or {}
    execution = payload.get("execution_gate") or {}
    detection = payload.get("detection") or {}
    pairing = payload.get("pairing") or {}
    regime = payload.get("regime") or {}
    conversion = payload.get("price_conversion") or {}
    clock = payload.get("analysis_clock") or {}

    return {
        "snapshot_id": row["snapshot_id"],
        "event_id": row["event_id"],
        "daily_group_id": row["daily_group_id"],
        "evaluation_split": row["evaluation_split"],
        "pair": row["pair"],
        "year": row["year"],
        "trading_date_utc": row["trading_date_utc"],
        "slot": row["slot"],
        "timeframe": row["timeframe"],
        "chart_datetime": row["chart_end_open_datetime"],
        "analysis_target_datetime": row["analysis_target_market_datetime"],
        "image_path": row["planned_image_path"],
        "image_sha256": row["_image_sha256"],
        "manifest_digest_sha256": manifest_digest_sha256,
        "inference_contract_sha256": inference_contract_sha256,
        "request_status": "SUCCESS",
        "cache_status": cache_status,
        "http_status": envelope.get("http_status", ""),
        "latency_ms": envelope.get("latency_ms", ""),
        "response_path": response_path,
        "response_sha256": response_sha256,
        "pipeline_status": payload.get("pipeline_status", ""),
        "analysis_clock_status": clock.get("status", ""),
        "analysis_clock_validated": int(
            clock.get("anti_lookahead_validated") is True
        ),
        "public_decision": recommendation.get("decision", ""),
        "internal_decision": recommendation.get("internal_decision", ""),
        "execution_status": execution.get("execution_status", ""),
        "final_decision_ready": int(
            bool(execution.get("final_decision_ready", False))
        ),
        "detection_count": detection.get("total", 0),
        "pair_count": pairing.get("total_pairs", 0),
        "regime_label": regime.get("label", regime.get("regime", "")),
        "regime_confidence": regime.get("confidence", ""),
        "mapping_status": conversion.get("status", ""),
        "mapping_mode": conversion.get("mapping_index_mode", ""),
        "mapping_confidence": conversion.get("mapping_confidence", ""),
        "mapping_provisional": int(
            bool(conversion.get("mapping_provisional", False))
        ),
        "mapping_calibration_applied": int(
            bool(conversion.get("mapping_calibration_applied", False))
        ),
        "advanced_score": execution.get("advanced_score", ""),
        "session_score": execution.get("session_score", ""),
        "risk_reward_ratio": execution.get("risk_reward_ratio", ""),
        "entry_distance_atr": execution.get("entry_distance_atr", ""),
        "blockers_json": _json_list(execution.get("blockers")),
        "warnings_json": _json_list(execution.get("warnings")),
        "yolo_model_path": detection.get("model_path", ""),
        "error": "",
        "inferred_at_utc": envelope.get("received_at_utc", ""),
    }


def build_error_row(
    *,
    row: dict[str, Any],
    request_status: str,
    error: str,
    manifest_digest_sha256: str,
    inference_contract_sha256: str,
    http_status: int | None = None,
    latency_ms: float | None = None,
    response_path: str = "",
    response_sha256: str = "",
) -> dict[str, Any]:
    result = {field: "" for field in INFERENCE_FIELDS}
    result.update(
        {
            "snapshot_id": row["snapshot_id"],
            "event_id": row["event_id"],
            "daily_group_id": row["daily_group_id"],
            "evaluation_split": row["evaluation_split"],
            "pair": row["pair"],
            "year": row["year"],
            "trading_date_utc": row["trading_date_utc"],
            "slot": row["slot"],
            "timeframe": row["timeframe"],
            "chart_datetime": row["chart_end_open_datetime"],
            "analysis_target_datetime": row["analysis_target_market_datetime"],
            "image_path": row["planned_image_path"],
            "image_sha256": row["_image_sha256"],
            "manifest_digest_sha256": manifest_digest_sha256,
            "inference_contract_sha256": inference_contract_sha256,
            "request_status": request_status,
            "cache_status": "",
            "http_status": "" if http_status is None else http_status,
            "latency_ms": (
                ""
                if latency_ms is None
                else round(float(latency_ms), 3)
            ),
            "response_path": response_path,
            "response_sha256": response_sha256,
            "error": str(error),
            "inferred_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    return result


def _load_envelope(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"Cached response tidak ditemukan: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Cached response JSON rusak: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Cached response bukan JSON object: {path}")
    return payload


def recover_cached_response(
    *,
    experiment_dir: Path,
    row: dict[str, Any],
    existing_row: dict[str, str] | None,
    request_parameters: dict[str, Any],
    manifest_digest_sha256: str,
    inference_contract_sha256: str,
) -> dict[str, Any] | None:
    response_relative = _response_relative_path(row)
    response_path = _safe_experiment_path(experiment_dir, response_relative)

    if existing_row is not None:
        if existing_row.get("manifest_digest_sha256") != manifest_digest_sha256:
            raise ValueError(f"{row['snapshot_id']}: checkpoint manifest berubah.")
        if existing_row.get("inference_contract_sha256") != (
            inference_contract_sha256
        ):
            raise ValueError(f"{row['snapshot_id']}: checkpoint contract berubah.")
        if existing_row.get("image_sha256") != row["_image_sha256"]:
            raise ValueError(f"{row['snapshot_id']}: checkpoint image berubah.")
        if existing_row.get("response_path") and existing_row.get(
            "response_path"
        ) != response_relative:
            raise ValueError(f"{row['snapshot_id']}: response path berubah.")
        if existing_row.get("request_status") != "SUCCESS":
            return None

    if not response_path.exists():
        if existing_row is not None and existing_row.get("request_status") == "SUCCESS":
            raise ValueError(f"{row['snapshot_id']}: cached response hilang.")
        return None

    actual_sha256 = file_sha256(response_path)
    if existing_row is not None and existing_row.get("response_sha256") != (
        actual_sha256
    ):
        raise ValueError(f"{row['snapshot_id']}: SHA256 cached response berubah.")

    envelope = _load_envelope(response_path)
    payload = validate_response_envelope(
        envelope,
        row=row,
        request_parameters=request_parameters,
        manifest_digest_sha256=manifest_digest_sha256,
        inference_contract_sha256=inference_contract_sha256,
    )
    return build_success_row(
        row=row,
        payload=payload,
        envelope=envelope,
        response_path=response_relative,
        response_sha256=str(actual_sha256),
        cache_status=(
            "REUSED" if existing_row is not None else "RECOVERED"
        ),
        manifest_digest_sha256=manifest_digest_sha256,
        inference_contract_sha256=inference_contract_sha256,
    )


def _pipeline_content_digest() -> tuple[str, int]:
    paths = sorted(
        (PROJECT_ROOT / "backend" / "app").rglob("*.py")
    )
    paths.extend(
        path
        for path in [
            Path(__file__).resolve(),
            PROJECT_ROOT / "ai" / "scripts" / "audit_decision_coverage.py",
            PROJECT_ROOT / "config" / "project_contract.json",
            PROJECT_ROOT
            / "ai"
            / "classification"
            / "models"
            / "ensemble"
            / "ensemble_config.json",
        ]
        if path.is_file()
    )
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest(), len(paths)


def _git_lineage() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {"git_commit": None, "git_dirty": None}
    return {
        "git_commit": (
            commit.stdout.strip() if commit.returncode == 0 else None
        ),
        "git_dirty": (
            bool(dirty.stdout.strip()) if dirty.returncode == 0 else None
        ),
    }


def build_run_config(
    *,
    args: argparse.Namespace,
    manifest_digest_sha256: str,
    inference_contract_sha256: str,
    request_contract: dict[str, Any],
    render_summary_path: Path,
    render_rows_path: Path,
    pipeline_content_sha256: str,
    pipeline_source_files: int,
    selected_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    config = {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "DAILY_INFERENCE_CACHE",
        "runner_version": RUNNER_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_performed": False,
        "policy_evaluation_performed": False,
        "base_url": str(_argument(args, "base_url", "")).rstrip("/"),
        "manifest_digest_sha256": manifest_digest_sha256,
        "inference_contract_sha256": inference_contract_sha256,
        "render_summary_sha256": file_sha256(render_summary_path),
        "render_rows_sha256_at_start": file_sha256(render_rows_path),
        "pipeline_content_sha256": pipeline_content_sha256,
        "pipeline_source_files": pipeline_source_files,
        "request_contract": request_contract,
        "last_invocation": {
            "years": sorted(
                set(_argument(args, "years", None) or DEVELOPMENT_YEARS)
            ),
            "timeframes": sorted(
                set(_argument(args, "timeframes", None) or [])
            ),
            "slots": sorted(set(_argument(args, "slots", None) or [])),
            "snapshot_ids": sorted(
                set(_argument(args, "snapshot_ids", None) or [])
            ),
            "limit": _argument(args, "limit", None),
            "selected_rows": len(selected_rows),
        },
        "raw_response_reuse": {
            "standard_policy": True,
            "high_risk_policy": True,
            "one_inference_per_snapshot": True,
        },
    }
    config.update(_git_lineage())
    return config


def ensure_resume_compatible(
    existing: dict[str, Any],
    current: dict[str, Any],
) -> None:
    keys = (
        "schema_version",
        "experiment_id",
        "stage",
        "runner_version",
        "manifest_digest_sha256",
        "inference_contract_sha256",
        "render_summary_sha256",
        "render_rows_sha256_at_start",
        "pipeline_content_sha256",
        "request_contract",
    )
    mismatched = [key for key in keys if existing.get(key) != current.get(key)]
    if mismatched:
        raise ValueError(
            "Konfigurasi --resume berbeda pada: " + ", ".join(mismatched)
        )


def _float_values(
    rows: list[dict[str, Any]],
    field: str,
) -> list[float]:
    values: list[float] = []
    for row in rows:
        raw = row.get(field)
        if raw in (None, ""):
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return round(ordered[index], 3)


def build_summary(
    *,
    all_manifest_rows: list[dict[str, Any]],
    inference_rows: dict[str, dict[str, Any]],
    manifest_digest_sha256: str,
    inference_contract_sha256: str,
    selected_count: int,
) -> dict[str, Any]:
    cumulative = list(inference_rows.values())
    successful = [
        row for row in cumulative if row.get("request_status") == "SUCCESS"
    ]
    eligible_ids = {
        str(row["snapshot_id"])
        for row in all_manifest_rows
        if row["status"] == "READY"
        and row["evaluation_split"] in DEVELOPMENT_SPLITS
        and int(row["year"]) in DEVELOPMENT_YEARS
    }
    successful_ids = {
        str(row.get("snapshot_id", ""))
        for row in successful
        if row.get("snapshot_id")
    }
    failures = [
        row for row in cumulative if row.get("request_status") != "SUCCESS"
    ]

    split_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"rows": 0, "success": 0, "errors": 0}
    )
    for row in cumulative:
        split = str(row.get("evaluation_split", "UNKNOWN"))
        split_counts[split]["rows"] += 1
        if row.get("request_status") == "SUCCESS":
            split_counts[split]["success"] += 1
        else:
            split_counts[split]["errors"] += 1

    latencies = _float_values(successful, "latency_ms")
    return {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "DAILY_INFERENCE_CACHE",
        "runner_version": RUNNER_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_performed": False,
        "inference_performed": bool(cumulative),
        "policy_evaluation_performed": False,
        "manifest_digest_sha256": manifest_digest_sha256,
        "inference_contract_sha256": inference_contract_sha256,
        "selected_rows_this_invocation": selected_count,
        "eligible_policy_development_rows": len(eligible_ids),
        "cumulative_inference_rows": len(cumulative),
        "successful_inference_rows": len(successful),
        "failed_inference_rows": len(failures),
        "remaining_policy_development_rows": len(
            eligible_ids.difference(successful_ids)
        ),
        "request_status_counts": dict(
            sorted(Counter(str(row.get("request_status", "")) for row in cumulative).items())
        ),
        "cache_status_counts": dict(
            sorted(Counter(str(row.get("cache_status", "")) for row in successful).items())
        ),
        "public_decision_counts": dict(
            sorted(Counter(str(row.get("public_decision", "")) for row in successful).items())
        ),
        "split_counts": dict(sorted(split_counts.items())),
        "latency_ms": {
            "mean": (
                round(sum(latencies) / len(latencies), 3)
                if latencies
                else None
            ),
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "maximum": round(max(latencies), 3) if latencies else None,
        },
        "yolo_model_paths": sorted(
            {
                str(row.get("yolo_model_path", ""))
                for row in successful
                if row.get("yolo_model_path")
            }
        ),
        "frozen_holdout_inference_rows": sum(
            int(row.get("year", 0)) == 2024 for row in cumulative
        ),
        "final_2025_inference_rows": sum(
            int(row.get("year", 0)) == 2025 for row in cumulative
        ),
        "complete_for_policy_development": (
            successful_ids == eligible_ids
            and not failures
            and bool(eligible_ids)
        ),
        "raw_response_reusable_by_both_policy_arms": True,
        "raw_response_is_ground_truth": False,
    }


def _persist_checkpoint(
    *,
    rows_path: Path,
    summary_path: Path,
    inference_rows: dict[str, dict[str, Any]],
    manifest_rows: list[dict[str, Any]],
    manifest_digest_sha256: str,
    inference_contract_sha256: str,
    selected_count: int,
) -> None:
    write_inference_rows(rows_path, inference_rows)
    write_json_atomic(
        summary_path,
        build_summary(
            all_manifest_rows=manifest_rows,
            inference_rows=inference_rows,
            manifest_digest_sha256=manifest_digest_sha256,
            inference_contract_sha256=inference_contract_sha256,
            selected_count=selected_count,
        ),
    )


def run(
    args: argparse.Namespace,
    *,
    request_function: RequestFunction = request_analysis,
    health_function: HealthFunction = check_health,
) -> dict[str, Any]:
    validate_args(args)
    experiment_dir = Path(args.experiment_dir).resolve()
    manifest_path = experiment_dir / "input" / "daily_snapshot_manifest.csv"
    manifest_summary_path = (
        experiment_dir / "input" / "daily_manifest_summary.json"
    )
    manifest_run_config_path = experiment_dir / "input" / "run_config.json"
    render_rows_path = (
        experiment_dir / "render" / "daily_snapshot_render_rows.csv"
    )
    render_summary_path = (
        experiment_dir / "render" / "daily_snapshot_render_summary.json"
    )
    inference_dir = experiment_dir / "inference"
    rows_path = inference_dir / "daily_snapshot_inference_rows.csv"
    summary_path = inference_dir / "daily_snapshot_inference_summary.json"
    run_config_path = inference_dir / "run_config.json"

    manifest_rows = read_manifest(manifest_path)
    manifest_summary = read_json(manifest_summary_path)
    manifest_run_config = read_json(manifest_run_config_path)
    manifest_result = read_json(Path(args.manifest_result))
    manifest_digest_sha256 = validate_reviewed_manifest(
        manifest_rows,
        manifest_summary,
        manifest_run_config,
        manifest_result,
    )
    contract_path = Path(args.contract)
    contract = read_json(contract_path)
    request_contract = validate_inference_contract(contract, manifest_result)
    inference_contract_sha256 = str(file_sha256(contract_path))

    render_rows = read_render_rows(render_rows_path)
    render_summary = read_json(render_summary_path)
    validate_render_contract(
        manifest_rows=manifest_rows,
        manifest_digest_sha256=manifest_digest_sha256,
        render_rows=render_rows,
        render_summary=render_summary,
        contract=contract,
    )

    selected = select_development_rows(
        manifest_rows,
        years=_argument(args, "years", None),
        timeframes=_argument(args, "timeframes", None),
        slots=_argument(args, "slots", None),
        snapshot_ids=_argument(args, "snapshot_ids", None),
        limit=_argument(args, "limit", None),
    )
    selected = attach_verified_images(
        selected,
        experiment_dir=experiment_dir,
        render_rows=render_rows,
        manifest_digest_sha256=manifest_digest_sha256,
        contract=contract,
    )

    pipeline_content_sha256, pipeline_source_files = _pipeline_content_digest()
    current_run_config = build_run_config(
        args=args,
        manifest_digest_sha256=manifest_digest_sha256,
        inference_contract_sha256=inference_contract_sha256,
        request_contract=request_contract,
        render_summary_path=render_summary_path,
        render_rows_path=render_rows_path,
        pipeline_content_sha256=pipeline_content_sha256,
        pipeline_source_files=pipeline_source_files,
        selected_rows=selected,
    )

    resume = bool(_argument(args, "resume", False))
    artifacts_exist = (
        rows_path.exists()
        or run_config_path.exists()
        or (inference_dir / "responses").exists()
    )
    if artifacts_exist and not resume:
        raise FileExistsError(
            "Artifact inference sudah ada. Gunakan --resume agar cache diverifikasi."
        )
    if resume and artifacts_exist and not run_config_path.exists():
        raise ValueError(
            "Artifact inference ada tetapi run_config.json hilang; "
            "lineage cache tidak dapat diverifikasi."
        )

    if resume and run_config_path.exists():
        existing_config = read_json(run_config_path)
        ensure_resume_compatible(existing_config, current_run_config)
        current_run_config["created_at_utc"] = existing_config.get(
            "created_at_utc",
            current_run_config["created_at_utc"],
        )
        current_run_config["initial_git_commit"] = existing_config.get(
            "initial_git_commit",
            existing_config.get("git_commit"),
        )
    else:
        current_run_config["initial_git_commit"] = current_run_config.get(
            "git_commit"
        )

    inference_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(run_config_path, current_run_config)
    inference_rows = read_inference_rows(rows_path) if resume else {}

    manifest_by_id = {
        str(row["snapshot_id"]): row
        for row in manifest_rows
        if row["status"] == "READY"
    }
    for snapshot_id, existing in inference_rows.items():
        manifest_row = manifest_by_id.get(snapshot_id)
        if manifest_row is None:
            raise ValueError(
                f"{snapshot_id}: checkpoint tidak ada pada manifest READY."
            )
        if int(manifest_row["year"]) not in DEVELOPMENT_YEARS:
            raise ValueError(
                f"{snapshot_id}: checkpoint menyentuh holdout/final yang terkunci."
            )

    selected_ids = {str(row["snapshot_id"]) for row in selected}
    outside_selected = attach_verified_images(
        [
            manifest_by_id[snapshot_id]
            for snapshot_id in inference_rows
            if snapshot_id not in selected_ids
        ],
        experiment_dir=experiment_dir,
        render_rows=render_rows,
        manifest_digest_sha256=manifest_digest_sha256,
        contract=contract,
    )
    for row in outside_selected:
        snapshot_id = str(row["snapshot_id"])
        existing = inference_rows[snapshot_id]
        recovered = recover_cached_response(
            experiment_dir=experiment_dir,
            row=row,
            existing_row=existing,
            request_parameters=_request_parameters(row, request_contract),
            manifest_digest_sha256=manifest_digest_sha256,
            inference_contract_sha256=inference_contract_sha256,
        )
        if existing.get("request_status") == "SUCCESS":
            if recovered is None:
                raise ValueError(
                    f"{snapshot_id}: checkpoint SUCCESS tidak dapat dipulihkan."
                )
            inference_rows[snapshot_id] = recovered

    cached = 0
    pending: list[dict[str, Any]] = []
    for row in selected:
        request_parameters = _request_parameters(row, request_contract)
        recovered = recover_cached_response(
            experiment_dir=experiment_dir,
            row=row,
            existing_row=inference_rows.get(str(row["snapshot_id"])),
            request_parameters=request_parameters,
            manifest_digest_sha256=manifest_digest_sha256,
            inference_contract_sha256=inference_contract_sha256,
        )
        if recovered is None:
            pending.append(row)
        else:
            inference_rows[str(row["snapshot_id"])] = recovered
            cached += 1

    if pending and not bool(_argument(args, "skip_health_check", False)):
        health_function(
            str(args.base_url),
            float(_argument(args, "timeout_seconds", 300.0)),
        )

    print(
        f"Selected: {len(selected)} | Cached: {cached} | Pending: {len(pending)}"
    )
    print(f"Output: {inference_dir}")
    if cached:
        _persist_checkpoint(
            rows_path=rows_path,
            summary_path=summary_path,
            inference_rows=inference_rows,
            manifest_rows=manifest_rows,
            manifest_digest_sha256=manifest_digest_sha256,
            inference_contract_sha256=inference_contract_sha256,
            selected_count=len(selected),
        )

    consecutive_errors = 0
    stopped_due_to_errors = False
    interrupted = False
    processed = 0
    checkpoint_every = int(_argument(args, "checkpoint_every", 10))
    progress_every = int(_argument(args, "progress_every", 1))

    try:
        for index, row in enumerate(pending, start=1):
            snapshot_id = str(row["snapshot_id"])
            request_parameters = _request_parameters(row, request_contract)
            response_relative = _response_relative_path(row)
            response_path = _safe_experiment_path(
                experiment_dir,
                response_relative,
            )
            started = time.perf_counter()
            try:
                payload, http_status = request_function(
                    base_url=str(args.base_url),
                    sample={
                        "image_path": str(row["_image_path"]),
                        "pair": row["pair"],
                        "timeframe": row["timeframe"],
                        "chart_datetime": row["chart_end_open_datetime"],
                    },
                    confidence_threshold=request_contract[
                        "confidence_threshold"
                    ],
                    chart_candles=request_contract["chart_candles"],
                    context_candles=request_contract["context_candles"],
                    utc_offset=request_contract["market_utc_offset_hours"],
                    include_annotated_chart=False,
                    plot_aware_mapping=True,
                    timeout_seconds=float(
                        _argument(args, "timeout_seconds", 300.0)
                    ),
                    analysis_target_datetime=row[
                        "analysis_target_market_datetime"
                    ],
                )
                latency_ms = (time.perf_counter() - started) * 1000.0
                if int(http_status) != 200:
                    raise ValueError(
                        f"Full-analysis HTTP status bukan 200: {http_status}"
                    )
                validate_full_analysis_response(payload, row)
                envelope = build_response_envelope(
                    row=row,
                    payload=payload,
                    request_parameters=request_parameters,
                    http_status=http_status,
                    latency_ms=latency_ms,
                    manifest_digest_sha256=manifest_digest_sha256,
                    inference_contract_sha256=inference_contract_sha256,
                )
                response_sha256 = write_json_atomic(response_path, envelope)
                inference_row = build_success_row(
                    row=row,
                    payload=payload,
                    envelope=envelope,
                    response_path=response_relative,
                    response_sha256=response_sha256,
                    cache_status="WRITTEN",
                    manifest_digest_sha256=manifest_digest_sha256,
                    inference_contract_sha256=inference_contract_sha256,
                )
                consecutive_errors = 0
                status_text = (
                    f"{inference_row['public_decision']} | "
                    f"det={inference_row['detection_count']} "
                    f"pair={inference_row['pair_count']} | "
                    f"{latency_ms:.0f} ms"
                )

            except AuditRequestError as error:
                latency_ms = (time.perf_counter() - started) * 1000.0
                inference_row = build_error_row(
                    row=row,
                    request_status="REQUEST_ERROR",
                    error=str(error),
                    http_status=error.status_code,
                    latency_ms=latency_ms,
                    manifest_digest_sha256=manifest_digest_sha256,
                    inference_contract_sha256=inference_contract_sha256,
                )
                consecutive_errors += 1
                status_text = f"REQUEST_ERROR: {error}"

            except (OSError, TypeError, ValueError) as error:
                latency_ms = (time.perf_counter() - started) * 1000.0
                inference_row = build_error_row(
                    row=row,
                    request_status="RESPONSE_CONTRACT_ERROR",
                    error=str(error),
                    latency_ms=latency_ms,
                    manifest_digest_sha256=manifest_digest_sha256,
                    inference_contract_sha256=inference_contract_sha256,
                )
                consecutive_errors += 1
                status_text = f"RESPONSE_CONTRACT_ERROR: {error}"

            inference_rows[snapshot_id] = inference_row
            processed += 1
            if (
                processed % checkpoint_every == 0
                or processed == len(pending)
                or inference_row["request_status"] != "SUCCESS"
            ):
                _persist_checkpoint(
                    rows_path=rows_path,
                    summary_path=summary_path,
                    inference_rows=inference_rows,
                    manifest_rows=manifest_rows,
                    manifest_digest_sha256=manifest_digest_sha256,
                    inference_contract_sha256=inference_contract_sha256,
                    selected_count=len(selected),
                )
            if (
                processed == 1
                or processed % progress_every == 0
                or processed == len(pending)
                or inference_row["request_status"] != "SUCCESS"
            ):
                print(f"[{index}/{len(pending)}] {snapshot_id} -> {status_text}")

            if (
                inference_row["request_status"] != "SUCCESS"
                and bool(_argument(args, "fail_fast", False))
            ):
                raise RuntimeError(
                    f"{snapshot_id}: {inference_row['request_status']}: "
                    f"{inference_row['error']}"
                )
            max_errors = int(_argument(args, "max_errors", 5))
            if max_errors and consecutive_errors >= max_errors:
                stopped_due_to_errors = True
                print(
                    "Inference dihentikan setelah "
                    f"{consecutive_errors} error berturut-turut."
                )
                break

    except KeyboardInterrupt:
        interrupted = True
        print("\nInference dihentikan pengguna; checkpoint tetap disimpan.")

    _persist_checkpoint(
        rows_path=rows_path,
        summary_path=summary_path,
        inference_rows=inference_rows,
        manifest_rows=manifest_rows,
        manifest_digest_sha256=manifest_digest_sha256,
        inference_contract_sha256=inference_contract_sha256,
        selected_count=len(selected),
    )
    current_run_config["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    current_run_config["interrupted"] = interrupted
    current_run_config["stopped_due_to_errors"] = stopped_due_to_errors
    current_run_config["cumulative_inference_rows"] = len(inference_rows)
    write_json_atomic(run_config_path, current_run_config)

    summary = read_json(summary_path)
    print(f"Rows: {rows_path}")
    print(f"Summary: {summary_path}")
    print(f"Raw responses: {inference_dir / 'responses'}")
    if interrupted or stopped_due_to_errors:
        print("Jalankan command yang sama dengan --resume untuk melanjutkan.")

    return {
        "exit_code": 130 if interrupted else (3 if stopped_due_to_errors else 0),
        "rows_path": rows_path,
        "summary_path": summary_path,
        "run_config_path": run_config_path,
        "summary": summary,
        "inference_rows": inference_rows,
    }


def main() -> int:
    try:
        result = run(parse_args())
        return int(result["exit_code"])
    except (
        AuditRequestError,
        FileNotFoundError,
        FileExistsError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"ERROR: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
