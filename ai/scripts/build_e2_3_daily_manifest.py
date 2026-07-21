from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_3_daily_manifest.json"
)
DEFAULT_MAPPING_DECISION = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_2_plot_mapping_decision.json"
)
DEFAULT_RAW_ROOT = (
    PROJECT_ROOT
    / "ai"
    / "datasets"
    / "raw"
    / "ohlcv"
)

MANIFEST_FIELDS = [
    "schema_version",
    "experiment_id",
    "event_id",
    "daily_group_id",
    "snapshot_id",
    "evaluation_split",
    "pair",
    "year",
    "trading_date_utc",
    "slot",
    "target_session",
    "analysis_target_utc_datetime",
    "analysis_target_market_datetime",
    "market_utc_offset_hours",
    "source_timestamp_semantics",
    "timezone_assumption",
    "closed_candle_rule",
    "timeframe",
    "timeframe_minutes",
    "chart_candles",
    "context_candles",
    "chart_start_datetime",
    "chart_end_open_datetime",
    "chart_end_close_datetime",
    "ohlcv_cutoff_datetime",
    "staleness_minutes",
    "available_history_candles",
    "resolved_bar_session",
    "session_alignment_status",
    "anti_lookahead_verified",
    "plot_aware_mapping",
    "mapping_fallback",
    "planned_image_path",
    "source_paths",
    "source_sha256s",
    "missing_source_years",
    "status",
    "duplicate_of_snapshot_id",
    "event_ready",
    "max_candidates_per_tier_per_day",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the deterministic E2.3 GBPUSD daily snapshot manifest. "
            "This stage performs no model inference or training."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Frozen E2.3 daily-manifest contract.",
    )
    parser.add_argument(
        "--mapping-decision",
        type=Path,
        default=DEFAULT_MAPPING_DECISION,
        help="Final E2.2 mapping decision contract.",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=DEFAULT_RAW_ROOT,
        help="Local root containing pair/timeframe/year OHLCV files.",
    )
    parser.add_argument(
        "--year",
        dest="years",
        action="append",
        type=int,
        help="Year to include. Repeat as needed; default is all permitted years.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Local output directory under local_artifacts/.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Contract tidak ditemukan: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON contract tidak valid: {path}: {error}") from error

    if not isinstance(payload, dict):
        raise ValueError(f"Contract harus berupa JSON object: {path}")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def classify_session(utc_hour: int) -> str:
    if 0 <= utc_hour < 7:
        return "ASIA"
    if 7 <= utc_hour < 13:
        return "LONDON"
    if 13 <= utc_hour < 16:
        return "LONDON_NEW_YORK_OVERLAP"
    if 16 <= utc_hour < 22:
        return "NEW_YORK"
    return "OFF_PEAK"


def year_split(config: dict[str, Any], year: int) -> str:
    for split, years in config.get("period_splits", {}).items():
        if year in years:
            return str(split)
    raise ValueError(f"Year {year} tidak memiliki evaluation split.")


