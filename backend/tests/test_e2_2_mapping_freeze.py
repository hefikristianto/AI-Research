from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

from ai.scripts.validate_e2_2_final_comparison import (
    validate_final_pair,
    validate_freeze_contract,
)
from app.services.chart_plot_geometry_service import (
    ChartPlotGeometryService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_2_plot_mapping_freeze.json"
)
DECISION_PATH = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_2_plot_mapping_decision.json"
)


class E22MappingFreezeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.freeze = json.loads(
            FREEZE_PATH.read_text(encoding="utf-8")
        )
        self.decision = json.loads(
            DECISION_PATH.read_text(encoding="utf-8")
        )

    def test_freeze_contract_is_valid(self) -> None:
        self.assertEqual(
            validate_freeze_contract(self.freeze),
            [],
        )

    def test_frozen_geometry_constants_match_implementation(self) -> None:
        constants = self.freeze["geometry_constants"]

        self.assertEqual(
            constants["difference_threshold"],
            ChartPlotGeometryService.DIFFERENCE_THRESHOLD,
        )
        self.assertEqual(
            constants["minimum_span_ratio"],
            ChartPlotGeometryService.MINIMUM_SPAN_RATIO,
        )
        self.assertEqual(
            constants["maximum_span_ratio"],
            ChartPlotGeometryService.MAXIMUM_SPAN_RATIO,
        )
        self.assertEqual(
            constants["minimum_margin_ratio"],
            ChartPlotGeometryService.MINIMUM_MARGIN_RATIO,
        )
        self.assertEqual(
            constants["maximum_margin_ratio"],
            ChartPlotGeometryService.MAXIMUM_MARGIN_RATIO,
        )
        self.assertEqual(
            constants["minimum_active_column_ratio"],
            ChartPlotGeometryService.MINIMUM_ACTIVE_COLUMN_RATIO,
        )

    def test_api_default_remains_opt_in(self) -> None:
        source = (
            PROJECT_ROOT
            / "backend"
            / "app"
            / "api"
            / "full_analysis.py"
        ).read_text(encoding="utf-8")

        self.assertIsNotNone(
            re.search(
                r"plot_aware_mapping:\s*bool\s*=\s*Query\(\s*"
                r"default=False,",
                source,
            )
        )

    def test_final_decision_promotes_only_canonical_mapping(self) -> None:
        evidence = self.decision["final_comparison_evidence"]
        review = self.decision["targeted_review_evidence"]
        policy = self.decision["selected_policy"]
        guardrails = self.decision["interpretation_guardrails"]

        self.assertEqual(
            self.decision["decision_status"],
            "PROMOTED_FOR_CANONICAL_PIPELINE",
        )
        self.assertEqual(
            self.decision["freeze_contract"],
            "config/experiments/e2_2_plot_mapping_freeze.json",
        )
        self.assertFalse(self.decision["training_performed"])
        self.assertEqual(evidence["population"], 165)
        self.assertEqual(evidence["successful_responses_per_mode"], 165)
        self.assertEqual(evidence["failed_responses_per_mode"], 0)
        self.assertEqual(
            evidence["git_commit"],
            "9e3d33ff6bcb3664bcc98fb13ea6c7e4b4ee80af",
        )
        self.assertEqual(
            evidence["sample_digest_sha256"],
            "cae8c845214492a1085dfd93e6979b28e0dee1867ed6b4e168b1988a2a95c9f3",
        )
        self.assertEqual(
            evidence["public_decisions"]["full_image"],
            {"NO_TRADE": 153, "WATCHLIST": 12, "BUY": 0, "SELL": 0},
        )
        self.assertEqual(
            evidence["public_decisions"]["plot_aware"],
            {"NO_TRADE": 150, "WATCHLIST": 14, "BUY": 0, "SELL": 1},
        )
        self.assertEqual(evidence["paired_ob_error"]["worsened"], 0)
        self.assertEqual(evidence["paired_fvg_error"]["worsened"], 2)
        self.assertEqual(
            evidence["actionable_candidate"]["image_id"],
            "GBPUSD_H4_2025_20250522_000000_0007",
        )
        self.assertFalse(evidence["actionable_candidate"]["outcome_verified"])
        self.assertEqual(policy["canonical_generated_chart_mapping"], "PLOT_AWARE")
        self.assertEqual(policy["e2_3_canonical_experiment_mapping"], "PLOT_AWARE")
        self.assertEqual(policy["arbitrary_user_upload_api_default"], "FULL_IMAGE")
        self.assertEqual(policy["uncertain_geometry_fallback"], "FULL_IMAGE")
        self.assertTrue(policy["global_default_promotion_deferred"])
        self.assertGreaterEqual(
            len(policy["external_screenshot_validation_required"]),
            4,
        )
        self.assertEqual(review["selected_cases_per_mode"], 7)
        self.assertEqual(review["rendered_and_sha256_verified_per_mode"], 7)
        self.assertEqual(review["artifact_errors"], 0)
        self.assertTrue(review["annotated_chart_boxes_unchanged_between_modes"])
        self.assertEqual(review["changed_pixels_below_decision_banner"], 0)
        self.assertFalse(guardrails["actionable_candidate_outcome_verified"])
        self.assertFalse(guardrails["global_upload_robustness_established"])

    def test_final_pair_rejects_lineage_or_parameter_drift(self) -> None:
        final = self.freeze["final_comparison_protocol"]
        common = {
            "schema_version": 3,
            "base_url": "http://127.0.0.1:8000",
            "git_commit": "frozen-commit",
            "git_dirty": False,
            "dataset_version": "v1.0",
            "dataset_status": "raw_chart_generated",
            "metadata": "chart_image_metadata.csv",
            "images_root": "charts",
            "metadata_sha256": "metadata",
            "project_contract_sha256": "contract",
            "ensemble_config_sha256": "ensemble",
            "sample_digest_sha256": "sample",
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
            "selected_images": 165,
            "processed_rows": 165,
            "interrupted": False,
            "stopped_due_to_errors": False,
        }
        baseline = {**common, "plot_aware_mapping": False}
        candidate = {**common, "plot_aware_mapping": True}

        self.assertEqual(
            validate_final_pair(
                self.freeze,
                baseline,
                candidate,
            ),
            [],
        )

        drifted = copy.deepcopy(candidate)
        drifted["chart_candles"] = 99
        drifted["sample_digest_sha256"] = "different-sample"
        errors = validate_final_pair(
            self.freeze,
            baseline,
            drifted,
        )

        self.assertTrue(
            any("candidate.chart_candles" in error for error in errors)
        )
        self.assertTrue(
            any("sample_digest_sha256" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
