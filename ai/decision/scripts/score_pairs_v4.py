from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


KEY_CANDIDATES = [
    "image_id",
    "clean_image_path",
    "sample_id",
    "image_name",
    "image_path",
    "file",
    "file_name",
    "filename",
    "source_file",
    "label_file",
]

DIRECTION_CANDIDATES = [
    "predicted_direction",
    "direction",
    "ohlcv_direction",
    "setup_direction",
    "pair_direction",
]

SCORE_CANDIDATES = [
    "final_score_v3",
    "score_v3",
    "final_score",
    "pair_score",
    "score",
]

CNN_KEY_CANDIDATES = [
    "sample_id",
    "image_id",
    "image_name",
    "image_path",
    "clean_image_path",
    "file_name",
    "filename",
]


def find_column(
    dataframe: pd.DataFrame,
    candidates: list[str],
    label: str,
) -> str:
    for candidate in candidates:
        if candidate in dataframe.columns:
            return candidate

    raise ValueError(
        f"Kolom {label} tidak ditemukan. "
        f"Kandidat: {candidates}. "
        f"Kolom tersedia: {list(dataframe.columns)}"
    )


def normalize_sample_id(value: object) -> str:
    text = str(value).strip()

    if not text:
        return ""

    return Path(text).stem.lower()


def normalize_direction(value: object) -> str:
    text = str(value).strip().lower()

    if "bull" in text or text in {"buy", "long"}:
        return "bullish"

    if "bear" in text or text in {"sell", "short"}:
        return "bearish"

    return "uncertain"


def calculate_alignment(
    setup_direction: str,
    cnn_label: str,
) -> float:
    if setup_direction == "uncertain":
        return 0.50

    if cnn_label == setup_direction:
        return 1.00

    if cnn_label == "sideways":
        return 0.55

    if cnn_label == "unknown":
        return 0.50

    return 0.00