def validate_contracts(
    config: dict[str, Any],
    mapping_decision: dict[str, Any],
    years: list[int],
) -> list[str]:
    errors: list[str] = []

    if config.get("schema_version") != 1:
        errors.append("E2.3 schema_version harus 1.")
    if config.get("experiment_id") != "E2.3":
        errors.append("experiment_id harus E2.3.")
    if config.get("stage") != "DAILY_MANIFEST":
        errors.append("stage harus DAILY_MANIFEST.")
    if config.get("decision_status") != "PREREGISTERED_FOR_DEVELOPMENT":
        errors.append("decision_status E2.3 harus PREREGISTERED_FOR_DEVELOPMENT.")
    if config.get("pair") != "GBPUSD":
        errors.append("Pair E2.3 harus GBPUSD.")
    if config.get("training_performed") is not False:
        errors.append("Manifest E2.3 tidak boleh melakukan training.")
    if config.get("chart_candles") != 100:
        errors.append("Chart window E2.3 harus 100 candle.")
    if config.get("context_candles") != 300:
        errors.append("Context window E2.3 harus 300 candle.")

    mapping = config.get("mapping_policy", {})
    selected = mapping_decision.get("selected_policy", {})
    if mapping_decision.get("decision_status") != "PROMOTED_FOR_CANONICAL_PIPELINE":
        errors.append("Keputusan mapping E2.2 belum dipromosikan untuk chart kanonis.")
    if mapping.get("canonical_mode") != "PLOT_AWARE":
        errors.append("Canonical mapping E2.3 harus PLOT_AWARE.")
    if mapping.get("decision_contract") != (
        "config/experiments/e2_2_plot_mapping_decision.json"
    ):
        errors.append("Dependency contract E2.2 berubah.")
    if mapping.get("plot_aware_mapping") is not True:
        errors.append("plot_aware_mapping E2.3 harus true.")
    if mapping.get("uncertain_geometry_fallback") != "FULL_IMAGE":
        errors.append("Fallback geometry E2.3 harus FULL_IMAGE.")
    if selected.get("e2_3_canonical_experiment_mapping") != "PLOT_AWARE":
        errors.append("E2.2 decision tidak memilih PLOT_AWARE untuk E2.3.")
    if selected.get("uncertain_geometry_fallback") != "FULL_IMAGE":
        errors.append("E2.2 decision tidak mengunci FULL_IMAGE fallback.")

    time_policy = config.get("time_policy", {})
    if time_policy.get("source_timestamp_semantics") != "MT5_BAR_OPEN_TIME":
        errors.append("Timestamp OHLCV harus diperlakukan sebagai MT5 bar-open time.")
    if time_policy.get("closed_candle_rule") != (
        "BAR_OPEN_PLUS_TIMEFRAME_DURATION_LTE_TARGET"
    ):
        errors.append("Closed-candle anti-lookahead rule tidak terkunci.")
    if time_policy.get("session_evaluation_timestamp") != "ANALYSIS_TARGET_UTC":
        errors.append("Session E2.3 harus dinilai dari analysis target UTC.")
    if time_policy.get("market_utc_offset_hours") != 0.0:
        errors.append("Offset sumber E2.3 v1 harus 0.0 jam.")
    if time_policy.get("timezone_assumption_provisional") is not True:
        errors.append("Asumsi timezone sumber E2.3 v1 harus ditandai provisional.")
    if time_policy.get("endpoint_session_override_required") is not True:
        errors.append("Runner E2.3 harus mewajibkan session-target override.")

    timeframes = config.get("timeframes", [])
    if sorted(timeframes) != ["H1", "H4", "M15", "M5"]:
        errors.append("Timeframe E2.3 harus M5, M15, H1, dan H4.")
    if config.get("reference_timeframe") != "M5":
        errors.append("Reference timeframe kalender harus M5.")
    expected_minutes = {"M5": 5, "M15": 15, "H1": 60, "H4": 240}
    if config.get("timeframe_minutes") != expected_minutes:
        errors.append("Durasi timeframe E2.3 berubah.")
    if config.get("maximum_staleness_minutes") != expected_minutes:
        errors.append("Batas staleness E2.3 harus satu durasi timeframe.")
    expected_splits = {
        "POLICY_DEVELOPMENT": [2020, 2021, 2022],
        "POLICY_SELECTION": [2023],
        "FROZEN_HOLDOUT": [2024],
        "FINAL_TEMPORAL_TEST": [2025],
    }
    if config.get("period_splits") != expected_splits:
        errors.append("Temporal split E2.3 berubah.")
    if config.get("permitted_manifest_years") != [2020, 2021, 2022, 2023, 2024]:
        errors.append("Permitted manifest years harus tepat 2020-2024.")
    if config.get("final_temporal_test_locked") is not True:
        errors.append("Final temporal test 2025 harus tetap terkunci.")
    if (
        config.get("deduplication", {}).get("max_candidates_per_tier_per_day")
        != 1
    ):
        errors.append("Candidate cap E2.3 harus satu per tier per hari.")
    if config.get("trading_calendar") != {
        "source": "OBSERVED_REFERENCE_TIMEFRAME_DATES",
        "weekdays": [0, 1, 2, 3, 4],
        "holiday_calendar_claimed": False,
    }:
        errors.append("Trading-calendar contract E2.3 berubah.")
    if config.get("source_path_template") != (
        "ai/datasets/raw/ohlcv/{pair}/{timeframe}/{year}/"
        "{pair}_{timeframe}_{year}_RAW.csv"
    ):
        errors.append("Source-path contract E2.3 berubah.")
    if config.get("output_contract") != {
        "snapshot_manifest": "daily_snapshot_manifest.csv",
        "summary": "daily_manifest_summary.json",
        "run_config": "run_config.json",
        "planned_image_root": "images",
    }:
        errors.append("Output contract E2.3 berubah.")

    guardrails = config.get("guardrails", {})
    expected_guardrails = {
        "manifest_generation_is_inference": False,
        "manifest_generation_is_training": False,
        "daily_analysis_implies_daily_trade": False,
        "final_2025_policy_tuning_allowed": False,
        "standard_and_high_risk_share_same_event": True,
        "standard_and_high_risk_share_same_mapping": True,
        "raw_prediction_is_ground_truth": False,
    }
    for field, expected in expected_guardrails.items():
        if guardrails.get(field) is not expected:
            errors.append(f"Guardrail {field} harus {expected}.")

    slots = time_policy.get("slots", [])
    expected_slots = [
        {
            "name": "LONDON",
            "utc_time": "09:00:00",
            "expected_session": "LONDON",
        },
        {
            "name": "LONDON_NEW_YORK_OVERLAP",
            "utc_time": "14:00:00",
            "expected_session": "LONDON_NEW_YORK_OVERLAP",
        },
    ]
    if slots != expected_slots:
        errors.append("Slot E2.3 harus tepat 09:00 dan 14:00 UTC.")
    slot_names = [slot.get("name") for slot in slots if isinstance(slot, dict)]
    if slot_names != ["LONDON", "LONDON_NEW_YORK_OVERLAP"]:
        errors.append("Slot harus LONDON lalu LONDON_NEW_YORK_OVERLAP.")
    for slot in slots:
        if not isinstance(slot, dict):
            continue
        try:
            hour = time.fromisoformat(str(slot["utc_time"])).hour
        except (KeyError, TypeError, ValueError):
            errors.append("utc_time slot tidak valid.")
            continue
        if classify_session(hour) != slot.get("expected_session"):
            errors.append(f"Session slot {slot.get('name')} tidak sesuai utc_time.")

    permitted = set(config.get("permitted_manifest_years", []))
    final_years = set(config.get("period_splits", {}).get("FINAL_TEMPORAL_TEST", []))
    if not years:
        errors.append("Minimal satu year harus dipilih.")
    for year in years:
        if year not in permitted:
            errors.append(f"Year {year} belum diizinkan untuk manifest E2.3.")
        if config.get("final_temporal_test_locked") and year in final_years:
            errors.append(f"Final temporal test {year} masih terkunci.")

    return errors


