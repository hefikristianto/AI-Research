from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def numeric(
    dataframe: pd.DataFrame,
    column: str,
    default: float = 0.50,
) -> pd.Series:
    return (
        pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )
        .fillna(default)
        .clip(0.0, 1.0)
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
            "scoring_v6_results.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "SCORING_V6_SUMMARY.md"
        ),
    )

    args = parser.parse_args()

    dataframe = pd.read_csv(
        args.input
    )

    required = {
        "final_score_v5_1",
        "htf_alignment_v6",
        "volatility_score_v6",
        "volatility_regime_v6",
        "session_v6",
    }

    missing = required - set(
        dataframe.columns
    )

    if missing:
        raise ValueError(
            f"Kolom kurang: {sorted(missing)}"
        )

    dataframe["base_score_v6"] = numeric(
        dataframe,
        "final_score_v5_1",
        default=0.0,
    )

    dataframe["htf_component_v6"] = numeric(
        dataframe,
        "htf_alignment_v6",
        default=0.50,
    )

    dataframe[
        "volatility_component_v6"
    ] = numeric(
        dataframe,
        "volatility_score_v6",
        default=0.50,
    )

    dataframe[
        "htf_adjustment_v6"
    ] = (
        0.10
        * (
            dataframe[
                "htf_component_v6"
            ]
            - 0.50
        )
    )

    dataframe[
        "volatility_adjustment_v6"
    ] = (
        0.06
        * (
            dataframe[
                "volatility_component_v6"
            ]
            - 0.50
        )
    )

    dataframe["final_score_v6"] = (
        dataframe["base_score_v6"]
        + dataframe[
            "htf_adjustment_v6"
        ]
        + dataframe[
            "volatility_adjustment_v6"
        ]
    )

    extreme_mask = (
        dataframe[
            "volatility_regime_v6"
        ]
        .astype(str)
        .str.lower()
        .eq("extreme")
    )

    dataframe.loc[
        extreme_mask,
        "final_score_v6",
    ] -= 0.02

    htf_conflict_mask = (
        dataframe[
            "htf_alignment_v6"
        ]
        == 0.0
    )

    dataframe.loc[
        htf_conflict_mask,
        "final_score_v6",
    ] -= 0.02

    dataframe["final_score_v6"] = (
        dataframe["final_score_v6"]
        .clip(0.0, 1.0)
    )

    decisions = (
        dataframe["final_score_v6"]
        .map(classify_decision)
    )

    dataframe["quality_v6"] = [
        item[0]
        for item in decisions
    ]

    dataframe["decision_v6"] = [
        item[1]
        for item in decisions
    ]

    dataframe["rank_v6"] = (
        dataframe["final_score_v6"]
        .rank(
            method="first",
            ascending=False,
        )
        .astype(int)
    )

    dataframe = dataframe.sort_values(
        "rank_v6"
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
        dataframe["decision_v6"]
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
        "# Scoring v6 Summary",
        "",
        "## Method",
        "",
        (
            "Scoring v6 uses scoring v5.1 as "
            "the base score."
        ),
        "",
        "## Context Adjustments",
        "",
        "- HTF alignment: maximum ±0.05",
        "- Volatility context: maximum ±0.03",
        "- Extreme-volatility penalty: -0.02",
        "- HTF-conflict penalty: -0.02",
        "- Session context: logged only, not scored",
        "",
        "## Results",
        "",
        f"- Total setups: {len(dataframe)}",
        (
            "- Average scoring v5.1: "
            f"{dataframe['final_score_v5_1'].mean():.4f}"
        ),
        (
            "- Average scoring v6: "
            f"{dataframe['final_score_v6'].mean():.4f}"
        ),
        (
            "- HTF aligned: "
            f"{int((dataframe['htf_alignment_v6'] == 1.0).sum())}"
        ),
        (
            "- HTF conflicts: "
            f"{int((dataframe['htf_alignment_v6'] == 0.0).sum())}"
        ),
        (
            "- Extreme volatility: "
            f"{int(extreme_mask.sum())}"
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
    print("Scoring v6 selesai")
    print(
        f"Average v5.1 : "
        f"{dataframe['final_score_v5_1'].mean():.4f}"
    )
    print(
        f"Average v6   : "
        f"{dataframe['final_score_v6'].mean():.4f}"
    )
    print("")
    print(decision_counts.to_string())
    print("")
    print(f"CSV     : {args.output}")
    print(f"Summary : {args.summary_output}")


if __name__ == "__main__":
    main()
