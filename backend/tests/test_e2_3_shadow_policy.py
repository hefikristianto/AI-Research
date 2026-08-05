from __future__ import annotations

import unittest

from ai.scripts.evaluate_e2_3_shadow_policy import (
    DEFAULT_POLICY,
    build_daily_rows,
    evaluate_snapshot,
    read_json,
    validate_policy,
)


class E23ShadowPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = read_json(DEFAULT_POLICY)
        validate_policy(cls.policy)

    @staticmethod
    def _fixture(
        *,
        snapshot_id: str = "GBPUSD_20230103_LONDON_M5",
        public_decision: str = "NO_TRADE",
        execution_status: str = "WAIT",
        final_ready: bool = False,
        direction: str = "bullish",
        advanced_score: float = 0.81,
        session_score: float = 1.0,
        risk_reward: float = 1.3,
        entry_distance: float = 1.2,
        blockers: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> tuple[dict[str, str], dict[str, object]]:
        blockers = blockers if blockers is not None else ["RISK_REWARD_BELOW_1_5"]
        warnings = warnings if warnings is not None else []
        row = {
            "snapshot_id": snapshot_id,
            "daily_group_id": "GBPUSD_20230103",
            "evaluation_split": "POLICY_SELECTION",
            "year": "2023",
            "trading_date_utc": "2023-01-03",
            "slot": "LONDON",
            "timeframe": "M5",
            "analysis_target_datetime": "2023-01-03T09:00:00",
            "request_status": "SUCCESS",
            "analysis_clock_validated": "1",
            "public_decision": public_decision,
            "execution_status": execution_status,
            "pair_count": "1",
            "mapping_status": "MAPPED",
            "mapping_mode": "PLOT_AWARE",
            "mapping_confidence": "0.91",
            "mapping_provisional": "0",
            "advanced_score": str(advanced_score),
            "session_score": str(session_score),
            "risk_reward_ratio": str(risk_reward),
            "entry_distance_atr": str(entry_distance),
            "blockers_json": __import__("json").dumps(blockers),
            "warnings_json": __import__("json").dumps(warnings),
            "response_path": "inference/responses/sample.json",
            "response_sha256": "a" * 64,
        }
        payload: dict[str, object] = {
            "recommendation": {
                "decision": public_decision,
                "internal_decision": (
                    public_decision if public_decision in {"BUY", "SELL"} else "WAIT"
                ),
            },
            "execution_gate": {
                "execution_status": execution_status,
                "final_decision_ready": final_ready,
                "setup_direction": direction,
                "order_type": (
                    "BUY_LIMIT" if direction == "bullish" else "SELL_LIMIT"
                ),
                "advanced_score": advanced_score,
                "session_score": session_score,
                "risk_reward_ratio": risk_reward,
                "entry_distance_atr": entry_distance,
                "entry": 1.27,
                "stop_loss": 1.265,
                "take_profit": 1.28,
                "blockers": blockers,
                "warnings": warnings,
            },
            "price_conversion": {
                "status": "MAPPED",
                "mapping_index_mode": "PLOT_AWARE",
                "mapping_confidence": 0.91,
                "mapping_provisional": False,
                "mapping_calibration_applied": True,
            },
            "pairing": {"total_pairs": 1},
            "analysis_clock": {"anti_lookahead_validated": True},
        }
        return row, payload

    def test_registered_policy_is_valid(self) -> None:
        validate_policy(self.policy)
        self.assertEqual(
            self.policy["high_risk_candidate"]["minimum_risk_reward_ratio"],
            1.25,
        )

    def test_rr_only_wait_becomes_high_risk_candidate(self) -> None:
        row, payload = self._fixture()
        result = evaluate_snapshot(row=row, payload=payload, policy=self.policy)
        self.assertEqual(result["standard_eligible"], 0)
        self.assertEqual(result["high_risk_eligible"], 1)
        self.assertEqual(result["high_risk_rule"], "RR_RELAXATION")
        self.assertEqual(result["candidate_decision"], "BUY")
        self.assertEqual(result["order_type"], "BUY_LIMIT")
        self.assertEqual(result["data_quality"], "VALID")

    def test_non_limit_order_cannot_enter_shadow_policy(self) -> None:
        row, payload = self._fixture()
        payload["execution_gate"]["order_type"] = "BUY_MARKET"  # type: ignore[index]
        result = evaluate_snapshot(row=row, payload=payload, policy=self.policy)
        self.assertEqual(result["high_risk_eligible"], 0)
        self.assertIn(
            "ORDER_TYPE_INVALID",
            result["high_risk_rejection_reasons_json"],
        )

    def test_entry_distance_review_becomes_high_risk_candidate(self) -> None:
        row, payload = self._fixture(
            public_decision="WATCHLIST",
            execution_status="REVIEW",
            risk_reward=2.1,
            entry_distance=2.2,
            blockers=[],
            warnings=["ENTRY_DISTANCE_ABOVE_1_5_ATR"],
        )
        result = evaluate_snapshot(row=row, payload=payload, policy=self.policy)
        self.assertEqual(result["high_risk_eligible"], 1)
        self.assertEqual(result["high_risk_rule"], "ENTRY_DISTANCE_WARNING")

    def test_hard_blocker_cannot_become_high_risk(self) -> None:
        row, payload = self._fixture(
            blockers=["RISK_REWARD_BELOW_1_5", "ZONE_INVALIDATED"]
        )
        result = evaluate_snapshot(row=row, payload=payload, policy=self.policy)
        self.assertEqual(result["high_risk_eligible"], 0)
        self.assertIn(
            "HARD_OR_UNKNOWN_BLOCKER_PRESENT",
            result["high_risk_rejection_reasons_json"],
        )

    def test_standard_control_is_not_reclassified(self) -> None:
        row, payload = self._fixture(
            public_decision="BUY",
            execution_status="TRADE_CANDIDATE",
            final_ready=True,
            risk_reward=2.0,
            entry_distance=1.0,
            blockers=[],
            warnings=[],
        )
        result = evaluate_snapshot(row=row, payload=payload, policy=self.policy)
        self.assertEqual(result["standard_eligible"], 1)
        self.assertEqual(result["high_risk_eligible"], 0)
        self.assertEqual(result["candidate_decision"], "BUY")

    @staticmethod
    def _manifest(snapshot_id: str, timeframe: str = "M5") -> dict[str, str]:
        return {
            "snapshot_id": snapshot_id,
            "daily_group_id": "GBPUSD_20230103",
            "evaluation_split": "POLICY_SELECTION",
            "year": "2023",
            "trading_date_utc": "2023-01-03",
            "status": "READY",
            "timeframe": timeframe,
        }

    def test_standard_precedes_high_risk_in_daily_selection(self) -> None:
        standard_row, standard_payload = self._fixture(
            snapshot_id="GBPUSD_20230103_LONDON_H1",
            public_decision="BUY",
            execution_status="TRADE_CANDIDATE",
            final_ready=True,
            risk_reward=2.0,
            entry_distance=1.0,
            blockers=[],
            warnings=[],
        )
        standard_row["timeframe"] = "H1"
        high_row, high_payload = self._fixture()
        snapshots = [
            evaluate_snapshot(
                row=standard_row,
                payload=standard_payload,
                policy=self.policy,
            ),
            evaluate_snapshot(row=high_row, payload=high_payload, policy=self.policy),
        ]
        daily = build_daily_rows(
            manifest_rows=[
                self._manifest(standard_row["snapshot_id"], "H1"),
                self._manifest(high_row["snapshot_id"], "M5"),
            ],
            snapshot_rows=snapshots,
        )[0]
        self.assertEqual(daily["selected_tier"], "STANDARD")
        self.assertEqual(daily["combined_policy_decision"], "BUY")
        self.assertEqual(daily["selected_order_type"], "BUY_LIMIT")
        self.assertEqual(daily["high_risk_added"], 0)

    def test_standard_direction_conflict_fails_closed(self) -> None:
        buy_row, buy_payload = self._fixture(
            snapshot_id="GBPUSD_20230103_LONDON_H1",
            public_decision="BUY",
            execution_status="TRADE_CANDIDATE",
            final_ready=True,
            blockers=[],
            warnings=[],
            risk_reward=2.0,
            entry_distance=1.0,
        )
        buy_row["timeframe"] = "H1"
        sell_row, sell_payload = self._fixture(
            snapshot_id="GBPUSD_20230103_LONDON_M5",
            public_decision="SELL",
            execution_status="TRADE_CANDIDATE",
            final_ready=True,
            direction="bearish",
            blockers=[],
            warnings=[],
            risk_reward=2.0,
            entry_distance=1.0,
        )
        snapshots = [
            evaluate_snapshot(row=buy_row, payload=buy_payload, policy=self.policy),
            evaluate_snapshot(row=sell_row, payload=sell_payload, policy=self.policy),
        ]
        daily = build_daily_rows(
            manifest_rows=[
                self._manifest(buy_row["snapshot_id"], "H1"),
                self._manifest(sell_row["snapshot_id"], "M5"),
            ],
            snapshot_rows=snapshots,
        )[0]
        self.assertEqual(daily["daily_status"], "STANDARD_DIRECTION_CONFLICT")
        self.assertEqual(daily["standard_only_decision"], "WATCHLIST")
        self.assertEqual(daily["combined_policy_decision"], "WATCHLIST")
        self.assertEqual(daily["selected_snapshot_id"], "")

    def test_high_risk_direction_conflict_fails_closed(self) -> None:
        buy_row, buy_payload = self._fixture(
            snapshot_id="GBPUSD_20230103_LONDON_M5"
        )
        sell_row, sell_payload = self._fixture(
            snapshot_id="GBPUSD_20230103_LONDON_NEW_YORK_OVERLAP_M15",
            direction="bearish",
        )
        sell_row["slot"] = "LONDON_NEW_YORK_OVERLAP"
        sell_row["timeframe"] = "M15"
        snapshots = [
            evaluate_snapshot(row=buy_row, payload=buy_payload, policy=self.policy),
            evaluate_snapshot(row=sell_row, payload=sell_payload, policy=self.policy),
        ]
        daily = build_daily_rows(
            manifest_rows=[
                self._manifest(buy_row["snapshot_id"], "M5"),
                self._manifest(sell_row["snapshot_id"], "M15"),
            ],
            snapshot_rows=snapshots,
        )[0]
        self.assertEqual(daily["daily_status"], "HIGH_RISK_DIRECTION_CONFLICT")
        self.assertEqual(daily["combined_policy_decision"], "WATCHLIST")
        self.assertEqual(daily["selected_tier"], "")


if __name__ == "__main__":
    unittest.main()
