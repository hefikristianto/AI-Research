from __future__ import annotations

from typing import Any


class LiveContextScoringService:
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
    def _alignment_adjustment(
        alignment: str,
    ) -> float:
        adjustments = {
            "aligned": 0.05,
            "neutral": 0.00,
            "unknown": 0.00,
            "conflict": -0.05,
        }

        return adjustments.get(
            alignment,
            0.00,
        )

    @staticmethod
    def _sweep_adjustment(
        latest_sweep: dict[str, Any] | None,
        setup_direction: str,
    ) -> tuple[float, str]:
        if latest_sweep is None:
            return 0.00, "NO_SWEEP"

        confirmation_direction = str(
            latest_sweep.get(
                "confirmation_direction",
                "unknown",
            )
        ).lower()

        if confirmation_direction == setup_direction:
            return 0.03, "ALIGNED"

        if confirmation_direction in {
            "bullish",
            "bearish",
        }:
            return -0.03, "CONFLICT"

        return 0.00, "UNKNOWN"

    @staticmethod
    def _zone_adjustment(
        zone: dict[str, Any],
    ) -> tuple[float, str, bool]:
        zone_status = str(
            zone.get(
                "zone_status",
                "unknown",
            )
        ).lower()

        mapping_mode = str(
            zone.get(
                "mapping_mode",
                "unknown",
            )
        )

        provisional = (
            mapping_mode
            == "approximate_full_image_linear"
        )

        if zone_status == "fresh":
            adjustment = 0.02

        elif (
            zone_status
            == "partially_mitigated"
        ):
            adjustment = 0.00

        elif zone_status == "mitigated":
            adjustment = -0.01

        elif zone_status == "invalidated":
            adjustment = -0.08

        else:
            adjustment = 0.00

        return (
            adjustment,
            zone_status,
            provisional,
        )

    def score(
        self,
        preliminary_scoring: dict[str, Any],
        market_structure: dict[str, Any],
    ) -> dict[str, Any]:
        if (
            market_structure.get("status")
            != "STRUCTURE_COMPLETE"
        ):
            return {
                "status": "SKIPPED",
                "reason": (
                    "Market structure belum selesai."
                ),
                "final_decision_ready": False,
            }

        best_setup = preliminary_scoring.get(
            "best_setup"
        )

        if not best_setup:
            return {
                "status": "NO_VALID_SETUP",
                "reason": (
                    "Tidak ada setup valid dari "
                    "preliminary scoring."
                ),
                "final_decision_ready": False,
            }

        base_score = float(
            best_setup.get(
                "live_score",
                0.0,
            )
        )

        detector_valid = bool(
            best_setup.get(
                "detector_valid",
                False,
            )
        )

        setup_direction = (
            self._normalize_direction(
                best_setup.get(
                    "setup_direction",
                    best_setup.get(
                        "direction",
                    ),
                )
            )
        )

        structure_direction = (
            self._normalize_direction(
                market_structure.get(
                    "structure_direction",
                )
            )
        )

        structure_alignment = str(
            market_structure.get(
                "structure_alignment",
                "unknown",
            )
        ).lower()

        alignment_adjustment = (
            self._alignment_adjustment(
                structure_alignment
            )
        )

        (
            sweep_adjustment,
            sweep_relation,
        ) = self._sweep_adjustment(
            latest_sweep=(
                market_structure.get(
                    "latest_sweep"
                )
            ),
            setup_direction=setup_direction,
        )

        zone = market_structure.get(
            "zone",
            {},
        )

        (
            zone_adjustment,
            zone_status,
            zone_mapping_provisional,
        ) = self._zone_adjustment(zone)

        total_adjustment = (
            alignment_adjustment
            + sweep_adjustment
            + zone_adjustment
        )

        final_score = self._clamp(
            base_score + total_adjustment
        )

        if not detector_valid:
            final_status = "LOW_CONFIDENCE"

        else:
            final_status = (
                self._decision_from_score(
                    final_score
                )
            )

        conflict = (
            structure_alignment
            == "conflict"
        )

        return {
            "status": (
                "STRUCTURE_SCORING_COMPLETE"
            ),
            "pair_id": best_setup.get(
                "pair_id"
            ),
            "setup_direction": (
                setup_direction
            ),
            "structure_direction": (
                structure_direction
            ),
            "structure_alignment": (
                structure_alignment
            ),
            "direction_conflict": conflict,
            "detector_valid": (
                detector_valid
            ),
            "base_live_score": (
                base_score
            ),
            "alignment_adjustment": (
                alignment_adjustment
            ),
            "sweep_adjustment": (
                sweep_adjustment
            ),
            "sweep_relation": (
                sweep_relation
            ),
            "zone_adjustment": (
                zone_adjustment
            ),
            "zone_status": zone_status,
            "zone_mapping_provisional": (
                zone_mapping_provisional
            ),
            "total_adjustment": (
                total_adjustment
            ),
            "final_structure_score": (
                final_score
            ),
            "final_structure_status": (
                final_status
            ),
            "market_structure_score": float(
                market_structure.get(
                    "market_structure_score",
                    0.5,
                )
            ),
            "scoring_stage": (
                "LIVE_STRUCTURE_ENRICHED"
            ),
            "final_decision_ready": False,
            "required_next_context": [
                "HTF alignment",
                "volatility regime",
                "session context",
                "risk-reward",
                "execution gate",
            ],
        }
