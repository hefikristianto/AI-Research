from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def as_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )


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


def rr_adjustment(value: object) -> float:
    rr = pd.to_numeric(
        value,
        errors="coerce",
    )

    if pd.isna(rr):
        return 0.00

    rr = float(rr)

    if rr >= 3.0:
        return 0.04

    if rr >= 2.0:
        return 0.03

    if rr >= 1.5:
        return 0.01

    if rr >= 1.0:
        return -0.03

    return -0.05


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "ai/risk/reports/"
            "pairs_risk_v7_3.csv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "scoring_v7_1_results.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "SCORING_V7_1_SUMMARY.md"
        ),
    )

    args = parser.parse_args()

    dataframe = pd.read_csv(
        args.input
    ).copy()

    # Rebuild internal DataFrame blocks before adding
    # scoring columns.
    dataframe = dataframe.copy(deep=True)

    required = {
        "final_score_v6_1",
        "rr_ratio_v7",
        "zone_invalidated_v7",
        "entry_feasibility_v7",
        "target_price_v7",
    }

    missing = (
        required
        - set(dataframe.columns)
    )

    if missing:
        raise ValueError(
            f"Kolom kurang: {sorted(missing)}"
        )

    dataframe["base_score_v7_1"] = (
        pd.to_numeric(
            dataframe["final_score_v6_1"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(0.0, 1.0)
    )

    dataframe["rr_adjustment_v7_1"] = (
        dataframe["rr_ratio_v7"]
        .map(rr_adjustment)
    )

    invalidated = as_bool(
        dataframe[
            "zone_invalidated_v7"
        ]
    )

    dataframe[
        "invalidation_adjustment_v7_1"
    ] = np.where(
        invalidated,
        -0.10,
        0.00,
    )

    entry_status = (
        dataframe[
            "entry_feasibility_v7"
        ]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    dataframe[
        "entry_distance_adjustment_v7_1"
    ] = 0.00

    dataframe.loc[
        entry_status.eq("far"),
        "entry_distance_adjustment_v7_1",
    ] = -0.01

    dataframe.loc[
        entry_status.eq("very_far"),
        "entry_distance_adjustment_v7_1",
    ] = -0.02

    dataframe.loc[
        entry_status.eq("invalidated"),
        "entry_distance_adjustment_v7_1",
    ] = 0.00

    dataframe["final_score_v7_1"] = (
        dataframe["base_score_v7_1"]
        + dataframe[
            "rr_adjustment_v7_1"
        ]
        + dataframe[
            "invalidation_adjustment_v7_1"
        ]
        + dataframe[
            "entry_distance_adjustment_v7_1"
        ]
    ).clip(0.0, 1.0)

    decisions = (
        dataframe["final_score_v7_1"]
        .map(classify_decision)
    )

    dataframe["quality_v7_1"] = [
        item[0]
        for item in decisions
    ]

    dataframe["decision_v7_1"] = [
        item[1]
        for item in decisions
    ]

    dataframe["rank_v7_1"] = (
        dataframe["final_score_v7_1"]
        .rank(
            method="first",
            ascending=False,
        )
        .astype(int)
    )

    dataframe = dataframe.sort_values(
        "rank_v7_1"
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        args.output,
        index=False,
    )

    decision_counts = (
        dataframe["decision_v7_1"]
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

    valid_targets = (
        pd.to_numeric(
            dataframe["target_price_v7"],
            errors="coerce",
        )
        .notna()
    )

    lines = [
        "# Scoring v7.1 Summary",
        "",
        "## Method",
        "",
        (
            "Scoring v7.1 uses scoring v6.1 as "
            "the base and applies bounded risk and "
            "reward adjustments."
        ),
        "",
        "## Rules",
        "",
        "- Missing RR target: neutral",
        "- RR below 1.0: -0.05",
        "- RR 1.0 to 1.5: -0.03",
        "- RR 1.5 to 2.0: +0.01",
        "- RR 2.0 to 3.0: +0.03",
        "- RR at least 3.0: +0.04",
        "- Invalidated zone: -0.10",
        "- Far entry: -0.01",
        "- Very far entry: -0.02",
        "",
        "## Results",
        "",
        f"- Total setups: {len(dataframe)}",
        (
            "- Average scoring v6.1: "
            f"{dataframe['final_score_v6_1'].mean():.4f}"
        ),
        (
            "- Average scoring v7.1: "
            f"{dataframe['final_score_v7_1'].mean():.4f}"
        ),
        (
            "- Valid RR targets: "
            f"{int(valid_targets.sum())}"
        ),
        (
            "- Invalidated zones: "
            f"{int(invalidated.sum())}"
        ),
        "",
        "| Decision | Count |",
        "|---|---:|",
    ]

    for decision, count in (
        decision_counts.items()
    ):
        lines.append(
            f"| {decision} | {int(count)} |"
        )

    args.summary_output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("")
    print("Scoring v7.1 selesai")
    print(
        f"Average v6.1 : "
        f"{dataframe['final_score_v6_1'].mean():.4f}"
    )
    print(
        f"Average v7.1 : "
        f"{dataframe['final_score_v7_1'].mean():.4f}"
    )
    print(
        f"Valid targets: "
        f"{int(valid_targets.sum())}"
    )
    print(
        f"Invalidated  : "
        f"{int(invalidated.sum())}"
    )
    print("")
    print(decision_counts.to_string())
    print("")
    print(f"CSV     : {args.output}")
    print(f"Summary : {args.summary_output}")


if __name__ == "__main__":
    main()


