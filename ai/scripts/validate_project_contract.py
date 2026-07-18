from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = PROJECT_ROOT / "config" / "project_contract.json"

EXPECTED_YOLO_CLASSES = [
    "order_block",
    "fair_value_gap",
]

REQUIRED_DERIVED_FEATURES = {
    "liquidity_level",
    "liquidity_sweep",
    "equal_high",
    "equal_low",
    "bos",
    "choch",
    "candle_pattern",
}

REQUIRED_PUBLIC_DECISIONS = {
    "BUY",
    "SELL",
    "WATCHLIST",
    "NO_TRADE",
}

REQUIRED_ENTRY_FIELDS = {
    "entry",
    "stop_loss",
    "take_profit",
    "risk_reward_ratio",
}

REQUIRED_EXCEL_SHEETS = {
    "Analyses",
    "Trade_Outcomes",
    "Model_Metadata",
    "Definitions",
}


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Project contract tidak ditemukan: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def _nested(data: dict[str, Any], *keys: str) -> Any:
    value: Any = data

    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]

    return value


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if _nested(contract, "project", "primary_pair") != "GBPUSD":
        errors.append("Primary pair wajib GBPUSD.")

    if _nested(contract, "project", "system_type") != "decision_support":
        errors.append("AI-TDSS wajib bertipe decision_support.")

    if _nested(contract, "project", "automatic_trade_execution") is not False:
        errors.append("Eksekusi trade otomatis wajib dinonaktifkan.")

    public_decisions = set(
        _nested(contract, "analysis_pipeline", "public_decisions") or []
    )
    if public_decisions != REQUIRED_PUBLIC_DECISIONS:
        errors.append(
            "Public decision wajib BUY, SELL, WATCHLIST, dan NO_TRADE."
        )

    entry_fields = set(
        _nested(contract, "analysis_pipeline", "entry_fields") or []
    )
    if not REQUIRED_ENTRY_FIELDS.issubset(entry_fields):
        errors.append("Kontrak entry/SL/TP/RR belum lengkap.")

    yolo = _nested(
        contract,
        "analysis_pipeline",
        "model_roles",
        "yolo",
    ) or {}

    if yolo.get("production_classes") != EXPECTED_YOLO_CLASSES:
        errors.append("Kelas YOLO produksi wajib hanya order_block dan fair_value_gap.")

    if yolo.get("annotated_image_required") is not True:
        errors.append("YOLO wajib menghasilkan annotated image untuk pengguna.")

    if yolo.get("direct_trade_decision_allowed") is not False:
        errors.append("YOLO tidak boleh mengambil keputusan trade secara langsung.")

    derived_features = set(
        _nested(
            contract,
            "analysis_pipeline",
            "model_roles",
            "ohlcv_rules",
            "derived_features",
        )
        or []
    )
    missing_features = REQUIRED_DERIVED_FEATURES - derived_features
    if missing_features:
        errors.append(
            "Fitur OHLCV wajib belum lengkap: "
            + ", ".join(sorted(missing_features))
        )

    decision_engine = _nested(
        contract,
        "analysis_pipeline",
        "model_roles",
        "decision_engine",
    ) or {}
    if decision_engine.get("requires_canonical_ohlcv_for_entry") is not True:
        errors.append("Entry wajib menggunakan canonical OHLCV.")

    journal = contract.get("journal", {})
    if journal.get("record_every_analysis") is not True:
        errors.append("Setiap hasil analisis wajib dicatat ke jurnal.")
    if journal.get("excel_export_required") is not True:
        errors.append("Jurnal wajib mendukung ekspor Excel.")
    if not REQUIRED_EXCEL_SHEETS.issubset(set(journal.get("excel_sheets", []))):
        errors.append("Sheet ekspor Excel belum lengkap.")

    incremental = contract.get("incremental_learning", {})
    if incremental.get("execution_location") != "local_laptop_only":
        errors.append("Training incremental wajib dijalankan di laptop lokal.")
    if incremental.get("raw_prediction_as_ground_truth") is not False:
        errors.append("Prediksi mentah tidak boleh menjadi ground truth.")
    if incremental.get("eligible_data_requires_verified_outcome") is not True:
        errors.append("Data training wajib memiliki outcome terverifikasi.")
    if incremental.get("yolo_update_requires_reviewed_bounding_boxes") is not True:
        errors.append("Update YOLO wajib memakai bounding box yang direview.")

    triggers = incremental.get("triggers", {})
    preferred = int(triggers.get("preferred_batch_size", 0))
    minimum = int(triggers.get("minimum_batch_size", 0))
    maximum_days = int(triggers.get("maximum_interval_days", 0))
    drift_threshold = float(triggers.get("drift_score_threshold", -1.0))

    if minimum <= 0 or preferred < minimum:
        errors.append("Ukuran batch trigger incremental tidak valid.")
    if maximum_days <= 0:
        errors.append("Interval incremental wajib lebih dari nol hari.")
    if not 0.0 <= drift_threshold <= 1.0:
        errors.append("Drift threshold wajib berada pada rentang 0-1.")

    return errors


def _python_class_names(path: Path) -> list[str] | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        if not any(
            isinstance(target, ast.Name) and target.id == "CLASS_NAMES"
            for target in node.targets
        ):
            continue

        value = ast.literal_eval(node.value)
        if not isinstance(value, dict):
            return None

        return [value[key] for key in sorted(value)]

    return None


def _metadata_class_names(path: Path) -> list[str]:
    class_names: list[str] = []
    in_classes = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line == "classes:":
            in_classes = True
            continue

        if not in_classes:
            continue

        if raw_line and not raw_line.startswith(" "):
            break

        stripped = raw_line.strip()
        if not stripped:
            continue

        _, name = stripped.split(":", maxsplit=1)
        class_names.append(name.strip())

    return class_names


def validate_repository_scope(project_root: Path = PROJECT_ROOT) -> list[str]:
    errors: list[str] = []

    metadata_path = project_root / "ai" / "datasets" / "metadata" / "class_mapping.yaml"
    metadata_classes = _metadata_class_names(metadata_path)
    if metadata_classes != EXPECTED_YOLO_CLASSES:
        errors.append("Metadata class mapping tidak sama dengan scope YOLO produksi.")

    sample_classes_path = (
        project_root
        / "ai"
        / "datasets"
        / "annotation"
        / "samples"
        / "labels"
        / "classes.txt"
    )
    sample_classes = [
        line.strip()
        for line in sample_classes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if sample_classes != EXPECTED_YOLO_CLASSES:
        errors.append("Sample classes.txt tidak sama dengan scope YOLO produksi.")

    script_paths = [
        project_root
        / "ai"
        / "datasets"
        / "annotation"
        / "tools"
        / "build_cumulative_yolo_2020_2024.py",
        project_root
        / "ai"
        / "datasets"
        / "annotation"
        / "tools"
        / "build_incremental_yolo_dataset.py",
    ]

    for script_path in script_paths:
        script_classes = _python_class_names(script_path)
        if script_classes != EXPECTED_YOLO_CLASSES:
            errors.append(
                f"{script_path.name} tidak sama dengan scope YOLO produksi."
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validasi kontrak kanonis proyek AI-TDSS."
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
    )
    args = parser.parse_args()

    contract = load_contract(args.contract)
    errors = validate_contract(contract)
    errors.extend(validate_repository_scope())

    if errors:
        print("Project contract INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Project contract VALID")
    print(f"Contract: {args.contract}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
