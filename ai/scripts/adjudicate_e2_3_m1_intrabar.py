from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from ai.scripts.evaluate_e2_3_forward_outcomes import (
        BREAKDOWN_FIELDS,
        OUTCOME_FIELDS,
        Candle,
        _as_float,
        _as_int,
        _gross_r,
        _safe_relative_path,
        _touches_entry,
        _touches_levels,
        build_breakdowns,
        evaluate_acceptance_gates,
        file_sha256,
        object_sha256,
        read_csv_rows,
        read_json,
        validate_config as validate_forward_config,
        write_csv_atomic,
        write_json_atomic,
    )
except ImportError:
    from evaluate_e2_3_forward_outcomes import (  # type: ignore[no-redef]
        BREAKDOWN_FIELDS,
        OUTCOME_FIELDS,
        Candle,
        _as_float,
        _as_int,
        _gross_r,
        _safe_relative_path,
        _touches_entry,
        _touches_levels,
        build_breakdowns,
        evaluate_acceptance_gates,
        file_sha256,
        object_sha256,
        read_csv_rows,
        read_json,
        validate_config as validate_forward_config,
        write_csv_atomic,
        write_json_atomic,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_3_1_m1_intrabar_adjudication.json"
)
DEFAULT_RAW_ROOT = PROJECT_ROOT / "ai" / "datasets" / "raw" / "ohlcv"
DEFAULT_M1_MANIFEST = (
    DEFAULT_RAW_ROOT
    / "GBPUSD"
    / "M1"
    / "GBPUSD_M1_2020_2023_MT5_STAGING_MANIFEST.json"
)
ADJUDICATOR_VERSION = "1.0.0"
ALLOWED_YEARS = {2020, 2021, 2022, 2023}
ALLOWED_SPLITS = {"POLICY_DEVELOPMENT", "POLICY_SELECTION"}

ADJUDICATION_FIELDS = [
    "snapshot_id",
    "evaluation_split",
    "year",
    "selected_tier",
    "decision",
    "original_outcome_status",
    "original_entry_bar_target_ambiguous",
    "original_same_bar_both_ambiguous",
    "original_net_r_primary",
    "original_optimistic_net_r_primary",
    "m1_resolution_status",
    "m1_primary_changed",
    "m1_unresolved",
    "m1_data_error",
    "m1_fill_bar_start",
    "m1_exit_bar_start",
    "m1_event_datetime",
    "m1_event",
    "m1_m5_ohlc_verified",
    "revised_outcome_status",
    "revised_net_r_primary",
    "revised_optimistic_net_r_primary",
    "m1_source_path",
    "m1_source_sha256",
    "notes",
]

ADDITIONAL_OUTCOME_FIELDS = [
    "original_outcome_status",
    "original_gross_r",
    "original_net_r_primary",
    "original_optimistic_gross_r",
    "original_optimistic_net_r_primary",
    "original_entry_bar_target_ambiguous",
    "original_same_bar_both_ambiguous",
    "m1_adjudication_required",
    "m1_resolution_status",
    "m1_primary_changed",
    "m1_unresolved",
    "m1_data_error",
    "m1_event_datetime",
    "m1_m5_ohlc_verified",
    "m1_source_path",
    "m1_source_sha256",
    "m1_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Adjudicate only the frozen ambiguous E2.3 M5 outcomes with "
            "verified GBPUSD M1 data. No candidate selection, training, "
            "inference, or 2024/2025 access is performed."
        )
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help="E2.3 experiment root containing frozen forward outcomes.",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=DEFAULT_RAW_ROOT,
        help="Local OHLCV root. Raw files remain local-only.",
    )
    parser.add_argument(
        "--m1-manifest",
        type=Path,
        default=DEFAULT_M1_MANIFEST,
        help="Validated local GBPUSD M1 2020-2023 source manifest.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Registered E2.3.1 adjudication contract.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress every N ambiguous observations.",
    )
    return parser.parse_args()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _pct(count: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * count / denominator, 6)


def _parse_datetime(value: Any) -> datetime:
    result = datetime.fromisoformat(str(value))
    if result.tzinfo is not None:
        offset = result.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError(f"Datetime harus UTC/naive: {value}")
        result = result.replace(tzinfo=None)
    return result