def _normalize_header(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.replace("\ufeff", "").upper())


def read_mt5_datetimes(path: Path) -> list[datetime]:
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        lines = [line.rstrip("\r\n") for line in handle if line.strip()]

    if not lines:
        raise ValueError(f"File OHLCV kosong: {path}")

    header = lines[0]
    delimiter = next((item for item in ("\t", ",", ";") if item in header), None)

    def split_line(line: str) -> list[str]:
        if delimiter is None:
            return re.split(r"\s+", line.strip())
        return next(csv.reader([line], delimiter=delimiter))

    columns = [_normalize_header(value) for value in split_line(header)]
    required_columns = ("DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE")
    try:
        indexes = {column: columns.index(column) for column in required_columns}
    except ValueError as error:
        raise ValueError(f"Kolom OHLCV minimum tidak ditemukan: {path}") from error

    date_index = indexes["DATE"]
    time_index = indexes["TIME"]
    maximum_required_index = max(indexes.values())

    values: list[datetime] = []
    invalid = 0
    for line in lines[1:]:
        parts = split_line(line)
        if maximum_required_index >= len(parts):
            invalid += 1
            continue
        raw_value = f"{parts[date_index].strip()} {parts[time_index].strip()}"
        parsed: datetime | None = None
        for pattern in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(raw_value, pattern)
                break
            except ValueError:
                continue
        if parsed is None:
            invalid += 1
            continue
        try:
            open_price = float(parts[indexes["OPEN"]])
            high_price = float(parts[indexes["HIGH"]])
            low_price = float(parts[indexes["LOW"]])
            close_price = float(parts[indexes["CLOSE"]])
        except (TypeError, ValueError):
            invalid += 1
            continue
        if (
            min(open_price, high_price, low_price, close_price) <= 0
            or high_price < low_price
        ):
            invalid += 1
            continue
        values.append(parsed)

    if not values:
        raise ValueError(f"Tidak ada timestamp OHLCV valid: {path}")
    if invalid:
        raise ValueError(
            f"{invalid} timestamp OHLCV tidak valid ditemukan: {path}"
        )
    if len(values) != len(set(values)):
        raise ValueError(f"Timestamp OHLCV duplikat ditemukan: {path}")

    return sorted(values)


