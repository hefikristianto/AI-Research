from __future__ import annotations

import unittest

from app.services.live_execution_gate_service import (
    LiveExecutionGateService,
)


class LiveExecutionGateServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = LiveExecutionGateService()
        self.advanced = {
            "status": "HTF_VOLATILITY_SCORING_COMPLETE",
            "setup_direction": "bullish",
            "advanced_score": 0.70,
            "advanced_status": "ACCEPT",
            "detector_valid": True,
            "volatility_regime": "NORMAL",
        }
        self.context = {"direction_conflict": False}
        self.htf = {"htf_alignment_score": 0.80}
        self.structure = {}

    @staticmethod
    def _session_risk(session_score: float) -> dict[str, object]:
        return {
            "status": "SESSION_RISK_COMPLETE",
            "session": {
                "session": "LONDON",
                "session_score": session_score,
            },
            "risk_reward": {
                "status": "COMPLETE",
                "risk_reward_ratio": 2.0,
                "entry_side_valid": True,
                "zone_invalidated": False,
                "price_mapping_provisional": False,
                "entry": 1.25,
                "stop_loss": 1.24,
                "take_profit": 1.27,
            },
        }

    def _evaluate(self, session_score: float) -> dict[str, object]:
        return self.service.evaluate(
            advanced_scoring=self.advanced,
            context_scoring=self.context,
            htf_volatility=self.htf,
            session_risk=self._session_risk(session_score),
            market_structure=self.structure,
        )

    def test_mid_session_score_explains_review_status(self) -> None:
        result = self._evaluate(0.55)

        self.assertEqual(result["execution_status"], "REVIEW")
        self.assertFalse(result["final_decision_ready"])
        self.assertIn(
            "SESSION_BELOW_TRADE_CANDIDATE",
            result["warnings"],
        )

    def test_candidate_threshold_remains_unchanged(self) -> None:
        result = self._evaluate(0.65)

        self.assertEqual(result["execution_status"], "TRADE_CANDIDATE")
        self.assertTrue(result["final_decision_ready"])
        self.assertEqual(result["decision"], "BUY")
        self.assertNotIn(
            "SESSION_BELOW_TRADE_CANDIDATE",
            result["warnings"],
        )


if __name__ == "__main__":
    unittest.main()
