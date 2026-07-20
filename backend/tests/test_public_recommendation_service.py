from __future__ import annotations

import unittest

from app.services.public_recommendation_service import (
    PublicRecommendationService,
)


class PublicRecommendationServiceTest(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.service = PublicRecommendationService()

    def test_ready_buy_is_actionable(self) -> None:
        result = self.service.build(
            {
                "decision": "BUY",
                "execution_status": "TRADE_CANDIDATE",
                "final_decision_ready": True,
                "entry": 1.275,
                "stop_loss": 1.27,
                "take_profit": 1.285,
                "risk_reward_ratio": 2.0,
            }
        )

        self.assertEqual(result["decision"], "BUY")
        self.assertTrue(result["actionable"])
        self.assertFalse(result["educational_only"])
        self.assertEqual(result["entry"], 1.275)

    def test_review_maps_to_watchlist(self) -> None:
        result = self.service.build(
            {
                "decision": "WAIT",
                "execution_status": "REVIEW",
                "final_decision_ready": False,
                "warnings": [
                    "LOW_SESSION_SUITABILITY"
                ],
            }
        )

        self.assertEqual(
            result["decision"],
            "WATCHLIST",
        )
        self.assertFalse(result["actionable"])

    def test_no_setup_maps_to_no_trade(self) -> None:
        result = self.service.build(
            {
                "decision": "WAIT",
                "execution_status": "NO_SETUP",
                "final_decision_ready": False,
                "blockers": ["NO_VALID_SETUP"],
            }
        )

        self.assertEqual(
            result["decision"],
            "NO_TRADE",
        )

    def test_unready_buy_redacts_trade_levels(self) -> None:
        result = self.service.build(
            {
                "decision": "BUY",
                "execution_status": "REVIEW",
                "final_decision_ready": False,
                "entry": 1.275,
                "stop_loss": 1.270,
                "take_profit": 1.285,
                "risk_reward_ratio": 2.0,
                "order_type": "BUY_LIMIT",
            }
        )

        self.assertEqual(
            result["decision"],
            "WATCHLIST",
        )
        self.assertIsNone(result["entry"])
        self.assertIsNone(result["stop_loss"])
        self.assertIsNone(result["take_profit"])
        self.assertIsNone(result["risk_reward_ratio"])
        self.assertIsNone(result["order_type"])

    def test_inconsistent_ready_flag_fails_closed(
        self,
    ) -> None:
        result = self.service.build(
            {
                "decision": "SELL",
                "execution_status": "INVALID",
                "final_decision_ready": True,
                "entry": 1.275,
            }
        )

        self.assertEqual(
            result["decision"],
            "NO_TRADE",
        )
        self.assertFalse(result["actionable"])
        self.assertIsNone(result["entry"])