def source_path(raw_root: Path, pair: str, timeframe: str, year: int) -> Path:
    return (
        raw_root
        / pair
        / timeframe
        / str(year)
        / f"{pair}_{timeframe}_{year}_RAW.csv"
    )


def load_source_indexes(
    raw_root: Path,
    pair: str,
    timeframes: list[str],
    years: list[int],
) -> tuple[dict[str, list[datetime]], dict[tuple[str, int], dict[str, str]]]:
    indexes: dict[str, list[datetime]] = {}
    lineage: dict[tuple[str, int], dict[str, str]] = {}
    years_to_load = range(min(years) - 1, max(years) + 1)

    for timeframe in timeframes:
        timestamps: list[datetime] = []
        for year in years_to_load:
            path = source_path(raw_root, pair, timeframe, year)
            if not path.exists():
                continue
            timestamps.extend(read_mt5_datetimes(path))
            lineage[(timeframe, year)] = {
                "path": path.relative_to(raw_root).as_posix(),
                "sha256": file_sha256(path),
            }
        if len(timestamps) != len(set(timestamps)):
            raise ValueError(
                f"Timestamp OHLCV lintas file duplikat untuk {pair}/{timeframe}."
            )
        indexes[timeframe] = sorted(timestamps)

    return indexes, lineage


def select_closed_window(
    timestamps: list[datetime],
    *,
    target_market_datetime: datetime,
    timeframe_minutes: int,
    chart_candles: int,
    context_candles: int,
    maximum_staleness_minutes: int,
) -> dict[str, Any]:
    duration = timedelta(minutes=timeframe_minutes)
    cutoff_open = target_market_datetime - duration
    end_index = bisect.bisect_right(timestamps, cutoff_open) - 1

    if end_index < 0:
        return {"status": "NO_CLOSED_CANDLE", "available_history_candles": 0}

    end_open = timestamps[end_index]
    end_close = end_open + duration
    staleness = (target_market_datetime - end_close).total_seconds() / 60.0
    available = end_index + 1

    result: dict[str, Any] = {
        "chart_end_open_datetime": end_open,
        "chart_end_close_datetime": end_close,
        "ohlcv_cutoff_datetime": end_open,
        "staleness_minutes": staleness,
        "available_history_candles": available,
        "anti_lookahead_verified": end_close <= target_market_datetime,
    }

    if staleness > maximum_staleness_minutes:
        result["status"] = "STALE_SOURCE"
        return result
    if available < context_candles:
        result["status"] = "INSUFFICIENT_CONTEXT"
        return result

    chart_start_index = end_index - chart_candles + 1
    result["chart_start_datetime"] = timestamps[chart_start_index]
    result["context_start_datetime"] = timestamps[end_index - context_candles + 1]
    result["status"] = "READY"
    return result


