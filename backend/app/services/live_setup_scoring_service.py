from __future__ import annotations

from typing import Any


class LiveSetupScoringService:
    def __init__(
        self,
        minimum_ob_confidence: float = 0.05,
        minimum_fvg_confidence: float = 0.005,
    ) -> None:
        self.minimum_ob_confidence = (
            minimum_ob_confidence
        )
        self.minimum_fvg_confidence = (
            minimum_fvg_confidence
        )

    @staticmethod
    def normalize_direction(
        direction: str,
    ) -> str:
        if direction.startswith("bullish"):
            return "bullish"

        if direction.startswith("bearish"):
            return "bearish"

        return "unknown"

    @staticmethod
    def cnn_alignment(
        setup_direction: str,
        regime_label: str,
    ) -> float:
        if regime_label == "sideways":
            return 0.55

        if setup_direction == regime_label:
            return 1.0

        if setup_direction in {
            "bullish",
            "bearish",
        }:
            return 0.0

        return 0.50

    def score(
        self,
        pairing_result: dict[str, Any],
        regime_result: dict[str, Any],
    ) -> dict[str, Any]:
        regime_label = str(
            regime_result.get(
                "label",
                "unknown",
            )
        )

        regime_confidence = float(
            regime_result.get(
                "confidence",
                0.0,
            )
        )

        scored_setups: list[
            dict[str, Any]
        ] = []

        for pair in pairing_result.get(
            "pairs",
            [],
        ):
            ob_confidence = float(
                pair.get(
                    "ob_confidence",
                    0.0,
                )
            )

            fvg_confidence = float(
                pair.get(
                    "fvg_confidence",
                    0.0,
                )
            )

            setup_direction = (
                self.normalize_direction(
                    str(
                        pair.get(
                            "direction",
                            "unknown",
                        )
                    )
                )
            )

            alignment = self.cnn_alignment(
                setup_direction,
                regime_label,
            )

            cnn_context_score = (
                alignment
                * (
                    0.50
                    + 0.50
                    * regime_confidence
                )
            )

            spatial_score = float(
                pair.get(
                    "spatial_score",
                    0.0,
                )
            )

            average_confidence = float(
                pair.get(
                    "average_confidence",
                    0.0,
                )
            )

            detector_valid = (
                ob_confidence
                >= self.minimum_ob_confidence
                and fvg_confidence
                >= self.minimum_fvg_confidence
            )

            detector_score = min(
                1.0,
                average_confidence / 0.25,
            )

            live_score = (
                detector_score * 0.35
                + spatial_score * 0.40
                + cnn_context_score * 0.25
            )

            if not detector_valid:
                status = "LOW_CONFIDENCE"

            elif live_score >= 0.75:
                status = "ACCEPT"

            elif live_score >= 0.60:
                status = "REVIEW"

            elif live_score >= 0.45:
                status = "WATCHLIST"

            else:
                status = "REJECT"

            scored_setups.append(
                {
                    **pair,
                    "setup_direction": (
                        setup_direction
                    ),
                    "regime_label": (
                        regime_label
                    ),
                    "regime_confidence": (
                        regime_confidence
                    ),
                    "cnn_alignment": alignment,
                    "cnn_context_score": (
                        cnn_context_score
                    ),
                    "detector_score": (
                        detector_score
                    ),
                    "detector_valid": (
                        detector_valid
                    ),
                    "live_score": live_score,
                    "live_status": status,
                }
            )

        scored_setups.sort(
            key=lambda item: item[
                "live_score"
            ],
            reverse=True,
        )

        valid_setups = [
            setup
            for setup in scored_setups
            if setup["detector_valid"]
        ]

        return {
            "total_setups": len(
                scored_setups
            ),
            "valid_setups": len(
                valid_setups
            ),
            "low_confidence_setups": (
                len(scored_setups)
                - len(valid_setups)
            ),
            "best_setup": (
                valid_setups[0]
                if valid_setups
                else None
            ),
            "setups": scored_setups,
            "scoring_stage": (
                "LIVE_PRELIMINARY"
            ),
            "final_decision_ready": False,
            "required_next_context": [
                "pair",
                "timeframe",
                "chart_datetime",
                "OHLCV",
            ],
        }
