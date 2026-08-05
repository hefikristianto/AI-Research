from __future__ import annotations

import unittest
from datetime import datetime

from ai.scripts.adjudicate_e2_3_m1_intrabar import (
    DEFAULT_CONFIG,
    _apply_resolution,
    adjudicate_ambiguous_row,
    build_ambiguity_summary,
    read_json,
    scan_entry_ambiguity,
    scan_filled_stop_target_ambiguity,
    validate_config,
    verify_m1_m5_ohlc,
)
from ai.scripts.evaluate_e2_3_forward_outcomes import Candle


class E231M1IntrabarAdjudicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = read_json(DEFAULT_CONFIG)
        validate_config(cls.config)

    @staticmethod
    def _row(
        *,
        entry_ambiguous: int = 0,
        both_ambiguous: int = 1,
        outcome_status: str = "AMBIGUOUS_BOTH_CONSERVATIVE_SL",
    ) -> dict[str, object]:
        return {
            "daily_group_id": "GBPUSD_20230103",
            "evaluation_split": "POLICY_SELECTION",
            "year": "2023",
            "trading_date_utc": "2023-01-03",
            "selected_tier": "HIGH_RISK",
            "selected_candidate_rule": "ENTRY_DISTANCE_WARNING",
            "snapshot_id": "GBPUSD_20230103_LONDON_M5",
            "slot": "LONDON",
            "source_timeframe": "M5",
            "analysis_target_datetime": "2023-01-03T09:00:00",
            "decision": "BUY",
            "order_type": "BUY_LIMIT",
            "entry": "1.3000",
            "stop_loss": "1.2950",
            "take_profit": "1.3100",
            "risk_reward_ratio": "2.0",
            "risk_price": "0.005",
            "risk_pips": "50",
            "horizon_end_datetime": "2023-01-04T09:00:00",
            "outcome_status": outcome_status,
            "filled": "1",
            "fill_datetime": "2023-01-03T09:00:00",
            "exit_datetime": "2023-01-03T09:00:00",
            "exit_price": "1.2950",
            "observed_m5_bars": "288",
            "entry_bar_target_ambiguous": str(entry_ambiguous),
            "same_bar_both_ambiguous": str(both_ambiguous),
            "right_censored": "0",
            "gross_r": "-1.0",
            "net_r_primary": "-1.03",
            "optimistic_gross_r": "2.0",
            "optimistic_net_r_primary": "1.97",
            "primary_friction_r": "0.03",
            "source_paths_json": "[]",
            "source_sha256s_json": "[]",
            "error": "",
        }

    def test_registered_contract_locks_55_ambiguities_and_2024_2025(self) -> None:
        validate_config(self.config)
        self.assertEqual(
            self.config["lineage"]["baseline_ambiguity_observations"], 55
        )
        self.assertFalse(
            self.config["guardrails"]["holdout_2024_access_allowed"]
        )
        self.assertFalse(
            self.config["guardrails"]["final_2025_access_allowed"]
        )

    def test_filled_trade_target_before_stop_is_resolved_tp(self) -> None:
        row = self._row()
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.301, 1.306, 1.299, 1.304),
            Candle(datetime(2023, 1, 3, 9, 1), 1.304, 1.311, 1.303, 1.309),
            Candle(datetime(2023, 1, 3, 9, 2), 1.309, 1.309, 1.294, 1.296),
        ]
        result = scan_filled_stop_target_ambiguity(row, candles)
        self.assertEqual(result["status"], "RESOLVED_TARGET_FIRST")
        self.assertEqual(result["event"], "TAKE_PROFIT")

    def test_filled_trade_stop_before_target_is_resolved_sl(self) -> None:
        row = self._row()
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.301, 1.304, 1.294, 1.296),
            Candle(datetime(2023, 1, 3, 9, 1), 1.296, 1.311, 1.296, 1.309),
        ]
        result = scan_filled_stop_target_ambiguity(row, candles)
        self.assertEqual(result["status"], "RESOLVED_STOP_FIRST")
        self.assertEqual(result["event"], "STOP_LOSS")

    def test_same_m1_stop_and_target_stays_conservative_unresolved(self) -> None:
        row = self._row()
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.301, 1.311, 1.294, 1.300),
        ]
        result = scan_filled_stop_target_ambiguity(row, candles)
        revised, evidence = _apply_resolution(
            row,
            result,
            source_path="GBPUSD/M1/2023/GBPUSD_M1_2023_RAW.csv",
            source_sha256="a" * 64,
            ohlc_verified=True,
        )
        self.assertEqual(
            result["status"], "M1_UNRESOLVED_STOP_AND_TARGET_SAME_BAR"
        )
        self.assertEqual(revised["outcome_status"], row["outcome_status"])
        self.assertEqual(revised["net_r_primary"], row["net_r_primary"])
        self.assertEqual(revised["m1_unresolved"], 1)
        self.assertIsNotNone(evidence)

    def test_entry_target_after_marketable_open_is_resolved_tp(self) -> None:
        row = self._row(entry_ambiguous=1, both_ambiguous=0, outcome_status="STOP_LOSS")
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.299, 1.311, 1.298, 1.308),
        ]
        result = scan_entry_ambiguity(row, candles)
        self.assertEqual(result["status"], "RESOLVED_TARGET_FIRST")

    def test_entry_and_target_same_m1_is_unresolved_when_not_marketable(self) -> None:
        row = self._row(entry_ambiguous=1, both_ambiguous=0, outcome_status="STOP_LOSS")
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.305, 1.311, 1.299, 1.304),
        ]
        result = scan_entry_ambiguity(row, candles)
        self.assertEqual(
            result["status"], "M1_UNRESOLVED_ENTRY_AND_TARGET_SAME_BAR"
        )

    def test_target_before_fill_retains_baseline_continuation(self) -> None:
        row = self._row(entry_ambiguous=1, both_ambiguous=0, outcome_status="STOP_LOSS")
        candles = [
            Candle(datetime(2023, 1, 3, 9, 0), 1.305, 1.311, 1.304, 1.306),
            Candle(datetime(2023, 1, 3, 9, 1), 1.306, 1.307, 1.299, 1.301),
        ]
        result = scan_entry_ambiguity(row, candles)
        revised, _ = _apply_resolution(row, result, ohlc_verified=True)
        self.assertEqual(result["status"], "RESOLVED_TARGET_BEFORE_FILL")
        self.assertEqual(revised["outcome_status"], "STOP_LOSS")
        self.assertEqual(revised["optimistic_net_r_primary"], "-1.03")
        self.assertEqual(revised["entry_bar_target_ambiguous"], 0)

    def test_m1_aggregate_must_match_registered_m5_bar(self) -> None:
        start = datetime(2023, 1, 3, 9, 0)
        m1 = {
            start: [
                Candle(start, 1.300, 1.302, 1.299, 1.301),
                Candle(datetime(2023, 1, 3, 9, 1), 1.301, 1.303, 1.300, 1.302),
            ]
        }
        m5 = {start: [Candle(start, 1.300, 1.303, 1.299, 1.302)]}
        audit = verify_m1_m5_ohlc(
            required_bars={start},
            m1_bars=m1,
            m5_bars=m5,
            tolerance=1e-9,
        )
        self.assertTrue(audit[start]["verified"])
        m5[start] = [Candle(start, 1.300, 1.304, 1.299, 1.302)]
        audit = verify_m1_m5_ohlc(
            required_bars={start},
            m1_bars=m1,
            m5_bars=m5,
            tolerance=1e-9,
        )
        self.assertFalse(audit[start]["verified"])

    def test_combined_adjudicator_refuses_unverified_window(self) -> None:
        row = self._row()
        start = datetime(2023, 1, 3, 9, 0)
        result = adjudicate_ambiguous_row(
            row,
            fill_bar=None,
            exit_bar=start,
            m1_bars={},
            ohlc_audit={start: {"verified": False}},
        )
        self.assertEqual(result["status"], "M1_DATA_ERROR_OHLC_NOT_VERIFIED")

    def test_ambiguity_summary_separates_observation_and_sensitive_rates(self) -> None:
        ambiguous = self._row()
        same_result = {
            **self._row(
                entry_ambiguous=1,
                both_ambiguous=0,
                outcome_status="TAKE_PROFIT",
            ),
            "net_r_primary": "1.97",
            "optimistic_net_r_primary": "1.97",
        }
        revised_ambiguous, _ = _apply_resolution(
            ambiguous,
            {
                "status": "RESOLVED_TARGET_FIRST",
                "event": "TAKE_PROFIT",
                "event_datetime": datetime(2023, 1, 3, 9, 1),
                "notes": "",
            },
            ohlc_verified=True,
        )
        revised_same, _ = _apply_resolution(
            same_result,
            {
                "status": "RESOLVED_TARGET_BEFORE_FILL",
                "event": "",
                "event_datetime": None,
                "notes": "",
            },
            ohlc_verified=True,
        )
        summary = build_ambiguity_summary(
            [ambiguous, same_result],
            [revised_ambiguous, revised_same],
        )
        self.assertEqual(summary["baseline_ambiguity_observations"], 2)
        self.assertEqual(
            summary["baseline_outcome_sensitive_ambiguity_observations"], 1
        )
        self.assertEqual(summary["remaining_ambiguity_observations"], 0)


if __name__ == "__main__":
    unittest.main()