def _iso(value: datetime | None, *, utc: bool = False) -> str:
    if value is None:
        return ""
    suffix = "Z" if utc else ""
    return value.isoformat(timespec="seconds") + suffix


def _source_lineage_for_window(
    lineage: dict[tuple[str, int], dict[str, str]],
    timeframe: str,
    start_datetime: datetime | None,
    end_datetime: datetime | None,
) -> tuple[str, str, str]:
    if start_datetime is None or end_datetime is None:
        return "", "", ""
    required_years = list(range(start_datetime.year, end_datetime.year + 1))
    entries = [
        lineage[(timeframe, year)]
        for year in required_years
        if (timeframe, year) in lineage
    ]
    missing_years = [
        year for year in required_years if (timeframe, year) not in lineage
    ]
    return (
        "|".join(entry["path"] for entry in entries),
        "|".join(entry["sha256"] for entry in entries),
        "|".join(str(year) for year in missing_years),
    )


def build_manifest_rows(
    config: dict[str, Any],
    *,
    raw_root: Path,
    years: list[int],
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], dict[str, str]]]:
    pair = str(config["pair"])
    timeframes = [str(value) for value in config["timeframes"]]
    reference_timeframe = str(config["reference_timeframe"])
    indexes, lineage = load_source_indexes(raw_root, pair, timeframes, years)

    reference = indexes.get(reference_timeframe, [])
    if not reference:
        raise FileNotFoundError(
            f"Reference OHLCV {pair}/{reference_timeframe} tidak ditemukan."
        )

    weekdays = set(config["trading_calendar"]["weekdays"])
    trading_dates = sorted(
        {
            timestamp.date()
            for timestamp in reference
            if timestamp.year in years and timestamp.weekday() in weekdays
        }
    )
    if not trading_dates:
        raise ValueError("Tidak ada observed trading date untuk year terpilih.")

    time_policy = config["time_policy"]
    market_offset = float(time_policy["market_utc_offset_hours"])
    rows: list[dict[str, Any]] = []

    for trading_date in trading_dates:
        split = year_split(config, trading_date.year)
        daily_group_id = f"{pair}_{trading_date.strftime('%Y%m%d')}"
        for slot in time_policy["slots"]:
            slot_name = str(slot["name"])
            target_time = time.fromisoformat(str(slot["utc_time"]))
            target_utc = datetime.combine(trading_date, target_time)
            target_market = target_utc + timedelta(hours=market_offset)
            event_id = f"{daily_group_id}_{slot_name}"

            for timeframe in timeframes:
                timeframe_minutes = int(config["timeframe_minutes"][timeframe])
                result = select_closed_window(
                    indexes.get(timeframe, []),
                    target_market_datetime=target_market,
                    timeframe_minutes=timeframe_minutes,
                    chart_candles=int(config["chart_candles"]),
                    context_candles=int(config["context_candles"]),
                    maximum_staleness_minutes=int(
                        config["maximum_staleness_minutes"][timeframe]
                    ),
                )

                end_open = result.get("chart_end_open_datetime")
                end_close = result.get("chart_end_close_datetime")
                chart_start = result.get("chart_start_datetime")
                context_start = result.get("context_start_datetime")
                source_paths, source_hashes, missing_source_years = (
                    _source_lineage_for_window(
                        lineage,
                        timeframe,
                        context_start,
                        end_open,
                    )
                )

                source_year_available = (timeframe, trading_date.year) in lineage
                status = str(result["status"])
                if not source_year_available or missing_source_years:
                    status = "MISSING_SOURCE_YEAR"

                end_utc = (
                    end_open - timedelta(hours=market_offset)
                    if isinstance(end_open, datetime)
                    else None
                )
                resolved_session = (
                    classify_session(end_utc.hour)
                    if isinstance(end_utc, datetime)
                    else ""
                )
                target_session = str(slot["expected_session"])
                alignment = (
                    "ALIGNED"
                    if resolved_session == target_session
                    else "TARGET_OVERRIDE_REQUIRED"
                    if resolved_session
                    else "UNAVAILABLE"
                )

                image_name = (
                    f"{pair.lower()}_{timeframe.lower()}_"
                    f"{trading_date.year}_{target_utc.strftime('%Y%m%d_%H%M%S')}_"
                    f"e2_3_{slot_name.lower()}.png"
                )
                snapshot_id = f"{event_id}_{timeframe}"
                rows.append(
                    {
                        "schema_version": 1,
                        "experiment_id": "E2.3",
                        "event_id": event_id,
                        "daily_group_id": daily_group_id,
                        "snapshot_id": snapshot_id,
                        "evaluation_split": split,
                        "pair": pair,
                        "year": trading_date.year,
                        "trading_date_utc": trading_date.isoformat(),
                        "slot": slot_name,
                        "target_session": target_session,
                        "analysis_target_utc_datetime": _iso(target_utc, utc=True),
                        "analysis_target_market_datetime": _iso(target_market),
                        "market_utc_offset_hours": market_offset,
                        "source_timestamp_semantics": time_policy[
                            "source_timestamp_semantics"
                        ],
                        "timezone_assumption": time_policy[
                            "timezone_assumption"
                        ],
                        "closed_candle_rule": time_policy[
                            "closed_candle_rule"
                        ],
                        "timeframe": timeframe,
                        "timeframe_minutes": timeframe_minutes,
                        "chart_candles": int(config["chart_candles"]),
                        "context_candles": int(config["context_candles"]),
                        "chart_start_datetime": _iso(chart_start),
                        "chart_end_open_datetime": _iso(end_open),
                        "chart_end_close_datetime": _iso(end_close),
                        "ohlcv_cutoff_datetime": _iso(end_open),
                        "staleness_minutes": (
                            round(float(result["staleness_minutes"]), 6)
                            if "staleness_minutes" in result
                            else ""
                        ),
                        "available_history_candles": int(
                            result.get("available_history_candles", 0)
                        ),
                        "resolved_bar_session": resolved_session,
                        "session_alignment_status": alignment,
                        "anti_lookahead_verified": int(
                            bool(result.get("anti_lookahead_verified", False))
                        ),
                        "plot_aware_mapping": 1,
                        "mapping_fallback": "FULL_IMAGE",
                        "planned_image_path": (
                            Path(config["output_contract"]["planned_image_root"])
                            / pair
                            / timeframe
                            / str(trading_date.year)
                            / image_name
                        ).as_posix(),
                        "source_paths": source_paths,
                        "source_sha256s": source_hashes,
                        "missing_source_years": missing_source_years,
                        "status": status,
                        "duplicate_of_snapshot_id": "",
                        "event_ready": 0,
                        "max_candidates_per_tier_per_day": int(
                            config["deduplication"][
                                "max_candidates_per_tier_per_day"
                            ]
                        ),
                    }
                )

    mark_duplicate_windows(rows)
    mark_event_readiness(rows, expected_timeframes=set(timeframes))
    return rows, lineage


