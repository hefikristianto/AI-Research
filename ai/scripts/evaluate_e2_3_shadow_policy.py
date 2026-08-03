from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_3_high_risk_policy_candidate.json"
)
EVALUATOR_VERSION = "1.1.0"
ALLOWED_SPLITS = {"POLICY_DEVELOPMENT", "POLICY_SELECTION"}
ALLOWED_YEARS = {2020, 2021, 2022, 2023}
TIMEFRAME_MINUTES = {"M5": 5, "M15": 15, "H1": 60, "H4": 240}

SNAPSHOT_FIELDS = [
    "snapshot_id",
    "daily_group_id",
    "evaluation_split",
    "year",
    "trading_date_utc",
    "slot",
    "timeframe",
    "analysis_target_datetime",
    "request_status",
    "public_decision",
    "execution_status",
    "data_quality",
    "standard_eligible",
    "high_risk_eligible",
    "high_risk_rule",
    "candidate_decision",
    "setup_direction",
    "order_type",
    "advanced_score",
    "session_score",
    "risk_reward_ratio",
    "entry_distance_atr",
    "mapping_status",
    "mapping_mode",
    "mapping_confidence",
    "mapping_provisional",
    "entry",
    "stop_loss",
    "take_profit",
    "blockers_json",
    "warnings_json",
    "high_risk_rejection_reasons_json",
    "response_path",
    "response_sha256",
]

DAILY_FIELDS = [
    "daily_group_id",
    "evaluation_split",
    "year",
    "trading_date_utc",
    "planned_snapshot_count",
    "ready_snapshot_count",
    "successful_snapshot_count",
    "analysis_available",
    "watchlist_snapshot_count",
    "standard_candidate_count",
    "high_risk_candidate_count",
    "standard_directions",
    "high_risk_directions",
    "standard_direction_conflict",
    "high_risk_direction_conflict",
    "daily_status",
    "standard_only_decision",
    "combined_policy_decision",
    "selected_tier",
    "selected_snapshot_id",
    "selected_candidate_rule",
    "selected_slot",
    "selected_timeframe",
    "selected_analysis_target_datetime",
    "selected_order_type",
    "selected_advanced_score",
    "selected_mapping_confidence",
    "selected_risk_reward_ratio",
    "selected_entry_distance_atr",
    "selected_entry",
    "selected_stop_loss",
    "selected_take_profit",
    "high_risk_added",
]

