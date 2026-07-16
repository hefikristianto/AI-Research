from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def as_bool(value: object) -> bool:
    return (
        str(value)
        .strip()
        .lower()
        == "true"
    )


def determine_execution_status(
    row: pd.Series,
) -> tuple[str, str]:
    invalidated = as_bool(
        row.get(
            "zone_invalidated_v7",
            False,
        )
    )

    if invalidated:
        return (
            "INVALIDATED",
            "Harga telah melewati batas invalidasi zona.",
        )

    entry_status = (
        str(
            row.get(
                "entry_feasibility_v7",
                "unknown",
            )
        )
        .strip()
        .lower()
    )

    rr = pd.to_numeric(
        row.get("rr_ratio_v7"),
        errors="coerce",
    )

    target = pd.to_numeric(
        row.get("target_price_v7"),
        errors="coerce",
    )

    if entry_status == "very_far":
        return (
            "WAIT_RETRACE",
            "Harga terlalu jauh dari zona entry.",
        )

    if entry_status == "far":
        return (
            "WAIT_RETRACE",
            "Harga belum cukup dekat dengan zona entry.",
        )

    if pd.isna(target):
        return (
            "REVIEW_TARGET",
            "Target liquidity valid belum ditemukan.",
        )

    if pd.isna(rr):
        return (
            "REVIEW_RISK",
            "Risk-reward belum dapat dihitung.",
        )

    if float(rr) < 1.0:
        return (
            "NOT_FEASIBLE",
            "Risk-reward berada di bawah 1.0.",
        )

    if float(rr) < 1.5:
        return (
            "LOW_RR",
            "Risk-reward belum mencapai 1.5.",
        )

    if entry_status in {
        "near",
        "reachable",
        "inside_zone",
    }:
        return (
            "READY",
            "Zona entry terjangkau dan risk-reward layak.",
        )

    return (
        "REVIEW_ENTRY",
        "Setup valid tetapi kondisi entry perlu diperiksa.",
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "scoring_v7_1_results.csv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "final_execution_candidates.csv"
        ),
    )

    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path(
            "ai/decision/reports/"
            "FINAL_EXECUTION_SUMMARY.md"
        ),
    )

    args = parser.parse_args()

    dataframe = pd.read_csv(
        args.input
    ).copy()

    results = dataframe.apply(
        determine_execution_status,
        axis=1,
    )

    execution = pd.DataFrame(
        {
            "execution_status": [
                item[0]
                for item in results
            ],
            "execution_reason": [
                item[1]
                for item in results
            ],
        }
    )

    dataframe = pd.concat(
        [
            dataframe.reset_index(
                drop=True
            ),
            execution,
        ],
        axis=1,
    )

    ready_mask = (
        dataframe["execution_status"]
        == "READY"
    )

    quality_mask = (
        dataframe["decision_v7_1"]
        == "ACCEPT"
    )

    dataframe[
        "final_actionable_candidate"
    ] = (
        ready_mask
        & quality_mask
    )

    dataframe["final_system_status"] = "REVIEW"

    dataframe.loc[
        dataframe[
            "execution_status"
        ].eq("INVALIDATED"),
        "final_system_status",
    ] = "INVALID"

    dataframe.loc[
        dataframe[
            "execution_status"
        ].isin(
            [
                "WAIT_RETRACE",
                "REVIEW_TARGET",
                "REVIEW_RISK",
                "REVIEW_ENTRY",
                "LOW_RR",
                "NOT_FEASIBLE",
            ]
        ),
        "final_system_status",
    ] = "WAIT"

    dataframe.loc[
        dataframe[
            "final_actionable_candidate"
        ],
        "final_system_status",
    ] = "TRADE_CANDIDATE"

    dataframe = dataframe.sort_values(
        [
            "final_actionable_candidate",
            "final_score_v7_1",
        ],
        ascending=[
            False,
            False,
        ],
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
        dataframe["execution_status"]
        .value_counts()
    )

    actionable_count = int(
        dataframe[
            "final_actionable_candidate"
        ].sum()
    )

    lines = [
        "# Final Execution Summary",
        "",
        "## Concept",
        "",
        (
            "Setup quality and execution readiness "
            "are evaluated separately."
        ),
        "",
        "## Results",
        "",
        f"- Total setups: {len(dataframe)}",
        (
            "- Quality ACCEPT: "
            f"{int(quality_mask.sum())}"
        ),
        (
            "- Execution READY: "
            f"{int(ready_mask.sum())}"
        ),
        (
            "- Final actionable candidates: "
            f"{actionable_count}"
        ),
        "",
        "| Execution status | Count |",
        "|---|---:|",
    ]

    for status, count in counts.items():
        lines.append(
            f"| {status} | {int(count)} |"
        )

    args.summary_output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("")
    print("Execution gate selesai")
    print(
        f"Total setups          : "
        f"{len(dataframe)}"
    )
    print(
        f"Quality ACCEPT        : "
        f"{int(quality_mask.sum())}"
    )
    print(
        f"Execution READY       : "
        f"{int(ready_mask.sum())}"
    )
    print(
        f"Actionable candidates : "
        f"{actionable_count}"
    )
    print("")
    print(counts.to_string())
    print("")
    print(f"CSV     : {args.output}")
    print(f"Summary : {args.summary_output}")


if __name__ == "__main__":
    main()