def mark_duplicate_windows(rows: list[dict[str, Any]]) -> None:
    seen: dict[tuple[str, str, str, str], str] = {}
    for row in rows:
        if row.get("status") != "READY":
            continue
        key = (
            str(row.get("pair", "")),
            str(row.get("timeframe", "")),
            str(row.get("chart_start_datetime", "")),
            str(row.get("chart_end_open_datetime", "")),
        )
        previous = seen.get(key)
        if previous is None:
            seen[key] = str(row["snapshot_id"])
            continue
        row["status"] = "DUPLICATE_WINDOW"
        row["duplicate_of_snapshot_id"] = previous


def mark_event_readiness(
    rows: list[dict[str, Any]],
    *,
    expected_timeframes: set[str],
) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["event_id"])].append(row)

    for event_rows in grouped.values():
        present = {str(row["timeframe"]) for row in event_rows}
        ready = (
            present == expected_timeframes
            and all(row.get("status") == "READY" for row in event_rows)
            and all(
                int(row.get("anti_lookahead_verified", 0)) == 1
                for row in event_rows
            )
        )
        for row in event_rows:
            row["event_ready"] = int(ready)


def validate_manifest_rows(
    rows: list[dict[str, Any]],
    *,
    expected_timeframes: set[str],
) -> list[str]:
    errors: list[str] = []
    snapshot_ids = [str(row.get("snapshot_id", "")) for row in rows]
    if len(snapshot_ids) != len(set(snapshot_ids)):
        errors.append("snapshot_id tidak unik.")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ready_windows: set[tuple[str, str, str, str]] = set()
    allowed_statuses = {
        "READY",
        "NO_CLOSED_CANDLE",
        "STALE_SOURCE",
        "INSUFFICIENT_CONTEXT",
        "MISSING_SOURCE_YEAR",
        "DUPLICATE_WINDOW",
    }
    for row in rows:
        grouped[str(row.get("event_id", ""))].append(row)
        if row.get("status") not in allowed_statuses:
            errors.append(f"{row.get('snapshot_id')}: status tidak dikenal.")
        if int(row.get("plot_aware_mapping", 0)) != 1:
            errors.append(f"{row.get('snapshot_id')}: mapping bukan plot-aware.")
        if row.get("mapping_fallback") != "FULL_IMAGE":
            errors.append(f"{row.get('snapshot_id')}: fallback bukan full-image.")
        if row.get("status") == "READY":
            if int(row.get("anti_lookahead_verified", 0)) != 1:
                errors.append(f"{row.get('snapshot_id')}: anti-lookahead gagal.")
            if not row.get("source_paths") or not row.get("source_sha256s"):
                errors.append(f"{row.get('snapshot_id')}: lineage sumber kosong.")
            if row.get("missing_source_years"):
                errors.append(f"{row.get('snapshot_id')}: source year tidak lengkap.")
            try:
                target = datetime.fromisoformat(
                    str(row["analysis_target_market_datetime"])
                )
                end_close = datetime.fromisoformat(
                    str(row["chart_end_close_datetime"])
                )
            except (KeyError, TypeError, ValueError):
                errors.append(
                    f"{row.get('snapshot_id')}: timestamp manifest tidak valid."
                )
            else:
                if end_close > target:
                    errors.append(
                        f"{row.get('snapshot_id')}: candle belum close pada target."
                    )
            key = (
                str(row.get("pair", "")),
                str(row.get("timeframe", "")),
                str(row.get("chart_start_datetime", "")),
                str(row.get("chart_end_open_datetime", "")),
            )
            if key in ready_windows:
                errors.append(f"{row.get('snapshot_id')}: duplicate READY window.")
            ready_windows.add(key)

    for event_id, event_rows in grouped.items():
        present = {str(row.get("timeframe", "")) for row in event_rows}
        if present != expected_timeframes:
            errors.append(f"{event_id}: set timeframe tidak lengkap.")
        if len(event_rows) != len(expected_timeframes):
            errors.append(f"{event_id}: jumlah row timeframe tidak tepat.")
        readiness = {int(row.get("event_ready", 0)) for row in event_rows}
        if len(readiness) != 1:
            errors.append(f"{event_id}: event_ready tidak konsisten.")
        expected_ready = int(
            len(event_rows) == len(expected_timeframes)
            and present == expected_timeframes
            and all(row.get("status") == "READY" for row in event_rows)
            and all(
                int(row.get("anti_lookahead_verified", 0)) == 1
                for row in event_rows
            )
        )
        if readiness != {expected_ready}:
            errors.append(f"{event_id}: event_ready tidak sesuai status row.")

    return errors


