from __future__ import annotations

import argparse
from pathlib import Path

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
            "pairs_context_v6.csv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "scoring_v6_1_results.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "SCORING_V6_1_SUMMARY.md"
        ),
    )

    args = parser.parse_args()

    dataframe = pd.read_csv(args.input)

    required = {
        "final_score_v5_1",
        "htf_alignment_v6",
        "volatility_regime_v6",
    }

    missing = required - set(
        dataframe.columns
    )

    if missing:
        raise ValueError(
            f"Kolom kurang: {sorted(missing)}"
        )

    dataframe["base_score_v6_1"] = (
        pd.to_numeric(
            dataframe["final_score_v5_1"],
            errors="coerce",
        )
        .fillna(0.0)
        .clip(0.0, 1.0)
    )

    htf_alignment = pd.to_numeric(
        dataframe["htf_alignment_v6"],
        errors="coerce",
    ).fillna(0.5)

    dataframe[
        "htf_adjustment_v6_1"
    ] = 0.0

    dataframe.loc[
        htf_alignment == 1.0,
        "htf_adjustment_v6_1",
    ] = 0.04

    dataframe.loc[
        htf_alignment == 0.0,
        "htf_adjustment_v6_1",
    ] = -0.06

    volatility_adjustments = {
        "normal": 0.00,
        "high": -0.01,
        "low": -0.015,
        "extreme": -0.04,
        "unknown": 0.00,
    }

    dataframe[
        "volatility_adjustment_v6_1"
    ] = (
        dataframe[
            "volatility_regime_v6"
        ]
        .astype(str)
        .str.lower()
        .map(volatility_adjustments)
        .fillna(0.0)
    )

    dataframe["final_score_v6_1"] = (
        dataframe["base_score_v6_1"]
        + dataframe[
            "htf_adjustment_v6_1"
        ]
        + dataframe[
            "volatility_adjustment_v6_1"
        ]
    ).clip(0.0, 1.0)

    decisions = (
        dataframe["final_score_v6_1"]
        .map(classify_decision)
    )

    dataframe["quality_v6_1"] = [
        item[0]
        for item in decisions
    ]

    dataframe["decision_v6_1"] = [
        item[1]
        for item in decisions
    ]

    dataframe["rank_v6_1"] = (
        dataframe["final_score_v6_1"]
        .rank(
            method="first",
            ascending=False,
        )
        .astype(int)
    )

    dataframe = dataframe.sort_values(
        "rank_v6_1"
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        args.output,
        index=False,
    )

    counts = (
        dataframe["decision_v6_1"]
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
        "# Scoring v6.1 Summary",
        "",
        "## Adjustment Rules",
        "",
        "- HTF aligned: +0.04",
        "- HTF neutral: 0.00",
        "- HTF conflict: -0.06",
        "- Normal volatility: 0.00",
        "- High volatility: -0.01",
        "- Low volatility: -0.015",
        "- Extreme volatility: -0.04",
        "- Session context: not scored",
        "",
        "## Results",
        "",
        f"- Total setups: {len(dataframe)}",
        (
            "- Average v5.1: "
            f"{dataframe['final_score_v5_1'].mean():.4f}"
        ),
        (
            "- Average v6.1: "
            f"{dataframe['final_score_v6_1'].mean():.4f}"
        ),
        "",
        "| Decision | Count |",
        "|---|---:|",
    ]

    for decision, count in counts.items():
        lines.append(
            f"| {decision} | {int(count)} |"
        )

    args.summary_output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("")
    print("Scoring v6.1 selesai")
    print(
        f"Average v5.1 : "
        f"{dataframe['final_score_v5_1'].mean():.4f}"
    )
    print(
        f"Average v6.1 : "
        f"{dataframe['final_score_v6_1'].mean():.4f}"
    )
    print("")
    print(counts.to_string())
    print("")
    print(f"CSV     : {args.output}")
    print(f"Summary : {args.summary_output}")


if __name__ == "__main__":
    main()
