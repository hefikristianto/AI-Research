from __future__ import annotations

import unittest

from app.services.decision_coverage_audit_service import (
    DecisionCoverageAuditService,
)


class DecisionCoverageAuditServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sample = {
            "image_id": "GBPUSD_M5_2025_SAMPLE",
            "file_name": "gbpusd_m5_2025_sample.png",
            "image_path": "C:/data/gbpusd_m5_2025_sample.png",
            "pair": "GBPUSD",
            "timeframe": "M5",
            "year": "2025",
            "chart_datetime": "2025-01-03 09:15:00",
        }

    def test_success_row_extracts_live_decision_funnel(self) -> None:
        row = DecisionCoverageAuditService.success_row(
            self.sample,
            {
                "pipeline_status": "EXECUTION_COMPLETE",
                "regime": {
                    "label": "bullish",
                    "confidence": 0.649,
                },
                "detection": {
                    "total": 2,
                    "class_counts": {
                        "order_block": 1,
                        "fair_value_gap": 1,
                    },
                },
                "pairing": {
                    "total_pairs": 1,
                    "pairing_status": "PAIRS_FOUND",
                },
                "scoring": {
                    "total_setups": 1,
                    "valid_setups": 1,
                    "best_setup": {
                        "live_status": "ACCEPT",
                    },
                },
                "price_conversion": {
                    "status": "MAPPED",
                    "mapping_confidence": 0.82,
                },
                "execution_gate": {
                    "entry_distance_atr": 1.8,
                },
                "recommendation": {
                    "decision": "WATCHLIST",
                    "internal_decision": "WAIT",
                    "execution_status": "REVIEW",
                    "final_decision_ready": False,
                    "actionable": False,
                    "setup_direction": "bullish",
                    "blockers": [],
                    "warnings": [
                        "ENTRY_DISTANCE_ABOVE_1_5_ATR",
                    ],
                    "reasons": [
                        "ENTRY_DISTANCE_ABOVE_1_5_ATR",
                    ],
                },
            },
            latency_ms=123.4567,
        )

        self.assertEqual(row["request_status"], "SUCCESS")
        self.assertEqual(row["decision"], "WATCHLIST")
        self.assertEqual(row["detection_count"], 2)
        self.assertEqual(row["order_block_count"], 1)
        self.assertEqual(row["fair_value_gap_count"], 1)
        self.assertEqual(row["pair_count"], 1)
        self.assertEqual(row["valid_setup_count"], 1)
        self.assertEqual(row["best_setup_status"], "ACCEPT")
        self.assertEqual(row["actionable"], 0)
        self.assertEqual(
            row["warnings"],
            "ENTRY_DISTANCE_ABOVE_1_5_ATR",
        )
        self.assertEqual(row["latency_ms"], 123.457)

    def test_summary_uses_only_successful_responses_as_denominator(
        self,
    ) -> None:
        actionable = DecisionCoverageAuditService.success_row(
            self.sample,
            {
                "regime": {"label": "bullish"},
                "detection": {
                    "total": 2,
                    "class_counts": {
                        "order_block": 1,
                        "fair_value_gap": 1,
                    },
                },
                "pairing": {
                    "total_pairs": 1,
                    "pairing_status": "PAIRS_FOUND",
                },
                "scoring": {
                    "total_setups": 1,
                    "valid_setups": 1,
                    "best_setup": {
                        "live_status": "ACCEPT",
                    },
                },
                "recommendation": {
                    "decision": "BUY",
                    "internal_decision": "BUY",
                    "execution_status": "TRADE_CANDIDATE",
                    "final_decision_ready": True,
                    "actionable": True,
                    "blockers": [],
                    "warnings": [],
                    "reasons": ["ALL_EXECUTION_GATES_PASSED"],
                },
            },
            latency_ms=100,
        )

        no_trade_sample = dict(self.sample)
        no_trade_sample["image_id"] = "GBPUSD_M5_2025_NO_SETUP"
        no_trade = DecisionCoverageAuditService.success_row(
            no_trade_sample,
            {
                "regime": {"label": "sideways"},
                "detection": {
                    "total": 0,
                    "class_counts": {},
                },
                "pairing": {
                    "total_pairs": 0,
                    "pairing_status": "NO_VALID_PAIR",
                },
                "scoring": {
                    "total_setups": 0,
                    "valid_setups": 0,
                    "best_setup": None,
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
            },
            latency_ms=200,
        )

        failed_sample = dict(self.sample)
        failed_sample["image_id"] = "GBPUSD_M5_2025_MISSING"
        failed = DecisionCoverageAuditService.error_row(
            failed_sample,
            request_status="IMAGE_MISSING",
            error="missing",
        )

        summary = DecisionCoverageAuditService.summarize(
            [actionable, no_trade, failed],
            {
                "year": 2025,
                "pairs": ["GBPUSD"],
                "timeframes": ["M5"],
                "confidence_threshold": 0.25,
                "selected_images": 3,
            },
        )

        self.assertEqual(summary["population"]["successful_responses"], 2)
        self.assertEqual(summary["population"]["failed_responses"], 1)
        self.assertEqual(
            summary["coverage"]["detection"],
            {"count": 1, "denominator": 2, "rate": 0.5},
        )
        self.assertEqual(
            summary["coverage"]["paired_setup"],
            {"count": 1, "denominator": 2, "rate": 0.5},
        )
        self.assertEqual(
            summary["coverage"]["valid_setup"],
            {"count": 1, "denominator": 2, "rate": 0.5},
        )
        self.assertEqual(
            summary["coverage"]["actionable"],
            {"count": 1, "denominator": 2, "rate": 0.5},
        )
        self.assertEqual(
            summary["distributions"]["blockers"],
            {"NO_VALID_SETUP": 1},
        )
        self.assertEqual(
            summary["distributions"]["failure_status"],
            {"IMAGE_MISSING": 1},
        )
        self.assertEqual(summary["latency"]["p50_ms"], 150.0)
        self.assertEqual(summary["latency"]["p95_ms"], 200.0)

        markdown = DecisionCoverageAuditService.render_markdown(summary)
        self.assertIn("Actionable BUY/SELL", markdown)
        self.assertIn("Coverage measures pipeline selectivity", markdown)
        self.assertIn("not evidence of profitability", markdown)


if __name__ == "__main__":
    unittest.main()
