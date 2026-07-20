from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import ceil
from statistics import mean, median
from typing import Any, Iterable


class DecisionCoverageAuditService:
    """Build auditable rows and summaries from full-analysis responses."""

    CSV_FIELDS = [
        "image_id",
        "file_name",
        "image_path",
        "pair",
        "timeframe",
        "year",
        "chart_datetime",
        "request_status",
        "http_status",
        "latency_ms",
        "pipeline_status",
        "decision",
        "internal_decision",
        "execution_status",
        "final_decision_ready",
        "actionable",
        "regime_label",
        "regime_confidence",
        "cnn_device",
        "detection_count",
        "order_block_count",
        "fair_value_gap_count",
        "both_detection_classes",
        "rightmost_detection_right_edge_ratio",
        "rightmost_detection_gap_ratio",
        "detector_threshold",
        "yolo_model_path",
        "pair_count",
        "candidate_pair_combinations",
        "pairing_status",
        "setup_count",
        "valid_setup_count",
        "best_setup_status",
        "best_setup_live_score",
        "best_setup_detector_valid",
        "best_setup_average_confidence",
        "best_setup_x_distance",
        "best_setup_y_distance",
        "best_pair_right_edge_ratio",
        "best_pair_gap_ratio",
        "setup_direction",
        "base_structure_score",
        "advanced_score",
        "advanced_status",
        "htf_alignment_score",
        "volatility_regime",
        "session_name",
        "session_score",
        "risk_reward_ratio",
        "pre_quality_decision",
        "pre_quality_execution_status",
        "pre_quality_final_decision_ready",
        "quality_status_changed",
        "quality_added_blockers",
        "quality_added_warnings",
        "mapping_status",
        "mapping_mode",
        "mapping_provisional",
        "mapping_confidence",
        "mapping_ob_index_error",
        "mapping_fvg_index_error",
        "mapping_distance_from_prediction",
        "mapped_ob_datetime",
        "mapped_fvg_datetime",
        "mapped_ob_candles_from_end",
        "mapped_fvg_candles_from_end",
        "zone_status",
        "zone_touch_count",
        "entry_distance_atr",
        "entry_side_valid",
        "zone_invalidated",
        "blockers",
        "warnings",
        "reasons",
        "response_json_path",
        "annotated_chart_path",
        "annotated_chart_status",
        "annotated_chart_sha256",
        "annotated_chart_sha256_verified",
        "review_artifact_error",
        "error",
    ]

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _codes(value: Any) -> list[str]:
        if isinstance(value, str):
            return [
                item.strip()
                for item in value.split("|")
                if item.strip()
            ]

        if isinstance(value, (list, tuple, set)):
            return [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

        return []

    @classmethod
    def _join_codes(cls, value: Any) -> str:
        return "|".join(cls._codes(value))

    @staticmethod
    def _integer(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _number(value: Any) -> float | None:
        if value in (None, ""):
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return bool(value)

        return str(value).strip().lower() in {
            "1",
            "true",
            "yes",
        }

    @classmethod
    def _optional_boolean(
        cls,
        value: Any,
    ) -> int | None:
        if value in (None, ""):
            return None

        return int(cls._boolean(value))

    @classmethod
    def _rightmost_edge(
        cls,
        boxes: Iterable[Any],
    ) -> float | None:
        right_edges: list[float] = []

        for raw_box in boxes:
            box = cls._mapping(raw_box)
            center_x = cls._number(
                box.get("x")
            )
            width = cls._number(
                box.get("width")
            )

            if center_x is None:
                continue

            if width is None:
                width = 0.0

            right_edges.append(
                max(
                    0.0,
                    min(
                        1.0,
                        center_x
                        + width / 2.0,
                    ),
                )
            )

        if not right_edges:
            return None

        return max(right_edges)

    @classmethod
    def _candles_from_end(
        cls,
        index: Any,
        window_size: Any,
    ) -> int | None:
        parsed_index = cls._number(index)
        parsed_size = cls._number(window_size)

        if (
            parsed_index is None
            or parsed_size is None
            or parsed_size <= 0
        ):
            return None

        return max(
            0,
            int(parsed_size)
            - 1
            - int(parsed_index),
        )

    @classmethod
    def success_row(
        cls,
        sample: dict[str, Any],
        payload: dict[str, Any],
        *,
        latency_ms: float,
        http_status: int = 200,
    ) -> dict[str, Any]:
        regime = cls._mapping(payload.get("regime"))
        detection = cls._mapping(payload.get("detection"))
        pairing = cls._mapping(payload.get("pairing"))
        scoring = cls._mapping(payload.get("scoring"))
        ohlcv_context = cls._mapping(payload.get("ohlcv_context"))
        advanced_scoring = cls._mapping(payload.get("advanced_scoring"))
        session_risk = cls._mapping(payload.get("session_risk"))
        recommendation = cls._mapping(payload.get("recommendation"))
        execution_gate = cls._mapping(payload.get("execution_gate"))
        price_conversion = cls._mapping(payload.get("price_conversion"))
        annotated_chart = cls._mapping(payload.get("annotated_chart"))
        quality_normalization = cls._mapping(
            execution_gate.get("quality_normalization")
        )
        session = cls._mapping(session_risk.get("session"))
        risk_reward = cls._mapping(session_risk.get("risk_reward"))

        class_counts = cls._mapping(detection.get("class_counts"))
        detections = detection.get("detections")
        if not isinstance(detections, list):
            detections = []

        detection_count = cls._integer(
            detection.get("total"),
            len(detections),
        )

        blockers = recommendation.get(
            "blockers",
            execution_gate.get("blockers", []),
        )
        warnings = recommendation.get(
            "warnings",
            execution_gate.get("warnings", []),
        )
        reasons = recommendation.get(
            "reasons",
            execution_gate.get("reasons", []),
        )
        best_setup = cls._mapping(scoring.get("best_setup"))

        detection_boxes = [
            cls._mapping(item).get(
                "bbox_normalized"
            )
            for item in detections
            if isinstance(item, dict)
        ]
        rightmost_detection_edge = (
            cls._rightmost_edge(
                detection_boxes
            )
        )
        best_pair_edge = cls._rightmost_edge(
            [
                best_setup.get("ob_bbox"),
                best_setup.get("fvg_bbox"),
            ]
        )

        resolved_chart_candles = (
            ohlcv_context.get(
                "resolved_chart_candles"
            )
        )

        order_block_count = cls._integer(
            class_counts.get("order_block")
        )
        fair_value_gap_count = cls._integer(
            class_counts.get("fair_value_gap")
        )

        return {
            "image_id": sample.get("image_id", ""),
            "file_name": sample.get("file_name", ""),
            "image_path": sample.get("image_path", ""),
            "pair": sample.get("pair", ""),
            "timeframe": sample.get("timeframe", ""),
            "year": sample.get("year", ""),
            "chart_datetime": sample.get("chart_datetime", ""),
            "request_status": "SUCCESS",
            "http_status": http_status,
            "latency_ms": round(float(latency_ms), 3),
            "pipeline_status": payload.get("pipeline_status", ""),
            "decision": recommendation.get("decision", "UNKNOWN"),
            "internal_decision": recommendation.get(
                "internal_decision",
                execution_gate.get("decision", "UNKNOWN"),
            ),
            "execution_status": recommendation.get(
                "execution_status",
                execution_gate.get("execution_status", "UNKNOWN"),
            ),
            "final_decision_ready": int(
                cls._boolean(
                    recommendation.get(
                        "final_decision_ready",
                        execution_gate.get("final_decision_ready", False),
                    )
                )
            ),
            "actionable": int(
                cls._boolean(recommendation.get("actionable", False))
            ),
            "regime_label": regime.get("label", "unknown"),
            "regime_confidence": cls._number(regime.get("confidence")),
            "cnn_device": regime.get("device", "unknown"),
            "detection_count": detection_count,
            "order_block_count": order_block_count,
            "fair_value_gap_count": fair_value_gap_count,
            "both_detection_classes": int(
                order_block_count > 0
                and fair_value_gap_count > 0
            ),
            "rightmost_detection_right_edge_ratio": (
                rightmost_detection_edge
            ),
            "rightmost_detection_gap_ratio": (
                None
                if rightmost_detection_edge is None
                else 1.0
                - rightmost_detection_edge
            ),
            "detector_threshold": cls._number(
                detection.get("confidence_threshold")
            ),
            "yolo_model_path": detection.get("model_path", ""),
            "pair_count": cls._integer(pairing.get("total_pairs")),
            "candidate_pair_combinations": cls._integer(
                pairing.get("candidate_combinations")
            ),
            "pairing_status": pairing.get("pairing_status", "UNKNOWN"),
            "setup_count": cls._integer(scoring.get("total_setups")),
            "valid_setup_count": cls._integer(scoring.get("valid_setups")),
            "best_setup_status": best_setup.get("live_status", "NONE"),
            "best_setup_live_score": cls._number(
                best_setup.get("live_score")
            ),
            "best_setup_detector_valid": cls._optional_boolean(
                best_setup.get("detector_valid")
            ),
            "best_setup_average_confidence": cls._number(
                best_setup.get("average_confidence")
            ),
            "best_setup_x_distance": cls._number(
                best_setup.get("x_distance")
            ),
            "best_setup_y_distance": cls._number(
                best_setup.get("y_distance")
            ),
            "best_pair_right_edge_ratio": (
                best_pair_edge
            ),
            "best_pair_gap_ratio": (
                None
                if best_pair_edge is None
                else 1.0 - best_pair_edge
            ),
            "setup_direction": recommendation.get(
                "setup_direction",
                execution_gate.get("setup_direction", "unknown"),
            ),
            "base_structure_score": cls._number(
                advanced_scoring.get(
                    "base_structure_score"
                )
            ),
            "advanced_score": cls._number(
                execution_gate.get(
                    "advanced_score",
                    advanced_scoring.get("advanced_score"),
                )
            ),
            "advanced_status": execution_gate.get(
                "advanced_status",
                advanced_scoring.get("advanced_status", "UNKNOWN"),
            ),
            "htf_alignment_score": cls._number(
                execution_gate.get(
                    "htf_alignment_score",
                    advanced_scoring.get(
                        "htf_alignment_score"
                    ),
                )
            ),
            "volatility_regime": execution_gate.get(
                "volatility_regime",
                advanced_scoring.get(
                    "volatility_regime",
                    "UNKNOWN",
                ),
            ),
            "session_name": execution_gate.get(
                "session",
                session.get("session", "UNKNOWN"),
            ),
            "session_score": cls._number(
                execution_gate.get(
                    "session_score",
                    session.get("session_score"),
                )
            ),
            "risk_reward_ratio": cls._number(
                execution_gate.get(
                    "risk_reward_ratio",
                    risk_reward.get("risk_reward_ratio"),
                )
            ),
            "pre_quality_decision": quality_normalization.get(
                "pre_decision",
                execution_gate.get("decision", "UNKNOWN"),
            ),
            "pre_quality_execution_status": (
                quality_normalization.get(
                    "pre_execution_status",
                    execution_gate.get(
                        "execution_status",
                        "UNKNOWN",
                    ),
                )
            ),
            "pre_quality_final_decision_ready": (
                cls._optional_boolean(
                    quality_normalization.get(
                        "pre_final_decision_ready",
                        execution_gate.get(
                            "final_decision_ready"
                        ),
                    )
                )
            ),
            "quality_status_changed": cls._optional_boolean(
                quality_normalization.get(
                    "status_changed"
                )
            ),
            "quality_added_blockers": cls._join_codes(
                quality_normalization.get(
                    "added_blockers"
                )
            ),
            "quality_added_warnings": cls._join_codes(
                quality_normalization.get(
                    "added_warnings"
                )
            ),
            "mapping_status": price_conversion.get("status", "UNKNOWN"),
            "mapping_mode": price_conversion.get("mapping_mode", ""),
            "mapping_provisional": cls._optional_boolean(
                price_conversion.get(
                    "mapping_provisional",
                    risk_reward.get(
                        "price_mapping_provisional"
                    ),
                )
            ),
            "mapping_confidence": cls._number(
                execution_gate.get(
                    "mapping_confidence",
                    price_conversion.get("mapping_confidence"),
                )
            ),
            "mapping_ob_index_error": cls._number(
                price_conversion.get("ob_index_error")
            ),
            "mapping_fvg_index_error": cls._number(
                price_conversion.get("fvg_index_error")
            ),
            "mapping_distance_from_prediction": cls._number(
                price_conversion.get(
                    "distance_from_prediction"
                )
            ),
            "mapped_ob_datetime": price_conversion.get(
                "ob_datetime",
                "",
            ),
            "mapped_fvg_datetime": price_conversion.get(
                "fvg_datetime",
                "",
            ),
            "mapped_ob_candles_from_end": cls._candles_from_end(
                price_conversion.get("matched_ob_idx"),
                resolved_chart_candles,
            ),
            "mapped_fvg_candles_from_end": cls._candles_from_end(
                price_conversion.get("matched_fvg_idx"),
                resolved_chart_candles,
            ),
            "zone_status": price_conversion.get("zone_status", ""),
            "zone_touch_count": cls._integer(
                price_conversion.get("zone_touch_count")
            ),
            "entry_distance_atr": cls._number(
                execution_gate.get("entry_distance_atr")
            ),
            "entry_side_valid": cls._optional_boolean(
                risk_reward.get("entry_side_valid")
            ),
            "zone_invalidated": cls._optional_boolean(
                risk_reward.get("zone_invalidated")
            ),
            "blockers": cls._join_codes(blockers),
            "warnings": cls._join_codes(warnings),
            "reasons": cls._join_codes(reasons),
            "response_json_path": "",
            "annotated_chart_path": "",
            "annotated_chart_status": annotated_chart.get(
                "status",
                "UNKNOWN",
            ),
            "annotated_chart_sha256": annotated_chart.get(
                "sha256",
                "",
            ),
            "annotated_chart_sha256_verified": "",
            "review_artifact_error": "",
            "error": "",
        }

    @classmethod
    def error_row(
        cls,
        sample: dict[str, Any],
        *,
        request_status: str,
        error: str,
        latency_ms: float | None = None,
        http_status: int | None = None,
    ) -> dict[str, Any]:
        row = {field: "" for field in cls.CSV_FIELDS}
        row.update(
            {
                "image_id": sample.get("image_id", ""),
                "file_name": sample.get("file_name", ""),
                "image_path": sample.get("image_path", ""),
                "pair": sample.get("pair", ""),
                "timeframe": sample.get("timeframe", ""),
                "year": sample.get("year", ""),
                "chart_datetime": sample.get("chart_datetime", ""),
                "request_status": request_status,
                "http_status": "" if http_status is None else http_status,
                "latency_ms": (
                    "" if latency_ms is None else round(float(latency_ms), 3)
                ),
                "error": str(error),
            }
        )
        return row

    @staticmethod
    def _distribution(values: Iterable[Any]) -> dict[str, int]:
        counts = Counter(
            str(value) if value not in (None, "") else "UNKNOWN"
            for value in values
        )
        return dict(
            sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        )

    @classmethod
    def _code_distribution(
        cls,
        rows: Iterable[dict[str, Any]],
        field: str,
    ) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for row in rows:
            counts.update(cls._codes(row.get(field)))

        return dict(
            sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        )

    @staticmethod
    def _metric(count: int, denominator: int) -> dict[str, Any]:
        rate = 0.0
        if denominator:
            rate = count / denominator

        return {
            "count": count,
            "denominator": denominator,
            "rate": round(rate, 6),
        }

    @classmethod
    def summarize(
        cls,
        rows: list[dict[str, Any]],
        run_configuration: dict[str, Any],
    ) -> dict[str, Any]:
        successful = [
            row
            for row in rows
            if row.get("request_status") == "SUCCESS"
        ]
        failed = [
            row
            for row in rows
            if row.get("request_status") != "SUCCESS"
        ]
        denominator = len(successful)

        with_detection = sum(
            cls._integer(row.get("detection_count")) > 0
            for row in successful
        )
        with_pair = sum(
            cls._integer(row.get("pair_count")) > 0
            for row in successful
        )
        with_valid_setup = sum(
            cls._integer(row.get("valid_setup_count")) > 0
            for row in successful
        )
        valid_rows = [
            row
            for row in successful
            if cls._integer(
                row.get("valid_setup_count")
            )
            > 0
        ]
        with_both_classes = sum(
            cls._integer(
                row.get("order_block_count")
            )
            > 0
            and cls._integer(
                row.get("fair_value_gap_count")
            )
            > 0
            for row in successful
        )
        order_block_only = sum(
            cls._integer(
                row.get("order_block_count")
            )
            > 0
            and cls._integer(
                row.get("fair_value_gap_count")
            )
            == 0
            for row in successful
        )
        fair_value_gap_only = sum(
            cls._integer(
                row.get("order_block_count")
            )
            == 0
            and cls._integer(
                row.get("fair_value_gap_count")
            )
            > 0
            for row in successful
        )
        paired_with_both_classes = sum(
            cls._integer(
                row.get("pair_count")
            )
            > 0
            and cls._integer(
                row.get("order_block_count")
            )
            > 0
            and cls._integer(
                row.get("fair_value_gap_count")
            )
            > 0
            for row in successful
        )
        unclassified_detection = max(
            0,
            with_detection
            - order_block_only
            - fair_value_gap_only
            - with_both_classes,
        )
        actionable = sum(
            cls._boolean(row.get("actionable"))
            for row in successful
        )
        watchlist = sum(
            str(row.get("decision")) == "WATCHLIST"
            for row in successful
        )
        no_trade = sum(
            str(row.get("decision")) == "NO_TRADE"
            for row in successful
        )

        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in successful:
            groups[
                (
                    str(row.get("pair", "UNKNOWN")),
                    str(row.get("timeframe", "UNKNOWN")),
                )
            ].append(row)

        by_pair_timeframe: list[dict[str, Any]] = []
        for (pair, timeframe), group_rows in sorted(groups.items()):
            group_total = len(group_rows)
            group_detection = sum(
                cls._integer(row.get("detection_count")) > 0
                for row in group_rows
            )
            group_pair = sum(
                cls._integer(row.get("pair_count")) > 0
                for row in group_rows
            )
            group_valid_setup = sum(
                cls._integer(row.get("valid_setup_count")) > 0
                for row in group_rows
            )
            group_both_classes = sum(
                cls._integer(
                    row.get("order_block_count")
                )
                > 0
                and cls._integer(
                    row.get("fair_value_gap_count")
                )
                > 0
                for row in group_rows
            )
            group_paired_with_both = sum(
                cls._integer(
                    row.get("pair_count")
                )
                > 0
                and cls._integer(
                    row.get("order_block_count")
                )
                > 0
                and cls._integer(
                    row.get("fair_value_gap_count")
                )
                > 0
                for row in group_rows
            )
            group_actionable = sum(
                cls._boolean(row.get("actionable"))
                for row in group_rows
            )
            group_watchlist = sum(
                str(row.get("decision")) == "WATCHLIST"
                for row in group_rows
            )

            by_pair_timeframe.append(
                {
                    "pair": pair,
                    "timeframe": timeframe,
                    "successful": group_total,
                    "detection_coverage": cls._metric(
                        group_detection,
                        group_total,
                    ),
                    "pair_coverage": cls._metric(
                        group_pair,
                        group_total,
                    ),
                    "valid_setup_coverage": cls._metric(
                        group_valid_setup,
                        group_total,
                    ),
                    "both_class_coverage": cls._metric(
                        group_both_classes,
                        group_total,
                    ),
                    "pair_given_both_classes": cls._metric(
                        group_paired_with_both,
                        group_both_classes,
                    ),
                    "watchlist_coverage": cls._metric(
                        group_watchlist,
                        group_total,
                    ),
                    "actionable_coverage": cls._metric(
                        group_actionable,
                        group_total,
                    ),
                }
            )

        latencies = [
            value
            for row in successful
            if (value := cls._number(row.get("latency_ms"))) is not None
        ]

        latency_summary: dict[str, Any] = {
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "maximum_ms": None,
        }
        if latencies:
            ordered_latencies = sorted(latencies)
            p95_index = max(
                0,
                ceil(0.95 * len(ordered_latencies)) - 1,
            )
            latency_summary = {
                "mean_ms": round(mean(latencies), 3),
                "p50_ms": round(median(latencies), 3),
                "p95_ms": round(ordered_latencies[p95_index], 3),
                "maximum_ms": round(max(latencies), 3),
            }

        selected_images = cls._integer(
            run_configuration.get("selected_images"),
            len(rows),
        )

        entry_distances = [
            value
            for row in valid_rows
            if (
                value := cls._number(
                    row.get("entry_distance_atr")
                )
            )
            is not None
        ]
        distance_at_or_below_warning = sum(
            value <= 1.5
            for value in entry_distances
        )
        distance_warning_band = sum(
            1.5 < value <= 3.0
            for value in entry_distances
        )
        distance_blocker_band = sum(
            value > 3.0
            for value in entry_distances
        )
        valid_without_blockers = sum(
            not cls._codes(row.get("blockers"))
            for row in valid_rows
        )
        pre_quality_trade_candidates = sum(
            str(
                row.get(
                    "pre_quality_execution_status"
                )
            )
            == "TRADE_CANDIDATE"
            for row in valid_rows
        )
        quality_status_changed = sum(
            cls._boolean(
                row.get("quality_status_changed")
            )
            for row in valid_rows
        )

        return {
            "schema_version": 2,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "run_configuration": run_configuration,
            "population": {
                "selected_images": selected_images,
                "processed_rows": len(rows),
                "successful_responses": denominator,
                "failed_responses": len(failed),
                "unprocessed_images": max(0, selected_images - len(rows)),
            },
            "coverage": {
                "detection": cls._metric(with_detection, denominator),
                "both_detection_classes": cls._metric(
                    with_both_classes,
                    denominator,
                ),
                "paired_setup": cls._metric(with_pair, denominator),
                "paired_given_both_classes": cls._metric(
                    paired_with_both_classes,
                    with_both_classes,
                ),
                "valid_setup": cls._metric(with_valid_setup, denominator),
                "watchlist": cls._metric(watchlist, denominator),
                "actionable": cls._metric(actionable, denominator),
                "no_trade": cls._metric(no_trade, denominator),
            },
            "distributions": {
                "public_decision": cls._distribution(
                    row.get("decision") for row in successful
                ),
                "internal_decision": cls._distribution(
                    row.get("internal_decision") for row in successful
                ),
                "execution_status": cls._distribution(
                    row.get("execution_status") for row in successful
                ),
                "pipeline_status": cls._distribution(
                    row.get("pipeline_status") for row in successful
                ),
                "regime": cls._distribution(
                    row.get("regime_label") for row in successful
                ),
                "advanced_status": cls._distribution(
                    row.get("advanced_status") for row in valid_rows
                ),
                "pre_quality_execution_status": cls._distribution(
                    row.get("pre_quality_execution_status")
                    for row in valid_rows
                ),
                "mapping_status": cls._distribution(
                    row.get("mapping_status") for row in valid_rows
                ),
                "session": cls._distribution(
                    row.get("session_name") for row in valid_rows
                ),
                "volatility_regime": cls._distribution(
                    row.get("volatility_regime")
                    for row in valid_rows
                ),
                "blockers": cls._code_distribution(successful, "blockers"),
                "warnings": cls._code_distribution(successful, "warnings"),
                "quality_added_blockers": cls._code_distribution(
                    valid_rows,
                    "quality_added_blockers",
                ),
                "quality_added_warnings": cls._code_distribution(
                    valid_rows,
                    "quality_added_warnings",
                ),
                "failure_status": cls._distribution(
                    row.get("request_status") for row in failed
                ),
            },
            "diagnostics": {
                "detection_composition": {
                    "no_detection": (
                        denominator
                        - with_detection
                    ),
                    "order_block_only": order_block_only,
                    "fair_value_gap_only": fair_value_gap_only,
                    "both_classes": with_both_classes,
                    "unclassified_detection": (
                        unclassified_detection
                    ),
                },
                "valid_setup_execution": {
                    "valid_setups": len(valid_rows),
                    "without_hard_blockers": (
                        valid_without_blockers
                    ),
                    "pre_quality_trade_candidates": (
                        pre_quality_trade_candidates
                    ),
                    "quality_status_changed": (
                        quality_status_changed
                    ),
                },
                "entry_distance_atr": {
                    "observed": len(entry_distances),
                    "at_or_below_1_5": (
                        distance_at_or_below_warning
                    ),
                    "above_1_5_to_3": (
                        distance_warning_band
                    ),
                    "above_3": distance_blocker_band,
                },
            },
            "by_pair_timeframe": by_pair_timeframe,
            "latency": latency_summary,
            "interpretation": {
                "coverage_is_not_accuracy": True,
                "coverage_is_not_profitability": True,
                "threshold_changes_require_separate_evaluation": True,
                "raw_predictions_are_not_ground_truth": True,
            },
        }

    @staticmethod
    def _percent(metric: dict[str, Any]) -> str:
        return f"{float(metric.get('rate', 0.0)) * 100:.2f}%"

    @classmethod
    def render_markdown(cls, summary: dict[str, Any]) -> str:
        population = cls._mapping(summary.get("population"))
        coverage = cls._mapping(summary.get("coverage"))
        distributions = cls._mapping(summary.get("distributions"))
        diagnostics = cls._mapping(summary.get("diagnostics"))
        config = cls._mapping(summary.get("run_configuration"))

        lines = [
            "# AI-TDSS Decision Coverage Audit",
            "",
            f"Generated (UTC): `{summary.get('generated_at_utc', '')}`",
            "",
            "## Scope",
            "",
            f"- Year: `{config.get('year', 'unknown')}`",
            f"- Pairs: `{', '.join(config.get('pairs', [])) or 'all'}`",
            f"- Timeframes: `{', '.join(config.get('timeframes', [])) or 'all'}`",
            "- Confidence threshold: "
            f"`{config.get('confidence_threshold', 'unknown')}`",
            f"- Successful responses: `{population.get('successful_responses', 0)}`",
            f"- Failed responses: `{population.get('failed_responses', 0)}`",
            "",
            "## Coverage Funnel",
            "",
            "| Stage | Count | Denominator | Rate |",
            "|---|---:|---:|---:|",
        ]

        for label, key in (
            ("At least one YOLO detection", "detection"),
            ("Both YOLO classes present", "both_detection_classes"),
            ("At least one OB/FVG pair", "paired_setup"),
            ("At least one valid scored setup", "valid_setup"),
            ("Public WATCHLIST", "watchlist"),
            ("Actionable BUY/SELL", "actionable"),
            ("Public NO_TRADE", "no_trade"),
        ):
            metric = cls._mapping(coverage.get(key))
            lines.append(
                "| "
                f"{label} | {metric.get('count', 0)} | "
                f"{metric.get('denominator', 0)} | {cls._percent(metric)} |"
            )

        detection_composition = cls._mapping(
            diagnostics.get("detection_composition")
        )
        valid_execution = cls._mapping(
            diagnostics.get("valid_setup_execution")
        )
        distance_diagnostics = cls._mapping(
            diagnostics.get("entry_distance_atr")
        )
        paired_given_both = cls._mapping(
            coverage.get("paired_given_both_classes")
        )

        lines.extend(
            [
                "",
                "## Diagnostic Funnel",
                "",
                f"- No detection: `{detection_composition.get('no_detection', 0)}`",
                "- Order Block only: "
                f"`{detection_composition.get('order_block_only', 0)}`",
                "- Fair Value Gap only: "
                f"`{detection_composition.get('fair_value_gap_only', 0)}`",
                f"- Both classes: `{detection_composition.get('both_classes', 0)}`",
                "- Unclassified detections: "
                f"`{detection_composition.get('unclassified_detection', 0)}`",
                "- Pairing success when both classes are present: "
                f"`{paired_given_both.get('count', 0)}/"
                f"{paired_given_both.get('denominator', 0)}` "
                f"(`{cls._percent(paired_given_both)}`)",
                "- Valid setups without hard blockers: "
                f"`{valid_execution.get('without_hard_blockers', 0)}`",
                "- Pre-quality trade candidates: "
                f"`{valid_execution.get('pre_quality_trade_candidates', 0)}`",
                "- Quality-normalization status changes: "
                f"`{valid_execution.get('quality_status_changed', 0)}`",
                "- Entry distance <= 1.5 ATR: "
                f"`{distance_diagnostics.get('at_or_below_1_5', 0)}`",
                "- Entry distance > 1.5 and <= 3 ATR: "
                f"`{distance_diagnostics.get('above_1_5_to_3', 0)}`",
                f"- Entry distance > 3 ATR: `{distance_diagnostics.get('above_3', 0)}`",
            ]
        )

        lines.extend(
            [
                "",
                "## Public Decisions",
                "",
                "| Decision | Count |",
                "|---|---:|",
            ]
        )
        for key, count in cls._mapping(
            distributions.get("public_decision")
        ).items():
            lines.append(f"| {key} | {count} |")

        lines.extend(
            [
                "",
                "## Dominant Blockers",
                "",
                "| Blocker | Count |",
                "|---|---:|",
            ]
        )
        blockers = cls._mapping(distributions.get("blockers"))
        if blockers:
            for key, count in list(blockers.items())[:10]:
                lines.append(f"| {key} | {count} |")
        else:
            lines.append("| None recorded | 0 |")

        lines.extend(
            [
                "",
                "## Dominant Warnings",
                "",
                "| Warning | Count |",
                "|---|---:|",
            ]
        )
        warnings = cls._mapping(distributions.get("warnings"))
        if warnings:
            for key, count in list(warnings.items())[:10]:
                lines.append(f"| {key} | {count} |")
        else:
            lines.append("| None recorded | 0 |")

        lines.extend(
            [
                "",
                "## Pair / Timeframe Breakdown",
                "",
                "| Pair | TF | N | Detection | Both classes | Pair | "
                "Pair / both | Valid setup | Watchlist | Actionable |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for group in summary.get("by_pair_timeframe", []):
            lines.append(
                "| "
                f"{group.get('pair')} | {group.get('timeframe')} | "
                f"{group.get('successful')} | "
                f"{cls._percent(cls._mapping(group.get('detection_coverage')))} | "
                f"{cls._percent(cls._mapping(group.get('both_class_coverage')))} | "
                f"{cls._percent(cls._mapping(group.get('pair_coverage')))} | "
                f"{cls._percent(cls._mapping(group.get('pair_given_both_classes')))} | "
                f"{cls._percent(cls._mapping(group.get('valid_setup_coverage')))} | "
                f"{cls._percent(cls._mapping(group.get('watchlist_coverage')))} | "
                f"{cls._percent(cls._mapping(group.get('actionable_coverage')))} |"
            )

        latency = cls._mapping(summary.get("latency"))
        lines.extend(
            [
                "",
                "## Latency",
                "",
                f"- Mean: `{latency.get('mean_ms')}` ms",
                f"- p50: `{latency.get('p50_ms')}` ms",
                f"- p95: `{latency.get('p95_ms')}` ms",
                f"- Maximum: `{latency.get('maximum_ms')}` ms",
            ]
        )

        lines.extend(
            [
                "",
                "## Interpretation Guardrails",
                "",
                "- Coverage measures pipeline selectivity, not prediction accuracy.",
                "- Actionable coverage is not evidence of profitability.",
                "- Do not tune thresholds on the final 2025 test set.",
                "- Raw predictions and user uploads are not ground truth.",
                "- Any model update requires reviewed labels and a "
                "separate validation split.",
                "",
            ]
        )

        return "\n".join(lines)
