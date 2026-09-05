from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from collections import Counter
from collections import defaultdict
from datetime import datetime
from datetime import timezone
from pathlib import Path
from statistics import mean
from typing import Any
from typing import Callable

from PIL import Image

from app.services.chart_plot_geometry_service import (
    ChartPlotGeometryService,
)
from app.services.screenshot_price_axis_calibration_service import (
    OptionalTesseractPriceAxisOCRProvider,
)
from app.services.screenshot_price_axis_calibration_service import (
    ScreenshotPriceAxisCalibrationService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_4_1_ocr_benchmark.json"
)
CALIBRATION_SERVICE_SOURCE = (
    PROJECT_ROOT
    / "backend"
    / "app"
    / "services"
    / "screenshot_price_axis_calibration_service.py"
)
RUNNER_VERSION = "1.1.0"

FORBIDDEN_OUTCOME_KEYS = {
    "trade_outcome",
    "outcome_label",
    "win_rate",
    "profit_factor",
    "net_expectancy",
    "expectancy_r",
    "drawdown",
    "tp_hit",
    "sl_hit",
    "result_r",
}

ROW_FIELDS = [
    "schema_version",
    "experiment_id",
    "fixture_set_id",
    "fixture_id",
    "profile_id",
    "fixture_source",
    "external_reviewed",
    "pair",
    "timeframe",
    "platform",
    "theme",
    "locale",
    "variant",
    "scale_mode",
    "tick_metric_eligible",
    "image_path",
    "image_sha256",
    "image_sha256_verified",
    "request_status",
    "error",
    "geometry_status",
    "geometry_method",
    "plot_right_absolute_error_pixels",
    "axis_region_method",
    "axis_region_iou",
    "axis_region_contains_expected",
    "ocr_status",
    "ocr_engine",
    "tesseract_version",
    "ocr_observation_count",
    "ocr_pass_count",
    "ocr_selected_pass_id",
    "ocr_filled_background_rejection_count",
    "ground_truth_tick_count",
    "recognized_tick_count",
    "tick_true_positive",
    "tick_false_positive",
    "tick_false_negative",
    "exact_text_match_count",
    "tick_precision",
    "tick_recall",
    "exact_text_accuracy",
    "mean_tick_y_error_pixels",
    "calibration_status",
    "calibration_reason_code",
    "expected_status",
    "expected_status_match",
    "false_calibration",
    "fail_closed_expected",
    "fail_closed_correct",
    "mapping_point_count",
    "mapping_absolute_error_sum",
    "mapping_normalized_absolute_error_sum",
    "mapping_pixel_absolute_error_sum",
    "mapping_mae",
    "mapping_maximum_error",
    "normalized_mapping_mae",
    "mapping_mae_pixels",
    "mapping_maximum_error_pixels",
    "entry_price_authorized",
    "production_decision_changed",
    "telemetry_boundary_valid",
    "latency_ms",
    "raw_response_path",
    "raw_response_sha256",
]


class _StaticOCRProvider:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    def extract(self, image: Image.Image) -> dict[str, Any]:
        return self.result


