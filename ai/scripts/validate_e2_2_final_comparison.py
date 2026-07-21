from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FREEZE = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_2_plot_mapping_freeze.json"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)

    if not isinstance(value, dict):
        raise ValueError(f"JSON root harus berupa object: {path}")

    return value


def validate_freeze_contract(
    freeze: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    policy = freeze.get("mapping_policy", {})
    final = freeze.get("final_comparison_protocol", {})
    guardrails = freeze.get("interpretation_guardrails", {})

    expected = {
        "schema_version": 1,
        "experiment_id": "E2.2",
        "decision_status": "FROZEN_FOR_SINGLE_FINAL_COMPARISON",
        "training_performed": False,
    }

    for key, value in expected.items():
        if freeze.get(key) != value:
            errors.append(f"Freeze field {key!r} harus bernilai {value!r}.")

    if policy.get("production_default") != "FULL_IMAGE":
        errors.append("Default produksi E2.2 harus tetap FULL_IMAGE.")
    if policy.get("candidate_mode") != "PLOT_AWARE":
        errors.append("Mode kandidat E2.2 harus PLOT_AWARE.")
    if policy.get("opt_in_query_parameter") != "plot_aware_mapping":
        errors.append("Query parameter kandidat E2.2 berubah.")
    if policy.get("uncertain_geometry_fallback") != "FULL_IMAGE":
        errors.append("Geometry tidak pasti harus fallback ke FULL_IMAGE.")
    if not policy.get("production_promotion_deferred"):
        errors.append("Promosi produksi harus ditunda sampai final comparison.")

    expected_final = {
        "pair": "GBPUSD",
        "year": 2025,
        "timeframes": ["H1", "H4", "M15", "M5"],
        "sample_size": 0,
        "sample_seed": 42,
        "confidence_threshold": 0.25,
        "chart_candles": 100,
        "context_candles": 300,
        "utc_offset": 0.0,
        "runs_per_mode": 1,
        "resume_same_run_only": True,
        "require_clean_git_tree": True,
        "require_matching_lineage_between_modes": True,
        "tuning_after_results_allowed": False,
    }

    for key, value in expected_final.items():
        if final.get(key) != value:
            errors.append(
                f"Final protocol {key!r} harus bernilai {value!r}."
            )

    expected_guardrails = {
        "coverage_is_accuracy": False,
        "actionable_coverage_is_profitability": False,
        "local_matcher_is_independent_ground_truth": False,
        "raw_predictions_are_ground_truth": False,
        "verified_outcomes_required_for_trade_quality_claims": True,
        "final_2025_results_may_change_frozen_constants": False,
    }

    for key, value in expected_guardrails.items():
        if guardrails.get(key) != value:
            errors.append(
                f"Interpretation guardrail {key!r} harus {value!r}."
            )

    return errors


def _expected_run_values(
    freeze: dict[str, Any],
) -> dict[str, Any]:
    final = freeze["final_comparison_protocol"]

    return {
        "year": final["year"],
        "pairs": [final["pair"]],
        "timeframes": final["timeframes"],
        "sample_size_requested": final["sample_size"],
        "sample_seed": final["sample_seed"],
        "confidence_threshold": final["confidence_threshold"],
        "chart_candles": final["chart_candles"],
        "context_candles": final["context_candles"],
        "utc_offset": final["utc_offset"],
        "training_performed": False,
        "image_ids_requested": [],
        "include_annotated_chart": False,
        "review_pack": False,
    }


def validate_final_pair(
    freeze: dict[str, Any],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> list[str]:
    errors = validate_freeze_contract(freeze)

    if errors:
        return errors

    expected = _expected_run_values(freeze)

    for mode, run in (
        ("baseline", baseline),
        ("candidate", candidate),
    ):
        for key, value in expected.items():
            if run.get(key) != value:
                errors.append(
                    f"{mode}.{key} harus {value!r}, "
                    f"bukan {run.get(key)!r}."
                )

        if run.get("git_dirty") is not False:
            errors.append(f"{mode} harus dijalankan dari git tree bersih.")
        if run.get("interrupted") is not False:
            errors.append(f"{mode} masih berstatus interrupted.")
        if run.get("stopped_due_to_errors") is not False:
            errors.append(f"{mode} berhenti karena request errors.")
        if run.get("processed_rows") != run.get("selected_images"):
            errors.append(
                f"{mode} belum memproses seluruh selected_images."
            )
        if not isinstance(run.get("selected_images"), int) or (
            run.get("selected_images", 0) <= 0
        ):
            errors.append(f"{mode}.selected_images harus lebih dari nol.")

    if baseline.get("plot_aware_mapping") is not False:
        errors.append("baseline.plot_aware_mapping harus false.")
    if candidate.get("plot_aware_mapping") is not True:
        errors.append("candidate.plot_aware_mapping harus true.")

    matched_fields = (
        "schema_version",
        "base_url",
        "git_commit",
        "dataset_version",
        "dataset_status",
        "metadata",
        "images_root",
        "metadata_sha256",
        "project_contract_sha256",
        "ensemble_config_sha256",
        "sample_digest_sha256",
        "selected_images",
    )

    for key in matched_fields:
        if key not in baseline or baseline.get(key) in (None, ""):
            errors.append(f"baseline.{key} wajib tersedia.")
        if key not in candidate or candidate.get(key) in (None, ""):
            errors.append(f"candidate.{key} wajib tersedia.")
        if baseline.get(key) != candidate.get(key):
            errors.append(
                f"Lineage mismatch pada {key}: "
                f"{baseline.get(key)!r} != {candidate.get(key)!r}."
            )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that the two frozen E2.2 final-test runs differ only "
            "by the approved plot-aware mapping mode."
        )
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to the full-image run_config.json.",
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Path to the plot-aware run_config.json.",
    )
    parser.add_argument(
        "--freeze",
        type=Path,
        default=DEFAULT_FREEZE,
        help="Path to the E2.2 machine-readable freeze contract.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        freeze = load_json(args.freeze)
        baseline = load_json(args.baseline)
        candidate = load_json(args.candidate)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"E2.2 final comparison INVALID: {exc}")
        return 1

    errors = validate_final_pair(
        freeze,
        baseline,
        candidate,
    )

    if errors:
        print("E2.2 final comparison INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print("E2.2 final comparison VALID")
    print(f"Baseline: {args.baseline.resolve()}")
    print(f"Candidate: {args.candidate.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
