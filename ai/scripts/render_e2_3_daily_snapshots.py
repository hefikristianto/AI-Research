from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw

try:
    from ai.scripts.build_e2_3_daily_manifest import (
        MANIFEST_FIELDS,
        manifest_digest,
    )
except ModuleNotFoundError:
    from build_e2_3_daily_manifest import (  # type: ignore[no-redef]
        MANIFEST_FIELDS,
        manifest_digest,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_ROOT = PROJECT_ROOT / "ai" / "datasets" / "raw" / "ohlcv"
DEFAULT_RESULT = (
    PROJECT_ROOT
    / "config"
    / "experiments"
    / "e2_3_daily_manifest_result.json"
)

RENDERER_VERSION = "1.0.0"
IMAGE_WIDTH = 691
IMAGE_HEIGHT = 482
SUPERSAMPLE = 3
UP_COLOR = (0, 99, 64)
DOWN_COLOR = (160, 33, 40)
BACKGROUND_COLOR = (255, 255, 255)

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
FLOAT_MANIFEST_FIELDS = {
    "market_utc_offset_hours",
    "staleness_minutes",
}

RENDER_FIELDS = [
    "snapshot_id",
    "event_id",
    "evaluation_split",
    "pair",
    "year",
    "slot",
    "timeframe",
    "manifest_status",
    "render_status",
    "reason",
    "image_path",
    "image_sha256",
    "width",
    "height",
    "chart_start_datetime",
    "chart_end_open_datetime",
    "analysis_target_market_datetime",
    "source_paths",
    "source_sha256s",
    "manifest_digest_sha256",
    "rendered_at_utc",
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
            "Render deterministic canonical PNG snapshots from the reviewed "
            "E2.3 manifest. This script performs no inference or training."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-summary", type=Path, required=True)
    parser.add_argument("--manifest-run-config", type=Path, required=True)
    parser.add_argument("--manifest-result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--year", dest="years", action="append", type=int)
    parser.add_argument(
        "--timeframe",
        dest="timeframes",
        action="append",
        choices=["M5", "M15", "H1", "H4"],
    )
    parser.add_argument(
        "--slot",
        dest="slots",
        action="append",
        choices=["LONDON", "LONDON_NEW_YORK_OVERLAP"],
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=250,
        help="Persist the resumable audit after this many snapshots.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print progress after this many snapshots.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Artifact tidak ditemukan: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON tidak valid: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON harus berupa object: {path}")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _typed_manifest_value(field: str, value: str) -> Any:
    if field in INTEGER_MANIFEST_FIELDS:
        return int(value)
    if field in FLOAT_MANIFEST_FIELDS:
        return "" if value == "" else float(value)
    return value


def read_manifest(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != MANIFEST_FIELDS:
            raise ValueError("Kolom daily manifest tidak sama dengan kontrak E2.3.")
        rows = [
            {
                field: _typed_manifest_value(field, str(raw.get(field, "")))
                for field in MANIFEST_FIELDS
            }
            for raw in reader
        ]
    if not rows:
        raise ValueError("Daily manifest kosong.")
    return rows


def validate_reviewed_manifest(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    run_config: dict[str, Any],
    result: dict[str, Any],
) -> str:
    errors: list[str] = []
    reviewed_manifest = result.get("manifest", {})
    expected_digest = str(reviewed_manifest.get("sha256", ""))
    actual_digest = manifest_digest(rows)

    if result.get("decision_status") != "VALIDATED_FOR_RENDERING":
        errors.append("Manifest belum berstatus VALIDATED_FOR_RENDERING.")
    if actual_digest != expected_digest:
        errors.append("Digest CSV manifest tidak sama dengan hasil review.")
    if summary.get("manifest_digest_sha256") != expected_digest:
        errors.append("Digest summary tidak sama dengan hasil review.")
    if run_config.get("manifest_digest_sha256") != expected_digest:
        errors.append("Digest run_config tidak sama dengan hasil review.")
    if run_config.get("git_commit") != reviewed_manifest.get("git_commit"):
        errors.append("Git commit manifest tidak sama dengan hasil review.")
    if bool(run_config.get("git_dirty")) != bool(reviewed_manifest.get("git_dirty")):
        errors.append("Status dirty-tree manifest tidak sama dengan hasil review.")
    if run_config.get("pair") != reviewed_manifest.get("pair"):
        errors.append("Pair run_config tidak sama dengan hasil review.")
    if run_config.get("years") != reviewed_manifest.get("years"):
        errors.append("Tahun run_config tidak sama dengan hasil review.")
    if int(summary.get("snapshot_rows", -1)) != len(rows):
        errors.append("Jumlah row manifest tidak sama dengan summary.")
    if len(rows) != int(reviewed_manifest.get("snapshot_rows", -1)):
        errors.append("Jumlah row manifest tidak sama dengan hasil review.")
    if run_config.get("training_performed") is not False:
        errors.append("Run manifest tidak boleh melakukan training.")
    if run_config.get("inference_performed") is not False:
        errors.append("Run manifest tidak boleh melakukan inference.")
    if any(int(row["year"]) == 2025 for row in rows):
        errors.append("Manifest renderer tidak boleh memuat target 2025.")
    if any(
        int(row["plot_aware_mapping"]) != 1
        or row["mapping_fallback"] != "FULL_IMAGE"
        for row in rows
    ):
        errors.append("Policy mapping manifest berubah dari keputusan E2.2.")

    expected_ready = int(
        result.get("render_authorization", {}).get("expected_render_count", -1)
    )
    actual_ready = sum(row["status"] == "READY" for row in rows)
    if actual_ready != expected_ready:
        errors.append("Jumlah READY tidak sama dengan izin render hasil review.")
    if actual_ready != int(reviewed_manifest.get("ready_snapshot_rows", -1)):
        errors.append("Jumlah READY tidak sama dengan hasil review.")
    if len(run_config.get("source_files", [])) != int(
        reviewed_manifest.get("source_files", -1)
    ):
        errors.append("Jumlah source file tidak sama dengan hasil review.")

    if errors:
        raise ValueError("Reviewed manifest INVALID:\n- " + "\n- ".join(errors))
    return actual_digest


def select_ready_rows(
    rows: list[dict[str, Any]],
    *,
    years: list[int] | None,
    timeframes: list[str] | None,
    slots: list[str] | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    selected = [row for row in rows if row["status"] == "READY"]
    if years:
        selected = [row for row in selected if int(row["year"]) in set(years)]
    if timeframes:
        selected = [row for row in selected if row["timeframe"] in set(timeframes)]
    if slots:
        selected = [row for row in selected if row["slot"] in set(slots)]
    selected.sort(key=lambda row: str(row["snapshot_id"]))
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit harus minimal 1.")
        selected = selected[:limit]
    if not selected:
        raise ValueError("Tidak ada row READY yang cocok dengan filter renderer.")
    return selected


def _source_contract(run_config: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source in run_config.get("source_files", []):
        path = str(source.get("path", ""))
        digest = str(source.get("sha256", ""))
        if not path or len(digest) != 64:
            raise ValueError("Lineage source_files pada run_config tidak lengkap.")
        result[path] = digest
    return result


def validate_source_hashes(
    rows: list[dict[str, Any]],
    *,
    raw_root: Path,
    run_config: dict[str, Any],
) -> dict[str, Path]:
    contract = _source_contract(run_config)
    required: dict[str, str] = {}
    for row in rows:
        paths = str(row["source_paths"]).split("|")
        hashes = str(row["source_sha256s"]).split("|")
        if len(paths) != len(hashes) or not paths or not paths[0]:
            raise ValueError(f"{row['snapshot_id']}: lineage source tidak valid.")
        for relative, digest in zip(paths, hashes):
            if contract.get(relative) != digest:
                raise ValueError(
                    f"{row['snapshot_id']}: hash source berbeda dari run_config."
                )
            required[relative] = digest

    resolved: dict[str, Path] = {}
    root = raw_root.resolve()
    for relative, expected in sorted(required.items()):
        path = (root / Path(relative)).resolve()
        if root not in path.parents:
            raise ValueError(f"Source path keluar dari raw root: {relative}")
        if not path.is_file():
            raise FileNotFoundError(f"Source OHLCV tidak ditemukan: {path}")
        actual = file_sha256(path)
        if actual != expected:
            raise ValueError(f"SHA256 source berubah: {relative}")
        resolved[relative] = path
        print(f"Source verified: {relative}")
    return resolved


def read_ohlcv_sources(paths: Iterable[Path]) -> tuple[list[datetime], list[Candle]]:
    candles_by_time: dict[datetime, Candle] = {}
    required_columns = {"<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>"}

    for path in paths:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not required_columns.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"Kolom OHLCV minimum tidak lengkap: {path}")
            for raw in reader:
                timestamp = datetime.strptime(
                    f"{raw['<DATE>']} {raw['<TIME>']}",
                    "%Y.%m.%d %H:%M:%S",
                )
                if timestamp in candles_by_time:
                    raise ValueError(f"Timestamp OHLCV duplikat: {timestamp.isoformat()}")
                candle = Candle(
                    timestamp=timestamp,
                    open=float(raw["<OPEN>"]),
                    high=float(raw["<HIGH>"]),
                    low=float(raw["<LOW>"]),
                    close=float(raw["<CLOSE>"]),
                )
                if candle.high < max(candle.open, candle.close) or candle.low > min(
                    candle.open, candle.close
                ):
                    raise ValueError(f"OHLC tidak konsisten: {path} {timestamp}")
                candles_by_time[timestamp] = candle

    timestamps = sorted(candles_by_time)
    return timestamps, [candles_by_time[value] for value in timestamps]


def extract_chart_window(
    row: dict[str, Any],
    timestamps: list[datetime],
    candles: list[Candle],
) -> list[Candle]:
    start = datetime.fromisoformat(str(row["chart_start_datetime"]))
    end = datetime.fromisoformat(str(row["chart_end_open_datetime"]))
    left = bisect.bisect_left(timestamps, start)
    right = bisect.bisect_right(timestamps, end)
    window = candles[left:right]
    expected = int(row["chart_candles"])
    if (
        len(window) != expected
        or not window
        or window[0].timestamp != start
        or window[-1].timestamp != end
    ):
        raise ValueError(
            f"{row['snapshot_id']}: window OHLCV bukan tepat {expected} candle."
        )
    return window


def render_candles_png(candles: list[Candle]) -> bytes:
    if not candles:
        raise ValueError("Candle window kosong.")

    scale = SUPERSAMPLE
    width = IMAGE_WIDTH * scale
    height = IMAGE_HEIGHT * scale
    image = Image.new("RGB", (width, height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)

    left = 36 * scale
    right = (IMAGE_WIDTH - 34) * scale
    top = 22 * scale
    bottom = (IMAGE_HEIGHT - 20) * scale

    lowest = min(candle.low for candle in candles)
    highest = max(candle.high for candle in candles)
    price_range = highest - lowest
    if price_range <= 0:
        price_range = max(abs(highest) * 0.001, 0.00001)
    price_padding = price_range * 0.05
    floor = lowest - price_padding
    ceiling = highest + price_padding

    def y(value: float) -> int:
        ratio = (ceiling - value) / (ceiling - floor)
        return int(round(top + ratio * (bottom - top)))

    step = (right - left) / max(len(candles) - 1, 1)
    body_half_width = max(2 * scale, int(round(step * 0.31)))
    wick_width = max(1, scale)

    for index, candle in enumerate(candles):
        x = int(round(left + index * step))
        color = UP_COLOR if candle.close >= candle.open else DOWN_COLOR
        high_y = y(candle.high)
        low_y = y(candle.low)
        open_y = y(candle.open)
        close_y = y(candle.close)
        draw.line((x, high_y, x, low_y), fill=color, width=wick_width)
        body_top = min(open_y, close_y)
        body_bottom = max(open_y, close_y)
        if body_bottom == body_top:
            body_bottom += scale
        draw.rectangle(
            (x - body_half_width, body_top, x + body_half_width, body_bottom),
            fill=color,
            outline=color,
        )

    image = image.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=6)
    return buffer.getvalue()


def _safe_output_path(output_dir: Path, planned_path: str) -> Path:
    relative = Path(planned_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"planned_image_path tidak aman: {planned_path}")
    root = output_dir.resolve()
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError(f"planned_image_path keluar dari output: {planned_path}")
    return target


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_render_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != RENDER_FIELDS:
            raise ValueError("Checkpoint renderer memakai schema yang berbeda.")
        return {str(row["snapshot_id"]): dict(row) for row in reader}


def write_render_rows(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=RENDER_FIELDS)
        writer.writeheader()
        writer.writerows(rows[key] for key in sorted(rows))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _base_render_row(
    row: dict[str, Any],
    *,
    manifest_digest_sha256: str,
) -> dict[str, Any]:
    return {
        "snapshot_id": row["snapshot_id"],
        "event_id": row["event_id"],
        "evaluation_split": row["evaluation_split"],
        "pair": row["pair"],
        "year": row["year"],
        "slot": row["slot"],
        "timeframe": row["timeframe"],
        "manifest_status": row["status"],
        "render_status": "",
        "reason": "",
        "image_path": row["planned_image_path"],
        "image_sha256": "",
        "width": "",
        "height": "",
        "chart_start_datetime": row["chart_start_datetime"],
        "chart_end_open_datetime": row["chart_end_open_datetime"],
        "analysis_target_market_datetime": row[
            "analysis_target_market_datetime"
        ],
        "source_paths": row["source_paths"],
        "source_sha256s": row["source_sha256s"],
        "manifest_digest_sha256": manifest_digest_sha256,
        "rendered_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_summary(
    path: Path,
    *,
    all_manifest_rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    audit_rows: dict[str, dict[str, Any]],
    manifest_digest_sha256: str,
) -> None:
    counts = Counter(str(row.get("render_status", "")) for row in audit_rows.values())
    payload = {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "DAILY_SNAPSHOT_RENDER",
        "renderer_version": RENDERER_VERSION,
        "training_performed": False,
        "inference_performed": False,
        "manifest_digest_sha256": manifest_digest_sha256,
        "manifest_rows": len(all_manifest_rows),
        "manifest_ready_rows": sum(row["status"] == "READY" for row in all_manifest_rows),
        "manifest_non_ready_rows": sum(
            row["status"] != "READY" for row in all_manifest_rows
        ),
        "selected_ready_rows_this_invocation": len(selected_rows),
        "cumulative_audit_rows": len(audit_rows),
        "render_status_counts": dict(sorted(counts.items())),
        "complete_for_reviewed_manifest": (
            counts.get("RENDERED", 0) + counts.get("REUSED", 0)
            == sum(row["status"] == "READY" for row in all_manifest_rows)
            and counts.get("FAILED", 0) == 0
        ),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    rows = read_manifest(args.manifest)
    summary = read_json(args.manifest_summary)
    manifest_run_config = read_json(args.manifest_run_config)
    result = read_json(args.manifest_result)
    digest = validate_reviewed_manifest(rows, summary, manifest_run_config, result)
    selected = select_ready_rows(
        rows,
        years=args.years,
        timeframes=args.timeframes,
        slots=args.slots,
        limit=args.limit,
    )

    output_dir = args.output_dir.resolve()
    render_dir = output_dir / "render"
    audit_path = render_dir / "daily_snapshot_render_rows.csv"
    summary_path = render_dir / "daily_snapshot_render_summary.json"
    config_path = render_dir / "run_config.json"

    audit_rows = read_render_rows(audit_path) if args.resume else {}
    if audit_path.exists() and not args.resume and not args.force:
        raise ValueError("Checkpoint render sudah ada. Gunakan --resume atau --force.")
    if args.force and not args.resume:
        audit_rows = {}

    source_paths = validate_source_hashes(
        selected,
        raw_root=args.raw_root,
        run_config=manifest_run_config,
    )

    render_dir.mkdir(parents=True, exist_ok=True)
    run_config = {
        "schema_version": 1,
        "experiment_id": "E2.3",
        "stage": "DAILY_SNAPSHOT_RENDER",
        "renderer_version": RENDERER_VERSION,
        "training_performed": False,
        "inference_performed": False,
        "manifest_digest_sha256": digest,
        "manifest_path": str(args.manifest.resolve()),
        "raw_root": str(args.raw_root.resolve()),
        "output_dir": str(output_dir),
        "canonical_image": {
            "width": IMAGE_WIDTH,
            "height": IMAGE_HEIGHT,
            "style": "CHARLES_COMPATIBLE_WHITE",
            "up_color": "#006340",
            "down_color": "#a02128",
        },
        "source_hash_verification": True,
    }
    config_path.write_text(json.dumps(run_config, indent=2) + "\n", encoding="utf-8")

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        grouped[(str(row["timeframe"]), int(row["year"]))].append(row)

    completed = 0
    total = len(selected)
    checkpoint_every = int(getattr(args, "checkpoint_every", 250))
    progress_every = int(getattr(args, "progress_every", 25))
    if checkpoint_every < 1 or progress_every < 1:
        raise ValueError("Interval checkpoint/progress harus minimal 1.")

    for group_key in sorted(grouped):
        group_rows = grouped[group_key]
        relative_sources = sorted(
            {
                relative
                for row in group_rows
                for relative in str(row["source_paths"]).split("|")
            }
        )
        timestamps, candles = read_ohlcv_sources(
            source_paths[relative] for relative in relative_sources
        )

        for row in group_rows:
            snapshot_id = str(row["snapshot_id"])
            existing_audit = audit_rows.get(snapshot_id)
            target = _safe_output_path(output_dir, str(row["planned_image_path"]))
            if existing_audit and existing_audit.get("manifest_digest_sha256") != digest:
                raise ValueError(f"{snapshot_id}: checkpoint berasal dari manifest lain.")

            try:
                window = extract_chart_window(row, timestamps, candles)
                payload = render_candles_png(window)
                expected_hash = hashlib.sha256(payload).hexdigest()

                if (
                    existing_audit
                    and existing_audit.get("render_status") in {"RENDERED", "REUSED"}
                    and target.is_file()
                    and file_sha256(target) == existing_audit.get("image_sha256")
                    and existing_audit.get("image_sha256") == expected_hash
                ):
                    render_status = "REUSED"
                else:
                    if target.exists() and file_sha256(target) != expected_hash and not args.force:
                        raise ValueError(
                            "PNG existing berbeda dari render deterministik; gunakan --force."
                        )
                    if not target.exists() or file_sha256(target) != expected_hash:
                        _write_bytes_atomic(target, payload)
                    render_status = "RENDERED"

                audit = _base_render_row(row, manifest_digest_sha256=digest)
                audit.update(
                    {
                        "render_status": render_status,
                        "image_sha256": expected_hash,
                        "width": IMAGE_WIDTH,
                        "height": IMAGE_HEIGHT,
                    }
                )
            except Exception as error:
                audit = _base_render_row(row, manifest_digest_sha256=digest)
                audit.update({"render_status": "FAILED", "reason": str(error)})
                if args.fail_fast:
                    audit_rows[snapshot_id] = audit
                    write_render_rows(audit_path, audit_rows)
                    raise

            audit_rows[snapshot_id] = audit
            completed += 1
            if (
                completed % checkpoint_every == 0
                or completed == total
                or audit["render_status"] == "FAILED"
            ):
                write_render_rows(audit_path, audit_rows)
            if (
                completed == 1
                or completed % progress_every == 0
                or completed == total
                or audit["render_status"] == "FAILED"
            ):
                print(
                    f"[{completed}/{total}] {snapshot_id} -> "
                    f"{audit['render_status']}"
                )

    write_summary(
        summary_path,
        all_manifest_rows=rows,
        selected_rows=selected,
        audit_rows=audit_rows,
        manifest_digest_sha256=digest,
    )
    print(f"Rows: {audit_path}")
    print(f"Summary: {summary_path}")
    print(f"Images root: {output_dir / 'images'}")
    return {
        "audit_rows": audit_rows,
        "audit_path": audit_path,
        "summary_path": summary_path,
    }


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
