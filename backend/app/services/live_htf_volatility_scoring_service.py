from __future__ import annotations

from typing import Any


class LiveHTFVolatilityScoringService:
    @staticmethod
    def _clamp(
        value: float,
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> float:
        return max(
            minimum,
            min(maximum, value),
        )

    @staticmethod
    def _decision_from_score(
        score: float,
    ) -> str:
        if score >= 0.75:
            return "ACCEPT"

        if score >= 0.60:
            return "REVIEW"

        if score >= 0.45:
            return "WATCHLIST"

        return "REJECT"

    @staticmethod
    def _volatility_adjustment(
        regime: str,
    ) -> float:
        adjustments = {
            "LOW": -0.02,
            "NORMAL": 0.02,
            "HIGH": 0.00,
            "EXTREME": -0.05,
            "UNKNOWN": 0.00,
        }

        return adjustments.get(
            regime,
            0.00,
        )

    def score(
        self,
        context_scoring: dict[str, Any],
        htf_volatility: dict[str, Any],
    ) -> dict[str, Any]:
        if (
            context_scoring.get("status")
            != "STRUCTURE_SCORING_COMPLETE"
        ):
            return {
                "status": "SKIPPED",
                "reason": (
                    "Structure scoring belum "
                    "selesai."
                ),
                "final_decision_ready": False,
            }

        if (
            htf_volatility.get("status")
            != "HTF_VOLATILITY_COMPLETE"
        ):
            return {
                "status": "SKIPPED",
                "reason": (
                    "HTF dan volatility belum "
                    "selesai."
                ),
                "final_decision_ready": False,
            }

        base_score = float(
            context_scoring.get(
                "final_structure_score",
                0.0,
            )
        )

        detector_valid = bool(
            context_scoring.get(
                "detector_valid",
                False,
            )
        )

        htf_alignment_score = float(
            htf_volatility.get(
                "htf_alignment_score",
                0.50,
            )
        )

        htf_adjustment = (
            htf_alignment_score
            - 0.50
        ) * 0.12

        volatility = (
            htf_volatility.get(
                "volatility",
                {},
            )
        )

        volatility_regime = str(
            volatility.get(
                "regime",
                "UNKNOWN",
            )
        ).upper()

        volatility_adjustment = (
            self._volatility_adjustment(
                volatility_regime
            )
        )

        total_adjustment = (
            htf_adjustment
            + volatility_adjustment
        )

        advanced_score = self._clamp(
            base_score
            + total_adjustment
        )

        if not detector_valid:
            advanced_status = (
                "LOW_CONFIDENCE"
            )

        else:
            advanced_status = (
                self._decision_from_score(
                    advanced_score
                )
            )

        return {
            "status": (
                "HTF_VOLATILITY_SCORING_"
                "COMPLETE"
            ),
            "pair_id": (
                context_scoring.get(
                    "pair_id"
                )
            ),
            "setup_direction": (
                context_scoring.get(
                    "setup_direction"
                )
            ),
            "detector_valid": (
                detector_valid
            ),
            "base_structure_score": (
                base_score
            ),
            "htf_consensus": (
                htf_volatility.get(
                    "htf_consensus"
                )
            ),
            "htf_alignment_score": (
                htf_alignment_score
            ),
            "htf_adjustment": (
                htf_adjustment
            ),
            "volatility_regime": (
                volatility_regime
            ),
            "volatility_atr_ratio": (
                volatility.get(
                    "atr_ratio_to_median"
                )
            ),
            "volatility_percentile": (
                volatility.get(
                    "percentile_100"
                )
            ),
            "volatility_adjustment": (
                volatility_adjustment
            ),
            "total_adjustment": (
                total_adjustment
            ),
            "advanced_score": (
                advanced_score
            ),
            "advanced_status": (
                advanced_status
            ),
            "scoring_stage": (
                "LIVE_HTF_VOLATILITY_"
                "ENRICHED"
            ),
            "final_decision_ready": False,
            "required_next_context": [
                "session context",
                "risk-reward",
                "execution gate",
            ],
        }