BREAKDOWN_FIELDS = [
    "evaluation_split",
    "year",
    "selected_tier",
    "slot",
    "timeframe",
    "selected_days",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate unchanged Standard and registered High Risk E2.3 "
            "policies from the same verified inference cache. No model "
            "request, training, outcome labeling, or 2024/2025 access occurs."
        )
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="Completed E2.3 experiment root.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
        help="Registered High Risk development-candidate policy.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Print progress after this many verified cached responses.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root harus object: {path}")
    return payload


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def write_json_atomic(path: Path, payload: Any) -> None:
    _write_text_atomic(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def write_csv_atomic(
    path: Path,
    rows: Iterable[dict[str, Any]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _safe_path(root: Path, relative: str) -> Path:
    value = Path(str(relative))
    if value.is_absolute():
        raise ValueError(f"Path cache tidak boleh absolut: {relative}")
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(
            f"Path cache keluar dari experiment root: {relative}"
        ) from error
    return candidate


def _as_int(value: Any, *, default: int | None = None) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        if default is not None:
            return default
        raise ValueError(f"Nilai integer tidak valid: {value!r}")


def _as_float(value: Any, *, default: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        if default is not None:
            return default
        raise ValueError(f"Nilai numerik tidak valid: {value!r}")
    if not math.isfinite(result):
        if default is not None:
            return default
        raise ValueError(f"Nilai numerik harus finite: {value!r}")
    return result


def _optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return _as_float(value)


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None or str(value).strip() == "":
        return []
    parsed = json.loads(str(value))
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON list, menerima: {value!r}")
    return [str(item) for item in parsed]


def _compact_json(values: Iterable[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _direction_to_decision(direction: Any) -> str:
    normalized = str(direction or "").strip().lower()
    if normalized == "bullish":
        return "BUY"
    if normalized == "bearish":
        return "SELL"
    return ""


def _same_number(left: Any, right: Any, tolerance: float = 1e-8) -> bool:
    left_value = _optional_float(left)
    right_value = _optional_float(right)
    if left_value is None or right_value is None:
        return left_value is right_value
    return math.isclose(left_value, right_value, rel_tol=tolerance, abs_tol=tolerance)


def validate_policy(policy: dict[str, Any]) -> None:
    errors: list[str] = []
    if policy.get("schema_version") != 1:
        errors.append("schema_version harus 1")
    if policy.get("experiment_id") != "E2.3":
        errors.append("experiment_id harus E2.3")
    if policy.get("stage") != "SHADOW_POLICY_EVALUATION":
        errors.append("stage policy tidak sesuai")
    if policy.get("training_performed") is not False:
        errors.append("training_performed harus false")
    if policy.get("outcome_evaluation_performed") is not False:
        errors.append("outcome_evaluation_performed harus false")
    if policy.get("production_policy_changed") is not False:
        errors.append("production_policy_changed harus false")

    lineage = policy.get("lineage") or {}
    if set(lineage.get("allowed_splits") or []) != ALLOWED_SPLITS:
        errors.append("split development policy berubah")
    if {_as_int(year) for year in lineage.get("allowed_years") or []} != ALLOWED_YEARS:
        errors.append("tahun development policy berubah")
    if _as_int(lineage.get("frozen_holdout_year"), default=-1) != 2024:
        errors.append("frozen holdout harus 2024")
    if _as_int(lineage.get("final_temporal_test_year"), default=-1) != 2025:
        errors.append("final temporal test harus 2025")

    candidate = policy.get("high_risk_candidate") or {}
    minimum_rr = _as_float(candidate.get("minimum_risk_reward_ratio"), default=-1)
    standard_rr = _as_float(candidate.get("standard_risk_reward_ratio"), default=-1)
    warning_distance = _as_float(
        candidate.get("warning_entry_distance_atr"), default=-1
    )
    maximum_distance = _as_float(
        candidate.get("maximum_entry_distance_atr"), default=-1
    )
    if not 0 < minimum_rr < standard_rr:
        errors.append("High Risk RR floor harus positif dan di bawah Standard")
    if not 0 < warning_distance < maximum_distance:
        errors.append("entry-distance warning harus di bawah hard maximum")
    if candidate.get("mapping_provisional_allowed") is not False:
        errors.append("mapping provisional tidak boleh lolos High Risk")
    if set(candidate.get("allowed_soft_blockers") or []) != {
        "RISK_REWARD_BELOW_1_5"
    }:
        errors.append("soft blocker whitelist berubah")
    if set(candidate.get("allowed_soft_warnings") or []) != {
        "ENTRY_DISTANCE_ABOVE_1_5_ATR"
    }:
        errors.append("soft warning whitelist berubah")

    daily = policy.get("daily_selection") or {}
    if _as_int(daily.get("maximum_candidates_per_tier_per_day"), default=-1) != 1:
        errors.append("maksimum kandidat harian per tier harus satu")
    if daily.get("standard_precedes_high_risk") is not True:
        errors.append("Standard harus mendahului High Risk")
    if daily.get("direction_conflict_action") != "FAIL_CLOSED_TO_WATCHLIST":
        errors.append("konflik arah harus fail closed")

    guardrails = policy.get("guardrails") or {}
    required_true = {
        "same_cached_response_for_both_arms",
        "unknown_blocker_is_hard",
        "raw_response_is_not_ground_truth",
        "request_failure_is_not_no_trade",
        "no_model_inference",
        "no_model_training",
        "no_outcome_claim",
    }
    required_false = {
        "holdout_inspection_allowed",
        "final_2025_inspection_allowed",
        "production_promotion_allowed",
    }
    for field in required_true:
        if guardrails.get(field) is not True:
            errors.append(f"guardrail {field} harus true")
    for field in required_false:
        if guardrails.get(field) is not False:
            errors.append(f"guardrail {field} harus false")
    if errors:
        raise ValueError("High Risk policy INVALID: " + "; ".join(errors))


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {"git_commit": None, "git_dirty": None}
    return {
        "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "git_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def _validate_inputs(
    experiment_dir: Path,
    policy: dict[str, Any],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, Any],
    dict[str, Any],
]:
    manifest_path = experiment_dir / "input" / "daily_snapshot_manifest.csv"
    inference_path = (
        experiment_dir / "inference" / "daily_snapshot_inference_rows.csv"
    )
    summary_path = (
        experiment_dir / "inference" / "daily_snapshot_inference_summary.json"
    )
    run_config_path = experiment_dir / "inference" / "run_config.json"
    for path in (manifest_path, inference_path, summary_path, run_config_path):
        if not path.is_file():
            raise ValueError(f"Artifact E2.3 tidak ditemukan: {path}")

    manifest_rows = read_csv_rows(manifest_path)
    inference_rows = read_csv_rows(inference_path)
    summary = read_json(summary_path)
    inference_run_config = read_json(run_config_path)
    lineage = policy["lineage"]
    expected_manifest = str(lineage["manifest_digest_sha256"])
    expected_contract = str(lineage["inference_contract_sha256"])

    if summary.get("complete_for_policy_development") is not True:
        raise ValueError("Inference cache belum complete_for_policy_development.")
    if _as_int(summary.get("remaining_policy_development_rows"), default=-1) != 0:
        raise ValueError("Inference cache masih memiliki development row tersisa.")
    if _as_int(summary.get("failed_inference_rows"), default=-1) != 0:
        raise ValueError("Inference cache masih memiliki failure.")
    if _as_int(summary.get("frozen_holdout_inference_rows"), default=-1) != 0:
        raise ValueError("Inference cache tidak boleh berisi 2024.")
    if _as_int(summary.get("final_2025_inference_rows"), default=-1) != 0:
        raise ValueError("Inference cache tidak boleh berisi 2025.")
    if str(summary.get("manifest_digest_sha256")) != expected_manifest:
        raise ValueError("Manifest digest inference summary berbeda dari policy.")
    if str(summary.get("inference_contract_sha256")) != expected_contract:
        raise ValueError("Inference contract digest berbeda dari policy.")

    snapshot_ids: set[str] = set()
    ready_snapshot_ids = {
        str(row.get("snapshot_id"))
        for row in manifest_rows
        if _as_int(row.get("year"), default=-1) in ALLOWED_YEARS
        and str(row.get("status")) == "READY"
    }
    for row in inference_rows:
        snapshot_id = str(row.get("snapshot_id"))
        if snapshot_id in snapshot_ids:
            raise ValueError(f"Duplicate inference snapshot: {snapshot_id}")
        snapshot_ids.add(snapshot_id)
        year = _as_int(row.get("year"), default=-1)
        split = str(row.get("evaluation_split"))
        if year not in ALLOWED_YEARS or split not in ALLOWED_SPLITS:
            raise ValueError(
                f"Inference row menyentuh split/tahun terkunci: {snapshot_id}"
            )
        if str(row.get("request_status")) != "SUCCESS":
            raise ValueError(f"Inference row tidak SUCCESS: {snapshot_id}")
        if _as_int(row.get("analysis_clock_validated"), default=0) != 1:
            raise ValueError(f"Analysis clock tidak tervalidasi: {snapshot_id}")
        if str(row.get("manifest_digest_sha256")) != expected_manifest:
            raise ValueError(f"Manifest digest row berbeda: {snapshot_id}")
        if str(row.get("inference_contract_sha256")) != expected_contract:
            raise ValueError(f"Inference contract row berbeda: {snapshot_id}")

    if snapshot_ids != ready_snapshot_ids:
        missing = sorted(ready_snapshot_ids - snapshot_ids)[:5]
        unexpected = sorted(snapshot_ids - ready_snapshot_ids)[:5]
        raise ValueError(
            "Inference population tidak sama dengan READY development manifest. "
            f"missing={missing}; unexpected={unexpected}"
        )
    if _as_int(summary.get("successful_inference_rows"), default=-1) != len(
        inference_rows
    ):
        raise ValueError("Successful-row count summary berbeda dari CSV.")
    if len(inference_rows) != 8158:
        raise ValueError(
            "Expected 8.158 development inference rows, menerima "
            f"{len(inference_rows)}."
        )
    return manifest_rows, inference_rows, summary, inference_run_config


def _validate_envelope(
    *,
    experiment_dir: Path,
    row: dict[str, str],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_id = str(row["snapshot_id"])
    response_path = _safe_path(experiment_dir, str(row["response_path"]))
    if not response_path.is_file():
        raise ValueError(f"Cached response hilang: {snapshot_id}: {response_path}")
    actual_digest = file_sha256(response_path)
    if actual_digest != str(row["response_sha256"]):
        raise ValueError(f"Cached response SHA256 berbeda: {snapshot_id}")
    envelope = read_json(response_path)
    lineage = policy["lineage"]
    errors: list[str] = []
    if envelope.get("schema_version") != 1:
        errors.append("schema")
    if envelope.get("stage") != "DAILY_INFERENCE_CACHE":
        errors.append("stage")
    if str(envelope.get("snapshot_id")) != snapshot_id:
        errors.append("snapshot_id")
    if str(envelope.get("evaluation_split")) != str(row["evaluation_split"]):
        errors.append("evaluation_split")
    if str(envelope.get("manifest_digest_sha256")) != str(
        lineage["manifest_digest_sha256"]
    ):
        errors.append("manifest digest")
    if str(envelope.get("inference_contract_sha256")) != str(
        lineage["inference_contract_sha256"]
    ):
        errors.append("inference contract")
    if envelope.get("training_performed") is not False:
        errors.append("training flag")
    if _as_int(envelope.get("http_status"), default=0) != 200:
        errors.append("HTTP status")
    payload = envelope.get("response")
    if not isinstance(payload, dict):
        errors.append("response payload")
        payload = {}
    if errors:
        raise ValueError(
            f"Cached response envelope INVALID {snapshot_id}: " + ", ".join(errors)
        )
    return envelope, payload


def _validate_row_payload_parity(
    row: dict[str, str],
    payload: dict[str, Any],
) -> None:
    snapshot_id = str(row["snapshot_id"])
    recommendation = payload.get("recommendation") or {}
    execution = payload.get("execution_gate") or {}
    conversion = payload.get("price_conversion") or {}
    pairing = payload.get("pairing") or {}
    parity_errors: list[str] = []
    exact_pairs = [
        (row.get("public_decision"), recommendation.get("decision"), "public decision"),
        (
            row.get("execution_status"),
            execution.get("execution_status"),
            "execution status",
        ),
        (row.get("mapping_status"), conversion.get("status"), "mapping status"),
        (row.get("mapping_mode"), conversion.get("mapping_index_mode"), "mapping mode"),
    ]
    for left, right, label in exact_pairs:
        if str(left or "") != str(right or ""):
            parity_errors.append(label)
    if _as_int(row.get("pair_count"), default=0) != _as_int(
        pairing.get("total_pairs"), default=0
    ):
        parity_errors.append("pair count")
    numeric_pairs = [
        (row.get("advanced_score"), execution.get("advanced_score"), "advanced score"),
        (row.get("session_score"), execution.get("session_score"), "session score"),
        (row.get("risk_reward_ratio"), execution.get("risk_reward_ratio"), "RR"),
        (
            row.get("entry_distance_atr"),
            execution.get("entry_distance_atr"),
            "distance",
        ),
        (
            row.get("mapping_confidence"),
            conversion.get("mapping_confidence"),
            "mapping confidence",
        ),
    ]
    for left, right, label in numeric_pairs:
        if not _same_number(left, right):
            parity_errors.append(label)
    if set(_json_list(row.get("blockers_json"))) != set(
        _json_list(execution.get("blockers"))
    ):
        parity_errors.append("blockers")
    if set(_json_list(row.get("warnings_json"))) != set(
        _json_list(execution.get("warnings"))
    ):
        parity_errors.append("warnings")
    if parity_errors:
        raise ValueError(
            f"Inference CSV/response parity INVALID {snapshot_id}: "
            + ", ".join(parity_errors)
        )


def evaluate_snapshot(
    *,
    row: dict[str, str],
    payload: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    _validate_row_payload_parity(row, payload)
    candidate = policy["high_risk_candidate"]
    recommendation = payload.get("recommendation") or {}
    execution = payload.get("execution_gate") or {}
    conversion = payload.get("price_conversion") or {}
    pairing = payload.get("pairing") or {}
    clock = payload.get("analysis_clock") or {}

    public_decision = str(recommendation.get("decision") or "")
    execution_status = str(execution.get("execution_status") or "")
    final_ready = bool(execution.get("final_decision_ready", False))
    direction = str(execution.get("setup_direction") or "")
    candidate_decision = _direction_to_decision(direction)
    order_type = str(execution.get("order_type") or "")
    expected_order_type = {
        "BUY": "BUY_LIMIT",
        "SELL": "SELL_LIMIT",
    }.get(candidate_decision, "")
    advanced_score = _optional_float(execution.get("advanced_score"))
    session_score = _optional_float(execution.get("session_score"))
    risk_reward = _optional_float(execution.get("risk_reward_ratio"))
    entry_distance = _optional_float(execution.get("entry_distance_atr"))
    mapping_confidence = _optional_float(conversion.get("mapping_confidence"))
    blockers = _json_list(execution.get("blockers"))
    warnings = _json_list(execution.get("warnings"))
    entry = _optional_float(execution.get("entry"))
    stop_loss = _optional_float(execution.get("stop_loss"))
    take_profit = _optional_float(execution.get("take_profit"))
    levels_valid = all(value is not None for value in (entry, stop_loss, take_profit))

    standard_eligible = public_decision in {"BUY", "SELL"}
    if standard_eligible:
        standard_errors: list[str] = []
        if execution_status != "TRADE_CANDIDATE":
            standard_errors.append("execution status")
        if not final_ready:
            standard_errors.append("final ready")
        if blockers:
            standard_errors.append("blockers")
        if candidate_decision != public_decision:
            standard_errors.append("direction")
        if not levels_valid:
            standard_errors.append("levels")
        if order_type != expected_order_type:
            standard_errors.append("order type")
        if standard_errors:
            raise ValueError(
                f"Standard control inconsistent {row['snapshot_id']}: "
                + ", ".join(standard_errors)
            )

    rejection_reasons: list[str] = []
    if _as_int(row.get("analysis_clock_validated"), default=0) != 1 or clock.get(
        "anti_lookahead_validated"
    ) is not True:
        rejection_reasons.append("ANALYSIS_CLOCK_INVALID")
    if _as_int(pairing.get("total_pairs"), default=0) < _as_int(
        candidate.get("required_pair_count_minimum"), default=1
    ):
        rejection_reasons.append("PAIR_COUNT_BELOW_MINIMUM")
    if str(conversion.get("status")) != str(candidate["required_mapping_status"]):
        rejection_reasons.append("MAPPING_STATUS_INVALID")
    if str(conversion.get("mapping_index_mode")) != str(
        candidate["required_mapping_mode"]
    ):
        rejection_reasons.append("MAPPING_MODE_INVALID")
    if bool(conversion.get("mapping_provisional", True)):
        rejection_reasons.append("MAPPING_PROVISIONAL")
    if mapping_confidence is None or mapping_confidence < _as_float(
        candidate["minimum_mapping_confidence"]
    ):
        rejection_reasons.append("MAPPING_CONFIDENCE_BELOW_MINIMUM")
    if candidate.get("required_mapping_calibration_applied") is True and not bool(
        conversion.get("mapping_calibration_applied", False)
    ):
        rejection_reasons.append("MAPPING_CALIBRATION_NOT_APPLIED")
    if not levels_valid:
        rejection_reasons.append("EXECUTION_LEVELS_UNAVAILABLE")
    if not candidate_decision:
        rejection_reasons.append("SETUP_DIRECTION_UNAVAILABLE")
    if not expected_order_type or order_type != expected_order_type:
        rejection_reasons.append("ORDER_TYPE_INVALID")
    if advanced_score is None or advanced_score < _as_float(
        candidate["minimum_advanced_score"]
    ):
        rejection_reasons.append("ADVANCED_SCORE_BELOW_MINIMUM")
    if session_score is None or session_score < _as_float(
        candidate["minimum_session_score"]
    ):
        rejection_reasons.append("SESSION_SCORE_BELOW_MINIMUM")
    if risk_reward is None or risk_reward < _as_float(
        candidate["minimum_risk_reward_ratio"]
    ):
        rejection_reasons.append("RISK_REWARD_BELOW_HIGH_RISK_FLOOR")
    if entry_distance is None or entry_distance > _as_float(
        candidate["maximum_entry_distance_atr"]
    ):
        rejection_reasons.append("ENTRY_DISTANCE_ABOVE_HARD_MAXIMUM")
    if standard_eligible:
        rejection_reasons.append("ALREADY_STANDARD_CANDIDATE")
    if execution_status not in set(candidate["allowed_source_execution_statuses"]):
        rejection_reasons.append("SOURCE_EXECUTION_STATUS_NOT_ALLOWED")

    allowed_blockers = set(candidate["allowed_soft_blockers"])
    unknown_blockers = set(blockers) - allowed_blockers
    if unknown_blockers:
        rejection_reasons.append("HARD_OR_UNKNOWN_BLOCKER_PRESENT")
    allowed_warnings = set(candidate["allowed_soft_warnings"])
    if set(warnings) - allowed_warnings:
        rejection_reasons.append("HARD_OR_UNKNOWN_WARNING_PRESENT")

    high_risk_rule = ""
    if not rejection_reasons:
        minimum_rr = _as_float(candidate["minimum_risk_reward_ratio"])
        standard_rr = _as_float(candidate["standard_risk_reward_ratio"])
        warning_distance = _as_float(candidate["warning_entry_distance_atr"])
        maximum_distance = _as_float(candidate["maximum_entry_distance_atr"])
        if not blockers:
            if (
                execution_status == "REVIEW"
                and set(warnings) == {"ENTRY_DISTANCE_ABOVE_1_5_ATR"}
                and risk_reward is not None
                and risk_reward >= standard_rr
                and entry_distance is not None
                and warning_distance < entry_distance <= maximum_distance
            ):
                high_risk_rule = "ENTRY_DISTANCE_WARNING"
            else:
                rejection_reasons.append("NO_REGISTERED_SOFT_CONDITION")
        elif set(blockers) == {"RISK_REWARD_BELOW_1_5"}:
            if (
                execution_status == "WAIT"
                and risk_reward is not None
                and minimum_rr <= risk_reward < standard_rr
                and set(warnings).issubset(allowed_warnings)
            ):
                high_risk_rule = "RR_RELAXATION"
            else:
                rejection_reasons.append("RR_RELAXATION_CONTRACT_MISMATCH")
        else:
            rejection_reasons.append("BLOCKER_SET_NOT_REGISTERED")

    high_risk_eligible = bool(high_risk_rule) and not rejection_reasons
    data_quality_reasons = {
        "ANALYSIS_CLOCK_INVALID",
        "PAIR_COUNT_BELOW_MINIMUM",
        "MAPPING_STATUS_INVALID",
        "MAPPING_MODE_INVALID",
        "MAPPING_PROVISIONAL",
        "MAPPING_CONFIDENCE_BELOW_MINIMUM",
        "MAPPING_CALIBRATION_NOT_APPLIED",
        "EXECUTION_LEVELS_UNAVAILABLE",
        "SETUP_DIRECTION_UNAVAILABLE",
        "ORDER_TYPE_INVALID",
    }
    data_quality = (
        "INVALID"
        if any(reason in data_quality_reasons for reason in rejection_reasons)
        else "VALID"
    )
    expose_levels = standard_eligible or high_risk_eligible
    return {
        "snapshot_id": row["snapshot_id"],
        "daily_group_id": row["daily_group_id"],
        "evaluation_split": row["evaluation_split"],
        "year": _as_int(row["year"]),
        "trading_date_utc": row["trading_date_utc"],
        "slot": row["slot"],
        "timeframe": row["timeframe"],
        "analysis_target_datetime": row["analysis_target_datetime"],
        "request_status": row["request_status"],
        "public_decision": public_decision,
        "execution_status": execution_status,
        "data_quality": data_quality,
        "standard_eligible": int(standard_eligible),
        "high_risk_eligible": int(high_risk_eligible),
        "high_risk_rule": high_risk_rule,
        "candidate_decision": candidate_decision if expose_levels else "",
        "setup_direction": direction if expose_levels else "",
        "order_type": order_type if expose_levels else "",
        "advanced_score": advanced_score if advanced_score is not None else "",
        "session_score": session_score if session_score is not None else "",
        "risk_reward_ratio": risk_reward if risk_reward is not None else "",
        "entry_distance_atr": entry_distance if entry_distance is not None else "",
        "mapping_status": conversion.get("status", ""),
        "mapping_mode": conversion.get("mapping_index_mode", ""),
        "mapping_confidence": (
            mapping_confidence if mapping_confidence is not None else ""
        ),
        "mapping_provisional": int(
            bool(conversion.get("mapping_provisional", False))
        ),
        "entry": entry if expose_levels and entry is not None else "",
        "stop_loss": stop_loss if expose_levels and stop_loss is not None else "",
        "take_profit": take_profit if expose_levels and take_profit is not None else "",
        "blockers_json": _compact_json(blockers),
        "warnings_json": _compact_json(warnings),
        "high_risk_rejection_reasons_json": _compact_json(rejection_reasons),
        "response_path": row["response_path"],
        "response_sha256": row["response_sha256"],
    }


def _candidate_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -_as_float(row.get("advanced_score"), default=-1.0),
        -_as_float(row.get("mapping_confidence"), default=-1.0),
        -_as_float(row.get("risk_reward_ratio"), default=-1.0),
        _as_float(row.get("entry_distance_atr"), default=float("inf")),
        -TIMEFRAME_MINUTES.get(str(row.get("timeframe")), 0),
        str(row.get("analysis_target_datetime") or ""),
        str(row.get("snapshot_id") or ""),
    )


def build_daily_rows(
    *,
    manifest_rows: list[dict[str, str]],
    snapshot_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    planned: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        year = _as_int(row.get("year"), default=-1)
        split = str(row.get("evaluation_split"))
        if year not in ALLOWED_YEARS or split not in ALLOWED_SPLITS:
            continue
        daily_id = str(row["daily_group_id"])
        current = planned.setdefault(
            daily_id,
            {
                "daily_group_id": daily_id,
                "evaluation_split": split,
                "year": year,
                "trading_date_utc": row["trading_date_utc"],
                "planned_snapshot_count": 0,
                "ready_snapshot_count": 0,
            },
        )
        if current["evaluation_split"] != split or current["year"] != year:
            raise ValueError(f"Daily manifest lineage tidak konsisten: {daily_id}")
        current["planned_snapshot_count"] += 1
        current["ready_snapshot_count"] += int(str(row.get("status")) == "READY")

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in snapshot_rows:
        by_day[str(row["daily_group_id"])].append(row)

    results: list[dict[str, Any]] = []
    for daily_id in sorted(planned):
        info = planned[daily_id]
        snapshots = by_day.get(daily_id, [])
        standards = [row for row in snapshots if _as_int(row["standard_eligible"]) == 1]
        high_risk = [
            row
            for row in snapshots
            if _as_int(row["high_risk_eligible"]) == 1
        ]
        watchlists = [row for row in snapshots if row["public_decision"] == "WATCHLIST"]
        standard_directions = sorted({row["candidate_decision"] for row in standards})
        high_risk_directions = sorted({row["candidate_decision"] for row in high_risk})
        standard_conflict = len(standard_directions) > 1
        high_risk_conflict = len(high_risk_directions) > 1
        analysis_available = bool(snapshots)
        selected: dict[str, Any] | None = None
        selected_tier = ""
        daily_status = ""

        if not analysis_available:
            standard_only = "UNAVAILABLE"
            combined = "UNAVAILABLE"
            daily_status = "ANALYSIS_UNAVAILABLE"
        elif standard_conflict:
            standard_only = "WATCHLIST"
            combined = "WATCHLIST"
            daily_status = "STANDARD_DIRECTION_CONFLICT"
        elif standards:
            selected = sorted(standards, key=_candidate_rank)[0]
            selected_tier = "STANDARD"
            standard_only = str(selected["candidate_decision"])
            combined = standard_only
            daily_status = "STANDARD_SELECTED"
        else:
            standard_only = "WATCHLIST" if watchlists else "NO_TRADE"
            if high_risk_conflict:
                combined = "WATCHLIST"
                daily_status = "HIGH_RISK_DIRECTION_CONFLICT"
            elif high_risk:
                selected = sorted(high_risk, key=_candidate_rank)[0]
                selected_tier = "HIGH_RISK"
                combined = str(selected["candidate_decision"])
                daily_status = "HIGH_RISK_SELECTED"
            else:
                combined = standard_only
                daily_status = "WATCHLIST_ONLY" if watchlists else "NO_TRADE"

        result = {
            **info,
            "successful_snapshot_count": len(snapshots),
            "analysis_available": int(analysis_available),
            "watchlist_snapshot_count": len(watchlists),
            "standard_candidate_count": len(standards),
            "high_risk_candidate_count": len(high_risk),
            "standard_directions": "|".join(standard_directions),
            "high_risk_directions": "|".join(high_risk_directions),
            "standard_direction_conflict": int(standard_conflict),
            "high_risk_direction_conflict": int(high_risk_conflict),
            "daily_status": daily_status,
            "standard_only_decision": standard_only,
            "combined_policy_decision": combined,
            "selected_tier": selected_tier,
            "selected_snapshot_id": selected["snapshot_id"] if selected else "",
            "selected_candidate_rule": (
                selected["high_risk_rule"] if selected_tier == "HIGH_RISK" else ""
            ),
            "selected_slot": selected["slot"] if selected else "",
            "selected_timeframe": selected["timeframe"] if selected else "",
            "selected_analysis_target_datetime": (
                selected["analysis_target_datetime"] if selected else ""
            ),
            "selected_order_type": selected["order_type"] if selected else "",
            "selected_advanced_score": selected["advanced_score"] if selected else "",
            "selected_mapping_confidence": (
                selected["mapping_confidence"] if selected else ""
            ),
            "selected_risk_reward_ratio": (
                selected["risk_reward_ratio"] if selected else ""
            ),
            "selected_entry_distance_atr": (
                selected["entry_distance_atr"] if selected else ""
            ),
            "selected_entry": selected["entry"] if selected else "",
            "selected_stop_loss": selected["stop_loss"] if selected else "",
            "selected_take_profit": selected["take_profit"] if selected else "",
            "high_risk_added": int(selected_tier == "HIGH_RISK"),
        }
        results.append(result)
    return results


def _rate(count: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * count / denominator, 6)


def _coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    planned = len(rows)
    available = sum(_as_int(row["analysis_available"]) for row in rows)
    standard = sum(row["selected_tier"] == "STANDARD" for row in rows)
    high_risk = sum(row["selected_tier"] == "HIGH_RISK" for row in rows)
    combined = standard + high_risk
    watchlist = sum(row["combined_policy_decision"] == "WATCHLIST" for row in rows)
    no_trade = sum(row["combined_policy_decision"] == "NO_TRADE" for row in rows)
    unavailable = sum(row["combined_policy_decision"] == "UNAVAILABLE" for row in rows)
    standard_conflict = sum(_as_int(row["standard_direction_conflict"]) for row in rows)
    high_risk_conflict = sum(
        row["daily_status"] == "HIGH_RISK_DIRECTION_CONFLICT" for row in rows
    )
    return {
        "planned_days": planned,
        "analysis_available_days": available,
        "analysis_unavailable_days": unavailable,
        "standard_candidate_days": standard,
        "additional_high_risk_days": high_risk,
        "combined_candidate_days": combined,
        "watchlist_days": watchlist,
        "no_trade_days": no_trade,
        "standard_direction_conflict_days": standard_conflict,
        "high_risk_direction_conflict_days": high_risk_conflict,
        "rates_over_planned_days_pct": {
            "analysis_available": _rate(available, planned),
            "standard_candidate": _rate(standard, planned),
            "additional_high_risk": _rate(high_risk, planned),
            "combined_candidate": _rate(combined, planned),
            "watchlist": _rate(watchlist, planned),
            "no_trade": _rate(no_trade, planned),
        },
        "rates_over_available_days_pct": {
            "standard_candidate": _rate(standard, available),
            "additional_high_risk": _rate(high_risk, available),
            "combined_candidate": _rate(combined, available),
        },
    }


def build_metrics(
    *,
    policy: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    inference_summary: dict[str, Any],
    inference_run_config: dict[str, Any],
) -> dict[str, Any]:
    by_split: dict[str, Any] = {}
    for split in sorted(ALLOWED_SPLITS):
        by_split[split] = _coverage(
            [row for row in daily_rows if row["evaluation_split"] == split]
        )
    by_year: dict[str, Any] = {}
    for year in sorted(ALLOWED_YEARS):
        by_year[str(year)] = _coverage(
            [row for row in daily_rows if _as_int(row["year"]) == year]
        )
    rule_counts = Counter(
        str(row["high_risk_rule"])
        for row in snapshot_rows
        if _as_int(row["high_risk_eligible"]) == 1
    )
    source_status = Counter(
        str(row["execution_status"])
        for row in snapshot_rows
        if _as_int(row["high_risk_eligible"]) == 1
    )
    design = by_split["POLICY_DEVELOPMENT"]
    selection = by_split["POLICY_SELECTION"]
    design_rate = design["rates_over_planned_days_pct"]["additional_high_risk"]
    selection_rate = selection["rates_over_planned_days_pct"]["additional_high_risk"]
    return {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "SHADOW_POLICY_EVALUATION",
        "evaluator_version": EVALUATOR_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy_version": policy["policy_version"],
        "policy_sha256": object_sha256(policy),
        "training_performed": False,
        "model_inference_performed": False,
        "outcome_evaluation_performed": False,
        "production_policy_changed": False,
        "raw_response_is_ground_truth": False,
        "lineage": {
            "manifest_digest_sha256": policy["lineage"][
                "manifest_digest_sha256"
            ],
            "inference_contract_sha256": policy["lineage"][
                "inference_contract_sha256"
            ],
            "inference_pipeline_content_sha256": inference_run_config.get(
                "pipeline_content_sha256"
            ),
            "inference_git_commit": inference_run_config.get("git_commit"),
            "successful_inference_rows": inference_summary.get(
                "successful_inference_rows"
            ),
        },
        "snapshot_funnel": {
            "successful_cached_snapshots": len(snapshot_rows),
            "standard_candidates": sum(
                _as_int(row["standard_eligible"]) for row in snapshot_rows
            ),
            "high_risk_candidates": sum(
                _as_int(row["high_risk_eligible"]) for row in snapshot_rows
            ),
            "high_risk_candidate_rules": dict(sorted(rule_counts.items())),
            "high_risk_source_statuses": dict(sorted(source_status.items())),
        },
        "daily_coverage": {
            "all_development_and_selection": _coverage(daily_rows),
            "by_split": by_split,
            "by_year": by_year,
        },
        "selection_stability": {
            "additional_high_risk_rate_design_pct": design_rate,
            "additional_high_risk_rate_selection_pct": selection_rate,
            "selection_minus_design_percentage_points": round(
                float(selection_rate) - float(design_rate), 6
            ),
        },
        "interpretation_guardrails": [
            "Coverage is not accuracy or profitability.",
            "The evaluator reuses cached responses and performs no inference.",
            "Raw model responses are not ground truth.",
            "2024 remains frozen and 2025 remains locked.",
            "High Risk remains shadow telemetry until verified outcome metrics pass.",
        ],
    }


def build_breakdown(daily_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, int, str, str, str]] = Counter()
    for row in daily_rows:
        tier = str(row["selected_tier"])
        if tier not in {"STANDARD", "HIGH_RISK"}:
            continue
        counts[
            (
                str(row["evaluation_split"]),
                _as_int(row["year"]),
                tier,
                str(row["selected_slot"]),
                str(row["selected_timeframe"]),
            )
        ] += 1
    return [
        {
            "evaluation_split": key[0],
            "year": key[1],
            "selected_tier": key[2],
            "slot": key[3],
            "timeframe": key[4],
            "selected_days": count,
        }
        for key, count in sorted(counts.items())
    ]


def build_report(metrics: dict[str, Any]) -> str:
    daily = metrics["daily_coverage"]
    design = daily["by_split"]["POLICY_DEVELOPMENT"]
    selection = daily["by_split"]["POLICY_SELECTION"]
    snapshots = metrics["snapshot_funnel"]

    def row(label: str, key: str) -> str:
        design_value = design[key]
        selection_value = selection[key]
        design_rate = _rate(design_value, design["planned_days"])
        selection_rate = _rate(selection_value, selection["planned_days"])
        return (
            f"| {label} | {design_value} ({design_rate:.2f}%) | "
            f"{selection_value} ({selection_rate:.2f}%) |"
        )

    lines = [
        "# E2.3 Standard / High Risk Shadow Policy",
        "",
        f"Generated (UTC): `{metrics['generated_at_utc']}`",
        "",
        "## Registered candidate",
        "",
        f"- Policy: `{metrics['policy_version']}`",
        "- Standard policy: unchanged cached production decision",
        "- High Risk RR floor: `1.25`",
        "- High Risk maximum entry distance: `3.0 ATR`",
        "- Required mapping: `MAPPED`, `PLOT_AWARE`, non-provisional, "
        "confidence >= `0.65`",
        "- Daily cap: one selected candidate per tier; Standard takes precedence",
        "- Direction conflict: fail closed to `WATCHLIST`",
        "",
        "## Snapshot funnel",
        "",
        f"- Successful cached snapshots: `{snapshots['successful_cached_snapshots']}`",
        f"- Standard candidates: `{snapshots['standard_candidates']}`",
        f"- High Risk candidates: `{snapshots['high_risk_candidates']}`",
        "- High Risk rules: `"
        + json.dumps(snapshots["high_risk_candidate_rules"], sort_keys=True)
        + "`",
        "",
        "## Daily coverage",
        "",
        "| Metric | 2020-2022 design | 2023 selection |",
        "|---|---:|---:|",
        row("Planned days", "planned_days"),
        row("Analysis available", "analysis_available_days"),
        row("Standard selected", "standard_candidate_days"),
        row("Additional High Risk selected", "additional_high_risk_days"),
        row("Combined candidate days", "combined_candidate_days"),
        row("WATCHLIST days", "watchlist_days"),
        row("NO_TRADE days", "no_trade_days"),
        row("Standard direction conflicts", "standard_direction_conflict_days"),
        row("High Risk direction conflicts", "high_risk_direction_conflict_days"),
        "",
        "## Interpretation",
        "",
        "This report measures decision coverage only. It contains no verified "
        "outcome label, win rate, expectancy, profit factor, or drawdown result. "
        "The High Risk tier remains shadow telemetry and must not be exposed in "
        "production before the registered outcome and 2024 holdout gates pass.",
        "",
    ]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    experiment_dir = Path(args.experiment_dir).resolve()
    policy_path = Path(args.policy).resolve()
    policy = read_json(policy_path)
    validate_policy(policy)
    manifest_rows, inference_rows, inference_summary, inference_run_config = (
        _validate_inputs(experiment_dir, policy)
    )

    snapshot_rows: list[dict[str, Any]] = []
    progress_every = max(0, _as_int(getattr(args, "progress_every", 500), default=500))
    for index, row in enumerate(inference_rows, start=1):
        _, payload = _validate_envelope(
            experiment_dir=experiment_dir,
            row=row,
            policy=policy,
        )
        snapshot_rows.append(
            evaluate_snapshot(row=row, payload=payload, policy=policy)
        )
        if progress_every and (
            index % progress_every == 0 or index == len(inference_rows)
        ):
            print(f"[{index}/{len(inference_rows)}] cached responses verified")

    expected_candidates = _as_int(
        policy["selection_evidence"]["eligible_high_risk_snapshots"]
    )
    actual_candidates = sum(
        _as_int(row["high_risk_eligible"]) for row in snapshot_rows
    )
    if actual_candidates != expected_candidates:
        raise ValueError(
            "High Risk candidate count berbeda dari registered development evidence: "
            f"expected={expected_candidates}; actual={actual_candidates}."
        )

    daily_rows = build_daily_rows(
        manifest_rows=manifest_rows,
        snapshot_rows=snapshot_rows,
    )
    metrics = build_metrics(
        policy=policy,
        snapshot_rows=snapshot_rows,
        daily_rows=daily_rows,
        inference_summary=inference_summary,
        inference_run_config=inference_run_config,
    )
    breakdown_rows = build_breakdown(daily_rows)

    policy_output = experiment_dir / "config" / "high_risk_policy.json"
    snapshot_output = (
        experiment_dir / "predictions" / "snapshot_shadow_decisions.csv"
    )
    daily_output = experiment_dir / "predictions" / "daily_decisions.csv"
    metrics_output = experiment_dir / "metrics" / "daily_coverage.json"
    breakdown_output = (
        experiment_dir / "metrics" / "session_timeframe_breakdown.csv"
    )
    report_output = (
        experiment_dir / "reports" / "high_risk_shadow_policy_report.md"
    )
    manifest_output = experiment_dir / "manifest.json"

    write_json_atomic(policy_output, policy)
    write_csv_atomic(snapshot_output, snapshot_rows, SNAPSHOT_FIELDS)
    write_csv_atomic(daily_output, daily_rows, DAILY_FIELDS)
    write_json_atomic(metrics_output, metrics)
    write_csv_atomic(breakdown_output, breakdown_rows, BREAKDOWN_FIELDS)
    _write_text_atomic(report_output, build_report(metrics))

    artifacts = {}
    for path in (
        policy_output,
        snapshot_output,
        daily_output,
        metrics_output,
        breakdown_output,
        report_output,
    ):
        artifacts[str(path.relative_to(experiment_dir)).replace("\\", "/")] = {
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
    experiment_manifest = {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "SHADOW_POLICY_EVALUATION",
        "evaluator_version": EVALUATOR_VERSION,
        "generated_at_utc": metrics["generated_at_utc"],
        "training_performed": False,
        "model_inference_performed": False,
        "outcome_evaluation_performed": False,
        "production_policy_changed": False,
        "policy_sha256": metrics["policy_sha256"],
        "input_lineage": metrics["lineage"],
        "evaluator_git": _git_state(),
        "artifacts": artifacts,
    }
    write_json_atomic(manifest_output, experiment_manifest)

    all_coverage = metrics["daily_coverage"]["all_development_and_selection"]
    print(f"Snapshot rows: {snapshot_output}")
    print(f"Daily decisions: {daily_output}")
    print(f"Coverage: {metrics_output}")
    print(f"Report: {report_output}")
    print(
        "Selected days: "
        f"Standard={all_coverage['standard_candidate_days']} | "
        f"High Risk added={all_coverage['additional_high_risk_days']} | "
        f"Combined={all_coverage['combined_candidate_days']}"
    )
    return metrics


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
