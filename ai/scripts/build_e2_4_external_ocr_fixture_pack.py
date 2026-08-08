from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PIL import Image

from ai.scripts.benchmark_e2_4_price_axis_ocr import DEFAULT_CONTRACT
from ai.scripts.benchmark_e2_4_price_axis_ocr import FORBIDDEN_OUTCOME_KEYS
from ai.scripts.benchmark_e2_4_price_axis_ocr import file_sha256
from ai.scripts.benchmark_e2_4_price_axis_ocr import read_json
from ai.scripts.benchmark_e2_4_price_axis_ocr import validate_contract
from ai.scripts.benchmark_e2_4_price_axis_ocr import validate_manifest


BUILDER_VERSION = "1.0.0"
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy reviewed TradingView/MT5 screenshots into a portable "
            "E2.4.1 fixture pack and freeze each image by SHA256."
        )
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        required=True,
        help="Reviewed external annotation JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New local fixture-pack directory.",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="Registered E2.4.1 benchmark contract.",
    )
    return parser.parse_args()


def _forbidden_keys(payload: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_OUTCOME_KEYS:
                found.add(normalized)
            found.update(_forbidden_keys(value))
    elif isinstance(payload, list):
        for value in payload:
            found.update(_forbidden_keys(value))
    return found


def _source_image(
    annotations_path: Path,
    raw_path: Any,
) -> Path:
    path = Path(str(raw_path or ""))
    if not path.is_absolute():
        path = annotations_path.resolve().parent / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Screenshot fixture tidak ditemukan: {path}")
    if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
        raise ValueError(f"Format screenshot fixture tidak didukung: {path}")
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as error:
        raise ValueError(f"Screenshot fixture rusak: {path}: {error}") from error
    return path


def build_pack(
    *,
    annotations_path: Path,
    output_dir: Path,
    contract_path: Path = DEFAULT_CONTRACT,
) -> Path:
    contract = read_json(contract_path.resolve())
    contract_errors = validate_contract(contract)
    if contract_errors:
        raise ValueError(
            "Contract E2.4.1 INVALID: " + "; ".join(contract_errors)
        )

    annotations_path = annotations_path.resolve()
    annotations = read_json(annotations_path)
    forbidden = _forbidden_keys(annotations)
    if forbidden:
        raise ValueError(
            "Annotation mengandung field outcome trading terlarang: "
            + ", ".join(sorted(forbidden))
        )
    if annotations.get("schema_version") != 1:
        raise ValueError("Annotation schema_version harus 1.")
    if annotations.get("experiment_id") != "E2.4.1":
        raise ValueError("Annotation experiment_id harus E2.4.1.")
    if annotations.get("trading_outcome_data_used") is not False:
        raise ValueError("Annotation tidak boleh memakai outcome trading.")

    fixture_set_id = str(annotations.get("fixture_set_id", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", fixture_set_id):
        raise ValueError("fixture_set_id annotation tidak valid.")
    annotation_fixtures = annotations.get("fixtures")
    if not isinstance(annotation_fixtures, list) or not annotation_fixtures:
        raise ValueError("Annotation fixtures harus list non-empty.")

    output_dir = output_dir.resolve()
    manifest_path = output_dir / "e2_4_1_fixture_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(
            "Fixture pack sudah ada; pilih output directory baru: "
            f"{manifest_path}"
        )
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    fixtures: list[dict[str, Any]] = []
    for index, annotation in enumerate(annotation_fixtures):
        if not isinstance(annotation, dict):
            raise ValueError(f"fixtures[{index}] harus object.")
        fixture_id = str(annotation.get("fixture_id", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", fixture_id):
            raise ValueError(f"fixtures[{index}].fixture_id tidak valid.")
        source = _source_image(
            annotations_path,
            annotation.get("source_image_path"),
        )
        target = images_dir / f"{fixture_id}{source.suffix.lower()}"
        if target.exists():
            raise FileExistsError(f"Target fixture sudah ada: {target}")
        shutil.copyfile(source, target)

        fixture = {
            key: value
            for key, value in annotation.items()
            if key != "source_image_path"
        }
        fixture.update(
            {
                "fixture_id": fixture_id,
                "fixture_source": "EXTERNAL_REVIEWED",
                "external_reviewed": True,
                "image_path": target.relative_to(output_dir).as_posix(),
                "image_sha256": file_sha256(target),
                "tick_metric_eligible": bool(
                    annotation.get("tick_metric_eligible", True)
                ),
                "outcome_data_used": False,
            }
        )
        fixtures.append(fixture)

    manifest = {
        "schema_version": 1,
        "experiment_id": "E2.4.1",
        "fixture_set_id": fixture_set_id,
        "builder_version": BUILDER_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "annotation_manifest_sha256": file_sha256(annotations_path),
        "fixture_root": ".",
        "trading_outcome_data_used": False,
        "production_decision_changed": False,
        "fixtures": fixtures,
    }
    errors = validate_manifest(manifest, contract, manifest_path)
    if errors:
        raise ValueError("External fixture pack INVALID: " + "; ".join(errors))

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"External fixtures: {len(fixtures)}")
    print(f"Manifest: {manifest_path}")
    print(f"Images: {images_dir}")
    return manifest_path


def run(args: argparse.Namespace | SimpleNamespace) -> Path:
    return build_pack(
        annotations_path=args.annotations,
        output_dir=args.output_dir,
        contract_path=args.contract,
    )


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
