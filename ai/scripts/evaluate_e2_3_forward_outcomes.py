from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import os
import random
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from ai.scripts.build_e2_3_daily_manifest import (
        MANIFEST_FIELDS,
        manifest_digest,
    )
except ImportError:
    from build_e2_3_daily_manifest import (  # type: ignore[no-redef]
        MANIFEST_FIELDS,
        manifest_digest,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_3_forward_outcome_policy.json"
)
DEFAULT_RAW_ROOT = PROJECT_ROOT / "ai" / "datasets" / "raw" / "ohlcv"
EVALUATOR_VERSION = "1.0.0"
ALLOWED_SPLITS = {"POLICY_DEVELOPMENT", "POLICY_SELECTION"}
ALLOWED_YEARS = {2020, 2021, 2022, 2023}
INTEGER_MANIFEST_FIELDS = {
    "schema_version",
    "year",
    "timeframe_minutes",
    "chart_candles",
    "context_candles",
    "available_history_candles",
    "anti_lookahead_verified",
    "plot_aware_mapping",
    "event_ready",
    "max_candidates_per_tier_per_day",
}
FLOAT_MANIFEST_FIELDS = {"market_utc_offset_hours", "staleness_minutes"}

OUTCOME_FIELDS = [
    "daily_group_id",
    "evaluation_split",
    "year",
    "trading_date_utc",
    "selected_tier",
    "selected_candidate_rule",
    "snapshot_id",
    "slot",
    "source_timeframe",
    "analysis_target_datetime",
    "decision",
    "order_type",
    "entry",
    "stop_loss",
    "take_profit",
    "risk_reward_ratio",
    "risk_price",
    "risk_pips",
    "horizon_end_datetime",
    "outcome_status",
    "filled",
    "fill_datetime",
    "exit_datetime",
    "exit_price",
    "observed_m5_bars",
    "entry_bar_target_ambiguous",
    "same_bar_both_ambiguous",
    "right_censored",
    "gross_r",
    "net_r_primary",
    "optimistic_gross_r",
    "optimistic_net_r_primary",
    "primary_friction_r",
    "source_paths_json",
    "source_sha256s_json",
    "error",
]

