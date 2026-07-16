from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


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
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "ai/structure/reports/"
            "pairs_structure_enriched.csv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "scoring_v5_results.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "SCORING_V5_SUMMARY.md"
        ),
    )

    args = parser.parse_args()

    dataframe = pd.read_csv(
        args.input
    )

    required = {
        "final_score_v4",
        "liquidity_score_v5",
        "market_structure_score_v5",
        "zone_score_v5",
    }

    missing = required - set(
        dataframe.columns
    )

    if missing:
        raise ValueError(
            f"Kolom kurang: {sorted(missing)}"
        )

    dataframe["score_v4_component"] = (
        pd.to_numeric(
            dataframe["final_score_v4"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(0.0, 1.0)
    )

    dataframe["liquidity_component_v5"] = (
        pd.to_numeric(
            dataframe["liquidity_score_v5"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(0.0, 1.0)
    )

    dataframe["structure_component_v5"] = (
        pd.to_numeric(
            dataframe[
                "market_structure_score_v5"
            ],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(0.0, 1.0)
    )

    dataframe["zone_component_v5"] = (
        pd.to_numeric(
            dataframe["zone_score_v5"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(0.0, 1.0)
    )

    dataframe["final_score_v5"] = (
        0.70
        * dataframe["score_v4_component"]
        + 0.12
        * dataframe["liquidity_component_v5"]
        + 0.10
        * dataframe["structure_component_v5"]
        + 0.08
        * dataframe["zone_component_v5"]
    )

    strong_setup_mask = (
        dataframe[
            "liquidity_confirmed_v5"
        ].astype(str).str.lower().eq("true")
        & dataframe[
            "structure_alignment_v5"
        ].astype(str).str.lower().eq("true")
        & dataframe[
            "zone_fresh_v5"
        ].astype(str).str.lower().eq("true")
    )

    dataframe.loc[
        strong_setup_mask,
        "final_score_v5",
    ] += 0.03

    weak_setup_mask = (
        dataframe[
            "zone_status_v5"
        ].astype(str).str.lower().eq("mitigated")
        & ~dataframe[
            "liquidity_present_v5"
        ].astype(str).str.lower().eq("true")
        & ~dataframe[
            "structure_alignment_v5"
        ].astype(str).str.lower().eq("true")
    )

    dataframe.loc[
        weak_setup_mask,
        "final_score_v5",
    ] -= 0.05

    dataframe["final_score_v5"] = (
        dataframe["final_score_v5"]
        .clip(0.0, 1.0)
    )

    decisions = dataframe[
        "final_score_v5"
    ].map(classify_decision)

    dataframe["quality_v5"] = [
        result[0]
        for result in decisions
    ]

    dataframe["decision_v5"] = [
        result[1]
        for result in decisions
    ]

    dataframe["rank_v5"] = (
        dataframe["final_score_v5"]
        .rank(
            method="first",
            ascending=False,
        )
        .astype(int)
    )

    dataframe = dataframe.sort_values(
        "rank_v5"
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
        dataframe["decision_v5"]
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

    lines = [
        "# Scoring v5 Summary",
        "",
        "## Weighting",
        "",
        "- Scoring v4: 70%",
        "- Liquidity: 12%",
        "- BOS/CHoCH structure: 10%",
        "- Zone freshness: 8%",
        "",
        "## Results",
        "",
        f"- Total setups: {len(dataframe)}",
        (
            "- Average scoring v4: "
            f"{dataframe['final_score_v4'].mean():.4f}"
        ),
        (
            "- Average scoring v5: "
            f"{dataframe['final_score_v5'].mean():.4f}"
        ),
        (
            "- Confirmed liquidity sweeps: "
            f"{dataframe['liquidity_confirmed_v5'].astype(str).str.lower().eq('true').sum()}"
        ),
        (
            "- Fresh zones: "
            f"{dataframe['zone_fresh_v5'].astype(str).str.lower().eq('true').sum()}"
        ),
        "",
        "| Decision | Count |",
        "|---|---:|",
    ]

    for decision, count in decision_counts.items():
        lines.append(
            f"| {decision} | {int(count)} |"
        )

    args.summary_output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("")
    print("Scoring v5 selesai")
    print(
        f"Average v4 : "
        f"{dataframe['final_score_v4'].mean():.4f}"
    )
    print(
        f"Average v5 : "
        f"{dataframe['final_score_v5'].mean():.4f}"
    )
    print("")
    print(decision_counts.to_string())
    print("")
    print(f"CSV     : {args.output}")
    print(f"Summary : {args.summary_output}")


if __name__ == "__main__":
    main()
