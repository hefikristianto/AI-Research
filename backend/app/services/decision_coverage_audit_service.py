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
        "detector_threshold",
        "yolo_model_path",
        "pair_count",
        "pairing_status",
        "setup_count",
        "valid_setup_count",
        "best_setup_status",
        "setup_direction",
        "mapping_status",
        "mapping_confidence",
        "entry_distance_atr",
        "blockers",
        "warnings",
        "reasons",
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
        recommendation = cls._mapping(payload.get("recommendation"))
        execution_gate = cls._mapping(payload.get("execution_gate"))
        price_conversion = cls._mapping(payload.get("price_conversion"))

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
            "order_block_count": cls._integer(
                class_counts.get("order_block")
            ),
            "fair_value_gap_count": cls._integer(
                class_counts.get("fair_value_gap")
            ),
            "detector_threshold": cls._number(
                detection.get("confidence_threshold")
            ),
            "yolo_model_path": detection.get("model_path", ""),
            "pair_count": cls._integer(pairing.get("total_pairs")),
            "pairing_status": pairing.get("pairing_status", "UNKNOWN"),
            "setup_count": cls._integer(scoring.get("total_setups")),
            "valid_setup_count": cls._integer(scoring.get("valid_setups")),
            "best_setup_status": best_setup.get("live_status", "NONE"),
            "setup_direction": recommendation.get(
                "setup_direction",
                execution_gate.get("setup_direction", "unknown"),
            ),
            "mapping_status": price_conversion.get("status", "UNKNOWN"),
            "mapping_confidence": cls._number(
                execution_gate.get(
                    "mapping_confidence",
                    price_conversion.get("mapping_confidence"),
                )
            ),
            "entry_distance_atr": cls._number(
                execution_gate.get("entry_distance_atr")
            ),
            "blockers": cls._join_codes(blockers),
            "warnings": cls._join_codes(warnings),
            "reasons": cls._join_codes(reasons),
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

        return {
            "schema_version": 1,
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
                "paired_setup": cls._metric(with_pair, denominator),
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
                "blockers": cls._code_distribution(successful, "blockers"),
                "warnings": cls._code_distribution(successful, "warnings"),
                "failure_status": cls._distribution(
                    row.get("request_status") for row in failed
                ),
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
            f"- Confidence threshold: `{config.get('confidence_threshold', 'unknown')}`",
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
                "| Pair | TF | N | Detection | Pair | Valid setup | Watchlist | Actionable |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for group in summary.get("by_pair_timeframe", []):
            lines.append(
                "| "
                f"{group.get('pair')} | {group.get('timeframe')} | "
                f"{group.get('successful')} | "
                f"{cls._percent(cls._mapping(group.get('detection_coverage')))} | "
                f"{cls._percent(cls._mapping(group.get('pair_coverage')))} | "
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
                "- Any model update requires reviewed labels and a separate validation split.",
                "",
            ]
        )

        return "\n".join(lines)
