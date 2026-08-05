from __future__ import annotations

import unittest
from datetime import datetime

from ai.scripts.evaluate_e2_3_forward_outcomes import (
    Candle,
    DEFAULT_CONFIG,
    build_breakdowns,
    build_report,
    evaluate_acceptance_gates,
    evaluate_candidate,
    read_json,
    summarize_rows,
    validate_config,
)


class E23ForwardOutcomeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = read_json(DEFAULT_CONFIG)
        validate_config(cls.config)

    @staticmethod
    def _row(
        *,
        decision: str = "BUY",
        order_type: str = "BUY_LIMIT",
        entry: float = 1.3000,
        stop_loss: float = 1.2950,
        take_profit: float = 1.3100,
        tier: str = "HIGH_RISK",
    ) -> dict[str, str]:
        return {
            "daily_group_id": "GBPUSD_20230103",
            "evaluation_split": "POLICY_SELECTION",
            "year": "2023",
            "trading_date_utc": "2023-01-03",
            "combined_policy_decision": decision,
            "selected_tier": tier,
            "selected_snapshot_id": "GBPUSD_20230103_LONDON_M5",
            "selected_candidate_rule": (
                "RR_RELAXATION" if tier == "HIGH_RISK" else ""
            ),
            "selected_slot": "LONDON",
            "selected_timeframe": "M5",
            "selected_analysis_target_datetime": "2023-01-03T09:00:00",
            "selected_order_type": order_type,
            "selected_risk_reward_ratio": "2.0",
            "selected_entry": str(entry),
            "selected_stop_loss": str(stop_loss),
            "selected_take_profit": str(take_profit),
        }

    @staticmethod
    def _evaluate(
        row: dict[str, str],
        candles: list[Candle],
        config: dict[str, object],
    ) -> dict[str, object]:
        timestamps = [candle.timestamp for candle in candles]
        return evaluate_candidate(
            row,
            timestamps=timestamps,
            candles=candles,
            config=config,
            source_contract={"GBPUSD/M5/2023/GBPUSD_M5_2023_RAW.csv": "a" * 64},
        )

    def test_registered_protocol_is_valid(self) -> None:
        validate_config(self.config)
        self.assertEqual(
            self.config["execution_model"]["horizon_calendar_hours"],
            24,
        )
        self.assertFalse(self.config["guardrails"]["holdout_2024_access_allowed"])

    def test_buy_limit_fills_then_hits_take_profit(self) -> None:
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.302, 1.303, 1.299, 1.301),
            Candle(datetime(2023, 1, 3, 9, 5), 1.301, 1.311, 1.298, 1.309),
        ]
        result = self._evaluate(self._row(), candles, self.config)
        self.assertEqual(result["outcome_status"], "TAKE_PROFIT")
        self.assertEqual(result["filled"], 1)
        self.assertAlmostEqual(float(result["gross_r"]), 2.0)
        self.assertLess(float(result["net_r_primary"]), 2.0)

    def test_unfilled_limit_contributes_zero_r(self) -> None:
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.305, 1.306, 1.304, 1.305),
            Candle(datetime(2023, 1, 3, 9, 5), 1.305, 1.307, 1.303, 1.306),
        ]
        result = self._evaluate(
            self._row(entry=1.290, stop_loss=1.285, take_profit=1.300),
            candles,
            self.config,
        )
        self.assertEqual(result["outcome_status"], "NOT_FILLED")
        self.assertEqual(result["filled"], 0)
        self.assertEqual(result["gross_r"], 0.0)
        self.assertEqual(result["net_r_primary"], 0.0)

    def test_same_bar_sl_and_tp_is_conservative_loss(self) -> None:
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.302, 1.311, 1.294, 1.300),
        ]
        result = self._evaluate(self._row(), candles, self.config)
        self.assertEqual(
            result["outcome_status"],
            "AMBIGUOUS_BOTH_CONSERVATIVE_SL",
        )
        self.assertEqual(result["same_bar_both_ambiguous"], 1)
        self.assertAlmostEqual(float(result["gross_r"]), -1.0)
        self.assertAlmostEqual(float(result["optimistic_gross_r"]), 2.0)

    def test_entry_bar_target_is_not_credited_in_primary_result(self) -> None:
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.302, 1.311, 1.299, 1.305),
            Candle(datetime(2023, 1, 3, 9, 5), 1.305, 1.306, 1.294, 1.296),
        ]
        result = self._evaluate(self._row(), candles, self.config)
        self.assertEqual(result["entry_bar_target_ambiguous"], 1)
        self.assertEqual(result["outcome_status"], "STOP_LOSS")
        self.assertAlmostEqual(float(result["gross_r"]), -1.0)
        self.assertAlmostEqual(float(result["optimistic_gross_r"]), 2.0)

    def test_sell_limit_uses_inverse_level_touches(self) -> None:
        row = self._row(
            decision="SELL",
            order_type="SELL_LIMIT",
            entry=1.300,
            stop_loss=1.305,
            take_profit=1.290,
        )
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.298, 1.301, 1.297, 1.300),
            Candle(datetime(2023, 1, 3, 9, 5), 1.300, 1.302, 1.289, 1.291),
        ]
        result = self._evaluate(row, candles, self.config)
        self.assertEqual(result["outcome_status"], "TAKE_PROFIT")
        self.assertAlmostEqual(float(result["gross_r"]), 2.0)

    def test_summary_separates_fill_and_resolved_win_rate(self) -> None:
        rows = [
            self._evaluate(
                self._row(),
                [
                    Candle(
                        datetime(2023, 1, 3, 9, 0),
                        1.302,
                        1.303,
                        1.299,
                        1.301,
                    ),
                    Candle(
                        datetime(2023, 1, 3, 9, 5),
                        1.301,
                        1.311,
                        1.298,
                        1.309,
                    ),
                ],
                self.config,
            ),
            self._evaluate(
                self._row(entry=1.290, stop_loss=1.285, take_profit=1.300),
                [
                    Candle(
                        datetime(2023, 1, 3, 9, 0),
                        1.305,
                        1.306,
                        1.304,
                        1.305,
                    )
                ],
                self.config,
            ),
        ]
        summary = summarize_rows(rows, config=self.config)
        self.assertEqual(summary["candidate_count"], 2)
        self.assertEqual(summary["filled_count"], 1)
        self.assertEqual(summary["fill_rate_pct"], 50.0)
        self.assertEqual(summary["resolved_win_rate_pct"], 100.0)

    def test_ambiguity_sensitivity_is_aggregated(self) -> None:
        row = self._evaluate(
            self._row(),
            [
                Candle(
                    datetime(2023, 1, 3, 9, 0),
                    1.302,
                    1.311,
                    1.294,
                    1.300,
                )
            ],
            self.config,
        )
        summary = summarize_rows([row], config=self.config)
        self.assertGreater(
            summary["optimistic_net_expectancy_r_candidate"],
            summary["net_expectancy_r_candidate"],
        )
        self.assertGreater(summary["ambiguity_expectancy_delta_r"], 0.0)

    def test_breakdowns_gate_and_report_share_one_metric_contract(self) -> None:
        outcome = self._evaluate(
            self._row(),
            [
                Candle(
                    datetime(2023, 1, 3, 9, 0),
                    1.302,
                    1.303,
                    1.299,
                    1.301,
                ),
                Candle(
                    datetime(2023, 1, 3, 9, 5),
                    1.301,
                    1.311,
                    1.298,
                    1.309,
                ),
            ],
            self.config,
        )
        breakdowns, flat_rows = build_breakdowns([outcome], config=self.config)
        gate = evaluate_acceptance_gates([outcome], config=self.config)
        report = build_report(
            {
                "generated_at_utc": "2026-08-04T00:00:00+00:00",
                "selected_candidate_days": 1,
                "breakdowns": breakdowns,
                "pre_holdout_acceptance": gate,
            },
            self.config,
        )
        self.assertTrue(flat_rows)
        self.assertIn("HIGH_RISK", breakdowns["tier"])
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("Pre-holdout High Risk acceptance", report)


if __name__ == "__main__":
    unittest.main()
