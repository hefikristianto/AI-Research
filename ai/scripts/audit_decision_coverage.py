from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import mimetypes
import random
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.decision_coverage_audit_service import (  # noqa: E402
    DecisionCoverageAuditService,
)


DEFAULT_METADATA = (
    PROJECT_ROOT
    / "ai"
    / "datasets"
    / "metadata"
    / "chart_image_metadata.csv"
)
DEFAULT_IMAGE_ROOT = (
    PROJECT_ROOT
    / "ai"
    / "datasets"
    / "raw"
    / "charts"
)


class AuditRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit decision coverage through the running local "
            "AI-TDSS full-analysis endpoint. This script does not train models."
        )
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Running AI-TDSS backend URL.",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA,
        help="Chart metadata CSV.",
    )
    parser.add_argument(
        "--images-root",
        type=Path,
        default=DEFAULT_IMAGE_ROOT,
        help="Root containing PAIR/TIMEFRAME/YEAR chart images.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Evaluation year. The canonical final test year is 2025.",
    )
    parser.add_argument(
        "--pair",
        dest="pairs",
        action="append",
        help="Pair filter. Repeat for multiple pairs. Default: GBPUSD.",
    )
    parser.add_argument(
        "--timeframe",
        dest="timeframes",
        action="append",
        help="Timeframe filter. Repeat as needed. Default: all available.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="Deterministic random sample size; 0 processes all selected rows.",
    )
    parser.add_argument(
        "--image-id",
        dest="image_ids",
        action="append",
        help=(
            "Exact metadata image_id untuk targeted review. "
            "Ulangi argumen untuk beberapa kasus."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Sampling seed.",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.25,
        help="YOLO request threshold. Keep 0.25 for the locked baseline.",
    )
    parser.add_argument(
        "--chart-candles",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--context-candles",
        type=int,
        default=300,
    )
    parser.add_argument(
        "--utc-offset",
        type=float,
        default=0.0,
        help="UTC offset associated with chart timestamps.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=300.0,
        help="Per-image HTTP timeout.",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=5,
        help="Stop after this many consecutive request errors; 0 disables.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Local output folder. Defaults under local_artifacts/.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an existing output directory and skip completed image IDs.",
    )
    parser.add_argument(
        "--include-annotated-chart",
        action="store_true",
        help="Request base64 annotated images. Disabled by default for batch speed.",
    )
    parser.add_argument(
        "--review-pack",
        action="store_true",
        help=(
            "Simpan full response JSON dan annotated PNG untuk setiap "
            "kasus terpilih. Opsi ini otomatis meminta annotated chart."
        ),
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip the initial /health request.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.sample_size < 0:
        raise ValueError("--sample-size tidak boleh negatif.")
    if not 0.001 <= args.confidence_threshold <= 1.0:
        raise ValueError("--confidence-threshold harus berada pada 0.001..1.0.")
    if not 30 <= args.chart_candles <= 500:
        raise ValueError("--chart-candles harus berada pada 30..500.")
    if not 100 <= args.context_candles <= 2000:
        raise ValueError("--context-candles harus berada pada 100..2000.")
    if not -12.0 <= args.utc_offset <= 14.0:
        raise ValueError("--utc-offset harus berada pada -12..14.")
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds harus lebih dari nol.")
    if args.max_errors < 0:
        raise ValueError("--max-errors tidak boleh negatif.")
    if args.image_ids and args.sample_size:
        raise ValueError(
            "--image-id tidak boleh digabung dengan --sample-size."
        )


def read_metadata(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Metadata tidak ditemukan: {path}")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    required = {
        "image_id",
        "file_name",
        "pair",
        "timeframe",
        "year",
        "end_datetime",
    }
    missing = required.difference(rows[0].keys() if rows else set())
    if missing:
        raise ValueError(
            "Kolom metadata tidak lengkap: " + ", ".join(sorted(missing))
        )

    return rows


def select_samples(
    metadata_rows: list[dict[str, str]],
    *,
    images_root: Path,
    year: int,
    pairs: list[str],
    timeframes: list[str],
    sample_size: int,
    seed: int,
    image_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    pair_filter = {value.upper() for value in pairs}
    timeframe_filter = {value.upper() for value in timeframes}
    image_id_filter = {
        value.upper()
        for value in (image_ids or [])
    }

    selected: list[dict[str, Any]] = []
    for row in metadata_rows:
        pair = row.get("pair", "").upper()
        timeframe = row.get("timeframe", "").upper()
        row_year = row.get("year", "")
        image_id = row.get("image_id", "")

        if row_year != str(year):
            continue
        if pair_filter and pair not in pair_filter:
            continue
        if timeframe_filter and timeframe not in timeframe_filter:
            continue
        if (
            image_id_filter
            and image_id.upper()
            not in image_id_filter
        ):
            continue

        image_path = (
            images_root
            / pair
            / timeframe
            / row_year
            / row.get("file_name", "")
        )
        selected.append(
            {
                "image_id": image_id,
                "file_name": row.get("file_name", ""),
                "image_path": str(image_path.resolve()),
                "pair": pair,
                "timeframe": timeframe,
                "year": row_year,
                "chart_datetime": row.get("end_datetime", ""),
            }
        )

    if image_id_filter:
        selected_ids = {
            str(item["image_id"]).upper()
            for item in selected
        }
        missing_ids = sorted(
            image_id_filter
            - selected_ids
        )
        if missing_ids:
            raise ValueError(
                "Image ID tidak ditemukan dalam filter aktif: "
                + ", ".join(missing_ids)
            )

    selected.sort(
        key=lambda item: (
            item["pair"],
            item["timeframe"],
            item["chart_datetime"],
            item["file_name"],
        )
    )

    if sample_size and sample_size < len(selected):
        selected = random.Random(seed).sample(selected, sample_size)
        selected.sort(
            key=lambda item: (
                item["pair"],
                item["timeframe"],
                item["chart_datetime"],
                item["file_name"],
            )
        )

    return selected


def sample_digest(samples: list[dict[str, Any]]) -> str:
    payload = "\n".join(str(sample.get("image_id", "")) for sample in samples)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_lineage() -> dict[str, Any]:
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {
            "git_commit": None,
            "git_dirty": None,
        }

    commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None
    dirty = None
    if status_result.returncode == 0:
        dirty = bool(status_result.stdout.strip())

    return {
        "git_commit": commit,
        "git_dirty": dirty,
    }


def dataset_lineage() -> dict[str, Any]:
    version_path = (
        PROJECT_ROOT / "ai" / "datasets" / "metadata" / "dataset_version.json"
    )
    if not version_path.exists():
        return {
            "dataset_version": None,
            "dataset_status": None,
        }

    try:
        payload = json.loads(version_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {
            "dataset_version": None,
            "dataset_status": None,
        }

    return {
        "dataset_version": payload.get("version"),
        "dataset_status": payload.get("status"),
    }


def default_output_dir(pairs: list[str], year: int) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pair_name = "-".join(pairs).lower() or "all-pairs"
    return (
        PROJECT_ROOT
        / "local_artifacts"
        / "decision_coverage"
        / f"{pair_name}_{year}_{timestamp}"
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _artifact_stem(value: str) -> str:
    stem = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        value,
    ).strip("._")
    return stem or "unnamed_case"


def persist_review_artifacts(
    output_dir: Path,
    sample: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    stem = _artifact_stem(
        str(sample.get("image_id", ""))
    )
    responses_dir = (
        output_dir
        / "review_pack"
        / "responses"
    )
    annotated_dir = (
        output_dir
        / "review_pack"
        / "annotated"
    )
    responses_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    annotated_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    response_path = (
        responses_dir
        / f"{stem}.json"
    )
    write_json(response_path, payload)

    annotated_chart = payload.get(
        "annotated_chart"
    )
    if not isinstance(annotated_chart, dict):
        annotated_chart = {}

    result: dict[str, Any] = {
        "response_json_path": response_path.relative_to(
            output_dir
        ).as_posix(),
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
    }

    if annotated_chart.get("status") != "RENDERED":
        result["review_artifact_error"] = (
            "Annotated chart tidak berstatus RENDERED."
        )
        return result

    data_url = str(
        annotated_chart.get("data_url", "")
    )
    prefix = "data:image/png;base64,"
    if not data_url.startswith(prefix):
        result["review_artifact_error"] = (
            "Annotated chart tidak memiliki PNG base64 data URL."
        )
        return result

    try:
        image_bytes = base64.b64decode(
            data_url[len(prefix) :],
            validate=True,
        )
    except (ValueError, TypeError) as error:
        result["review_artifact_error"] = (
            "Annotated chart gagal didekode: "
            + str(error)
        )
        return result

    annotated_path = (
        annotated_dir
        / f"{stem}.png"
    )
    annotated_path.write_bytes(image_bytes)
    actual_sha256 = hashlib.sha256(
        image_bytes
    ).hexdigest()
    expected_sha256 = str(
        annotated_chart.get("sha256", "")
    )

    result["annotated_chart_path"] = (
        annotated_path.relative_to(
            output_dir
        ).as_posix()
    )
    result[
        "annotated_chart_sha256_verified"
    ] = int(
        bool(expected_sha256)
        and actual_sha256
        == expected_sha256
    )

    if (
        expected_sha256
        and actual_sha256
        != expected_sha256
    ):
        result["review_artifact_error"] = (
            "SHA256 annotated chart tidak cocok."
        )

    return result


def read_existing_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _safe_filename(value: str) -> str:
    return value.replace('"', "").replace("\r", "").replace("\n", "")


def multipart_body(
    *,
    image_path: Path,
    boundary: str,
) -> tuple[bytes, str]:
    media_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    filename = _safe_filename(image_path.name)
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {media_type}\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return prefix + image_path.read_bytes() + suffix, media_type


def _error_message(body: bytes, fallback: str) -> str:
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return fallback

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text[:1000]

    if isinstance(payload, dict) and payload.get("detail"):
        return str(payload["detail"])
    return text[:1000]


def check_health(base_url: str, timeout_seconds: float) -> None:
    url = base_url.rstrip("/") + "/health"
    request = Request(url, method="GET")

    try:
        with urlopen(request, timeout=min(timeout_seconds, 30.0)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise AuditRequestError(
            f"Backend health check gagal pada {url}: {error}"
        ) from error

    if not isinstance(payload, dict) or payload.get("status") != "healthy":
        raise AuditRequestError(f"Respons health check tidak valid: {payload}")


def request_analysis(
    *,
    base_url: str,
    sample: dict[str, Any],
    confidence_threshold: float,
    chart_candles: int,
    context_candles: int,
    utc_offset: float,
    include_annotated_chart: bool,
    timeout_seconds: float,
) -> tuple[dict[str, Any], int]:
    query = urlencode(
        {
            "confidence_threshold": confidence_threshold,
            "pair": sample["pair"],
            "timeframe": sample["timeframe"],
            "chart_datetime": sample["chart_datetime"],
            "chart_candles": chart_candles,
            "context_candles": context_candles,
            "market_utc_offset_hours": utc_offset,
            "include_annotated_chart": str(include_annotated_chart).lower(),
        }
    )
    url = base_url.rstrip("/") + "/api/analysis/full?" + query
    image_path = Path(sample["image_path"])
    boundary = "----AITDSSAudit" + uuid.uuid4().hex
    body, _ = multipart_body(image_path=image_path, boundary=boundary)
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "AI-TDSS-decision-coverage-audit/1",
        },
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = int(response.status)
            raw = response.read()
    except HTTPError as error:
        raw = error.read()
        raise AuditRequestError(
            _error_message(raw, str(error)),
            status_code=error.code,
        ) from error
    except (URLError, TimeoutError) as error:
        raise AuditRequestError(str(error)) from error

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise AuditRequestError(
            "Backend mengembalikan JSON yang tidak valid."
        ) from error

    if not isinstance(payload, dict):
        raise AuditRequestError("Payload full analysis bukan JSON object.")

    return payload, status


def build_run_configuration(
    args: argparse.Namespace,
    *,
    pairs: list[str],
    timeframes: list[str],
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    configuration = {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url.rstrip("/"),
        "metadata": str(args.metadata.resolve()),
        "images_root": str(args.images_root.resolve()),
        "year": args.year,
        "pairs": pairs,
        "timeframes": timeframes,
        "sample_size_requested": args.sample_size,
        "image_ids_requested": sorted(
            args.image_ids or []
        ),
        "selected_images": len(samples),
        "sample_seed": args.seed,
        "sample_digest_sha256": sample_digest(samples),
        "confidence_threshold": args.confidence_threshold,
        "chart_candles": args.chart_candles,
        "context_candles": args.context_candles,
        "utc_offset": args.utc_offset,
        "include_annotated_chart": bool(
            args.include_annotated_chart
            or args.review_pack
        ),
        "review_pack": bool(
            args.review_pack
        ),
        "metadata_sha256": file_sha256(args.metadata),
        "project_contract_sha256": file_sha256(
            PROJECT_ROOT / "config" / "project_contract.json"
        ),
        "ensemble_config_sha256": file_sha256(
            PROJECT_ROOT
            / "ai"
            / "classification"
            / "models"
            / "ensemble"
            / "ensemble_config.json"
        ),
        "training_performed": False,
    }
    configuration.update(git_lineage())
    configuration.update(dataset_lineage())
    return configuration


def ensure_resume_compatible(
    existing: dict[str, Any],
    current: dict[str, Any],
) -> None:
    keys = (
        "schema_version",
        "year",
        "pairs",
        "timeframes",
        "sample_digest_sha256",
        "confidence_threshold",
        "chart_candles",
        "context_candles",
        "utc_offset",
        "image_ids_requested",
        "include_annotated_chart",
        "review_pack",
    )
    mismatched = [key for key in keys if existing.get(key) != current.get(key)]
    if mismatched:
        raise ValueError(
            "Konfigurasi --resume berbeda pada: " + ", ".join(mismatched)
        )


def persist_summary(
    output_dir: Path,
    rows: list[dict[str, Any]],
    run_configuration: dict[str, Any],
) -> None:
    summary = DecisionCoverageAuditService.summarize(rows, run_configuration)
    write_json(output_dir / "decision_coverage_summary.json", summary)
    (output_dir / "decision_coverage_summary.md").write_text(
        DecisionCoverageAuditService.render_markdown(summary),
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> int:
    validate_args(args)
    pairs = sorted({value.upper() for value in (args.pairs or ["GBPUSD"])})
    timeframes = sorted(
        {value.upper() for value in (args.timeframes or ["M5", "M15", "H1", "H4"])}
    )

    metadata_rows = read_metadata(args.metadata)
    samples = select_samples(
        metadata_rows,
        images_root=args.images_root,
        year=args.year,
        pairs=pairs,
        timeframes=timeframes,
        sample_size=args.sample_size,
        seed=args.seed,
        image_ids=args.image_ids,
    )
    if not samples:
        raise ValueError("Tidak ada metadata yang cocok dengan filter audit.")

    output_dir = args.output_dir or default_output_dir(pairs, args.year)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows_path = output_dir / "decision_coverage_rows.csv"
    config_path = output_dir / "run_config.json"
    run_configuration = build_run_configuration(
        args,
        pairs=pairs,
        timeframes=timeframes,
        samples=samples,
    )

    if rows_path.exists() and not args.resume:
        raise FileExistsError(
            "Output sudah berisi rows CSV. "
            "Gunakan --resume atau folder baru: "
            f"{rows_path}"
        )

    if args.resume and config_path.exists():
        existing_config = json.loads(config_path.read_text(encoding="utf-8"))
        ensure_resume_compatible(existing_config, run_configuration)
        run_configuration["created_at_utc"] = existing_config.get(
            "created_at_utc",
            run_configuration["created_at_utc"],
        )

    write_json(config_path, run_configuration)

    existing_rows = read_existing_rows(rows_path)
    completed_ids = {
        str(row.get("image_id", ""))
        for row in existing_rows
        if row.get("image_id")
    }

    if not args.skip_health_check:
        check_health(args.base_url, args.timeout_seconds)

    pending = [
        sample for sample in samples if sample["image_id"] not in completed_ids
    ]
    print(
        f"Selected: {len(samples)} | "
        f"Existing: {len(existing_rows)} | "
        f"Pending: {len(pending)}"
    )
    print(f"Output: {output_dir}")

    new_file = not rows_path.exists()
    consecutive_errors = 0
    interrupted = False
    stopped_due_to_errors = False

    with rows_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=DecisionCoverageAuditService.CSV_FIELDS,
            extrasaction="ignore",
        )
        if new_file:
            writer.writeheader()
            handle.flush()

        try:
            for index, sample in enumerate(pending, start=1):
                image_path = Path(sample["image_path"])
                prefix = f"[{index}/{len(pending)}] {sample['file_name']}"

                if not image_path.exists():
                    row = DecisionCoverageAuditService.error_row(
                        sample,
                        request_status="IMAGE_MISSING",
                        error=f"Image tidak ditemukan: {image_path}",
                    )
                    writer.writerow(row)
                    handle.flush()
                    print(prefix + " -> IMAGE_MISSING")
                    continue

                started = time.perf_counter()
                try:
                    payload, http_status = request_analysis(
                        base_url=args.base_url,
                        sample=sample,
                        confidence_threshold=args.confidence_threshold,
                        chart_candles=args.chart_candles,
                        context_candles=args.context_candles,
                        utc_offset=args.utc_offset,
                        include_annotated_chart=bool(
                            args.include_annotated_chart
                            or args.review_pack
                        ),
                        timeout_seconds=args.timeout_seconds,
                    )
                    latency_ms = (time.perf_counter() - started) * 1000.0
                    row = DecisionCoverageAuditService.success_row(
                        sample,
                        payload,
                        latency_ms=latency_ms,
                        http_status=http_status,
                    )
                    if args.review_pack:
                        try:
                            row.update(
                                persist_review_artifacts(
                                    output_dir,
                                    sample,
                                    payload,
                                )
                            )
                        except (OSError, ValueError, TypeError) as error:
                            row["review_artifact_error"] = (
                                "Review artifact gagal disimpan: "
                                + str(error)
                            )
                    consecutive_errors = 0
                    print(
                        prefix
                        + " -> "
                        + str(row["decision"])
                        + f" | det={row['detection_count']}"
                        + f" pair={row['pair_count']}"
                        + f" | {latency_ms:.0f} ms"
                    )

                except AuditRequestError as error:
                    latency_ms = (time.perf_counter() - started) * 1000.0
                    row = DecisionCoverageAuditService.error_row(
                        sample,
                        request_status="REQUEST_ERROR",
                        error=str(error),
                        latency_ms=latency_ms,
                        http_status=error.status_code,
                    )
                    consecutive_errors += 1
                    print(prefix + f" -> REQUEST_ERROR: {error}")

                writer.writerow(row)
                handle.flush()

                if (
                    args.max_errors
                    and consecutive_errors >= args.max_errors
                ):
                    stopped_due_to_errors = True
                    print(
                        "Audit dihentikan setelah "
                        f"{consecutive_errors} request error berturut-turut."
                    )
                    break

        except KeyboardInterrupt:
            interrupted = True
            print("\nAudit dihentikan pengguna; checkpoint tetap disimpan.")

    all_rows = read_existing_rows(rows_path)
    run_configuration["interrupted"] = interrupted
    run_configuration["stopped_due_to_errors"] = stopped_due_to_errors
    run_configuration["processed_rows"] = len(all_rows)
    run_configuration["finished_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()
    write_json(config_path, run_configuration)
    persist_summary(output_dir, all_rows, run_configuration)

    print(f"Rows: {rows_path}")
    print(f"Summary: {output_dir / 'decision_coverage_summary.md'}")
    if args.review_pack:
        print(
            "Review pack: "
            f"{output_dir / 'review_pack'}"
        )
    if interrupted:
        print("Jalankan ulang command yang sama dengan --resume untuk melanjutkan.")
        return 130

    if stopped_due_to_errors:
        print("Perbaiki backend lalu lanjutkan dengan --resume.")
        return 3

    return 0


def main() -> int:
    try:
        return run(parse_args())
    except (AuditRequestError, FileNotFoundError, FileExistsError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