BREAKDOWN_FIELDS = [
    "dimension",
    "value",
    "candidate_count",
    "evaluated_count",
    "filled_count",
    "not_filled_count",
    "take_profit_count",
    "stop_loss_count",
    "horizon_exit_count",
    "right_censored_count",
    "data_error_count",
    "ambiguous_count",
    "fill_rate_pct",
    "resolved_win_rate_pct",
    "gross_expectancy_r_candidate",
    "net_expectancy_r_candidate",
    "net_expectancy_r_filled",
    "net_profit_factor",
    "optimistic_net_expectancy_r_candidate",
    "optimistic_net_profit_factor",
    "ambiguity_expectancy_delta_r",
    "max_event_drawdown_r",
    "expectancy_ci_lower_r",
    "expectancy_ci_upper_r",
    "win_rate_ci_lower_pct",
    "win_rate_ci_upper_pct",
]


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate forward M5 outcomes for the frozen E2.3 Standard and "
            "High Risk daily candidates. This command performs no model "
            "training, inference, or 2024/2025 access."
        )
    )
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--progress-every", type=int, default=50)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Artifact tidak ditemukan: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON tidak valid: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root harus object: {path}")
    return payload


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        handle = path.open("r", newline="", encoding="utf-8-sig")
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Artifact tidak ditemukan: {path}") from error
    with handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def read_manifest(path: Path) -> list[dict[str, Any]]:
    fields, raw_rows = read_csv_rows(path)
    if fields != MANIFEST_FIELDS:
        raise ValueError("Kolom daily snapshot manifest berbeda dari kontrak E2.3.")
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        typed: dict[str, Any] = {}
        for field in MANIFEST_FIELDS:
            value = str(raw.get(field, ""))
            if field in INTEGER_MANIFEST_FIELDS:
                typed[field] = int(value)
            elif field in FLOAT_MANIFEST_FIELDS:
                typed[field] = "" if value == "" else float(value)
            else:
                typed[field] = value
        rows.append(typed)
    return rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def write_json_atomic(path: Path, payload: Any) -> None:
    _write_text_atomic(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def write_csv_atomic(
    path: Path,
    rows: Iterable[dict[str, Any]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _as_int(value: Any, *, default: int | None = None) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        if default is not None:
            return default
        raise ValueError(f"Nilai integer tidak valid: {value!r}")


def _as_float(value: Any, *, default: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        if default is not None:
            return default
        raise ValueError(f"Nilai numerik tidak valid: {value!r}")
    if not math.isfinite(result):
        if default is not None:
            return default
        raise ValueError(f"Nilai numerik harus finite: {value!r}")
    return result


def _optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return _as_float(value)


def _safe_relative_path(root: Path, relative: str) -> Path:
    value = Path(relative)
    if value.is_absolute():
        raise ValueError(f"Path source harus relatif terhadap raw root: {relative}")
    candidate = (root.resolve() / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"Path source keluar dari raw root: {relative}") from error
    return candidate


def validate_config(config: dict[str, Any]) -> None:
    errors: list[str] = []
    if config.get("experiment_id") != "E2.3":
        errors.append("experiment_id")
    if config.get("stage") != "FORWARD_OUTCOME_EVALUATION":
        errors.append("stage")
    lineage = config.get("lineage") or {}
    if set(lineage.get("allowed_years", [])) != ALLOWED_YEARS:
        errors.append("allowed years")
    if set(lineage.get("allowed_splits", [])) != ALLOWED_SPLITS:
        errors.append("allowed splits")
    if lineage.get("frozen_holdout_year") != 2024:
        errors.append("frozen holdout")
    if lineage.get("final_temporal_test_year") != 2025:
        errors.append("final year")
    execution = config.get("execution_model") or {}
    if execution.get("outcome_timeframe") != "M5":
        errors.append("outcome timeframe")
    if _as_int(execution.get("horizon_calendar_hours"), default=-1) != 24:
        errors.append("horizon")
    if set(execution.get("supported_order_types", [])) != {
        "BUY_LIMIT",
        "SELL_LIMIT",
    }:
        errors.append("order types")
    guardrails = config.get("guardrails") or {}
    for key in (
        "model_training_allowed",
        "model_inference_allowed",
        "holdout_2024_access_allowed",
        "final_2025_access_allowed",
        "production_promotion_allowed",
    ):
        if guardrails.get(key) is not False:
            errors.append(key)
    if errors:
        raise ValueError("Forward outcome policy INVALID: " + ", ".join(errors))


def _validate_shadow_artifacts(
    experiment_dir: Path,
    shadow_manifest: dict[str, Any],
) -> None:
    if shadow_manifest.get("stage") != "SHADOW_POLICY_EVALUATION":
        raise ValueError("Manifest shadow policy belum berada pada stage yang benar.")
    if shadow_manifest.get("training_performed") is not False:
        raise ValueError("Manifest shadow policy menyatakan training dilakukan.")
    if shadow_manifest.get("model_inference_performed") is not False:
        raise ValueError("Evaluator shadow tidak boleh menjalankan inference baru.")
    for relative, details in (shadow_manifest.get("artifacts") or {}).items():
        path = (experiment_dir / Path(relative)).resolve()
        try:
            path.relative_to(experiment_dir)
        except ValueError as error:
            raise ValueError(f"Artifact shadow keluar experiment root: {relative}") from error
        if not path.is_file():
            raise FileNotFoundError(f"Artifact shadow tidak ditemukan: {path}")
        if file_sha256(path) != str(details.get("sha256")):
            raise ValueError(f"SHA256 artifact shadow berubah: {relative}")


def validate_inputs(
    *,
    experiment_dir: Path,
    config: dict[str, Any],
    daily_fields: list[str],
    daily_rows: list[dict[str, str]],
    snapshot_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, Any]],
    shadow_policy: dict[str, Any],
    shadow_manifest: dict[str, Any],
) -> list[dict[str, str]]:
    _validate_shadow_artifacts(experiment_dir, shadow_manifest)
    lineage = config["lineage"]
    actual_manifest_digest = manifest_digest(manifest_rows)
    if actual_manifest_digest != lineage["manifest_digest_sha256"]:
        raise ValueError("Digest daily snapshot manifest berubah.")
    if shadow_manifest.get("input_lineage", {}).get(
        "inference_contract_sha256"
    ) != lineage["inference_contract_sha256"]:
        raise ValueError("Inference contract shadow berbeda dari outcome contract.")
    if shadow_policy.get("policy_version") != config["input_shadow_policy_version"]:
        raise ValueError("Versi shadow policy berbeda dari outcome contract.")
    if object_sha256(shadow_policy) != lineage["shadow_policy_sha256"]:
        raise ValueError("Object SHA256 shadow policy berubah.")
    required_daily = {
        "selected_order_type",
        "selected_entry",
        "selected_stop_loss",
        "selected_take_profit",
        "selected_analysis_target_datetime",
    }
    missing = required_daily - set(daily_fields)
    if missing:
        raise ValueError(
            "Output shadow policy belum menyimpan order contract. Jalankan ulang "
            "evaluate_e2_3_shadow_policy.py versi terbaru. Missing: "
            + ", ".join(sorted(missing))
        )
    selected = [row for row in daily_rows if str(row.get("selected_tier"))]
    if len(selected) != _as_int(lineage["expected_selected_candidate_days"]):
        raise ValueError("Jumlah selected candidate day berubah dari kontrak.")
    actual_tiers = Counter(str(row.get("selected_tier")) for row in selected)
    expected_tiers = Counter(
        {
            str(key): _as_int(value)
            for key, value in lineage["expected_selected_tier_counts"].items()
        }
    )
    if actual_tiers != expected_tiers:
        raise ValueError(
            "Komposisi tier selected candidate berubah dari kontrak: "
            f"expected={dict(expected_tiers)}; actual={dict(actual_tiers)}."
        )
    actual_directions = Counter(
        str(row.get("combined_policy_decision")) for row in selected
    )
    expected_directions = Counter(
        {
            str(key): _as_int(value)
            for key, value in lineage[
                "expected_selected_direction_counts"
            ].items()
        }
    )
    if actual_directions != expected_directions:
        raise ValueError(
            "Komposisi arah selected candidate berubah dari kontrak: "
            f"expected={dict(expected_directions)}; "
            f"actual={dict(actual_directions)}."
        )
    actual_high_risk_rules = Counter(
        str(row.get("selected_candidate_rule"))
        for row in selected
        if str(row.get("selected_tier")) == "HIGH_RISK"
    )
    expected_high_risk_rules = Counter(
        {
            str(key): _as_int(value)
            for key, value in lineage[
                "expected_high_risk_rule_counts"
            ].items()
        }
    )
    if actual_high_risk_rules != expected_high_risk_rules:
        raise ValueError(
            "Komposisi rule High Risk berubah dari kontrak: "
            f"expected={dict(expected_high_risk_rules)}; "
            f"actual={dict(actual_high_risk_rules)}."
        )
    snapshots = {row["snapshot_id"]: row for row in snapshot_rows}
    manifests = {str(row["snapshot_id"]): row for row in manifest_rows}
    for row in selected:
        year = _as_int(row.get("year"), default=-1)
        split = str(row.get("evaluation_split"))
        snapshot_id = str(row.get("selected_snapshot_id"))
        decision = str(row.get("combined_policy_decision"))
        order_type = str(row.get("selected_order_type"))
        expected_order = {"BUY": "BUY_LIMIT", "SELL": "SELL_LIMIT"}.get(
            decision, ""
        )
        if year not in ALLOWED_YEARS or split not in ALLOWED_SPLITS:
            raise ValueError(f"Selected row di luar development contract: {snapshot_id}")
        if order_type != expected_order:
            raise ValueError(f"Order type selected row tidak konsisten: {snapshot_id}")
        if snapshot_id not in snapshots or snapshot_id not in manifests:
            raise ValueError(f"Lineage selected snapshot tidak lengkap: {snapshot_id}")
        snapshot = snapshots[snapshot_id]
        if str(snapshot.get("order_type")) != order_type:
            raise ValueError(f"Order type daily/snapshot berbeda: {snapshot_id}")
        if str(snapshot.get("candidate_decision")) != decision:
            raise ValueError(f"Arah daily/snapshot berbeda: {snapshot_id}")
        if str(manifests[snapshot_id].get("status")) != "READY":
            raise ValueError(f"Selected snapshot bukan READY: {snapshot_id}")
        for field in ("selected_entry", "selected_stop_loss", "selected_take_profit"):
            _as_float(row.get(field))
    return selected


def _source_year(relative: str) -> int | None:
    match = re.search(r"(?:^|/)(\d{4})(?:/|$)", relative.replace("\\", "/"))
    return int(match.group(1)) if match else None


def build_m5_source_contract(
    manifest_rows: list[dict[str, Any]],
) -> dict[str, str]:
    contract: dict[str, str] = {}
    for row in manifest_rows:
        if str(row.get("timeframe")) != "M5":
            continue
        if _as_int(row.get("year"), default=-1) not in ALLOWED_YEARS:
            continue
        paths = str(row.get("source_paths") or "").split("|")
        hashes = str(row.get("source_sha256s") or "").split("|")
        if len(paths) != len(hashes):
            raise ValueError(f"Lineage source M5 tidak sejajar: {row['snapshot_id']}")
        for relative, digest in zip(paths, hashes):
            if not relative or _source_year(relative) not in ALLOWED_YEARS:
                continue
            if "/M5/" not in relative.replace("\\", "/"):
                continue
            if relative in contract and contract[relative] != digest:
                raise ValueError(f"SHA256 source M5 tidak konsisten: {relative}")
            contract[relative] = digest
    years = {_source_year(path) for path in contract}
    if years != ALLOWED_YEARS:
        raise ValueError(f"Source M5 2020-2023 tidak lengkap: {sorted(years)}")
    return dict(sorted(contract.items()))


def read_ohlcv_sources(
    *,
    raw_root: Path,
    source_contract: dict[str, str],
) -> tuple[list[datetime], list[Candle]]:
    candles_by_time: dict[datetime, Candle] = {}
    required = {"<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>"}
    for relative, expected_sha in source_contract.items():
        path = _safe_relative_path(raw_root, relative)
        if not path.is_file():
            raise FileNotFoundError(f"Source OHLCV tidak ditemukan: {path}")
        if file_sha256(path) != expected_sha:
            raise ValueError(f"SHA256 source OHLCV berubah: {relative}")
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"Kolom OHLCV minimum tidak lengkap: {path}")
            for raw in reader:
                timestamp = datetime.strptime(
                    f"{raw['<DATE>']} {raw['<TIME>']}",
                    "%Y.%m.%d %H:%M:%S",
                )
                if timestamp in candles_by_time:
                    raise ValueError(f"Timestamp M5 duplikat: {timestamp.isoformat()}")
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
                    raise ValueError(f"OHLC tidak konsisten: {path} {timestamp}")
                candles_by_time[timestamp] = candle
    timestamps = sorted(candles_by_time)
    if not timestamps:
        raise ValueError("Source M5 kosong.")
    return timestamps, [candles_by_time[value] for value in timestamps]


def _gross_r(decision: str, entry: float, stop_loss: float, exit_price: float) -> float:
    risk = abs(entry - stop_loss)
    if risk <= 0:
        raise ValueError("Risk price harus positif.")
    if decision == "BUY":
        return (exit_price - entry) / risk
    if decision == "SELL":
        return (entry - exit_price) / risk
    raise ValueError(f"Decision tidak didukung: {decision}")


def _touches_entry(candle: Candle, order_type: str, entry: float) -> bool:
    if order_type == "BUY_LIMIT":
        return candle.low <= entry
    if order_type == "SELL_LIMIT":
        return candle.high >= entry
    raise ValueError(f"Order type tidak didukung: {order_type}")


def _touches_levels(
    candle: Candle,
    decision: str,
    stop_loss: float,
    take_profit: float,
) -> tuple[bool, bool]:
    if decision == "BUY":
        return candle.low <= stop_loss, candle.high >= take_profit
    if decision == "SELL":
        return candle.high >= stop_loss, candle.low <= take_profit
    raise ValueError(f"Decision tidak didukung: {decision}")


def evaluate_candidate(
    row: dict[str, str],
    *,
    timestamps: Sequence[datetime],
    candles: Sequence[Candle],
    config: dict[str, Any],
    source_contract: dict[str, str],
) -> dict[str, Any]:
    decision = str(row["combined_policy_decision"])
    order_type = str(row["selected_order_type"])
    entry = _as_float(row["selected_entry"])
    stop_loss = _as_float(row["selected_stop_loss"])
    take_profit = _as_float(row["selected_take_profit"])
    signal = datetime.fromisoformat(str(row["selected_analysis_target_datetime"]))
    horizon_hours = _as_int(config["execution_model"]["horizon_calendar_hours"])
    horizon_end = signal + timedelta(hours=horizon_hours)
    left = bisect.bisect_left(timestamps, signal)
    right = bisect.bisect_left(timestamps, horizon_end)
    observed = list(candles[left:right])
    pip_size = _as_float(config["cost_model"]["pip_size"])
    friction_pips = _as_float(
        config["cost_model"]["primary_round_trip_friction_pips"]
    )
    risk_price = abs(entry - stop_loss)
    risk_pips = risk_price / pip_size
    if risk_price <= 0 or risk_pips <= 0:
        raise ValueError(f"Risk level tidak valid: {row['selected_snapshot_id']}")
    expected_order = {"BUY": "BUY_LIMIT", "SELL": "SELL_LIMIT"}.get(decision)
    if order_type != expected_order:
        raise ValueError(f"Order type tidak konsisten: {row['selected_snapshot_id']}")
    if decision == "BUY" and not (stop_loss < entry < take_profit):
        raise ValueError(f"Level BUY tidak berurutan: {row['selected_snapshot_id']}")
    if decision == "SELL" and not (take_profit < entry < stop_loss):
        raise ValueError(f"Level SELL tidak berurutan: {row['selected_snapshot_id']}")

    filled = False
    fill_datetime: datetime | None = None
    exit_datetime: datetime | None = None
    exit_price: float | None = None
    status = ""
    entry_bar_target_ambiguous = False
    same_bar_both_ambiguous = False
    optimistic_override_r: float | None = None
    target_r = _gross_r(decision, entry, stop_loss, take_profit)

    for candle in observed:
        is_entry_bar = False
        if not filled:
            if not _touches_entry(candle, order_type, entry):
                continue
            filled = True
            is_entry_bar = True
            fill_datetime = candle.timestamp

        stop_hit, target_hit = _touches_levels(
            candle,
            decision,
            stop_loss,
            take_profit,
        )
        if stop_hit:
            if target_hit:
                same_bar_both_ambiguous = True
                optimistic_override_r = target_r
                status = "AMBIGUOUS_BOTH_CONSERVATIVE_SL"
            else:
                status = "STOP_LOSS"
            exit_datetime = candle.timestamp
            exit_price = stop_loss
            break
        if target_hit:
            if is_entry_bar:
                entry_bar_target_ambiguous = True
                optimistic_override_r = target_r
                continue
            status = "TAKE_PROFIT"
            exit_datetime = candle.timestamp
            exit_price = take_profit
            break

    right_censored = False
    if not filled:
        if observed:
            status = "NOT_FILLED"
        else:
            status = "RIGHT_CENSORED_NO_MARKET_DATA"
            right_censored = True
    elif not status:
        if observed:
            status = "HORIZON_EXIT"
            exit_datetime = observed[-1].timestamp
            exit_price = observed[-1].close
        else:
            status = "RIGHT_CENSORED_OPEN"
            right_censored = True

    gross_r: float | None
    if not filled and not right_censored:
        gross_r = _as_float(config["execution_model"]["unfilled_result_r"])
    elif exit_price is not None:
        gross_r = _gross_r(decision, entry, stop_loss, exit_price)
    else:
        gross_r = None
    friction_r = friction_pips / risk_pips if filled and gross_r is not None else 0.0
    net_r = gross_r - friction_r if gross_r is not None else None
    optimistic_gross = (
        optimistic_override_r if optimistic_override_r is not None else gross_r
    )
    optimistic_net = (
        optimistic_gross - friction_r if optimistic_gross is not None else None
    )

    return {
        "daily_group_id": row["daily_group_id"],
        "evaluation_split": row["evaluation_split"],
        "year": _as_int(row["year"]),
        "trading_date_utc": row["trading_date_utc"],
        "selected_tier": row["selected_tier"],
        "selected_candidate_rule": row["selected_candidate_rule"],
        "snapshot_id": row["selected_snapshot_id"],
        "slot": row["selected_slot"],
        "source_timeframe": row["selected_timeframe"],
        "analysis_target_datetime": signal.isoformat(),
        "decision": decision,
        "order_type": order_type,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward_ratio": _as_float(row["selected_risk_reward_ratio"]),
        "risk_price": risk_price,
        "risk_pips": risk_pips,
        "horizon_end_datetime": horizon_end.isoformat(),
        "outcome_status": status,
        "filled": int(filled),
        "fill_datetime": fill_datetime.isoformat() if fill_datetime else "",
        "exit_datetime": exit_datetime.isoformat() if exit_datetime else "",
        "exit_price": exit_price if exit_price is not None else "",
        "observed_m5_bars": len(observed),
        "entry_bar_target_ambiguous": int(entry_bar_target_ambiguous),
        "same_bar_both_ambiguous": int(same_bar_both_ambiguous),
        "right_censored": int(right_censored),
        "gross_r": gross_r if gross_r is not None else "",
        "net_r_primary": net_r if net_r is not None else "",
        "optimistic_gross_r": optimistic_gross if optimistic_gross is not None else "",
        "optimistic_net_r_primary": optimistic_net if optimistic_net is not None else "",
        "primary_friction_r": friction_r,
        "source_paths_json": json.dumps(list(source_contract), separators=(",", ":")),
        "source_sha256s_json": json.dumps(
            [source_contract[path] for path in source_contract],
            separators=(",", ":"),
        ),
        "error": "",
    }


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def _rate(count: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * count / denominator, 6)


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _profit_factor(values: Sequence[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    if losses <= 0:
        return None
    return gains / losses


def _max_drawdown(values: Sequence[float]) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def _percentile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def bootstrap_mean_interval(
    values: Sequence[float],
    *,
    samples: int,
    seed: int,
    confidence_level: float,
) -> tuple[float | None, float | None]:
    if not values or samples <= 0:
        return None, None
    generator = random.Random(seed)
    size = len(values)
    estimates = [
        sum(values[generator.randrange(size)] for _ in range(size)) / size
        for _ in range(samples)
    ]
    alpha = 1.0 - confidence_level
    return (
        _percentile(estimates, alpha / 2.0),
        _percentile(estimates, 1.0 - alpha / 2.0),
    )


def wilson_interval(
    successes: int,
    total: int,
    *,
    confidence_level: float,
) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    if abs(confidence_level - 0.95) > 1e-9:
        raise ValueError("Implementasi Wilson saat ini mengunci confidence 95%.")
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _primary_evaluated_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if not _as_int(row.get("right_censored"), default=0)
        and not str(row.get("outcome_status", "")).startswith("DATA_ERROR")
    ]


def _net_values_for_friction(
    rows: Sequence[dict[str, Any]],
    *,
    friction_pips: float,
) -> list[float]:
    values: list[float] = []
    for row in _primary_evaluated_rows(rows):
        gross = _as_float(row.get("gross_r"), default=0.0)
        if _as_int(row.get("filled"), default=0):
            gross -= friction_pips / _as_float(row["risk_pips"])
        values.append(gross)
    return values


def summarize_rows(
    rows: Sequence[dict[str, Any]],
    *,
    config: dict[str, Any],
    seed_offset: int = 0,
) -> dict[str, Any]:
    evaluated = _primary_evaluated_rows(rows)
    filled = [row for row in evaluated if _as_int(row.get("filled"), default=0)]
    statuses = Counter(str(row.get("outcome_status")) for row in rows)
    take_profit = statuses["TAKE_PROFIT"]
    stop_loss = statuses["STOP_LOSS"] + statuses[
        "AMBIGUOUS_BOTH_CONSERVATIVE_SL"
    ]
    resolved = take_profit + stop_loss
    horizon_exit = statuses["HORIZON_EXIT"]
    right_censored = sum(
        _as_int(row.get("right_censored"), default=0) for row in rows
    )
    data_errors = sum(
        str(row.get("outcome_status", "")).startswith("DATA_ERROR") for row in rows
    )
    ambiguous = sum(
        bool(_as_int(row.get("entry_bar_target_ambiguous"), default=0))
        or bool(_as_int(row.get("same_bar_both_ambiguous"), default=0))
        for row in rows
    )
    gross_values = [_as_float(row.get("gross_r"), default=0.0) for row in evaluated]
    net_values = [
        _as_float(row.get("net_r_primary"), default=0.0) for row in evaluated
    ]
    optimistic_net_values = [
        _as_float(row.get("optimistic_net_r_primary"), default=0.0)
        for row in evaluated
    ]
    filled_net = [
        _as_float(row.get("net_r_primary"), default=0.0) for row in filled
    ]
    uncertainty = config["uncertainty"]
    ci_low, ci_high = bootstrap_mean_interval(
        net_values,
        samples=_as_int(uncertainty["bootstrap_samples"]),
        seed=_as_int(uncertainty["bootstrap_seed"]) + seed_offset,
        confidence_level=_as_float(uncertainty["confidence_level"]),
    )
    win_low, win_high = wilson_interval(
        take_profit,
        resolved,
        confidence_level=_as_float(uncertainty["confidence_level"]),
    )
    friction_sensitivity: dict[str, Any] = {}
    for friction in config["cost_model"][
        "sensitivity_round_trip_friction_pips"
    ]:
        friction_value = _as_float(friction)
        values = _net_values_for_friction(rows, friction_pips=friction_value)
        friction_sensitivity[f"{friction_value:.1f}"] = {
            "expectancy_r_candidate": _round(_mean(values)),
            "profit_factor": _round(_profit_factor(values)),
            "max_event_drawdown_r": _round(_max_drawdown(values)),
        }
    return {
        "candidate_count": len(rows),
        "evaluated_count": len(evaluated),
        "filled_count": len(filled),
        "not_filled_count": statuses["NOT_FILLED"],
        "take_profit_count": take_profit,
        "stop_loss_count": stop_loss,
        "horizon_exit_count": horizon_exit,
        "right_censored_count": right_censored,
        "data_error_count": data_errors,
        "ambiguous_count": ambiguous,
        "outcome_status_counts": dict(sorted(statuses.items())),
        "fill_rate_pct": _rate(len(filled), len(evaluated)),
        "resolved_win_rate_pct": _rate(take_profit, resolved),
        "gross_expectancy_r_candidate": _round(_mean(gross_values)),
        "net_expectancy_r_candidate": _round(_mean(net_values)),
        "net_expectancy_r_filled": _round(_mean(filled_net)),
        "net_profit_factor": _round(_profit_factor(net_values)),
        "optimistic_net_expectancy_r_candidate": _round(
            _mean(optimistic_net_values)
        ),
        "optimistic_net_profit_factor": _round(
            _profit_factor(optimistic_net_values)
        ),
        "ambiguity_expectancy_delta_r": _round(
            (_mean(optimistic_net_values) or 0.0) - (_mean(net_values) or 0.0)
        ),
        "max_event_drawdown_r": _round(_max_drawdown(net_values)),
        "ambiguous_filled_rate_pct": _rate(ambiguous, len(filled)),
        "expectancy_bootstrap_95_r": {
            "lower": _round(ci_low),
            "upper": _round(ci_high),
        },
        "resolved_win_rate_wilson_95_pct": {
            "lower": _round(None if win_low is None else 100.0 * win_low),
            "upper": _round(None if win_high is None else 100.0 * win_high),
        },
        "friction_sensitivity_pips": friction_sensitivity,
    }


def build_breakdowns(
    rows: Sequence[dict[str, Any]],
    *,
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dimensions = {
        "overall": lambda row: "ALL",
        "tier": lambda row: str(row["selected_tier"]),
        "split": lambda row: str(row["evaluation_split"]),
        "year": lambda row: str(row["year"]),
        "candidate_rule": lambda row: str(row["selected_candidate_rule"] or "STANDARD"),
        "source_timeframe": lambda row: str(row["source_timeframe"]),
        "slot": lambda row: str(row["slot"]),
        "direction": lambda row: str(row["decision"]),
    }
    nested: dict[str, Any] = {}
    flat: list[dict[str, Any]] = []
    offset = 0
    for dimension, getter in dimensions.items():
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[getter(row)].append(row)
        nested[dimension] = {}
        for value in sorted(groups):
            summary = summarize_rows(
                groups[value],
                config=config,
                seed_offset=offset,
            )
            offset += 1
            nested[dimension][value] = summary
            flat.append(
                {
                    "dimension": dimension,
                    "value": value,
                    **{
                        field: summary.get(field, "")
                        for field in BREAKDOWN_FIELDS
                        if field not in {"dimension", "value"}
                        and field
                        not in {
                            "expectancy_ci_lower_r",
                            "expectancy_ci_upper_r",
                            "win_rate_ci_lower_pct",
                            "win_rate_ci_upper_pct",
                        }
                    },
                    "expectancy_ci_lower_r": summary[
                        "expectancy_bootstrap_95_r"
                    ]["lower"],
                    "expectancy_ci_upper_r": summary[
                        "expectancy_bootstrap_95_r"
                    ]["upper"],
                    "win_rate_ci_lower_pct": summary[
                        "resolved_win_rate_wilson_95_pct"
                    ]["lower"],
                    "win_rate_ci_upper_pct": summary[
                        "resolved_win_rate_wilson_95_pct"
                    ]["upper"],
                }
            )
    return nested, flat


def evaluate_acceptance_gates(
    rows: Sequence[dict[str, Any]],
    *,
    config: dict[str, Any],
) -> dict[str, Any]:
    high_risk = [row for row in rows if row["selected_tier"] == "HIGH_RISK"]
    development = [
        row
        for row in high_risk
        if row["evaluation_split"] == "POLICY_DEVELOPMENT"
    ]
    selection = [
        row
        for row in high_risk
        if row["evaluation_split"] == "POLICY_SELECTION"
    ]
    combined_summary = summarize_rows(high_risk, config=config, seed_offset=100)
    development_summary = summarize_rows(
        development,
        config=config,
        seed_offset=101,
    )
    selection_summary = summarize_rows(selection, config=config, seed_offset=102)
    gate = config["pre_holdout_acceptance_gates"]
    checks = {
        "minimum_combined_filled_trades": combined_summary["filled_count"]
        >= _as_int(gate["minimum_combined_filled_trades"]),
        "minimum_selection_filled_trades": selection_summary["filled_count"]
        >= _as_int(gate["minimum_selection_filled_trades"]),
        "minimum_selection_net_expectancy_r": (
            selection_summary["net_expectancy_r_candidate"] is not None
            and selection_summary["net_expectancy_r_candidate"]
            > _as_float(gate["minimum_selection_net_expectancy_r"])
        ),
        "minimum_selection_net_profit_factor": (
            selection_summary["net_profit_factor"] is not None
            and selection_summary["net_profit_factor"]
            >= _as_float(gate["minimum_selection_net_profit_factor"])
        ),
        "minimum_selection_resolved_win_rate": (
            selection_summary["resolved_win_rate_pct"] is not None
            and selection_summary["resolved_win_rate_pct"]
            >= 100.0 * _as_float(gate["minimum_selection_resolved_win_rate"])
        ),
        "maximum_selection_event_drawdown_r": (
            selection_summary["max_event_drawdown_r"] is not None
            and selection_summary["max_event_drawdown_r"]
            <= _as_float(gate["maximum_selection_event_drawdown_r"])
        ),
        "maximum_selection_ambiguous_filled_rate": (
            selection_summary["ambiguous_filled_rate_pct"] is not None
            and selection_summary["ambiguous_filled_rate_pct"]
            <= 100.0 * _as_float(gate["maximum_selection_ambiguous_filled_rate"])
        ),
        "positive_development_net_expectancy": (
            not bool(gate["require_positive_development_net_expectancy"])
            or (
                development_summary["net_expectancy_r_candidate"] is not None
                and development_summary["net_expectancy_r_candidate"] > 0.0
            )
        ),
        "no_data_error": (
            not bool(gate["require_no_data_error"])
            or combined_summary["data_error_count"] == 0
        ),
        "no_unresolved_right_censoring": (
            not bool(gate["require_no_unresolved_right_censoring"])
            or combined_summary["right_censored_count"] == 0
        ),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "high_risk_combined": combined_summary,
        "high_risk_development": development_summary,
        "high_risk_selection": selection_summary,
        "holdout_2024_unlocked": False,
        "production_promotion_allowed": False,
    }


def _display(value: Any, *, suffix: str = "") -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}{suffix}"
    return f"{value}{suffix}"


def build_report(metrics: dict[str, Any], config: dict[str, Any]) -> str:
    breakdowns = metrics["breakdowns"]
    overall = breakdowns["overall"]["ALL"]
    standard = breakdowns["tier"].get("STANDARD", {})
    high_risk = breakdowns["tier"].get("HIGH_RISK", {})

    def metric_row(label: str, field: str, suffix: str = "") -> str:
        return (
            f"| {label} | {_display(standard.get(field), suffix=suffix)} | "
            f"{_display(high_risk.get(field), suffix=suffix)} | "
            f"{_display(overall.get(field), suffix=suffix)} |"
        )

    gate = metrics["pre_holdout_acceptance"]
    gate_lines = [
        "| Gate | Result |",
        "|---|---|",
        *[
            f"| `{name}` | {'PASS' if passed else 'FAIL'} |"
            for name, passed in gate["checks"].items()
        ],
    ]
    cost = config["cost_model"]
    execution = config["execution_model"]
    lines = [
        "# AI-TDSS E2.3 Forward Outcome Evaluation",
        "",
        f"Generated (UTC): `{metrics['generated_at_utc']}`",
        "",
        "## Registered protocol",
        "",
        f"- Candidate days: `{metrics['selected_candidate_days']}`",
        "- Outcome stream: raw GBPUSD M5 OHLCV with verified source SHA256.",
        f"- Signal horizon: `{execution['horizon_calendar_hours']} calendar hours`.",
        "- Orders: `BUY_LIMIT` and `SELL_LIMIT` only.",
        "- Entry-bar target touch is not credited in the primary result; the "
        "optimistic sensitivity credits TP.",
        "- A bar touching SL and TP is counted as SL in the primary result and "
        "TP in the optimistic sensitivity.",
        f"- Primary round-trip friction: "
        f"`{cost['primary_round_trip_friction_pips']} pips`.",
        "- Unfilled limit orders contribute `0R`; right-censored outcomes are "
        "excluded from primary metrics.",
        "- This evaluator performs no model training or inference and does not "
        "read 2024/2025.",
        "",
        "## Primary results",
        "",
        "| Metric | Standard | High Risk | Combined |",
        "|---|---:|---:|---:|",
        metric_row("Candidate days", "candidate_count"),
        metric_row("Filled", "filled_count"),
        metric_row("Fill rate", "fill_rate_pct", "%"),
        metric_row("TP", "take_profit_count"),
        metric_row("SL (conservative)", "stop_loss_count"),
        metric_row("Horizon exit", "horizon_exit_count"),
        metric_row("Resolved win rate", "resolved_win_rate_pct", "%"),
        metric_row("Net expectancy / candidate", "net_expectancy_r_candidate", "R"),
        metric_row("Net expectancy / filled", "net_expectancy_r_filled", "R"),
        metric_row("Net profit factor", "net_profit_factor"),
        metric_row(
            "Optimistic net expectancy / candidate",
            "optimistic_net_expectancy_r_candidate",
            "R",
        ),
        metric_row("Ambiguity expectancy delta", "ambiguity_expectancy_delta_r", "R"),
        metric_row("Maximum event drawdown", "max_event_drawdown_r", "R"),
        metric_row("Ambiguous observations", "ambiguous_count"),
        metric_row("Right censored", "right_censored_count"),
        "",
        "## Pre-holdout High Risk acceptance",
        "",
        f"Overall result: **{gate['status']}**",
        "",
        *gate_lines,
        "",
        "Passing this gate does not automatically unlock 2024 or promote High "
        "Risk. It only supplies evidence for a separate freeze decision.",
        "",
        "## Interpretation guardrails",
        "",
        "- The event-level cumulative R curve is not a live portfolio backtest; "
        "position sizing and concurrent exposure are not simulated.",
        "- Development results cannot be described as final generalization.",
        "- Raw predictions remain ineligible as automatic ground truth.",
        "- Keep 2024 frozen until this report is reviewed and the policy decision "
        "is recorded. Keep 2025 untouched until the final temporal test.",
        "",
    ]
    return "\n".join(lines)


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
    config = read_json(config_path)
    validate_config(config)

    daily_fields, daily_rows = read_csv_rows(
        experiment_dir / "predictions" / "daily_decisions.csv"
    )
    _, snapshot_rows = read_csv_rows(
        experiment_dir / "predictions" / "snapshot_shadow_decisions.csv"
    )
    manifest_rows = read_manifest(
        experiment_dir / "input" / "daily_snapshot_manifest.csv"
    )
    shadow_policy = read_json(experiment_dir / "config" / "high_risk_policy.json")
    shadow_manifest = read_json(experiment_dir / "manifest.json")
    selected = validate_inputs(
        experiment_dir=experiment_dir,
        config=config,
        daily_fields=daily_fields,
        daily_rows=daily_rows,
        snapshot_rows=snapshot_rows,
        manifest_rows=manifest_rows,
        shadow_policy=shadow_policy,
        shadow_manifest=shadow_manifest,
    )
    source_contract = build_m5_source_contract(manifest_rows)
    print(f"Verifying {len(source_contract)} local M5 source files...")
    timestamps, candles = read_ohlcv_sources(
        raw_root=raw_root,
        source_contract=source_contract,
    )

    outcomes: list[dict[str, Any]] = []
    progress_every = max(0, _as_int(getattr(args, "progress_every", 50), default=50))
    ordered_selected = sorted(
        selected,
        key=lambda row: (
            str(row["selected_analysis_target_datetime"]),
            str(row["selected_snapshot_id"]),
        ),
    )
    for index, row in enumerate(ordered_selected, start=1):
        try:
            outcome = evaluate_candidate(
                row,
                timestamps=timestamps,
                candles=candles,
                config=config,
                source_contract=source_contract,
            )
        except Exception as error:  # retain explicit data errors in research output
            outcome = {
                "daily_group_id": row.get("daily_group_id", ""),
                "evaluation_split": row.get("evaluation_split", ""),
                "year": row.get("year", ""),
                "trading_date_utc": row.get("trading_date_utc", ""),
                "selected_tier": row.get("selected_tier", ""),
                "selected_candidate_rule": row.get("selected_candidate_rule", ""),
                "snapshot_id": row.get("selected_snapshot_id", ""),
                "slot": row.get("selected_slot", ""),
                "source_timeframe": row.get("selected_timeframe", ""),
                "analysis_target_datetime": row.get(
                    "selected_analysis_target_datetime", ""
                ),
                "decision": row.get("combined_policy_decision", ""),
                "order_type": row.get("selected_order_type", ""),
                "outcome_status": "DATA_ERROR",
                "filled": 0,
                "entry_bar_target_ambiguous": 0,
                "same_bar_both_ambiguous": 0,
                "right_censored": 0,
                "error": str(error),
            }
        outcomes.append(outcome)
        if progress_every and (index % progress_every == 0 or index == len(selected)):
            print(
                f"[{index}/{len(selected)}] {outcome['snapshot_id']} -> "
                f"{outcome['outcome_status']}"
            )

    breakdowns, breakdown_rows = build_breakdowns(outcomes, config=config)
    acceptance = evaluate_acceptance_gates(outcomes, config=config)
    metrics = {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "FORWARD_OUTCOME_EVALUATION",
        "evaluator_version": EVALUATOR_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy_version": config["policy_version"],
        "policy_sha256": object_sha256(config),
        "input_shadow_policy_version": shadow_policy["policy_version"],
        "input_shadow_policy_sha256": object_sha256(shadow_policy),
        "manifest_digest_sha256": manifest_digest(manifest_rows),
        "selected_candidate_days": len(outcomes),
        "model_training_performed": False,
        "model_inference_performed": False,
        "holdout_2024_accessed": False,
        "final_2025_accessed": False,
        "event_level_curve_is_portfolio_backtest": False,
        "breakdowns": breakdowns,
        "pre_holdout_acceptance": acceptance,
    }

    policy_output = experiment_dir / "config" / "forward_outcome_policy.json"
    outcome_output = experiment_dir / "outcomes" / "daily_trade_outcomes.csv"
    metrics_output = experiment_dir / "metrics" / "forward_outcome_metrics.json"
    breakdown_output = experiment_dir / "metrics" / "outcome_breakdown.csv"
    report_output = experiment_dir / "reports" / "forward_outcome_report.md"
    manifest_output = experiment_dir / "outcome_manifest.json"

    write_json_atomic(policy_output, config)
    write_csv_atomic(outcome_output, outcomes, OUTCOME_FIELDS)
    write_json_atomic(metrics_output, metrics)
    write_csv_atomic(breakdown_output, breakdown_rows, BREAKDOWN_FIELDS)
    _write_text_atomic(report_output, build_report(metrics, config))

    artifacts: dict[str, Any] = {}
    for path in (
        policy_output,
        outcome_output,
        metrics_output,
        breakdown_output,
        report_output,
    ):
        artifacts[str(path.relative_to(experiment_dir)).replace("\\", "/")] = {
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
    outcome_manifest = {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "FORWARD_OUTCOME_EVALUATION",
        "evaluator_version": EVALUATOR_VERSION,
        "generated_at_utc": metrics["generated_at_utc"],
        "training_performed": False,
        "model_inference_performed": False,
        "holdout_2024_accessed": False,
        "final_2025_accessed": False,
        "production_promotion_allowed": False,
        "policy_sha256": metrics["policy_sha256"],
        "shadow_manifest_sha256": file_sha256(experiment_dir / "manifest.json"),
        "source_sha256s": source_contract,
        "artifacts": artifacts,
        "evaluator_git": git_lineage(),
    }
    write_json_atomic(manifest_output, outcome_manifest)

    print(f"Outcomes: {outcome_output}")
    print(f"Metrics: {metrics_output}")
    print(f"Report: {report_output}")
    print(f"Pre-holdout High Risk gate: {acceptance['status']}")
    return {
        "outcomes": outcomes,
        "metrics": metrics,
        "manifest": outcome_manifest,
    }


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