def classify_decision(
    score: float,
) -> tuple[str, str]:
    if score >= 0.75:
        return "HIGH", "ACCEPT"

    if score >= 0.60:
        return "MEDIUM", "REVIEW"

    if score >= 0.45:
        return "LOW", "WATCHLIST"

    return "REJECTED", "REJECT"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Gabungkan scoring v3 YOLO/OHLCV "
            "dengan konteks CNN ensemble."
        )
    )

    parser.add_argument(
        "--pairs",
        type=Path,
        default=Path(
            "ai/benchmarks/reports/"
            "yolo11s_pairing_v3/"
            "yolo11s_ob_fvg_pairs_v3.csv"
        ),
    )

    parser.add_argument(
        "--cnn",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "scoring_v4_results.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "SCORING_V4_SUMMARY.md"
        ),
    )

    parser.add_argument(
        "--base-weight",
        type=float,
        default=0.80,
    )

    parser.add_argument(
        "--cnn-weight",
        type=float,
        default=0.20,
    )

    args = parser.parse_args()

    if not args.pairs.exists():
        raise FileNotFoundError(
            f"File pairing tidak ditemukan: {args.pairs}"
        )

    if not args.cnn.exists():
        raise FileNotFoundError(
            f"File prediksi CNN tidak ditemukan: {args.cnn}"
        )

    if not np.isclose(
        args.base_weight + args.cnn_weight,
        1.0,
    ):
        raise ValueError(
            "Total base-weight dan cnn-weight harus 1.0"
        )

    pairs = pd.read_csv(args.pairs)
    cnn = pd.read_csv(args.cnn)

    pair_key_column = find_column(
        pairs,
        KEY_CANDIDATES,
        "identitas sample pairing",
    )

    cnn_key_column = find_column(
        cnn,
        CNN_KEY_CANDIDATES,
        "identitas sample CNN",
    )

    direction_column = find_column(
        pairs,
        DIRECTION_CANDIDATES,
        "arah setup",
    )

    score_column = find_column(
        pairs,
        SCORE_CANDIDATES,
        "scoring v3",
    )

    required_cnn_columns = {
        "cnn_label",
        "cnn_confidence",
    }

    missing_cnn_columns = (
        required_cnn_columns
        - set(cnn.columns)
    )

    if missing_cnn_columns:
        raise ValueError(
            f"Kolom CNN kurang: "
            f"{sorted(missing_cnn_columns)}"
        )

    pairs["_merge_key"] = (
        pairs[pair_key_column]
        .map(normalize_sample_id)
    )

    cnn["_merge_key"] = (
        cnn[cnn_key_column]
        .map(normalize_sample_id)
    )

    cnn_columns = [
        "_merge_key",
        "cnn_label",
        "cnn_confidence",
    ]

    optional_probability_columns = [
        "prob_bearish",
        "prob_bullish",
        "prob_sideways",
    ]

    for column in optional_probability_columns:
        if column in cnn.columns:
            cnn_columns.append(column)

    cnn_for_merge = (
        cnn[cnn_columns]
        .drop_duplicates(
            subset=["_merge_key"],
            keep="first",
        )
    )

    merged = pairs.merge(
        cnn_for_merge,
        on="_merge_key",
        how="left",
        validate="many_to_one",
    )

    merged["setup_direction_v4"] = (
        merged[direction_column]
        .map(normalize_direction)
    )

    merged["cnn_label"] = (
        merged["cnn_label"]
        .fillna("unknown")
        .astype(str)
        .str.lower()
        .str.strip()
    )

    merged["cnn_confidence"] = (
        pd.to_numeric(
            merged["cnn_confidence"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(0.0, 1.0)
    )

    merged["cnn_alignment"] = merged.apply(
        lambda row: calculate_alignment(
            row["setup_direction_v4"],
            row["cnn_label"],
        ),
        axis=1,
    )

    merged["cnn_context_score"] = (
        merged["cnn_alignment"]
        * (
            0.50
            + 0.50
            * merged["cnn_confidence"]
        )
    )

    base_score = (
        pd.to_numeric(
            merged[score_column],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(0.0, 1.0)
    )

    merged["base_score_v3"] = base_score

    merged["final_score_v4"] = (
        args.base_weight
        * merged["base_score_v3"]
        + args.cnn_weight
        * merged["cnn_context_score"]
    )

    opposite_mask = (
        (
            (merged["setup_direction_v4"] == "bullish")
            & (merged["cnn_label"] == "bearish")
        )
        |
        (
            (merged["setup_direction_v4"] == "bearish")
            & (merged["cnn_label"] == "bullish")
        )
    )

    strong_opposite_mask = (
        opposite_mask
        & (merged["cnn_confidence"] >= 0.70)
    )

    merged.loc[
        strong_opposite_mask,
        "final_score_v4",
    ] = np.minimum(
        merged.loc[
            strong_opposite_mask,
            "final_score_v4",
        ],
        0.59,
    )

    merged["final_score_v4"] = (
        merged["final_score_v4"]
        .clip(0.0, 1.0)
    )

    decisions = (
        merged["final_score_v4"]
        .map(classify_decision)
    )

    merged["quality_v4"] = [
        item[0]
        for item in decisions
    ]

    merged["decision_v4"] = [
        item[1]
        for item in decisions
    ]

    merged["cnn_missing"] = (
        merged["cnn_label"] == "unknown"
    )

    merged["direction_conflict"] = (
        opposite_mask
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    merged.drop(
        columns=["_merge_key"],
    ).to_csv(
        args.output,
        index=False,
    )

    decision_counts = (
        merged["decision_v4"]
        .value_counts()
        .reindex(
            [
                "ACCEPT",
                "REVIEW",
                "WATCHLIST",
                "REJECT",
            ],
            fill_value=0,
        )
    )

    summary_lines = [
        "# Scoring v4 Summary",
        "",
        "## Configuration",
        "",
        f"- Pairing source: {args.pairs}",
        f"- CNN source: {args.cnn}",
        f"- Base scoring v3 weight: {args.base_weight:.2f}",
        f"- CNN context weight: {args.cnn_weight:.2f}",
        "",
        "## Results",
        "",
        f"- Total pairs: {len(merged)}",
        (
            "- Average base score v3: "
            f"{merged['base_score_v3'].mean():.4f}"
        ),
        (
            "- Average final score v4: "
            f"{merged['final_score_v4'].mean():.4f}"
        ),
        (
            "- CNN matched samples: "
            f"{(~merged['cnn_missing']).sum()}"
        ),
        (
            "- CNN missing samples: "
            f"{merged['cnn_missing'].sum()}"
        ),
        (
            "- Direction conflicts: "
            f"{merged['direction_conflict'].sum()}"
        ),
        "",
        "## Decisions",
        "",
        "| Decision | Count |",
        "|---|---:|",
    ]

    for decision, count in decision_counts.items():
        summary_lines.append(
            f"| {decision} | {int(count)} |"
        )

    args.summary_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.summary_output.write_text(
        "\n".join(summary_lines),
        encoding="utf-8",
    )

    print("")
    print("Scoring v4 selesai")
    print(f"Total pairs      : {len(merged)}")
    print(
        f"Average v3       : "
        f"{merged['base_score_v3'].mean():.4f}"
    )
    print(
        f"Average v4       : "
        f"{merged['final_score_v4'].mean():.4f}"
    )
    print(
        f"CNN matched      : "
        f"{(~merged['cnn_missing']).sum()}"
    )
    print(
        f"CNN missing      : "
        f"{merged['cnn_missing'].sum()}"
    )
    print(
        f"Direction conflict: "
        f"{merged['direction_conflict'].sum()}"
    )
    print("")
    print(decision_counts.to_string())
    print("")
    print(f"CSV     : {args.output}")
    print(f"Summary : {args.summary_output}")


if __name__ == "__main__":
    main()