def manifest_digest(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        events[str(row["event_id"])].append(row)

    ready_events = sum(
        1 for event_rows in events.values() if int(event_rows[0]["event_ready"]) == 1
    )
    event_splits = Counter(
        str(event_rows[0]["evaluation_split"])
        for event_rows in events.values()
    )
    override_events = {
        str(row["event_id"])
        for row in rows
        if row["session_alignment_status"] == "TARGET_OVERRIDE_REQUIRED"
    }

    return {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "training_performed": False,
        "snapshot_rows": len(rows),
        "events": len(events),
        "ready_events": ready_events,
        "ready_event_rate": round(ready_events / max(1, len(events)), 6),
        "trading_days": len({str(row["daily_group_id"]) for row in rows}),
        "status_counts": dict(
            sorted(Counter(str(row["status"]) for row in rows).items())
        ),
        "snapshot_split_counts": dict(
            sorted(Counter(str(row["evaluation_split"]) for row in rows).items())
        ),
        "event_split_counts": dict(sorted(event_splits.items())),
        "slot_counts": dict(sorted(Counter(str(row["slot"]) for row in rows).items())),
        "timeframe_counts": dict(
            sorted(Counter(str(row["timeframe"]) for row in rows).items())
        ),
        "session_override_required_rows": sum(
            1
            for row in rows
            if row["session_alignment_status"] == "TARGET_OVERRIDE_REQUIRED"
        ),
        "session_override_required_events": len(override_events),
        "anti_lookahead_failures": sum(
            1
            for row in rows
            if row["status"] == "READY" and int(row["anti_lookahead_verified"]) != 1
        ),
        "duplicate_window_rows": sum(
            1 for row in rows if row["status"] == "DUPLICATE_WINDOW"
        ),
    }


def write_outputs(
    output_dir: Path,
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    run_config: dict[str, Any],
    output_contract: dict[str, str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / output_contract["snapshot_manifest"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    (output_dir / output_contract["summary"]).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / output_contract["run_config"]).write_text(
        json.dumps(run_config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = read_json(args.config)
    mapping_decision = read_json(args.mapping_decision)
    years = sorted(set(args.years or config.get("permitted_manifest_years", [])))
    contract_errors = validate_contracts(config, mapping_decision, years)
    if contract_errors:
        raise ValueError("Contract E2.3 INVALID:\n- " + "\n- ".join(contract_errors))

    rows, source_lineage = build_manifest_rows(
        config,
        raw_root=args.raw_root,
        years=years,
    )
    row_errors = validate_manifest_rows(
        rows,
        expected_timeframes=set(config["timeframes"]),
    )
    if row_errors:
        raise ValueError("Manifest E2.3 INVALID:\n- " + "\n- ".join(row_errors))

    digest = manifest_digest(rows)
    summary = build_summary(rows)
    summary["manifest_digest_sha256"] = digest
    summary["years"] = years
    summary["pair"] = config["pair"]

    sources = [
        {
            "timeframe": timeframe,
            "year": year,
            **details,
        }
        for (timeframe, year), details in sorted(source_lineage.items())
    ]
    run_config = {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "DAILY_MANIFEST",
        "decision_status": config["decision_status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_performed": False,
        "inference_performed": False,
        "pair": config["pair"],
        "years": years,
        "timeframes": config["timeframes"],
        "slots": config["time_policy"]["slots"],
        "time_policy": config["time_policy"],
        "chart_candles": config["chart_candles"],
        "context_candles": config["context_candles"],
        "plot_aware_mapping": True,
        "mapping_fallback": "FULL_IMAGE",
        "manifest_digest_sha256": digest,
        "config_path": portable_path(args.config),
        "config_sha256": file_sha256(args.config),
        "mapping_decision_path": portable_path(args.mapping_decision),
        "mapping_decision_sha256": file_sha256(args.mapping_decision),
        "raw_root": portable_path(args.raw_root),
        "source_files": sources,
        **git_lineage(),
    }
    write_outputs(
        args.output_dir,
        rows=rows,
        summary=summary,
        run_config=run_config,
        output_contract=config["output_contract"],
    )

    print("E2.3 daily manifest VALID")
    print(f"Rows: {summary['snapshot_rows']}")
    print(f"Trading days: {summary['trading_days']}")
    print(f"Events: {summary['events']} | Ready: {summary['ready_events']}")
    print(f"Digest: {digest}")
    print(f"Output: {args.output_dir.resolve()}")
    return {"rows": rows, "summary": summary, "run_config": run_config}


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
