from __future__ import annotations

import argparse
from pathlib import Path

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


def numeric_component(
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
            "scoring_v5_1_results.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "SCORING_V5_1_SUMMARY.md"
        ),
    )

    args = parser.parse_args()

    dataframe = pd.read_csv(args.input)

    required_columns = {
        "final_score_v4",
        "liquidity_score_v5",
        "market_structure_score_v5",
        "zone_score_v5",
        "liquidity_present_v5",
        "liquidity_confirmed_v5",
        "structure_alignment_v5",
        "zone_fresh_v5",
        "zone_status_v5",
    }

    missing = (
        required_columns
        - set(dataframe.columns)
    )

    if missing:
        raise ValueError(
            f"Kolom kurang: {sorted(missing)}"
        )

    dataframe["base_score_v5_1"] = (
        numeric_component(
            dataframe,
            "final_score_v4",
            default=0.0,
        )
    )

    raw_liquidity = numeric_component(
        dataframe,
        "liquidity_score_v5",
        default=0.50,
    )

    liquidity_present = as_bool(
        dataframe[
            "liquidity_present_v5"
        ]
    )

    liquidity_confirmed = as_bool(
        dataframe[
            "liquidity_confirmed_v5"
        ]
    )

    # Tidak ditemukan diperlakukan netral,
    # bukan otomatis buruk.
    dataframe[
        "liquidity_component_v5_1"
    ] = raw_liquidity.where(
        liquidity_present,
        0.50,
    )

    structure_alignment = as_bool(
        dataframe[
            "structure_alignment_v5"
        ]
    )

    raw_structure = numeric_component(
        dataframe,
        "market_structure_score_v5",
        default=0.50,
    )

    dataframe[
        "structure_component_v5_1"
    ] = raw_structure.where(
        structure_alignment,
        0.50,
    )

    dataframe[
        "zone_component_v5_1"
    ] = numeric_component(
        dataframe,
        "zone_score_v5",
        default=0.50,
    )

    dataframe[
        "liquidity_adjustment_v5_1"
    ] = (
        0.12
        * (
            dataframe[
                "liquidity_component_v5_1"
            ]
            - 0.50
        )
    )

    dataframe[
        "structure_adjustment_v5_1"
    ] = (
        0.10
        * (
            dataframe[
                "structure_component_v5_1"
            ]
            - 0.50
        )
    )

    dataframe[
        "zone_adjustment_v5_1"
    ] = (
        0.08
        * (
            dataframe[
                "zone_component_v5_1"
            ]
            - 0.50
        )
    )

    dataframe["final_score_v5_1"] = (
        dataframe["base_score_v5_1"]
        + dataframe[
            "liquidity_adjustment_v5_1"
        ]
        + dataframe[
            "structure_adjustment_v5_1"
        ]
        + dataframe[
            "zone_adjustment_v5_1"
        ]
    )

    # Bonus confluence kuat.
    strong_confluence = (
        liquidity_confirmed
        & structure_alignment
        & as_bool(
            dataframe["zone_fresh_v5"]
        )
    )

    dataframe.loc[
        strong_confluence,
        "final_score_v5_1",
    ] += 0.03

    # Penalti khusus zona sudah berkali-kali disentuh
    # tanpa liquidity dan structure pendukung.
    weak_context = (
        dataframe["zone_status_v5"]
        .astype(str)
        .str.lower()
        .eq("mitigated")
        & ~liquidity_present
        & ~structure_alignment
    )

    dataframe.loc[
        weak_context,
        "final_score_v5_1",
    ] -= 0.03

    dataframe["final_score_v5_1"] = (
        dataframe["final_score_v5_1"]
        .clip(0.0, 1.0)
    )

    decisions = (
        dataframe["final_score_v5_1"]
        .map(classify_decision)
    )

    dataframe["quality_v5_1"] = [
        item[0]
        for item in decisions
    ]

    dataframe["decision_v5_1"] = [
        item[1]
        for item in decisions
    ]

    dataframe["rank_v5_1"] = (
        dataframe["final_score_v5_1"]
        .rank(
            method="first",
            ascending=False,
        )
        .astype(int)
    )

    dataframe = dataframe.sort_values(
        "rank_v5_1"
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
        dataframe["decision_v5_1"]
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
        "# Scoring v5.1 Summary",
        "",
        "## Method",
        "",
        (
            "Scoring v5.1 uses scoring v4 as the "
            "base score and applies bounded market-context "
            "adjustments around a neutral value of 0.5."
        ),
        "",
        "## Maximum Context Influence",
        "",
        "- Liquidity: ±0.06",
        "- Market structure: ±0.05",
        "- Zone freshness: ±0.04",
        "- Strong-confluence bonus: +0.03",
        "- Weak-context penalty: -0.03",
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
        )
        if "final_score_v5" in dataframe.columns
        else "- Average scoring v5: unavailable",
        (
            "- Average scoring v5.1: "
            f"{dataframe['final_score_v5_1'].mean():.4f}"
        ),
        (
            "- Confirmed sweeps: "
            f"{int(liquidity_confirmed.sum())}"
        ),
        (
            "- Strong confluence: "
            f"{int(strong_confluence.sum())}"
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
    print("Scoring v5.1 selesai")
    print(
        f"Average v4   : "
        f"{dataframe['final_score_v4'].mean():.4f}"
    )

    if "final_score_v5" in dataframe.columns:
        print(
            f"Average v5   : "
            f"{dataframe['final_score_v5'].mean():.4f}"
        )

    print(
        f"Average v5.1 : "
        f"{dataframe['final_score_v5_1'].mean():.4f}"
    )
    print(
        f"Strong setup : "
        f"{int(strong_confluence.sum())}"
    )
    print("")
    print(decision_counts.to_string())
    print("")
    print(f"CSV     : {args.output}")
    print(f"Summary : {args.summary_output}")


if __name__ == "__main__":
    main()