def _m5_bar_start(value: Any) -> datetime:
    timestamp = _parse_datetime(value)
    return timestamp.replace(
        minute=(timestamp.minute // 5) * 5,
        second=0,
        microsecond=0,
    )


def _finite_difference(left: Any, right: Any) -> bool:
    try:
        first = _as_float(left)
        second = _as_float(right)
    except ValueError:
        return False
    return not math.isclose(first, second, rel_tol=0.0, abs_tol=1e-12)


def validate_config(config: dict[str, Any]) -> None:
    errors: list[str] = []
    if config.get("experiment_id") != "E2.3.1":
        errors.append("experiment_id")
    if config.get("stage") != "M1_INTRABAR_ADJUDICATION":
        errors.append("stage")
    lineage = config.get("lineage") or {}
    if set(lineage.get("allowed_years", [])) != ALLOWED_YEARS:
        errors.append("allowed years")
    if set(lineage.get("allowed_splits", [])) != ALLOWED_SPLITS:
        errors.append("allowed splits")
    if lineage.get("frozen_holdout_year") != 2024:
        errors.append("frozen holdout")
    if lineage.get("final_temporal_test_year") != 2025:
        errors.append("final temporal test")
    if _as_int(lineage.get("baseline_candidate_days"), default=-1) != 250:
        errors.append("baseline candidate days")
    if _as_int(
        lineage.get("baseline_ambiguity_observations"), default=-1
    ) != 55:
        errors.append("baseline ambiguity observations")
    if _as_int(
        lineage.get("baseline_outcome_sensitive_ambiguity_observations"),
        default=-1,
    ) != 40:
        errors.append("outcome-sensitive ambiguity observations")
    model = config.get("adjudication_model") or {}
    if model.get("source_pair") != "GBPUSD":
        errors.append("source pair")
    if model.get("source_timeframe") != "M1":
        errors.append("source timeframe")
    if _as_int(model.get("ambiguous_m5_window_minutes"), default=-1) != 5:
        errors.append("M5 window")
    guardrails = config.get("guardrails") or {}
    for key in (
        "model_training_allowed",
        "model_inference_allowed",
        "candidate_reselection_allowed",
        "threshold_tuning_allowed",
        "baseline_non_ambiguous_mutation_allowed",
        "holdout_2024_access_allowed",
        "final_2025_access_allowed",
        "production_promotion_allowed",
    ):
        if guardrails.get(key) is not False:
            errors.append(key)
    if guardrails.get("require_all_required_windows_verified") is not True:
        errors.append("required-window verification")
    if errors:
        raise ValueError("E2.3.1 contract INVALID: " + ", ".join(errors))


def _validate_frozen_baseline(
    *,
    experiment_dir: Path,
    config: dict[str, Any],
) -> tuple[list[str], list[dict[str, str]], dict[str, Any]]:
    lineage = config["lineage"]
    outcomes_path = experiment_dir / "outcomes" / "daily_trade_outcomes.csv"
    manifest_path = experiment_dir / "outcome_manifest.json"
    forward_policy_path = experiment_dir / "config" / "forward_outcome_policy.json"
    for path in (outcomes_path, manifest_path, forward_policy_path):
        if not path.is_file():
            raise FileNotFoundError(f"Frozen E2.3 artifact tidak ditemukan: {path}")
    if file_sha256(outcomes_path) != lineage["baseline_outcomes_sha256"]:
        raise ValueError("SHA256 frozen daily_trade_outcomes.csv berubah.")
    if file_sha256(manifest_path) != lineage["baseline_outcome_manifest_sha256"]:
        raise ValueError("SHA256 frozen outcome_manifest.json berubah.")
    if (
        file_sha256(forward_policy_path)
        != lineage["baseline_forward_policy_file_sha256"]
    ):
        raise ValueError("SHA256 frozen forward outcome policy berubah.")
    forward_policy = read_json(forward_policy_path)
    validate_forward_config(forward_policy)
    if (
        object_sha256(forward_policy)
        != lineage["baseline_forward_policy_object_sha256"]
    ):
        raise ValueError("Object SHA256 forward outcome policy berubah.")
    outcome_manifest = read_json(manifest_path)
    if outcome_manifest.get("stage") != "FORWARD_OUTCOME_EVALUATION":
        raise ValueError("Baseline manifest bukan forward-outcome stage.")
    if outcome_manifest.get("holdout_2024_accessed") is not False:
        raise ValueError("Baseline melanggar lock 2024.")
    if outcome_manifest.get("final_2025_accessed") is not False:
        raise ValueError("Baseline melanggar lock 2025.")
    artifact = (outcome_manifest.get("artifacts") or {}).get(
        "outcomes/daily_trade_outcomes.csv"
    ) or {}
    if artifact.get("sha256") != lineage["baseline_outcomes_sha256"]:
        raise ValueError("Baseline outcome manifest/CSV tidak konsisten.")

    fields, rows = read_csv_rows(outcomes_path)
    missing = set(OUTCOME_FIELDS) - set(fields)
    if missing:
        raise ValueError("Kolom baseline outcome kurang: " + ", ".join(sorted(missing)))
    if len(rows) != _as_int(lineage["baseline_candidate_days"]):
        raise ValueError("Jumlah kandidat baseline berubah.")
    years = {_as_int(row.get("year"), default=-1) for row in rows}
    splits = {str(row.get("evaluation_split")) for row in rows}
    if years != ALLOWED_YEARS or not splits.issubset(ALLOWED_SPLITS):
        raise ValueError("Baseline membaca split/tahun di luar kontrak.")
    tiers = Counter(str(row.get("selected_tier")) for row in rows)
    directions = Counter(str(row.get("decision")) for row in rows)
    if tiers != Counter(lineage["baseline_tier_counts"]):
        raise ValueError(f"Komposisi tier baseline berubah: {dict(tiers)}")
    if directions != Counter(lineage["baseline_direction_counts"]):
        raise ValueError(f"Komposisi arah baseline berubah: {dict(directions)}")
    ambiguous = [row for row in rows if _is_ambiguous(row)]
    sensitive = [row for row in ambiguous if _is_outcome_sensitive(row)]
    if len(ambiguous) != _as_int(lineage["baseline_ambiguity_observations"]):
        raise ValueError("Jumlah ambiguity observation baseline berubah.")
    if len(sensitive) != _as_int(
        lineage["baseline_outcome_sensitive_ambiguity_observations"]
    ):
        raise ValueError("Jumlah outcome-sensitive ambiguity baseline berubah.")
    return fields, rows, forward_policy


def _is_ambiguous(row: dict[str, Any]) -> bool:
    return bool(_as_int(row.get("entry_bar_target_ambiguous"), default=0)) or bool(
        _as_int(row.get("same_bar_both_ambiguous"), default=0)
    )


def _is_outcome_sensitive(row: dict[str, Any]) -> bool:
    return _finite_difference(
        row.get("net_r_primary"), row.get("optimistic_net_r_primary")
    )


def build_required_m5_bars(
    rows: Sequence[dict[str, Any]],
) -> tuple[set[datetime], dict[str, tuple[datetime | None, datetime | None]]]:
    required: set[datetime] = set()
    per_snapshot: dict[str, tuple[datetime | None, datetime | None]] = {}
    for row in rows:
        if not _is_ambiguous(row):
            continue
        fill_bar = None
        exit_bar = None
        if _as_int(row.get("entry_bar_target_ambiguous"), default=0):
            if not str(row.get("fill_datetime") or ""):
                raise ValueError(f"Ambiguous fill tanpa fill_datetime: {row['snapshot_id']}")
            fill_bar = _m5_bar_start(row["fill_datetime"])
            required.add(fill_bar)
        if _as_int(row.get("same_bar_both_ambiguous"), default=0):
            if not str(row.get("exit_datetime") or ""):
                raise ValueError(f"Ambiguous exit tanpa exit_datetime: {row['snapshot_id']}")
            exit_bar = _m5_bar_start(row["exit_datetime"])
            required.add(exit_bar)
        per_snapshot[str(row["snapshot_id"])] = (fill_bar, exit_bar)
    return required, per_snapshot


def _manifest_entry_hash(entry: dict[str, Any]) -> str:
    for key in ("sha256", "source_sha256", "file_sha256"):
        value = str(entry.get(key) or "").strip().lower()
        if len(value) == 64 and all(character in "0123456789abcdef" for character in value):
            return value
    raise ValueError("M1 manifest entry tidak memiliki SHA256 valid.")


def build_m1_source_contract(
    *,
    manifest_path: Path,
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    payload = read_json(manifest_path)
    entries = payload.get("years")
    if not isinstance(entries, dict):
        raise ValueError("M1 manifest harus memiliki object 'years'.")
    manifest_years = {_as_int(value, default=-1) for value in entries}
    if manifest_years != ALLOWED_YEARS:
        raise ValueError(
            "M1 manifest harus tepat 2020-2023; ditemukan "
            f"{sorted(manifest_years)}."
        )
    required_status = config["adjudication_model"][
        "required_m1_manifest_status"
    ]
    expected_rows = config["lineage"]["expected_m1_row_counts"]
    contract: dict[str, dict[str, Any]] = {}
    for year in sorted(ALLOWED_YEARS):
        entry = entries.get(str(year))
        if not isinstance(entry, dict):
            raise ValueError(f"M1 manifest entry {year} tidak valid.")
        if str(entry.get("validation_status")) != required_status:
            raise ValueError(f"M1 source {year} belum VALID_CANDIDATE.")
        relative = f"GBPUSD/M1/{year}/GBPUSD_M1_{year}_RAW.csv"
        contract[relative] = {
            "year": year,
            "sha256": _manifest_entry_hash(entry),
            "expected_rows": _as_int(expected_rows[str(year)]),
            "validation_status": required_status,
        }
    return contract


def build_m5_source_contract(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected = config["lineage"].get("expected_m5_source_sha256s") or {}
    contract: dict[str, dict[str, Any]] = {}
    for relative, digest in expected.items():
        normalized = str(relative).replace("\\", "/")
        year = next(
            (value for value in ALLOWED_YEARS if f"/{value}/" in normalized),
            None,
        )
        if year is None or f"/M5/{year}/" not in normalized:
            raise ValueError(f"M5 source contract di luar scope: {relative}")
        contract[normalized] = {"year": year, "sha256": str(digest).lower()}
    if {details["year"] for details in contract.values()} != ALLOWED_YEARS:
        raise ValueError("M5 source contract 2020-2023 tidak lengkap.")
    return dict(sorted(contract.items()))


def _parse_mt5_line(header: list[str], line: str) -> dict[str, str]:
    values = line.strip().split()
    if len(values) != len(header):
        raise ValueError(
            f"Jumlah kolom OHLCV tidak konsisten: expected={len(header)} actual={len(values)}"
        )
    return dict(zip(header, values))


def read_required_bars(
    *,
    raw_root: Path,
    source_contract: dict[str, dict[str, Any]],
    required_bars: set[datetime],
    timeframe: str,
) -> tuple[dict[datetime, list[Candle]], dict[str, dict[str, Any]]]:
    if timeframe not in {"M1", "M5"}:
        raise ValueError(f"Timeframe source tidak didukung: {timeframe}")
    grouped: dict[datetime, list[Candle]] = defaultdict(list)
    source_audit: dict[str, dict[str, Any]] = {}
    required_columns = {"<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>"}
    for relative, details in source_contract.items():
        path = _safe_relative_path(raw_root, relative)
        if not path.is_file():
            raise FileNotFoundError(f"Source {timeframe} tidak ditemukan: {path}")
        actual_sha = file_sha256(path)
        if actual_sha != details["sha256"]:
            raise ValueError(f"SHA256 source {timeframe} berubah: {relative}")
        row_count = 0
        previous: datetime | None = None
        first: datetime | None = None
        last: datetime | None = None
        with path.open("r", encoding="utf-8-sig") as handle:
            header = handle.readline().strip().split()
            if not required_columns.issubset(set(header)):
                raise ValueError(f"Kolom source {timeframe} tidak lengkap: {path}")
            for line_number, line in enumerate(handle, start=2):
                if not line.strip():
                    continue
                raw = _parse_mt5_line(header, line)
                timestamp = datetime.strptime(
                    f"{raw['<DATE>']} {raw['<TIME>']}",
                    "%Y.%m.%d %H:%M:%S",
                )
                if timestamp.year != _as_int(details["year"]):
                    raise ValueError(
                        f"Tahun source {timeframe} salah pada {path}:{line_number}"
                    )
                if previous is not None and timestamp <= previous:
                    raise ValueError(
                        f"Timestamp source {timeframe} tidak strictly increasing: "
                        f"{path}:{line_number}"
                    )
                previous = timestamp
                first = first or timestamp
                last = timestamp
                row_count += 1
                candle = Candle(
                    timestamp=timestamp,
                    open=_as_float(raw["<OPEN>"]),
                    high=_as_float(raw["<HIGH>"]),
                    low=_as_float(raw["<LOW>"]),
                    close=_as_float(raw["<CLOSE>"]),
                )
                if candle.high < max(candle.open, candle.close) or candle.low > min(
                    candle.open, candle.close
                ):
                    raise ValueError(
                        f"OHLC source {timeframe} invalid: {path}:{line_number}"
                    )
                bar_start = (
                    _m5_bar_start(timestamp)
                    if timeframe == "M1"
                    else timestamp
                )
                if bar_start in required_bars:
                    grouped[bar_start].append(candle)
        expected_rows = details.get("expected_rows")
        if expected_rows is not None and row_count != _as_int(expected_rows):
            raise ValueError(
                f"Row count source {timeframe} berubah: {relative}; "
                f"expected={expected_rows}; actual={row_count}"
            )
        source_audit[relative] = {
            "sha256": actual_sha,
            "rows": row_count,
            "first_timestamp": first.isoformat() if first else None,
            "last_timestamp": last.isoformat() if last else None,
        }
    for candles in grouped.values():
        candles.sort(key=lambda candle: candle.timestamp)
    return dict(grouped), source_audit


def verify_m1_m5_ohlc(
    *,
    required_bars: set[datetime],
    m1_bars: dict[datetime, list[Candle]],
    m5_bars: dict[datetime, list[Candle]],
    tolerance: float,
) -> dict[datetime, dict[str, Any]]:
    audit: dict[datetime, dict[str, Any]] = {}
    for bar_start in sorted(required_bars):
        minute_bars = m1_bars.get(bar_start) or []
        five_minute_bars = m5_bars.get(bar_start) or []
        if not minute_bars:
            audit[bar_start] = {"verified": False, "error": "M1_WINDOW_EMPTY"}
            continue
        if len(five_minute_bars) != 1:
            audit[bar_start] = {
                "verified": False,
                "error": "M5_REFERENCE_MISSING_OR_DUPLICATE",
            }
            continue
        reference = five_minute_bars[0]
        aggregate = Candle(
            timestamp=bar_start,
            open=minute_bars[0].open,
            high=max(candle.high for candle in minute_bars),
            low=min(candle.low for candle in minute_bars),
            close=minute_bars[-1].close,
        )
        differences = {
            "open": abs(aggregate.open - reference.open),
            "high": abs(aggregate.high - reference.high),
            "low": abs(aggregate.low - reference.low),
            "close": abs(aggregate.close - reference.close),
        }
        verified = all(value <= tolerance for value in differences.values())
        audit[bar_start] = {
            "verified": verified,
            "error": "" if verified else "M1_M5_OHLC_MISMATCH",
            "m1_count": len(minute_bars),
            "m1_open": aggregate.open,
            "m1_high": aggregate.high,
            "m1_low": aggregate.low,
            "m1_close": aggregate.close,
            "m5_open": reference.open,
            "m5_high": reference.high,
            "m5_low": reference.low,
            "m5_close": reference.close,
            "absolute_differences": differences,
        }
    return audit


def _marketable_at_open(candle: Candle, order_type: str, entry: float) -> bool:
    if order_type == "BUY_LIMIT":
        return candle.open <= entry
    if order_type == "SELL_LIMIT":
        return candle.open >= entry
    raise ValueError(f"Order type tidak didukung: {order_type}")


def _gap_through_stop(
    candle: Candle,
    *,
    decision: str,
    stop_loss: float,
) -> bool:
    if decision == "BUY":
        return candle.open <= stop_loss
    if decision == "SELL":
        return candle.open >= stop_loss
    raise ValueError(f"Decision tidak didukung: {decision}")


def _resolution(
    status: str,
    *,
    event: str = "",
    event_datetime: datetime | None = None,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "status": status,
        "event": event,
        "event_datetime": event_datetime,
        "notes": notes,
    }


def scan_entry_ambiguity(
    row: dict[str, Any],
    candles: Sequence[Candle],
) -> dict[str, Any]:
    decision = str(row["decision"])
    order_type = str(row["order_type"])
    entry = _as_float(row["entry"])
    stop_loss = _as_float(row["stop_loss"])
    take_profit = _as_float(row["take_profit"])
    filled = False
    target_before_fill = False
    for candle in candles:
        stop_hit, target_hit = _touches_levels(
            candle, decision, stop_loss, take_profit
        )
        if not filled:
            if not _touches_entry(candle, order_type, entry):
                target_before_fill = target_before_fill or target_hit
                continue
            filled = True
            if _gap_through_stop(candle, decision=decision, stop_loss=stop_loss):
                return _resolution(
                    "M1_UNRESOLVED_GAP_THROUGH_STOP",
                    notes="M1 opened beyond the registered stop after a nominal limit fill.",
                )
            if stop_hit and target_hit:
                return _resolution(
                    "M1_UNRESOLVED_STOP_AND_TARGET_SAME_BAR",
                    event_datetime=candle.timestamp,
                )
            if target_hit:
                if _marketable_at_open(candle, order_type, entry):
                    return _resolution(
                        "RESOLVED_TARGET_FIRST",
                        event="TAKE_PROFIT",
                        event_datetime=candle.timestamp,
                        notes="Limit was marketable at M1 open before target touch.",
                    )
                return _resolution(
                    "M1_UNRESOLVED_ENTRY_AND_TARGET_SAME_BAR",
                    event_datetime=candle.timestamp,
                )
            if stop_hit:
                return _resolution(
                    "RESOLVED_STOP_FIRST",
                    event="STOP_LOSS",
                    event_datetime=candle.timestamp,
                )
            continue
        if stop_hit and target_hit:
            return _resolution(
                "M1_UNRESOLVED_STOP_AND_TARGET_SAME_BAR",
                event_datetime=candle.timestamp,
            )
        if stop_hit:
            return _resolution(
                "RESOLVED_STOP_FIRST",
                event="STOP_LOSS",
                event_datetime=candle.timestamp,
            )
        if target_hit:
            return _resolution(
                "RESOLVED_TARGET_FIRST",
                event="TAKE_PROFIT",
                event_datetime=candle.timestamp,
            )
    if not filled:
        return _resolution(
            "M1_DATA_ERROR_FILL_NOT_REPRODUCED",
            notes="M5 baseline filled, but M1 window never touched the entry.",
        )
    if target_before_fill:
        return _resolution(
            "RESOLVED_TARGET_BEFORE_FILL",
            notes="Target occurred before the limit order filled; baseline continuation retained.",
        )
    return _resolution(
        "M1_DATA_ERROR_TARGET_NOT_REPRODUCED",
        notes="M5 target-touch ambiguity was not reproduced by matching M1 bars.",
    )


def scan_filled_stop_target_ambiguity(
    row: dict[str, Any],
    candles: Sequence[Candle],
) -> dict[str, Any]:
    decision = str(row["decision"])
    stop_loss = _as_float(row["stop_loss"])
    take_profit = _as_float(row["take_profit"])
    for candle in candles:
        stop_hit, target_hit = _touches_levels(
            candle, decision, stop_loss, take_profit
        )
        if stop_hit and target_hit:
            return _resolution(
                "M1_UNRESOLVED_STOP_AND_TARGET_SAME_BAR",
                event_datetime=candle.timestamp,
            )
        if stop_hit:
            return _resolution(
                "RESOLVED_STOP_FIRST",
                event="STOP_LOSS",
                event_datetime=candle.timestamp,
            )
        if target_hit:
            return _resolution(
                "RESOLVED_TARGET_FIRST",
                event="TAKE_PROFIT",
                event_datetime=candle.timestamp,
            )
    return _resolution(
        "M1_DATA_ERROR_LEVEL_TOUCH_NOT_REPRODUCED",
        notes="M5 stop/target ambiguity was not reproduced by matching M1 bars.",
    )


def adjudicate_ambiguous_row(
    row: dict[str, Any],
    *,
    fill_bar: datetime | None,
    exit_bar: datetime | None,
    m1_bars: dict[datetime, list[Candle]],
    ohlc_audit: dict[datetime, dict[str, Any]],
) -> dict[str, Any]:
    entry_ambiguous = bool(
        _as_int(row.get("entry_bar_target_ambiguous"), default=0)
    )
    both_ambiguous = bool(
        _as_int(row.get("same_bar_both_ambiguous"), default=0)
    )
    required = [value for value in (fill_bar, exit_bar) if value is not None]
    failed = [
        value
        for value in required
        if not bool((ohlc_audit.get(value) or {}).get("verified"))
    ]
    if failed:
        return _resolution(
            "M1_DATA_ERROR_OHLC_NOT_VERIFIED",
            notes=", ".join(value.isoformat() for value in failed),
        )

    entry_result: dict[str, Any] | None = None
    if entry_ambiguous:
        if fill_bar is None:
            return _resolution("M1_DATA_ERROR_FILL_BAR_MISSING")
        entry_result = scan_entry_ambiguity(row, m1_bars.get(fill_bar) or [])
        if entry_result["status"] not in {"RESOLVED_TARGET_BEFORE_FILL"}:
            return entry_result

    if both_ambiguous:
        if exit_bar is None:
            return _resolution("M1_DATA_ERROR_EXIT_BAR_MISSING")
        if entry_ambiguous and fill_bar == exit_bar:
            # The complete fill-bar state machine already inspected this window.
            return entry_result or _resolution(
                "M1_DATA_ERROR_COMBINED_AMBIGUITY_NOT_RESOLVED"
            )
        return scan_filled_stop_target_ambiguity(
            row,
            m1_bars.get(exit_bar) or [],
        )
    return entry_result or _resolution("M1_DATA_ERROR_NO_AMBIGUITY_FLAG")


def _apply_resolution(
    row: dict[str, Any],
    resolution: dict[str, Any] | None,
    *,
    source_path: str = "",
    source_sha256: str = "",
    ohlc_verified: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    revised: dict[str, Any] = dict(row)
    if resolution is None:
        revised.update(
            {
                "m1_adjudication_required": 0,
                "m1_resolution_status": "NOT_REQUIRED",
                "m1_primary_changed": 0,
                "m1_unresolved": 0,
                "m1_data_error": 0,
                "m1_event_datetime": "",
                "m1_m5_ohlc_verified": 0,
                "m1_source_path": "",
                "m1_source_sha256": "",
                "m1_notes": "",
            }
        )
        return revised, None

    status = str(resolution["status"])
    unresolved = status.startswith("M1_UNRESOLVED")
    data_error = status.startswith("M1_DATA_ERROR")
    revised.update(
        {
            "original_outcome_status": row.get("outcome_status", ""),
            "original_gross_r": row.get("gross_r", ""),
            "original_net_r_primary": row.get("net_r_primary", ""),
            "original_optimistic_gross_r": row.get("optimistic_gross_r", ""),
            "original_optimistic_net_r_primary": row.get(
                "optimistic_net_r_primary", ""
            ),
            "original_entry_bar_target_ambiguous": row.get(
                "entry_bar_target_ambiguous", 0
            ),
            "original_same_bar_both_ambiguous": row.get(
                "same_bar_both_ambiguous", 0
            ),
            "m1_adjudication_required": 1,
            "m1_resolution_status": status,
            "m1_primary_changed": 0,
            "m1_unresolved": int(unresolved),
            "m1_data_error": int(data_error),
            "m1_event_datetime": (
                resolution["event_datetime"].isoformat()
                if resolution.get("event_datetime")
                else ""
            ),
            "m1_m5_ohlc_verified": int(ohlc_verified),
            "m1_source_path": source_path,
            "m1_source_sha256": source_sha256,
            "m1_notes": resolution.get("notes", ""),
        }
    )

    if not unresolved and not data_error:
        revised["entry_bar_target_ambiguous"] = 0
        revised["same_bar_both_ambiguous"] = 0
        event = str(resolution.get("event") or "")
        if event in {"TAKE_PROFIT", "STOP_LOSS"}:
            decision = str(row["decision"])
            entry = _as_float(row["entry"])
            stop_loss = _as_float(row["stop_loss"])
            take_profit = _as_float(row["take_profit"])
            exit_price = take_profit if event == "TAKE_PROFIT" else stop_loss
            gross = _gross_r(decision, entry, stop_loss, exit_price)
            friction = _as_float(row.get("primary_friction_r"), default=0.0)
            revised.update(
                {
                    "outcome_status": event,
                    "exit_datetime": revised["m1_event_datetime"],
                    "exit_price": exit_price,
                    "gross_r": gross,
                    "net_r_primary": gross - friction,
                    "optimistic_gross_r": gross,
                    "optimistic_net_r_primary": gross - friction,
                }
            )
        else:
            revised["optimistic_gross_r"] = row.get("gross_r", "")
            revised["optimistic_net_r_primary"] = row.get("net_r_primary", "")
        revised["m1_primary_changed"] = int(
            str(revised.get("outcome_status")) != str(row.get("outcome_status"))
            or _finite_difference(
                revised.get("net_r_primary"), row.get("net_r_primary")
            )
        )

    evidence = {
        "snapshot_id": row.get("snapshot_id", ""),
        "evaluation_split": row.get("evaluation_split", ""),
        "year": row.get("year", ""),
        "selected_tier": row.get("selected_tier", ""),
        "decision": row.get("decision", ""),
        "original_outcome_status": row.get("outcome_status", ""),
        "original_entry_bar_target_ambiguous": row.get(
            "entry_bar_target_ambiguous", 0
        ),
        "original_same_bar_both_ambiguous": row.get(
            "same_bar_both_ambiguous", 0
        ),
        "original_net_r_primary": row.get("net_r_primary", ""),
        "original_optimistic_net_r_primary": row.get(
            "optimistic_net_r_primary", ""
        ),
        "m1_resolution_status": status,
        "m1_primary_changed": revised["m1_primary_changed"],
        "m1_unresolved": revised["m1_unresolved"],
        "m1_data_error": revised["m1_data_error"],
        "m1_fill_bar_start": "",
        "m1_exit_bar_start": "",
        "m1_event_datetime": revised["m1_event_datetime"],
        "m1_event": resolution.get("event", ""),
        "m1_m5_ohlc_verified": int(ohlc_verified),
        "revised_outcome_status": revised.get("outcome_status", ""),
        "revised_net_r_primary": revised.get("net_r_primary", ""),
        "revised_optimistic_net_r_primary": revised.get(
            "optimistic_net_r_primary", ""
        ),
        "m1_source_path": source_path,
        "m1_source_sha256": source_sha256,
        "notes": resolution.get("notes", ""),
    }
    return revised, evidence


def build_ambiguity_summary(
    baseline: Sequence[dict[str, Any]],
    revised: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    baseline_ambiguous = [row for row in baseline if _is_ambiguous(row)]
    revised_ambiguous = [row for row in revised if _is_ambiguous(row)]
    baseline_sensitive = [row for row in baseline_ambiguous if _is_outcome_sensitive(row)]
    revised_sensitive = [row for row in revised_ambiguous if _is_outcome_sensitive(row)]
    baseline_filled = sum(_as_int(row.get("filled"), default=0) for row in baseline)
    revised_filled = sum(_as_int(row.get("filled"), default=0) for row in revised)
    statuses = Counter(
        str(row.get("m1_resolution_status"))
        for row in revised
        if _as_int(row.get("m1_adjudication_required"), default=0)
    )
    changed = sum(_as_int(row.get("m1_primary_changed"), default=0) for row in revised)
    unresolved = sum(_as_int(row.get("m1_unresolved"), default=0) for row in revised)
    data_errors = sum(_as_int(row.get("m1_data_error"), default=0) for row in revised)
    return {
        "baseline_ambiguity_observations": len(baseline_ambiguous),
        "baseline_ambiguity_observation_rate_filled_pct": _pct(
            len(baseline_ambiguous), baseline_filled
        ),
        "baseline_outcome_sensitive_ambiguity_observations": len(
            baseline_sensitive
        ),
        "baseline_outcome_sensitive_rate_filled_pct": _pct(
            len(baseline_sensitive), baseline_filled
        ),
        "baseline_outcome_sensitive_share_of_ambiguity_pct": _pct(
            len(baseline_sensitive), len(baseline_ambiguous)
        ),
        "m1_resolution_status_counts": dict(sorted(statuses.items())),
        "m1_primary_changed_count": changed,
        "m1_unresolved_count": unresolved,
        "m1_data_error_count": data_errors,
        "remaining_ambiguity_observations": len(revised_ambiguous),
        "remaining_ambiguity_observation_rate_filled_pct": _pct(
            len(revised_ambiguous), revised_filled
        ),
        "remaining_outcome_sensitive_ambiguity_observations": len(
            revised_sensitive
        ),
        "remaining_outcome_sensitive_rate_filled_pct": _pct(
            len(revised_sensitive), revised_filled
        ),
    }


def _display(value: Any, suffix: str = "") -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}{suffix}"
    return f"{value}{suffix}"


def build_report(metrics: dict[str, Any]) -> str:
    baseline = metrics["baseline_breakdowns"]
    revised = metrics["revised_breakdowns"]
    ambiguity = metrics["ambiguity"]

    def result_row(label: str, field: str, suffix: str = "") -> str:
        before = baseline["overall"]["ALL"].get(field)
        after = revised["overall"]["ALL"].get(field)
        return f"| {label} | {_display(before, suffix)} | {_display(after, suffix)} |"

    acceptance = metrics["pre_holdout_acceptance"]
    gate_lines = [
        f"| `{name}` | {'PASS' if passed else 'FAIL'} |"
        for name, passed in acceptance["checks"].items()
    ]
    integrity_lines = [
        f"| `{name}` | {'PASS' if passed else 'FAIL'} |"
        for name, passed in acceptance["m1_integrity_checks"].items()
    ]
    status_lines = [
        f"| `{name}` | {count} |"
        for name, count in ambiguity["m1_resolution_status_counts"].items()
    ]
    return "\n".join(
        [
            "# AI-TDSS E2.3.1 M1 Intrabar Adjudication",
            "",
            f"Generated (UTC): `{metrics['generated_at_utc']}`",
            "",
            "## Frozen scope",
            "",
            "- Baseline candidate set: `250` frozen Standard/High Risk days.",
            "- M1 is read only for the `55` pre-existing M5 ambiguity observations.",
            "- Entry, SL, TP, horizon, friction, candidate selection, and gates are unchanged.",
            "- No model inference or training is performed.",
            "- 2024 and 2025 remain unread.",
            "",
            "## M1 resolution",
            "",
            "| Status | Count |",
            "|---|---:|",
            *status_lines,
            "",
            f"- Primary outcomes changed: `{ambiguity['m1_primary_changed_count']}`",
            f"- M1 unresolved: `{ambiguity['m1_unresolved_count']}`",
            f"- M1 data errors: `{ambiguity['m1_data_error_count']}`",
            "",
            "## Ambiguity definitions",
            "",
            "- **Ambiguity observation rate:** every filled candidate whose M5 bar could not order entry/TP or SL/TP.",
            "- **Outcome-sensitive ambiguity rate:** only ambiguity observations whose conservative and optimistic net R differ.",
            f"- Baseline observations: `{ambiguity['baseline_ambiguity_observations']}` "
            f"(`{ambiguity['baseline_ambiguity_observation_rate_filled_pct']}%` of filled).",
            f"- Baseline outcome-sensitive: `{ambiguity['baseline_outcome_sensitive_ambiguity_observations']}` "
            f"(`{ambiguity['baseline_outcome_sensitive_rate_filled_pct']}%` of filled; "
            f"`{ambiguity['baseline_outcome_sensitive_share_of_ambiguity_pct']}%` of ambiguity observations).",
            f"- Remaining observations after M1: `{ambiguity['remaining_ambiguity_observations']}`.",
            f"- Remaining outcome-sensitive after M1: `{ambiguity['remaining_outcome_sensitive_ambiguity_observations']}`.",
            "",
            "## Before / after primary result",
            "",
            "| Metric | M5 conservative baseline | M1 adjudicated |",
            "|---|---:|---:|",
            result_row("Candidate days", "candidate_count"),
            result_row("Filled", "filled_count"),
            result_row("TP", "take_profit_count"),
            result_row("SL", "stop_loss_count"),
            result_row("Resolved win rate", "resolved_win_rate_pct", "%"),
            result_row("Net expectancy / candidate", "net_expectancy_r_candidate", "R"),
            result_row("Net profit factor", "net_profit_factor"),
            result_row("Maximum event drawdown", "max_event_drawdown_r", "R"),
            result_row("Ambiguous observations", "ambiguous_count"),
            "",
            "## Pre-holdout High Risk acceptance",
            "",
            f"Overall result: **{acceptance['status']}**",
            "",
            "| Registered gate | Result |",
            "|---|---|",
            *gate_lines,
            "",
            "| M1 integrity gate | Result |",
            "|---|---|",
            *integrity_lines,
            "",
            "A PASS still does not unlock 2024 or promote High Risk. A separate reviewed freeze decision is required.",
            "",
            "## Interpretation guardrails",
            "",
            "- M1 resolves bar ordering; it does not turn predictions into ground truth automatically.",
            "- Any remaining same-M1 ambiguity retains the conservative primary result.",
            "- Event-level cumulative R is not a live portfolio backtest.",
            "- Keep 2024 frozen and 2025 untouched until the registered gates and review are complete.",
            "",
        ]
    )


def git_lineage() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {"git_commit": None, "git_dirty": None}
    return {
        "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "git_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    experiment_dir = Path(args.experiment_dir).resolve()
    raw_root = Path(args.raw_root).resolve()
    config_path = Path(args.config).resolve()
    m1_manifest_path = Path(args.m1_manifest).resolve()
    config = read_json(config_path)
    validate_config(config)
    _, baseline_rows, forward_policy = _validate_frozen_baseline(
        experiment_dir=experiment_dir,
        config=config,
    )
    ambiguous_rows = [row for row in baseline_rows if _is_ambiguous(row)]
    required_bars, per_snapshot = build_required_m5_bars(ambiguous_rows)
    m1_contract = build_m1_source_contract(
        manifest_path=m1_manifest_path,
        config=config,
    )
    m5_contract = build_m5_source_contract(config)
    print(f"Verifying {len(m1_contract)} M1 and {len(m5_contract)} M5 source files...")
    m1_bars, m1_source_audit = read_required_bars(
        raw_root=raw_root,
        source_contract=m1_contract,
        required_bars=required_bars,
        timeframe="M1",
    )
    m5_bars, m5_source_audit = read_required_bars(
        raw_root=raw_root,
        source_contract=m5_contract,
        required_bars=required_bars,
        timeframe="M5",
    )
    ohlc_audit = verify_m1_m5_ohlc(
        required_bars=required_bars,
        m1_bars=m1_bars,
        m5_bars=m5_bars,
        tolerance=_as_float(
            config["adjudication_model"]["ohlc_absolute_tolerance"]
        ),
    )

    m1_by_year = {
        details["year"]: (relative, details["sha256"])
        for relative, details in m1_contract.items()
    }
    revised_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    progress_every = max(0, _as_int(getattr(args, "progress_every", 10), default=10))
    processed = 0
    for row in baseline_rows:
        snapshot_id = str(row["snapshot_id"])
        if not _is_ambiguous(row):
            revised, _ = _apply_resolution(row, None)
            revised_rows.append(revised)
            continue
        fill_bar, exit_bar = per_snapshot[snapshot_id]
        resolution = adjudicate_ambiguous_row(
            row,
            fill_bar=fill_bar,
            exit_bar=exit_bar,
            m1_bars=m1_bars,
            ohlc_audit=ohlc_audit,
        )
        year = _as_int(row["year"])
        source_path, source_sha = m1_by_year[year]
        verified = all(
            bool((ohlc_audit.get(value) or {}).get("verified"))
            for value in (fill_bar, exit_bar)
            if value is not None
        )
        revised, evidence = _apply_resolution(
            row,
            resolution,
            source_path=source_path,
            source_sha256=source_sha,
            ohlc_verified=verified,
        )
        if evidence is None:
            raise AssertionError("Ambiguous row must produce evidence.")
        evidence["m1_fill_bar_start"] = fill_bar.isoformat() if fill_bar else ""
        evidence["m1_exit_bar_start"] = exit_bar.isoformat() if exit_bar else ""
        revised_rows.append(revised)
        evidence_rows.append(evidence)
        processed += 1
        if progress_every and (
            processed % progress_every == 0 or processed == len(ambiguous_rows)
        ):
            print(
                f"[{processed}/{len(ambiguous_rows)}] {snapshot_id} -> "
                f"{resolution['status']}"
            )

    if len(revised_rows) != len(baseline_rows):
        raise AssertionError("Adjudication changed candidate cardinality.")
    for baseline, revised in zip(baseline_rows, revised_rows):
        if baseline["snapshot_id"] != revised["snapshot_id"]:
            raise AssertionError("Candidate ordering changed.")
        if not _is_ambiguous(baseline):
            for field in OUTCOME_FIELDS:
                if str(baseline.get(field, "")) != str(revised.get(field, "")):
                    raise AssertionError(
                        f"Non-ambiguous baseline mutated: {baseline['snapshot_id']} {field}"
                    )

    baseline_breakdowns, _ = build_breakdowns(
        baseline_rows,
        config=forward_policy,
    )
    revised_breakdowns, breakdown_rows = build_breakdowns(
        revised_rows,
        config=forward_policy,
    )
    ambiguity = build_ambiguity_summary(baseline_rows, revised_rows)
    acceptance = evaluate_acceptance_gates(revised_rows, config=forward_policy)
    integrity_checks = {
        "frozen_candidate_set_unchanged": len(revised_rows)
        == _as_int(config["lineage"]["baseline_candidate_days"]),
        "all_55_ambiguity_observations_processed": len(evidence_rows)
        == _as_int(config["lineage"]["baseline_ambiguity_observations"]),
        "all_required_m1_m5_windows_verified": all(
            bool(details.get("verified")) for details in ohlc_audit.values()
        )
        and len(ohlc_audit) == len(required_bars),
        "no_m1_data_error": ambiguity["m1_data_error_count"] == 0,
        "holdout_2024_not_accessed": True,
        "final_2025_not_accessed": True,
    }
    registered_gate_status = acceptance["status"]
    acceptance["registered_gate_status"] = registered_gate_status
    acceptance["m1_integrity_checks"] = integrity_checks
    acceptance["status"] = (
        "PASS"
        if registered_gate_status == "PASS" and all(integrity_checks.values())
        else "FAIL"
    )
    acceptance["holdout_2024_unlocked"] = False
    acceptance["production_promotion_allowed"] = False

    generated_at = datetime.now(timezone.utc).isoformat()
    metrics = {
        "schema_version": 1,
        "experiment_id": "E2.3.1",
        "stage": "M1_INTRABAR_ADJUDICATION",
        "adjudicator_version": ADJUDICATOR_VERSION,
        "generated_at_utc": generated_at,
        "policy_version": config["policy_version"],
        "policy_sha256": object_sha256(config),
        "baseline_outcomes_sha256": file_sha256(
            experiment_dir / "outcomes" / "daily_trade_outcomes.csv"
        ),
        "m1_source_manifest_sha256": file_sha256(m1_manifest_path),
        "selected_candidate_days": len(revised_rows),
        "required_m5_windows": len(required_bars),
        "verified_m1_m5_windows": sum(
            bool(details.get("verified")) for details in ohlc_audit.values()
        ),
        "model_training_performed": False,
        "model_inference_performed": False,
        "candidate_reselection_performed": False,
        "holdout_2024_accessed": False,
        "final_2025_accessed": False,
        "baseline_breakdowns": baseline_breakdowns,
        "revised_breakdowns": revised_breakdowns,
        "ambiguity": ambiguity,
        "pre_holdout_acceptance": acceptance,
    }

    policy_output = experiment_dir / "config" / "e2_3_1_m1_adjudication_policy.json"
    source_output = experiment_dir / "config" / "e2_3_1_m1_source_contract.json"
    outcome_output = (
        experiment_dir / "outcomes" / "daily_trade_outcomes_m1_adjudicated.csv"
    )
    evidence_output = (
        experiment_dir / "outcomes" / "m1_ambiguity_adjudications.csv"
    )
    metrics_output = (
        experiment_dir / "metrics" / "e2_3_1_m1_adjudication_metrics.json"
    )
    breakdown_output = (
        experiment_dir / "metrics" / "e2_3_1_outcome_breakdown.csv"
    )
    report_output = (
        experiment_dir / "reports" / "e2_3_1_m1_adjudication_report.md"
    )
    manifest_output = experiment_dir / "e2_3_1_manifest.json"

    write_json_atomic(policy_output, config)
    write_json_atomic(
        source_output,
        {
            "schema_version": 1,
            "manifest_path_name": m1_manifest_path.name,
            "manifest_sha256": file_sha256(m1_manifest_path),
            "m1_sources": m1_source_audit,
            "m5_reference_sources": m5_source_audit,
            "required_window_audit": {
                value.isoformat(): details
                for value, details in sorted(ohlc_audit.items())
            },
        },
    )
    write_csv_atomic(
        outcome_output,
        revised_rows,
        OUTCOME_FIELDS + ADDITIONAL_OUTCOME_FIELDS,
    )
    write_csv_atomic(evidence_output, evidence_rows, ADJUDICATION_FIELDS)
    write_json_atomic(metrics_output, metrics)
    write_csv_atomic(breakdown_output, breakdown_rows, BREAKDOWN_FIELDS)
    _write_text_atomic(report_output, build_report(metrics))

    artifacts: dict[str, Any] = {}
    for path in (
        policy_output,
        source_output,
        outcome_output,
        evidence_output,
        metrics_output,
        breakdown_output,
        report_output,
    ):
        relative = str(path.relative_to(experiment_dir)).replace("\\", "/")
        artifacts[relative] = {
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
    manifest = {
        "schema_version": 1,
        "experiment_id": "E2.3.1",
        "stage": "M1_INTRABAR_ADJUDICATION",
        "adjudicator_version": ADJUDICATOR_VERSION,
        "generated_at_utc": generated_at,
        "training_performed": False,
        "model_inference_performed": False,
        "candidate_reselection_performed": False,
        "holdout_2024_accessed": False,
        "final_2025_accessed": False,
        "production_promotion_allowed": False,
        "baseline_outcomes_sha256": metrics["baseline_outcomes_sha256"],
        "m1_source_manifest_sha256": metrics["m1_source_manifest_sha256"],
        "m1_source_sha256s": {
            relative: details["sha256"] for relative, details in m1_contract.items()
        },
        "m5_reference_sha256s": {
            relative: details["sha256"] for relative, details in m5_contract.items()
        },
        "artifacts": artifacts,
        "adjudicator_git": git_lineage(),
    }
    write_json_atomic(manifest_output, manifest)

    print(f"Adjudicated outcomes: {outcome_output}")
    print(f"Evidence: {evidence_output}")
    print(f"Metrics: {metrics_output}")
    print(f"Report: {report_output}")
    print(f"Pre-holdout High Risk gate: {acceptance['status']}")
    return {
        "outcomes": revised_rows,
        "evidence": evidence_rows,
        "metrics": metrics,
        "manifest": manifest,
    }


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
