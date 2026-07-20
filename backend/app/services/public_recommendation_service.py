from __future__ import annotations

from typing import Any


class PublicRecommendationService:
    """Fail-closed mapping from internal execution state to public output."""

    ACTIONABLE_DECISIONS = {"BUY", "SELL"}
    WATCHLIST_STATUSES = {"REVIEW", "QUALITY_REVIEW"}

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        return [
            str(item)
            for item in value
            if item is not None
        ]

    def build(
        self,
        execution_gate: dict[str, Any],
    ) -> dict[str, Any]:
        internal_decision = str(
            execution_gate.get("decision", "WAIT")
        ).upper()
        execution_status = str(
            execution_gate.get(
                "execution_status",
                "INCOMPLETE",
            )
        ).upper()
        final_decision_ready = bool(
            execution_gate.get(
                "final_decision_ready",
                False,
            )
        )

        if (
            final_decision_ready
            and execution_status
            == "TRADE_CANDIDATE"
            and internal_decision
            in self.ACTIONABLE_DECISIONS
        ):
            decision = internal_decision
        elif execution_status in self.WATCHLIST_STATUSES:
            decision = "WATCHLIST"
        else:
            decision = "NO_TRADE"

        actionable = decision in self.ACTIONABLE_DECISIONS

        def actionable_value(key: str) -> Any:
            if not actionable:
                return None
            return execution_gate.get(key)

        return {
            "decision": decision,
            "internal_decision": internal_decision,
            "execution_status": execution_status,
            "final_decision_ready": final_decision_ready,
            "actionable": actionable,
            "educational_only": not actionable,
            "entry": actionable_value("entry"),
            "stop_loss": actionable_value("stop_loss"),
            "take_profit": actionable_value("take_profit"),
            "risk_reward_ratio": actionable_value(
                "risk_reward_ratio"
            ),
            "order_type": actionable_value("order_type"),
            "setup_direction": execution_gate.get(
                "setup_direction",
                "unknown",
            ),
            "blockers": self._string_list(
                execution_gate.get("blockers")
            ),
            "warnings": self._string_list(
                execution_gate.get("warnings")
            ),
            "reasons": self._string_list(
                execution_gate.get("reasons")
            ),
        }