ProviderFactory = Callable[
    [dict[str, Any], str | None],
    OptionalTesseractPriceAxisOCRProvider,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark E2.4 price-axis OCR profiles against a frozen "
            "SHA256 fixture manifest. This runner performs no training, "
            "model inference, trading outcome evaluation, or production "
            "decision change."
        )
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="Registered E2.4.1 or E2.4.2 benchmark contract.",
    )
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        required=True,
        help="Reviewed synthetic/external fixture manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Local output directory under local_artifacts/.",
    )
    parser.add_argument(
        "--profile",
        dest="profile_ids",
        action="append",
        help="Profile ID to run. Repeat as needed; default is all.",
    )
    parser.add_argument(
        "--tesseract-cmd",
        type=str,
        help=(
            "Optional explicit Tesseract executable. The environment "
            "AI_TDSS_TESSERACT_CMD is used when omitted."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit pending fixture/profile tasks; zero means all.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse validated rows from a compatible prior invocation.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first fixture processing error.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress every N newly processed tasks.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"JSON tidak ditemukan: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON tidak valid: {path}: {error}") from error

    if not isinstance(payload, dict):
        raise ValueError(f"JSON root harus object: {path}")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _forbidden_keys(payload: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_OUTCOME_KEYS:
                found.add(normalized)
            found.update(_forbidden_keys(value))
    elif isinstance(payload, list):
        for value in payload:
            found.update(_forbidden_keys(value))
    return found


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    experiment_id = str(contract.get("experiment_id") or "")
    expected_contracts = {
        "E2.4.1": (
            "OCR_BACKEND_AND_FIXTURE_BENCHMARK",
            {"PREREGISTERED_ENGINEERING_EVALUATION"},
        ),
        "E2.4.2": (
            "EXTERNAL_THEME_PLATFORM_ROBUSTNESS_REMEDIATION",
            {
                "PREREGISTERED_DEVELOPMENT_REMEDIATION",
                "IMPLEMENTATION_FROZEN_AWAITING_HOLDOUT",
            },
        ),
    }
    if contract.get("schema_version") != 1:
        errors.append("Schema contract OCR harus 1.")
    if experiment_id not in expected_contracts:
        errors.append("experiment_id harus E2.4.1 atau E2.4.2.")
    else:
        expected_stage, expected_statuses = expected_contracts[experiment_id]
        if contract.get("stage") != expected_stage:
            errors.append(f"Stage {experiment_id} berubah.")
        if contract.get("status") not in expected_statuses:
            errors.append(f"Status {experiment_id} tidak terdaftar.")
    for key in (
        "training_performed",
        "model_inference_performed",
        "trading_outcome_data_allowed",
        "production_default_changed",
        "production_decision_changed",
        "canonical_ohlcv_requirement_changed",
        "high_risk_policy_changed",
    ):
        if contract.get(key) is not False:
            errors.append(f"Contract {key} harus false.")

    if any(bool(value) for value in contract.get("holdout_access", {}).values()):
        errors.append("Semua akses outcome dan holdout OCR harus false.")

    if experiment_id == "E2.4.2":
        evidence_roles = contract.get("evidence_roles", {})
        if evidence_roles.get("development_metrics_may_pass_freeze") is not False:
            errors.append("Development E2.4.2 tidak boleh meluluskan freeze.")
        if evidence_roles.get("fresh_external_holdout_required") is not True:
            errors.append("E2.4.2 wajib memerlukan fresh external holdout.")
        holdout_requirements = contract.get("fixture_contract", {}).get(
            "fresh_holdout_manifest_requirements",
            {},
        )
        expected_holdout_requirements = {
            "evidence_role": "FRESH_EXTERNAL_HOLDOUT",
            "captured_after_implementation_freeze": True,
            "capture_started_at_utc_required": True,
            "implementation_freeze_id_required": True,
        }
        if holdout_requirements != expected_holdout_requirements:
            errors.append("Requirement manifest fresh holdout E2.4.2 berubah.")
        if contract.get("status") == "IMPLEMENTATION_FROZEN_AWAITING_HOLDOUT":
            implementation_freeze = contract.get("implementation_freeze")
            if not isinstance(implementation_freeze, dict):
                errors.append("E2.4.2 frozen wajib memiliki implementation_freeze.")
            else:
                freeze_id = str(
                    implementation_freeze.get("freeze_id") or ""
                )
                if not re.fullmatch(r"[A-Za-z0-9_.-]+", freeze_id):
                    errors.append("implementation_freeze.freeze_id tidak valid.")
                try:
                    frozen_at = datetime.fromisoformat(
                        str(implementation_freeze["frozen_at_utc"])
                        .replace("Z", "+00:00")
                    )
                    if frozen_at.utcoffset() is None:
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    errors.append(
                        "implementation_freeze.frozen_at_utc wajib ISO UTC."
                    )
                for key in (
                    "calibration_service_source_sha256",
                    "benchmark_runner_source_sha256",
                    "windows_development_result_zip_sha256",
                ):
                    if not re.fullmatch(
                        r"[0-9a-fA-F]{64}",
                        str(implementation_freeze.get(key) or ""),
                    ):
                        errors.append(
                            f"implementation_freeze.{key} wajib SHA256."
                        )

    profiles = contract.get("ocr_engine", {}).get("profiles", [])
    profile_ids = [str(profile.get("profile_id")) for profile in profiles]
    if len(profile_ids) != len(set(profile_ids)) or not profile_ids:
        errors.append("Profile OCR harus unik dan tidak kosong.")

    output = contract.get("output_contract", {})
    if output.get("production_promotion_possible") is not False:
        errors.append("Runner benchmark tidak boleh mempromosikan produksi.")
    if output.get("resumable") is not True:
        errors.append("Runner OCR wajib resumable.")
    return errors


def resolve_profiles(
    contract: dict[str, Any],
    requested_ids: list[str] | None,
) -> list[dict[str, Any]]:
    registered = contract["ocr_engine"]["profiles"]
    by_id = {
        str(profile["profile_id"]): dict(profile)
        for profile in registered
    }
    if not requested_ids:
        return [by_id[key] for key in by_id]

    unknown = sorted(set(requested_ids) - set(by_id))
    if unknown:
        raise ValueError(
            "Profile OCR tidak terdaftar: " + ", ".join(unknown)
        )
    return [by_id[profile_id] for profile_id in requested_ids]


def resolve_fixture_path(
    manifest_path: Path,
    fixture: dict[str, Any],
) -> Path:
    root = manifest_path.resolve().parent
    raw_path = Path(str(fixture.get("image_path", "")))
    if raw_path.is_absolute():
        candidate = raw_path.resolve()
    else:
        candidate = (root / raw_path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(
            "Image fixture harus berada di dalam fixture pack: "
            f"{candidate}"
        ) from error
    return candidate


def validate_manifest(
    manifest: dict[str, Any],
    contract: dict[str, Any],
    manifest_path: Path,
) -> list[str]:
    errors: list[str] = []
    fixture_contract = contract["fixture_contract"]

    if manifest.get("schema_version") != fixture_contract[
        "manifest_schema_version"
    ]:
        errors.append("Fixture manifest schema_version berubah.")
    accepted_experiment_ids = set(
        fixture_contract.get(
            "accepted_source_experiment_ids",
            [contract.get("experiment_id")],
        )
    )
    if manifest.get("experiment_id") not in accepted_experiment_ids:
        errors.append(
            "Fixture manifest tidak terdaftar untuk contract ini."
        )
    if manifest.get("trading_outcome_data_used") is not False:
        errors.append("Fixture manifest tidak boleh memakai outcome trading.")
    if manifest.get("production_decision_changed") is not False:
        errors.append("Fixture manifest tidak boleh mengubah produksi.")
    fixture_set_id = str(manifest.get("fixture_set_id", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", fixture_set_id):
        errors.append("fixture_set_id manifest tidak valid.")

    if (
        contract.get("experiment_id") == "E2.4.2"
        and manifest.get("experiment_id") == "E2.4.2"
    ):
        holdout_requirements = fixture_contract[
            "fresh_holdout_manifest_requirements"
        ]
        expected_evidence_role = holdout_requirements["evidence_role"]
        if contract.get("status") != "IMPLEMENTATION_FROZEN_AWAITING_HOLDOUT":
            errors.append(
                "Fresh holdout E2.4.2 ditolak sebelum implementation freeze."
            )
        implementation_freeze = contract.get("implementation_freeze", {})
        expected_freeze_id = str(
            implementation_freeze.get("freeze_id") or ""
        )
        if manifest.get("evidence_role") != expected_evidence_role:
            errors.append(
                "Manifest E2.4.2 wajib evidence_role FRESH_EXTERNAL_HOLDOUT."
            )
        if manifest.get("captured_after_implementation_freeze") is not (
            holdout_requirements[
                "captured_after_implementation_freeze"
            ]
        ):
            errors.append(
                "Manifest E2.4.2 wajib menyatakan capture setelah freeze."
            )
        if str(manifest.get("implementation_freeze_id") or "") != (
            expected_freeze_id
        ):
            errors.append("Manifest E2.4.2 memakai freeze_id yang berbeda.")
        try:
            captured_at = datetime.fromisoformat(
                str(manifest["capture_started_at_utc"]).replace(
                    "Z", "+00:00"
                )
            )
            frozen_at = datetime.fromisoformat(
                str(implementation_freeze["frozen_at_utc"]).replace(
                    "Z", "+00:00"
                )
            )
            if (
                captured_at.utcoffset() is None
                or frozen_at.utcoffset() is None
                or captured_at < frozen_at
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            errors.append(
                "capture_started_at_utc wajib ISO UTC dan tidak boleh "
                "mendahului implementation freeze."
            )

    forbidden = _forbidden_keys(manifest)
    if forbidden:
        errors.append(
            "Fixture mengandung field outcome terlarang: "
            + ", ".join(sorted(forbidden))
        )

    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        errors.append("Fixture manifest harus memiliki fixtures non-empty.")
        return errors

    ids: list[str] = []
    allowed_sources = set(fixture_contract["allowed_fixture_sources"])
    allowed_statuses = set(fixture_contract["allowed_expected_statuses"])
    allowed_pairs = set(fixture_contract["required_pairs"])
    allowed_timeframes = set(fixture_contract["required_timeframes"])
    allowed_platforms = set(fixture_contract["required_platforms"])
    allowed_themes = set(fixture_contract["required_themes"])
    allowed_locales = set(fixture_contract["required_locales"])

    for index, fixture in enumerate(fixtures):
        label = f"fixtures[{index}]"
        if not isinstance(fixture, dict):
            errors.append(f"{label} harus object.")
            continue

        fixture_id = str(fixture.get("fixture_id", "")).strip()
        if not fixture_id:
            errors.append(f"{label}.fixture_id wajib diisi.")
        elif not re.fullmatch(r"[A-Za-z0-9_.-]+", fixture_id):
            errors.append(
                f"{label}.fixture_id hanya boleh berisi huruf, angka, "
                "titik, garis bawah, dan tanda minus."
            )
        ids.append(fixture_id)

        if fixture.get("fixture_source") not in allowed_sources:
            errors.append(f"{label}.fixture_source tidak terdaftar.")
        if fixture.get("expected_status") not in allowed_statuses:
            errors.append(f"{label}.expected_status tidak valid.")
        if fixture.get("pair") not in allowed_pairs:
            errors.append(f"{label}.pair tidak valid.")
        if fixture.get("timeframe") not in allowed_timeframes:
            errors.append(f"{label}.timeframe tidak valid.")
        if fixture.get("platform") not in allowed_platforms:
            errors.append(f"{label}.platform tidak valid.")
        if fixture.get("theme") not in allowed_themes:
            errors.append(f"{label}.theme tidak valid.")
        if fixture.get("locale") not in allowed_locales:
            errors.append(f"{label}.locale tidak valid.")
        if fixture.get("outcome_data_used") is not False:
            errors.append(f"{label} tidak boleh memakai outcome trading.")
        if not isinstance(fixture.get("tick_metric_eligible"), bool):
            errors.append(f"{label}.tick_metric_eligible harus boolean.")
        if fixture.get("fixture_source") == "EXTERNAL_REVIEWED" and (
            fixture.get("external_reviewed") is not True
        ):
            errors.append(f"{label} external wajib reviewed=true.")
        if fixture.get("fixture_source") == "DETERMINISTIC_SYNTHETIC" and (
            fixture.get("external_reviewed") is not False
        ):
            errors.append(f"{label} synthetic tidak boleh external reviewed.")

        scale_mode = fixture.get("scale_mode")
        if scale_mode not in {"AUTO", "LINEAR", "LOG", "PERCENT"}:
            errors.append(f"{label}.scale_mode tidak valid.")
        reason_codes = fixture.get("expected_reason_codes")
        if not isinstance(reason_codes, list) or not all(
            isinstance(value, str) for value in reason_codes
        ):
            errors.append(f"{label}.expected_reason_codes harus list string.")

        axis_region = fixture.get("expected_axis_region")
        if not isinstance(axis_region, list) or len(axis_region) != 4:
            errors.append(f"{label}.expected_axis_region harus empat angka.")
        else:
            try:
                axis_values = [float(value) for value in axis_region]
                if (
                    axis_values[2] <= axis_values[0]
                    or axis_values[3] <= axis_values[1]
                ):
                    errors.append(f"{label}.expected_axis_region tidak valid.")
            except (TypeError, ValueError):
                errors.append(f"{label}.expected_axis_region harus empat angka.")
        try:
            float(fixture["expected_plot_right_pixel"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{label}.expected_plot_right_pixel wajib angka.")

        ticks = fixture.get("ground_truth_ticks")
        if not isinstance(ticks, list):
            errors.append(f"{label}.ground_truth_ticks harus list.")
        else:
            for tick_index, tick in enumerate(ticks):
                if not isinstance(tick, dict):
                    errors.append(
                        f"{label}.ground_truth_ticks[{tick_index}] harus object."
                    )
                    continue
                for key in ("text", "price", "y_center"):
                    if key not in tick:
                        errors.append(
                            f"{label}.ground_truth_ticks[{tick_index}].{key} "
                            "wajib diisi."
                        )
                try:
                    float(tick["price"])
                    float(tick["y_center"])
                except (KeyError, TypeError, ValueError):
                    errors.append(
                        f"{label}.ground_truth_ticks[{tick_index}] "
                        "price/y_center wajib angka."
                    )
            if fixture.get("expected_status") == "CALIBRATED" and len(ticks) < 3:
                errors.append(
                    f"{label} CALIBRATED membutuhkan minimal tiga ground-truth tick."
                )

        try:
            image_path = resolve_fixture_path(
                manifest_path,
                fixture,
            )
            if not image_path.is_file():
                errors.append(f"{label} image tidak ditemukan: {image_path}")
        except ValueError as error:
            errors.append(str(error))

        digest = str(fixture.get("image_sha256", ""))
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            errors.append(f"{label}.image_sha256 wajib SHA256 hex.")

    duplicate_ids = [
        fixture_id
        for fixture_id, count in Counter(ids).items()
        if fixture_id and count > 1
    ]
    if duplicate_ids:
        errors.append(
            "fixture_id duplikat: " + ", ".join(sorted(duplicate_ids))
        )
    return errors


def _default_provider_factory(
    profile: dict[str, Any],
    tesseract_cmd: str | None,
) -> OptionalTesseractPriceAxisOCRProvider:
    return OptionalTesseractPriceAxisOCRProvider(
        preprocessing_profile=str(profile["preprocessing_profile"]),
        tesseract_cmd=tesseract_cmd,
    )


def _normalize_confidence(value: Any) -> float:
    return ScreenshotPriceAxisCalibrationService._normalize_confidence(value)


def recognized_ticks(
    ocr_result: dict[str, Any],
    *,
    pair: str,
    axis_region: tuple[int, int, int, int],
    minimum_confidence: float,
) -> list[dict[str, Any]]:
    left, top, _, _ = axis_region
    recognized: list[dict[str, Any]] = []
    for observation in ocr_result.get("observations") or []:
        if not isinstance(observation, dict):
            continue
        confidence = _normalize_confidence(observation.get("confidence"))
        if confidence < minimum_confidence:
            continue
        text = str(observation.get("text", "")).strip()
        price = ScreenshotPriceAxisCalibrationService.parse_price_label(
            text,
            pair,
        )
        if price is None:
            continue
        try:
            x_value = left + float(observation.get("left", 0.0))
            y_value = (
                top
                + float(observation["top"])
                + float(observation.get("height", 0.0)) / 2.0
            )
        except (KeyError, TypeError, ValueError):
            continue
        recognized.append(
            {
                "text": text,
                "price": float(price),
                "confidence": confidence,
                "x_center": x_value,
                "y_center": y_value,
            }
        )
    return recognized


def selected_ocr_pass(
    ocr_result: dict[str, Any],
    calibration: dict[str, Any],
) -> dict[str, Any]:
    passes = ocr_result.get("passes")
    selected_id = calibration.get("ocr_selected_pass_id")
    if not isinstance(passes, list) or not selected_id:
        return ocr_result

    for pass_payload in passes:
        if (
            isinstance(pass_payload, dict)
            and str(pass_payload.get("pass_id")) == str(selected_id)
        ):
            return {
                "status": ocr_result.get("status"),
                "engine": ocr_result.get("engine"),
                "tesseract_version": ocr_result.get(
                    "tesseract_version"
                ),
                "tesseract_cmd": ocr_result.get("tesseract_cmd"),
                "pass_id": selected_id,
                "preprocessing_profile": pass_payload.get(
                    "preprocessing_profile"
                ),
                "ocr_input_region": pass_payload.get("ocr_input_region"),
                "observations": pass_payload.get("observations") or [],
            }
    return ocr_result


def match_ticks(
    ground_truth: list[dict[str, Any]],
    recognized: list[dict[str, Any]],
    *,
    maximum_y_error: float,
    maximum_price_error: float,
) -> dict[str, Any]:
    candidates: list[tuple[float, int, int, float, float]] = []
    for ground_index, ground in enumerate(ground_truth):
        for recognized_index, detected in enumerate(recognized):
            y_error = abs(
                float(ground["y_center"])
                - float(detected["y_center"])
            )
            price_error = abs(
                float(ground["price"])
                - float(detected["price"])
            )
            if (
                y_error <= maximum_y_error
                and price_error <= maximum_price_error
            ):
                score = (
                    y_error / max(maximum_y_error, 1e-12)
                    + price_error / max(maximum_price_error, 1e-12)
                )
                candidates.append(
                    (
                        score,
                        ground_index,
                        recognized_index,
                        y_error,
                        price_error,
                    )
                )

    matched_ground: set[int] = set()
    matched_recognized: set[int] = set()
    matches: list[dict[str, Any]] = []
    for _, ground_index, recognized_index, y_error, price_error in sorted(
        candidates
    ):
        if (
            ground_index in matched_ground
            or recognized_index in matched_recognized
        ):
            continue
        matched_ground.add(ground_index)
        matched_recognized.add(recognized_index)
        ground = ground_truth[ground_index]
        detected = recognized[recognized_index]
        matches.append(
            {
                "ground_truth_index": ground_index,
                "recognized_index": recognized_index,
                "y_error_pixels": y_error,
                "price_error": price_error,
                "exact_text_match": (
                    str(ground["text"]).strip()
                    == str(detected["text"]).strip()
                ),
            }
        )

    return {
        "matches": matches,
        "true_positive": len(matches),
        "false_positive": len(recognized) - len(matches),
        "false_negative": len(ground_truth) - len(matches),
        "exact_text_match_count": sum(
            1 for match in matches if match["exact_text_match"]
        ),
    }


def _safe_rate(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _axis_iou(
    expected: list[Any],
    actual: tuple[int, int, int, int],
) -> float | None:
    try:
        expected_box = tuple(float(value) for value in expected)
        actual_box = tuple(float(value) for value in actual)
    except (TypeError, ValueError):
        return None
    if len(expected_box) != 4 or len(actual_box) != 4:
        return None

    intersection_left = max(expected_box[0], actual_box[0])
    intersection_top = max(expected_box[1], actual_box[1])
    intersection_right = min(expected_box[2], actual_box[2])
    intersection_bottom = min(expected_box[3], actual_box[3])
    intersection = max(0.0, intersection_right - intersection_left) * max(
        0.0,
        intersection_bottom - intersection_top,
    )
    expected_area = max(0.0, expected_box[2] - expected_box[0]) * max(
        0.0,
        expected_box[3] - expected_box[1],
    )
    actual_area = max(0.0, actual_box[2] - actual_box[0]) * max(
        0.0,
        actual_box[3] - actual_box[1],
    )
    union = expected_area + actual_area - intersection
    return intersection / union if union > 0 else None


def _axis_contains_expected(
    expected: list[Any],
    actual: tuple[int, int, int, int],
) -> bool:
    try:
        expected_box = tuple(float(value) for value in expected)
        actual_box = tuple(float(value) for value in actual)
    except (TypeError, ValueError):
        return False
    if len(expected_box) != 4 or len(actual_box) != 4:
        return False
    return (
        actual_box[0] <= expected_box[0]
        and actual_box[1] <= expected_box[1]
        and actual_box[2] >= expected_box[2]
        and actual_box[3] >= expected_box[3]
    )


def _ground_truth_price_step(ticks: list[dict[str, Any]]) -> float | None:
    ordered = sorted(ticks, key=lambda tick: float(tick["y_center"]))
    deltas = [
        abs(float(right["price"]) - float(left["price"]))
        for left, right in zip(ordered, ordered[1:])
        if float(right["price"]) != float(left["price"])
    ]
    if not deltas:
        return None
    return sorted(deltas)[len(deltas) // 2]


def benchmark_fixture(
    *,
    fixture: dict[str, Any],
    profile: dict[str, Any],
    manifest_path: Path,
    output_dir: Path,
    contract: dict[str, Any],
    provider_factory: ProviderFactory = _default_provider_factory,
    tesseract_cmd: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    fixture_id = str(fixture["fixture_id"])
    profile_id = str(profile["profile_id"])
    image_path = resolve_fixture_path(manifest_path, fixture)
    expected_digest = str(fixture["image_sha256"]).lower()
    actual_digest = file_sha256(image_path)
    if actual_digest != expected_digest:
        raise ValueError(
            f"SHA256 fixture berubah: {fixture_id}: "
            f"expected={expected_digest}, actual={actual_digest}"
        )

    image = Image.open(image_path)
    image.load()
    image = image.convert("RGB")
    geometry = ChartPlotGeometryService.analyze(image)
    axis_region, axis_region_method = (
        ScreenshotPriceAxisCalibrationService._axis_region(
            image,
            geometry,
        )
    )

    provider = provider_factory(profile, tesseract_cmd)
    ocr_result = provider.extract(image.crop(axis_region))
    service = ScreenshotPriceAxisCalibrationService(
        _StaticOCRProvider(ocr_result)
    )
    calibration = service.calibrate(
        image,
        pair=str(fixture["pair"]),
        plot_geometry=geometry,
        declared_scale_mode=str(fixture.get("scale_mode", "AUTO")),
    )
    metric_ocr_result = selected_ocr_pass(ocr_result, calibration)

    matching_contract = contract["matching_contract"]
    ground_truth = [
        dict(tick) for tick in fixture.get("ground_truth_ticks", [])
    ]
    detected = recognized_ticks(
        metric_ocr_result,
        pair=str(fixture["pair"]),
        axis_region=axis_region,
        minimum_confidence=float(
            matching_contract["minimum_ocr_confidence"]
        ),
    )
    matching = match_ticks(
        ground_truth,
        detected,
        maximum_y_error=float(
            matching_contract["maximum_tick_y_error_pixels"]
        ),
        maximum_price_error=float(
            matching_contract["maximum_tick_price_error"][
                str(fixture["pair"])
            ]
        ),
    )

    true_positive = matching["true_positive"]
    false_positive = matching["false_positive"]
    false_negative = matching["false_negative"]
    exact_matches = matching["exact_text_match_count"]
    tick_precision = _safe_rate(
        true_positive,
        true_positive + false_positive,
    )
    tick_recall = _safe_rate(
        true_positive,
        true_positive + false_negative,
    )
    exact_text_accuracy = _safe_rate(exact_matches, true_positive)
    y_errors = [
        float(match["y_error_pixels"])
        for match in matching["matches"]
    ]

    mapping_errors: list[float] = []
    if calibration.get("status") == "CALIBRATED":
        for tick in ground_truth:
            predicted = service.price_at_y(
                calibration,
                float(tick["y_center"]),
            )
            mapping_errors.append(
                abs(predicted - float(tick["price"]))
            )
    price_step = _ground_truth_price_step(ground_truth)
    normalized_errors = (
        [error / price_step for error in mapping_errors]
        if price_step and price_step > 0
        else []
    )
    slope = calibration.get("slope_price_per_pixel")
    try:
        absolute_slope = abs(float(slope))
    except (TypeError, ValueError):
        absolute_slope = 0.0
    pixel_errors = (
        [error / absolute_slope for error in mapping_errors]
        if absolute_slope > 0.0
        else []
    )

    expected_status = str(fixture["expected_status"])
    calibration_status = str(calibration.get("status"))
    reason_code = calibration.get("reason_code")
    expected_reasons = {
        str(value) for value in fixture.get("expected_reason_codes", [])
    }
    expected_status_match = calibration_status == expected_status
    if expected_status == "FAIL_CLOSED" and expected_reasons:
        expected_status_match = (
            expected_status_match and str(reason_code) in expected_reasons
        )

    entry_authorized = bool(
        calibration.get("entry_price_authorized", False)
    )
    production_changed = bool(
        calibration.get("production_decision_changed", False)
    )
    telemetry_boundary_valid = not entry_authorized and not production_changed
    false_calibration = (
        expected_status == "FAIL_CLOSED"
        and calibration_status == "CALIBRATED"
    )

    expected_plot_right = fixture.get("expected_plot_right_pixel")
    detected_plot_right = geometry.get("plot_right_pixel")
    plot_right_error: float | None = None
    if expected_plot_right is not None and detected_plot_right is not None:
        plot_right_error = abs(
            float(expected_plot_right) - float(detected_plot_right)
        )

    raw_payload = {
        "schema_version": 1,
        "experiment_id": str(contract["experiment_id"]),
        "fixture_id": fixture_id,
        "profile_id": profile_id,
        "image_sha256": actual_digest,
        "geometry": geometry,
        "axis_region": list(axis_region),
        "axis_region_method": axis_region_method,
        "ocr": ocr_result,
        "metric_ocr_pass_id": calibration.get("ocr_selected_pass_id"),
        "metric_ocr": metric_ocr_result,
        "recognized_ticks": detected,
        "ground_truth_ticks": ground_truth,
        "matching": matching,
        "calibration": calibration,
        "production_decision_changed": False,
        "trading_outcome_data_used": False,
    }
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{fixture_id}__{profile_id}.json"
    raw_path.write_text(
        json.dumps(raw_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raw_digest = file_sha256(raw_path)
    latency_ms = (time.perf_counter() - started) * 1000.0

    return {
        "schema_version": 1,
        "experiment_id": str(contract["experiment_id"]),
        "fixture_set_id": None,
        "fixture_id": fixture_id,
        "profile_id": profile_id,
        "fixture_source": fixture["fixture_source"],
        "external_reviewed": int(bool(fixture.get("external_reviewed"))),
        "pair": fixture["pair"],
        "timeframe": fixture["timeframe"],
        "platform": fixture["platform"],
        "theme": fixture["theme"],
        "locale": fixture["locale"],
        "variant": fixture.get("variant"),
        "scale_mode": fixture.get("scale_mode"),
        "tick_metric_eligible": int(
            bool(fixture.get("tick_metric_eligible"))
        ),
        "image_path": portable_path(image_path, manifest_path.parent),
        "image_sha256": actual_digest,
        "image_sha256_verified": 1,
        "request_status": "SUCCESS",
        "error": "",
        "geometry_status": geometry.get("status"),
        "geometry_method": geometry.get("method"),
        "plot_right_absolute_error_pixels": plot_right_error,
        "axis_region_method": axis_region_method,
        "axis_region_iou": _axis_iou(
            fixture.get("expected_axis_region", []),
            axis_region,
        ),
        "axis_region_contains_expected": int(
            _axis_contains_expected(
                fixture.get("expected_axis_region", []),
                axis_region,
            )
        ),
        "ocr_status": ocr_result.get("status"),
        "ocr_engine": ocr_result.get("engine"),
        "tesseract_version": ocr_result.get("tesseract_version"),
        "ocr_observation_count": len(
            metric_ocr_result.get("observations") or []
        ),
        "ocr_pass_count": int(calibration.get("ocr_pass_count") or 1),
        "ocr_selected_pass_id": calibration.get("ocr_selected_pass_id"),
        "ocr_filled_background_rejection_count": int(
            calibration.get(
                "ocr_filled_background_rejection_count",
                0,
            )
            or 0
        ),
        "ground_truth_tick_count": len(ground_truth),
        "recognized_tick_count": len(detected),
        "tick_true_positive": true_positive,
        "tick_false_positive": false_positive,
        "tick_false_negative": false_negative,
        "exact_text_match_count": exact_matches,
        "tick_precision": tick_precision,
        "tick_recall": tick_recall,
        "exact_text_accuracy": exact_text_accuracy,
        "mean_tick_y_error_pixels": mean(y_errors) if y_errors else None,
        "calibration_status": calibration_status,
        "calibration_reason_code": reason_code,
        "expected_status": expected_status,
        "expected_status_match": int(expected_status_match),
        "false_calibration": int(false_calibration),
        "fail_closed_expected": int(expected_status == "FAIL_CLOSED"),
        "fail_closed_correct": int(
            expected_status == "FAIL_CLOSED" and expected_status_match
        ),
        "mapping_point_count": len(mapping_errors),
        "mapping_absolute_error_sum": sum(mapping_errors),
        "mapping_normalized_absolute_error_sum": sum(normalized_errors),
        "mapping_pixel_absolute_error_sum": sum(pixel_errors),
        "mapping_mae": mean(mapping_errors) if mapping_errors else None,
        "mapping_maximum_error": max(mapping_errors) if mapping_errors else None,
        "normalized_mapping_mae": (
            mean(normalized_errors) if normalized_errors else None
        ),
        "mapping_mae_pixels": mean(pixel_errors) if pixel_errors else None,
        "mapping_maximum_error_pixels": (
            max(pixel_errors) if pixel_errors else None
        ),
        "entry_price_authorized": int(entry_authorized),
        "production_decision_changed": int(production_changed),
        "telemetry_boundary_valid": int(telemetry_boundary_valid),
        "latency_ms": latency_ms,
        "raw_response_path": portable_path(raw_path, output_dir),
        "raw_response_sha256": raw_digest,
    }


def error_row(
    fixture: dict[str, Any],
    profile: dict[str, Any],
    error: Exception,
    *,
    experiment_id: str = "E2.4.1",
) -> dict[str, Any]:
    row = {field: None for field in ROW_FIELDS}
    row.update(
        {
            "schema_version": 1,
            "experiment_id": experiment_id,
            "fixture_id": fixture.get("fixture_id"),
            "profile_id": profile.get("profile_id"),
            "fixture_source": fixture.get("fixture_source"),
            "external_reviewed": int(
                bool(fixture.get("external_reviewed"))
            ),
            "pair": fixture.get("pair"),
            "timeframe": fixture.get("timeframe"),
            "platform": fixture.get("platform"),
            "theme": fixture.get("theme"),
            "locale": fixture.get("locale"),
            "variant": fixture.get("variant"),
            "scale_mode": fixture.get("scale_mode"),
            "tick_metric_eligible": int(
                bool(fixture.get("tick_metric_eligible"))
            ),
            "image_path": fixture.get("image_path"),
            "image_sha256": fixture.get("image_sha256"),
            "request_status": "ERROR",
            "error": f"{type(error).__name__}: {error}",
            "expected_status": fixture.get("expected_status"),
            "production_decision_changed": 0,
            "telemetry_boundary_valid": 1,
        }
    )
    return row


def _coerce_csv_value(field: str, value: str) -> Any:
    if value == "":
        return None
    integer_fields = {
        "schema_version",
        "external_reviewed",
        "tick_metric_eligible",
        "image_sha256_verified",
        "axis_region_contains_expected",
        "ocr_observation_count",
        "ocr_pass_count",
        "ocr_filled_background_rejection_count",
        "ground_truth_tick_count",
        "recognized_tick_count",
        "tick_true_positive",
        "tick_false_positive",
        "tick_false_negative",
        "exact_text_match_count",
        "expected_status_match",
        "false_calibration",
        "fail_closed_expected",
        "fail_closed_correct",
        "mapping_point_count",
        "entry_price_authorized",
        "production_decision_changed",
        "telemetry_boundary_valid",
    }
    float_fields = {
        "plot_right_absolute_error_pixels",
        "axis_region_iou",
        "tick_precision",
        "tick_recall",
        "exact_text_accuracy",
        "mean_tick_y_error_pixels",
        "mapping_absolute_error_sum",
        "mapping_normalized_absolute_error_sum",
        "mapping_pixel_absolute_error_sum",
        "mapping_mae",
        "mapping_maximum_error",
        "normalized_mapping_mae",
        "mapping_mae_pixels",
        "mapping_maximum_error_pixels",
        "latency_ms",
    }
    if field in integer_fields:
        return int(float(value))
    if field in float_fields:
        return float(value)
    return value


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [
            {
                field: _coerce_csv_value(field, value)
                for field, value in row.items()
            }
            for row in csv.DictReader(handle)
        ]


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in ROW_FIELDS})
    temporary_path.replace(path)


def _run_contract(
    *,
    experiment_id: str,
    fixture_manifest_experiment_id: str,
    contract_path: Path,
    fixture_manifest_path: Path,
    profiles: list[dict[str, Any]],
    tesseract_cmd: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "fixture_manifest_experiment_id": fixture_manifest_experiment_id,
        "runner_version": RUNNER_VERSION,
        "runner_source_sha256": file_sha256(Path(__file__)),
        "calibration_service_source_sha256": file_sha256(
            CALIBRATION_SERVICE_SOURCE
        ),
        "contract_sha256": file_sha256(contract_path),
        "fixture_manifest_sha256": file_sha256(fixture_manifest_path),
        "profile_ids": [profile["profile_id"] for profile in profiles],
        "preprocessing_profiles": [
            profile["preprocessing_profile"] for profile in profiles
        ],
        "tesseract_cmd": tesseract_cmd,
        "training_performed": False,
        "model_inference_performed": False,
        "trading_outcome_data_used": False,
        "production_decision_changed": False,
    }


def ensure_resume_compatible(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> None:
    for key in (
        "schema_version",
        "experiment_id",
        "fixture_manifest_experiment_id",
        "runner_version",
        "runner_source_sha256",
        "calibration_service_source_sha256",
        "contract_sha256",
        "fixture_manifest_sha256",
        "profile_ids",
        "preprocessing_profiles",
        "tesseract_cmd",
    ):
        if previous.get(key) != current.get(key):
            raise ValueError(
                f"Resume ditolak karena {key} berubah: "
                f"{previous.get(key)!r} != {current.get(key)!r}"
            )


def validate_cached_rows(
    rows: list[dict[str, Any]],
    *,
    output_dir: Path,
    fixtures: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    expected_images = {
        str(fixture["fixture_id"]): str(fixture["image_sha256"]).lower()
        for fixture in fixtures
    }
    expected_keys = {
        (str(fixture["fixture_id"]), str(profile["profile_id"]))
        for fixture in fixtures
        for profile in profiles
    }
    selected: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        key = (str(row.get("fixture_id")), str(row.get("profile_id")))
        if key not in expected_keys:
            raise ValueError(
                "Resume ditolak: cached task tidak terdaftar: "
                f"{key[0]} / {key[1]}"
            )
        if key in selected:
            raise ValueError(
                "Resume ditolak: cached task duplikat: "
                f"{key[0]} / {key[1]}"
            )

        if row.get("request_status") != "SUCCESS":
            continue
        if int(row.get("image_sha256_verified") or 0) != 1:
            raise ValueError(
                f"Resume ditolak: image SHA belum verified: {key[0]}"
            )
        if str(row.get("image_sha256", "")).lower() != expected_images[key[0]]:
            raise ValueError(
                f"Resume ditolak: image SHA cached berubah: {key[0]}"
            )

        raw_relative = Path(str(row.get("raw_response_path") or ""))
        if raw_relative.is_absolute() or not raw_relative.parts:
            raise ValueError(
                f"Resume ditolak: raw response path tidak portable: {key[0]}"
            )
        raw_path = (output_dir / raw_relative).resolve()
        try:
            raw_path.relative_to(output_dir.resolve())
        except ValueError as error:
            raise ValueError(
                f"Resume ditolak: raw response keluar output: {key[0]}"
            ) from error
        if not raw_path.is_file():
            raise ValueError(
                f"Resume ditolak: raw response hilang: {raw_path}"
            )
        expected_raw_digest = str(row.get("raw_response_sha256") or "")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_raw_digest):
            raise ValueError(
                f"Resume ditolak: raw response SHA tidak valid: {key[0]}"
            )
        if file_sha256(raw_path) != expected_raw_digest.lower():
            raise ValueError(
                f"Resume ditolak: raw response SHA berubah: {key[0]}"
            )
        selected[key] = row

    return selected


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row.get("request_status") == "SUCCESS"]
    tick_rows = [
        row for row in successful if bool(row.get("tick_metric_eligible"))
    ]
    true_positive = sum(
        int(row.get("tick_true_positive") or 0) for row in tick_rows
    )
    false_positive = sum(
        int(row.get("tick_false_positive") or 0) for row in tick_rows
    )
    false_negative = sum(
        int(row.get("tick_false_negative") or 0) for row in tick_rows
    )
    exact_matches = sum(
        int(row.get("exact_text_match_count") or 0) for row in tick_rows
    )
    expected_calibrated = [
        row for row in successful if row.get("expected_status") == "CALIBRATED"
    ]
    expected_failed = [
        row for row in successful if row.get("expected_status") == "FAIL_CLOSED"
    ]
    mapping_points = sum(
        int(row.get("mapping_point_count") or 0) for row in successful
    )
    mapping_error_sum = sum(
        float(row.get("mapping_absolute_error_sum") or 0.0)
        for row in successful
    )
    normalized_error_sum = sum(
        float(row.get("mapping_normalized_absolute_error_sum") or 0.0)
        for row in successful
    )
    pixel_error_sum = sum(
        float(row.get("mapping_pixel_absolute_error_sum") or 0.0)
        for row in successful
    )
    latencies = [
        float(row["latency_ms"])
        for row in successful
        if row.get("latency_ms") is not None
    ]
    axis_rows = [
        row
        for row in successful
        if row.get("axis_region_contains_expected") is not None
    ]

    return {
        "task_count": len(rows),
        "successful_tasks": len(successful),
        "failed_tasks": len(rows) - len(successful),
        "fixture_count": len({row.get("fixture_id") for row in rows}),
        "external_fixture_count": len(
            {
                row.get("fixture_id")
                for row in rows
                if bool(row.get("external_reviewed"))
            }
        ),
        "tick_true_positive": true_positive,
        "tick_false_positive": false_positive,
        "tick_false_negative": false_negative,
        "tick_metric_eligible_fixture_count": len(
            {row.get("fixture_id") for row in tick_rows}
        ),
        "tick_precision": _safe_rate(
            true_positive,
            true_positive + false_positive,
        ),
        "tick_recall": _safe_rate(
            true_positive,
            true_positive + false_negative,
        ),
        "exact_text_accuracy": _safe_rate(exact_matches, true_positive),
        "axis_region_containment_recall": _safe_rate(
            sum(
                int(row.get("axis_region_contains_expected") or 0)
                for row in axis_rows
            ),
            len(axis_rows),
        ),
        "expected_calibration_count": len(expected_calibrated),
        "calibrated_expected_count": sum(
            int(row.get("expected_status_match") or 0)
            for row in expected_calibrated
        ),
        "expected_calibration_recall": _safe_rate(
            sum(
                int(row.get("expected_status_match") or 0)
                for row in expected_calibrated
            ),
            len(expected_calibrated),
        ),
        "expected_fail_closed_count": len(expected_failed),
        "correct_fail_closed_count": sum(
            int(row.get("fail_closed_correct") or 0)
            for row in expected_failed
        ),
        "fail_closed_recall": _safe_rate(
            sum(
                int(row.get("fail_closed_correct") or 0)
                for row in expected_failed
            ),
            len(expected_failed),
        ),
        "false_calibration_count": sum(
            int(row.get("false_calibration") or 0) for row in expected_failed
        ),
        "false_calibration_rate": _safe_rate(
            sum(
                int(row.get("false_calibration") or 0)
                for row in expected_failed
            ),
            len(expected_failed),
        ),
        "mapping_point_count": mapping_points,
        "mapping_mae": _safe_rate(mapping_error_sum, mapping_points),
        "normalized_mapping_mae": _safe_rate(
            normalized_error_sum,
            mapping_points,
        ),
        "mapping_mae_pixels": _safe_rate(
            pixel_error_sum,
            mapping_points,
        ),
        "telemetry_boundary_violations": sum(
            1 for row in successful if not bool(row.get("telemetry_boundary_valid"))
        ),
        "tesseract_versions": sorted(
            {
                str(row["tesseract_version"])
                for row in successful
                if row.get("tesseract_version")
            }
        ),
        "mean_latency_ms": mean(latencies) if latencies else None,
        "request_status_counts": dict(
            Counter(str(row.get("request_status")) for row in rows)
        ),
        "calibration_status_counts": dict(
            Counter(
                str(row.get("calibration_status"))
                for row in successful
            )
        ),
        "calibration_reason_counts": dict(
            Counter(
                str(row.get("calibration_reason_code"))
                for row in successful
                if row.get("calibration_reason_code")
            )
        ),
    }


def _version_major(versions: list[str]) -> int | None:
    majors: list[int] = []
    for version in versions:
        try:
            majors.append(int(str(version).split(".", 1)[0]))
        except (TypeError, ValueError):
            continue
    return min(majors) if majors else None


def _required_strata_gate(
    rows: list[dict[str, Any]],
    fixture_contract: dict[str, Any],
) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {
        str(row["fixture_id"]): row
        for row in rows
        if bool(row.get("external_reviewed"))
    }
    minimum = int(
        fixture_contract["minimum_count_per_required_stratum_value"]
    )
    dimensions = {
        "pair": fixture_contract["required_pairs"],
        "platform": fixture_contract["required_platforms"],
        "theme": fixture_contract["required_themes"],
        "timeframe": fixture_contract["required_timeframes"],
        "locale": fixture_contract["required_locales"],
    }
    counts: dict[str, dict[str, int]] = {}
    passed = True
    for field, values in dimensions.items():
        counts[field] = {
            str(value): sum(
                1 for row in unique.values() if row.get(field) == value
            )
            for value in values
        }
        if any(count < minimum for count in counts[field].values()):
            passed = False
    return {
        "passed": passed,
        "minimum_per_value": minimum,
        "counts": counts,
    }


def evaluate_gates(
    rows: list[dict[str, Any]],
    aggregate: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    acceptance = contract["acceptance_gates"]
    fixture_contract = contract["fixture_contract"]
    external_rows = [row for row in rows if bool(row.get("external_reviewed"))]
    external_aggregate = _aggregate(external_rows)
    strata = _required_strata_gate(rows, fixture_contract)
    minimum_version = int(acceptance["minimum_tesseract_major_version"])
    actual_version = _version_major(aggregate["tesseract_versions"])

    def at_least(value: Any, threshold: float) -> bool:
        return value is not None and float(value) >= threshold

    def at_most(value: Any, threshold: float) -> bool:
        return value is not None and float(value) <= threshold

    pair_mapping_gates: dict[str, bool] = {}
    for pair, threshold in acceptance.get("maximum_mapping_mae", {}).items():
        pair_rows = [row for row in external_rows if row.get("pair") == pair]
        pair_aggregate = _aggregate(pair_rows)
        pair_mapping_gates[pair] = at_most(
            pair_aggregate["mapping_mae"],
            float(threshold),
        )

    gates = {
        "minimum_total_fixtures": (
            aggregate["fixture_count"]
            >= int(fixture_contract["minimum_total_fixtures"])
        ),
        "minimum_external_fixtures": (
            external_aggregate["fixture_count"]
            >= int(fixture_contract["minimum_external_fixtures"])
        ),
        "required_external_strata": strata["passed"],
        "minimum_tick_precision": at_least(
            external_aggregate["tick_precision"],
            float(acceptance["minimum_tick_precision"]),
        ),
        "minimum_tick_recall": at_least(
            external_aggregate["tick_recall"],
            float(acceptance["minimum_tick_recall"]),
        ),
        "minimum_exact_text_accuracy": at_least(
            external_aggregate["exact_text_accuracy"],
            float(acceptance["minimum_exact_text_accuracy"]),
        ),
        "minimum_axis_region_containment_recall": at_least(
            external_aggregate["axis_region_containment_recall"],
            float(
                acceptance["minimum_axis_region_containment_recall"]
            ),
        ),
        "minimum_expected_calibration_recall": at_least(
            external_aggregate["expected_calibration_recall"],
            float(acceptance["minimum_expected_calibration_recall"]),
        ),
        "minimum_fail_closed_recall": at_least(
            external_aggregate["fail_closed_recall"],
            float(acceptance["minimum_fail_closed_recall"]),
        ),
        "maximum_false_calibration_rate": at_most(
            external_aggregate["false_calibration_rate"],
            float(acceptance["maximum_false_calibration_rate"]),
        ),
        "maximum_normalized_mapping_mae": at_most(
            external_aggregate["normalized_mapping_mae"],
            float(acceptance["maximum_normalized_mapping_mae"]),
        ),
        "minimum_tesseract_major_version": (
            actual_version is not None and actual_version >= minimum_version
        ),
        "canonical_ohlcv_parity": (
            aggregate["telemetry_boundary_violations"] == 0
        ),
        "no_production_decision_change": (
            aggregate["telemetry_boundary_violations"] == 0
        ),
    }
    if pair_mapping_gates:
        gates["maximum_mapping_mae_by_pair"] = all(
            pair_mapping_gates.values()
        )
    maximum_pixel_mae = acceptance.get("maximum_mapping_mae_pixels")
    if maximum_pixel_mae is not None:
        gates["maximum_mapping_mae_pixels"] = at_most(
            external_aggregate["mapping_mae_pixels"],
            float(maximum_pixel_mae),
        )
    return {
        "overall_pass": all(gates.values()),
        "gates": gates,
        "pair_mapping_gates": pair_mapping_gates,
        "external_strata": strata,
        "external_metrics": external_aggregate,
        "minimum_tesseract_major_version": minimum_version,
        "observed_minimum_tesseract_major_version": actual_version,
        "production_promotion_allowed": False,
    }


def build_summary(
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
    fixture_set_id: str,
    run_contract: dict[str, Any],
    *,
    evidence_role: str = "EXTERNAL_GATE",
) -> dict[str, Any]:
    profile_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        profile_rows[str(row.get("profile_id"))].append(row)

    profiles: dict[str, Any] = {}
    for profile_id, selected in sorted(profile_rows.items()):
        aggregate = _aggregate(selected)
        profiles[profile_id] = {
            "all_fixtures": aggregate,
            "synthetic_fixtures": _aggregate(
                [
                    row
                    for row in selected
                    if row.get("fixture_source")
                    == "DETERMINISTIC_SYNTHETIC"
                ]
            ),
            "external_fixtures": _aggregate(
                [row for row in selected if bool(row.get("external_reviewed"))]
            ),
            "acceptance": evaluate_gates(
                selected,
                aggregate,
                contract,
            ),
        }

    passing_profiles = [
        profile_id
        for profile_id, result in profiles.items()
        if result["acceptance"]["overall_pass"]
    ]
    technical_gate_pass = bool(passing_profiles)
    freeze_evaluated = evidence_role != "DEVELOPMENT_REGRESSION_ONLY"
    return {
        "schema_version": 1,
        "experiment_id": str(contract["experiment_id"]),
        "stage": str(contract["stage"]),
        "runner_version": RUNNER_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixture_set_id": fixture_set_id,
        "run_contract": run_contract,
        "task_count": len(rows),
        "profile_count": len(profiles),
        "profiles": profiles,
        "passing_profiles": passing_profiles,
        "technical_gate_pass": technical_gate_pass,
        "evidence_role": evidence_role,
        "freeze_evaluated": freeze_evaluated,
        "benchmark_pass": technical_gate_pass and freeze_evaluated,
        "production_promotion_allowed": False,
        "training_performed": False,
        "model_inference_performed": False,
        "trading_outcome_data_used": False,
        "canonical_production_decision_changed": False,
        "interpretation": (
            "Development regression only; technical targets cannot pass the "
            "E2.4.2 freeze. A fresh post-freeze external holdout is required."
            if evidence_role == "DEVELOPMENT_REGRESSION_ONLY"
            else "OCR engineering evidence only; passing cannot authorize entry."
        ),
    }


def render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# AI-TDSS {summary['experiment_id']} OCR Benchmark",
        "",
        f"Generated (UTC): `{summary['generated_at_utc']}`",
        f"Evidence role: `{summary['evidence_role']}`",
        "",
        "## Boundary",
        "",
        "- Model training/inference: `false`",
        "- Trading outcome data used: `false`",
        "- Production decision changed: `false`",
        "- Production promotion allowed: `false`",
        "",
        "## Synthetic smoke results",
        "",
        "| Profile | Tasks | Success | Precision | Recall | Exact text | "
        "Calibration recall | Fail-closed recall | False calibration | "
        "Normalized MAE | Pixel MAE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def percent(value: Any) -> str:
        return "—" if value is None else f"{float(value) * 100:.2f}%"

    def decimal(value: Any) -> str:
        return "—" if value is None else f"{float(value):.6f}"

    for profile_id, result in summary["profiles"].items():
        synthetic = result["synthetic_fixtures"]
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{profile_id}`",
                    str(synthetic["task_count"]),
                    str(synthetic["successful_tasks"]),
                    percent(synthetic["tick_precision"]),
                    percent(synthetic["tick_recall"]),
                    percent(synthetic["exact_text_accuracy"]),
                    percent(synthetic["expected_calibration_recall"]),
                    percent(synthetic["fail_closed_recall"]),
                    percent(synthetic["false_calibration_rate"]),
                    decimal(synthetic["normalized_mapping_mae"]),
                    decimal(synthetic["mapping_mae_pixels"]),
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "Synthetic results verify OCR execution and fail-closed behavior; "
            "they never select a production profile.",
            "",
            "## External reviewed gate results",
            "",
            "| Profile | External N | Precision | Recall | Exact text | "
            "Calibration recall | Fail-closed recall | False calibration | "
            "Normalized MAE | Pixel MAE | Gate |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )

    for profile_id, result in summary["profiles"].items():
        external = result["external_fixtures"]
        gate = result["acceptance"]["overall_pass"]
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{profile_id}`",
                    str(external["fixture_count"]),
                    percent(external["tick_precision"]),
                    percent(external["tick_recall"]),
                    percent(external["exact_text_accuracy"]),
                    percent(external["expected_calibration_recall"]),
                    percent(external["fail_closed_recall"]),
                    percent(external["false_calibration_rate"]),
                    decimal(external["normalized_mapping_mae"]),
                    decimal(external["mapping_mae_pixels"]),
                    "PASS" if gate else "FAIL",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Gate interpretation",
            "",
            (
                "Overall benchmark: **PASS**"
                if summary["benchmark_pass"]
                else (
                    "Development targets: **PASS**; E2.4.2 freeze: "
                    "**NOT EVALUATED**"
                    if summary.get("technical_gate_pass")
                    and not summary.get("freeze_evaluated")
                    else "Overall benchmark: **FAIL / INCOMPLETE**"
                )
            ),
            "",
            "Synthetic fixtures are smoke tests. Profile selection and gate "
            "acceptance use reviewed external TradingView/MT5 fixtures only.",
            "A PASS does not change BUY/SELL/WATCHLIST/NO_TRADE, entry/SL/TP, "
            "High Risk, canonical OHLCV, or locked outcome datasets.",
            summary["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def run(
    args: argparse.Namespace,
    *,
    provider_factory: ProviderFactory = _default_provider_factory,
) -> dict[str, Any]:
    contract_path = args.contract.resolve()
    manifest_path = args.fixture_manifest.resolve()
    output_dir = args.output_dir.resolve()
    contract = read_json(contract_path)
    manifest = read_json(manifest_path)

    contract_errors = validate_contract(contract)
    if (
        not contract_errors
        and contract.get("status")
        == "IMPLEMENTATION_FROZEN_AWAITING_HOLDOUT"
    ):
        implementation_freeze = contract["implementation_freeze"]
        frozen_sources = {
            "calibration_service_source_sha256": file_sha256(
                CALIBRATION_SERVICE_SOURCE
            ),
            "benchmark_runner_source_sha256": file_sha256(Path(__file__)),
        }
        for key, actual_digest in frozen_sources.items():
            expected_digest = str(implementation_freeze[key]).lower()
            if actual_digest != expected_digest:
                contract_errors.append(
                    f"Frozen source SHA berubah untuk {key}: "
                    f"expected={expected_digest}, actual={actual_digest}"
                )
    manifest_errors = validate_manifest(manifest, contract, manifest_path)
    errors = contract_errors + manifest_errors
    if errors:
        raise ValueError(
            f"{contract.get('experiment_id', 'OCR')} INVALID: "
            + "; ".join(errors)
        )

    profiles = resolve_profiles(contract, args.profile_ids)
    effective_tesseract_cmd = (
        str(args.tesseract_cmd).strip()
        if args.tesseract_cmd
        else str(os.getenv("AI_TDSS_TESSERACT_CMD", "")).strip()
    ) or None
    run_contract = _run_contract(
        experiment_id=str(contract["experiment_id"]),
        fixture_manifest_experiment_id=str(manifest["experiment_id"]),
        contract_path=contract_path,
        fixture_manifest_path=manifest_path,
        profiles=profiles,
        tesseract_cmd=effective_tesseract_cmd,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = (
        str(contract["experiment_id"])
        .lower()
        .replace(".", "_")
        + "_ocr_benchmark"
    )
    rows_path = output_dir / f"{output_prefix}_rows.csv"
    summary_json_path = output_dir / f"{output_prefix}_summary.json"
    summary_md_path = output_dir / f"{output_prefix}_summary.md"
    run_contract_path = output_dir / "run_contract.json"

    existing_rows = read_rows(rows_path)
    if existing_rows and not args.resume:
        raise FileExistsError(
            "Output benchmark sudah ada; gunakan --resume atau output baru."
        )
    if args.resume and run_contract_path.exists():
        ensure_resume_compatible(
            read_json(run_contract_path),
            run_contract,
        )
    elif args.resume and existing_rows:
        raise ValueError("Resume ditolak: run_contract.json tidak ditemukan.")

    run_contract_path.write_text(
        json.dumps(run_contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    existing_by_key = validate_cached_rows(
        existing_rows,
        output_dir=output_dir,
        fixtures=manifest["fixtures"],
        profiles=profiles,
    )
    tasks = [
        (fixture, profile)
        for profile in profiles
        for fixture in manifest["fixtures"]
    ]
    pending = [
        task
        for task in tasks
        if (
            str(task[0]["fixture_id"]),
            str(task[1]["profile_id"]),
        )
        not in existing_by_key
    ]
    if args.limit > 0:
        pending = pending[: args.limit]

    print(
        f"Selected: {len(tasks)} | Cached: {len(existing_by_key)} | "
        f"Pending: {len(pending)}"
    )
    print(f"Output: {output_dir}")

    for index, (fixture, profile) in enumerate(pending, start=1):
        try:
            row = benchmark_fixture(
                fixture=fixture,
                profile=profile,
                manifest_path=manifest_path,
                output_dir=output_dir,
                contract=contract,
                provider_factory=provider_factory,
                tesseract_cmd=effective_tesseract_cmd,
            )
            row["fixture_set_id"] = manifest["fixture_set_id"]
        except Exception as error:
            row = error_row(
                fixture,
                profile,
                error,
                experiment_id=str(contract["experiment_id"]),
            )
            row["fixture_set_id"] = manifest["fixture_set_id"]
            if args.fail_fast:
                existing_by_key[
                    (str(fixture["fixture_id"]), str(profile["profile_id"]))
                ] = row
                write_rows(
                    rows_path,
                    sorted(
                        existing_by_key.values(),
                        key=lambda value: (
                            str(value.get("profile_id")),
                            str(value.get("fixture_id")),
                        ),
                    ),
                )
                raise

        existing_by_key[
            (str(fixture["fixture_id"]), str(profile["profile_id"]))
        ] = row
        if (
            index == 1
            or index == len(pending)
            or index % max(1, args.progress_every) == 0
        ):
            print(
                f"[{index}/{len(pending)}] {fixture['fixture_id']} / "
                f"{profile['profile_id']} -> {row['request_status']} | "
                f"ocr={row.get('ocr_status')} | "
                f"cal={row.get('calibration_status')}"
            )
        write_rows(
            rows_path,
            sorted(
                existing_by_key.values(),
                key=lambda value: (
                    str(value.get("profile_id")),
                    str(value.get("fixture_id")),
                ),
            ),
        )

    rows = sorted(
        existing_by_key.values(),
        key=lambda value: (
            str(value.get("profile_id")),
            str(value.get("fixture_id")),
        ),
    )
    evidence_role = "EXTERNAL_GATE"
    if (
        contract.get("experiment_id") == "E2.4.2"
        and manifest.get("experiment_id") != "E2.4.2"
    ):
        evidence_role = "DEVELOPMENT_REGRESSION_ONLY"
    elif contract.get("experiment_id") == "E2.4.2":
        evidence_role = "FRESH_EXTERNAL_HOLDOUT"

    summary = build_summary(
        rows,
        contract,
        str(manifest["fixture_set_id"]),
        run_contract,
        evidence_role=evidence_role,
    )
    summary_json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_md_path.write_text(
        render_summary_markdown(summary),
        encoding="utf-8-sig",
    )

    print(f"Rows: {rows_path}")
    print(f"Summary: {summary_json_path}")
    print(f"Report: {summary_md_path}")
    return summary


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
