from __future__ import annotations

from typing import Any


class LiveExecutionGateService:
    @staticmethod
    def _normalize_direction(
        value: Any,
    ) -> str:
        direction = str(
            value or "unknown"
        ).lower()

        if direction.startswith("bullish"):
            return "bullish"

        if direction.startswith("bearish"):
            return "bearish"

        return "unknown"

    def evaluate(
        self,
        advanced_scoring: dict[str, Any],
        context_scoring: dict[str, Any],
        htf_volatility: dict[str, Any],
        session_risk: dict[str, Any],
        market_structure: dict[str, Any],
    ) -> dict[str, Any]:
        if (
            advanced_scoring.get("status")
            != (
                "HTF_VOLATILITY_SCORING_"
                "COMPLETE"
            )
        ):
            return {
                "status": "SKIPPED",
                "decision": "WAIT",
                "execution_status": (
                    "INCOMPLETE"
                ),
                "final_decision_ready": (
                    False
                ),
                "reasons": [
                    "Advanced scoring belum "
                    "selesai."
                ],
            }

        if (
            session_risk.get("status")
            != "SESSION_RISK_COMPLETE"
        ):
            return {
                "status": "SKIPPED",
                "decision": "WAIT",
                "execution_status": (
                    "INCOMPLETE"
                ),
                "final_decision_ready": (
                    False
                ),
                "reasons": [
                    "Session dan risk analysis "
                    "belum selesai."
                ],
            }

        setup_direction = (
            self._normalize_direction(
                advanced_scoring.get(
                    "setup_direction"
                )
            )
        )

        advanced_score = float(
            advanced_scoring.get(
                "advanced_score",
                0.0,
            )
        )

        detector_valid = bool(
            advanced_scoring.get(
                "detector_valid",
                False,
            )
        )

        direction_conflict = bool(
            context_scoring.get(
                "direction_conflict",
                False,
            )
        )

        htf_alignment_score = float(
            htf_volatility.get(
                "htf_alignment_score",
                0.50,
            )
        )

        session = session_risk.get(
            "session",
            {},
        )

        session_score = float(
            session.get(
                "session_score",
                0.50,
            )
        )

        risk_reward = (
            session_risk.get(
                "risk_reward",
                {},
            )
        )

        blockers: list[str] = []
        warnings: list[str] = []

        if not detector_valid:
            blockers.append(
                "DETECTOR_CONFIDENCE_INVALID"
            )

        if (
            risk_reward.get("status")
            != "COMPLETE"
        ):
            blockers.append(
                "RISK_REWARD_UNAVAILABLE"
            )

        rr = risk_reward.get(
            "risk_reward_ratio"
        )

        if rr is not None:
            rr = float(rr)

            if rr < 1.50:
                blockers.append(
                    "RISK_REWARD_BELOW_1_5"
                )

        if not bool(
            risk_reward.get(
                "entry_side_valid",
                False,
            )
        ):
            blockers.append(
                "ENTRY_SIDE_INVALID"
            )

        if bool(
            risk_reward.get(
                "zone_invalidated",
                False,
            )
        ):
            blockers.append(
                "ZONE_INVALIDATED"
            )

        if advanced_score < 0.45:
            blockers.append(
                "ADVANCED_SCORE_BELOW_"
                "WATCHLIST"
            )

        if (
            direction_conflict
            and htf_alignment_score <= 0.25
        ):
            blockers.append(
                "STRUCTURE_AND_HTF_CONFLICT"
            )

        price_mapping_provisional = bool(
            risk_reward.get(
                "price_mapping_provisional",
                True,
            )
        )

        if price_mapping_provisional:
            blockers.append(
                "PRICE_MAPPING_PROVISIONAL"
            )

        if session_score < 0.50:
            warnings.append(
                "LOW_SESSION_SUITABILITY"
            )

        volatility_regime = str(
            advanced_scoring.get(
                "volatility_regime",
                "UNKNOWN",
            )
        )

        if volatility_regime == "EXTREME":
            blockers.append(
                "EXTREME_VOLATILITY"
            )

        blockers = list(
            dict.fromkeys(blockers)
        )

        warnings = list(
            dict.fromkeys(warnings)
        )

        if (
            "DETECTOR_CONFIDENCE_INVALID"
            in blockers
            or "ZONE_INVALIDATED"
            in blockers
            or (
                "RISK_REWARD_UNAVAILABLE"
                in blockers
            )
        ):
            execution_status = "INVALID"

        elif blockers:
            execution_status = "WAIT"

        elif (
            advanced_score >= 0.60
            and rr is not None
            and rr >= 1.50
            and session_score >= 0.65
        ):
            execution_status = (
                "TRADE_CANDIDATE"
            )

        elif advanced_score >= 0.45:
            execution_status = "REVIEW"

        else:
            execution_status = "WAIT"

        final_decision_ready = (
            execution_status
            == "TRADE_CANDIDATE"
            and not blockers
        )

        if final_decision_ready:
            if setup_direction == "bullish":
                decision = "BUY"

            elif setup_direction == "bearish":
                decision = "SELL"

            else:
                decision = "WAIT"

        else:
            decision = "WAIT"

        reasons = []

        if blockers:
            reasons.extend(blockers)

        if not reasons:
            reasons.append(
                "ALL_EXECUTION_GATES_PASSED"
            )

        return {
            "status": (
                "EXECUTION_GATE_COMPLETE"
            ),
            "decision": decision,
            "execution_status": (
                execution_status
            ),
            "final_decision_ready": (
                final_decision_ready
            ),
            "setup_direction": (
                setup_direction
            ),
            "advanced_score": (
                advanced_score
            ),
            "advanced_status": (
                advanced_scoring.get(
                    "advanced_status"
                )
            ),
            "structure_conflict": (
                direction_conflict
            ),
            "htf_alignment_score": (
                htf_alignment_score
            ),
            "session": session.get(
                "session"
            ),
            "session_score": (
                session_score
            ),
            "volatility_regime": (
                volatility_regime
            ),
            "entry": risk_reward.get(
                "entry"
            ),
            "stop_loss": (
                risk_reward.get(
                    "stop_loss"
                )
            ),
            "take_profit": (
                risk_reward.get(
                    "take_profit"
                )
            ),
            "risk_reward_ratio": rr,
            "order_type": (
                risk_reward.get(
                    "order_type"
                )
            ),
            "price_mapping_provisional": (
                price_mapping_provisional
            ),
            "blockers": blockers,
            "warnings": warnings,
            "reasons": reasons,
        }
