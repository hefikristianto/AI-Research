from pathlib import Path
import pandas as pd


INPUT_CSV = Path(
    "ai/benchmarks/reports/yolo11s_pairing_conf025/"
    "yolo11s_ohlcv_validation.csv"
)

OUTPUT_DIR = Path(
    "ai/benchmarks/reports/yolo11s_pairing_v3"
)

OUTPUT_CSV = OUTPUT_DIR / "yolo11s_ob_fvg_pairs_v3.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "yolo11s_pairing_v3_summary.md"


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def to_bool(value):
    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


def calculate_confidence_score(row):
    ob_conf = float(row["ob_conf"])
    fvg_conf = float(row["fvg_conf"])

    return clamp(
        (ob_conf + fvg_conf) / 2.0
    )


def calculate_spatial_score(row):
    x_distance = float(row["x_distance"])
    y_distance = float(row["y_distance"])

    x_score = clamp(
        1.0 - (x_distance / 0.12)
    )

    y_score = clamp(
        1.0 - (y_distance / 0.30)
    )

    return (
        x_score * 0.65
        + y_score * 0.35
    )


def calculate_ohlcv_score(row):
    ohlcv_status = str(row["ohlcv_status"]).strip().lower()
    direction_match = to_bool(row["direction_match_v2"])

    if ohlcv_status != "ok":
        return 0.0

    if direction_match:
        return 1.0

    ohlcv_direction = str(
        row["ohlcv_direction_v2"]
    ).strip().lower()

    if "uncertain" in ohlcv_direction:
        return 0.35

    return 0.0


def calculate_structure_score(row):
    local_structure_score = float(
        row["local_structure_score"]
    )

    impulse_body_ratio = float(
        row["impulse_body_ratio_v2"]
    )

    structure_component = clamp(
        local_structure_score
    )

    impulse_component = clamp(
        impulse_body_ratio
    )

    return (
        structure_component * 0.65
        + impulse_component * 0.35
    )


def calculate_alignment_score(row):
    value = row.get("distance_from_prediction")

    if pd.isna(value):
        return 0.15

    try:
        distance = abs(int(float(value)))
    except (TypeError, ValueError):
        return 0.15

    if distance == 0:
        return 1.0

    if distance <= 2:
        return 0.85

    if distance <= 4:
        return 0.65

    if distance <= 6:
        return 0.40

    return 0.15


def calculate_final_score(row):
    confidence_score = calculate_confidence_score(row)
    spatial_score = calculate_spatial_score(row)
    ohlcv_score = calculate_ohlcv_score(row)
    structure_score = calculate_structure_score(row)
    alignment_score = calculate_alignment_score(row)

    final_score = (
        confidence_score * 0.20
        + spatial_score * 0.15
        + ohlcv_score * 0.30
        + structure_score * 0.25
        + alignment_score * 0.10
    )

    return {
        "confidence_score_v3": confidence_score,
        "spatial_score_v3": spatial_score,
        "ohlcv_score_v3": ohlcv_score,
        "structure_score_v3": structure_score,
        "alignment_score_v3": alignment_score,
        "final_score_v3": clamp(final_score),
    }


def assign_quality(row):
    final_score = float(row["final_score_v3"])
    ohlcv_score = float(row["ohlcv_score_v3"])
    structure_score = float(row["structure_score_v3"])
    confidence_score = float(row["confidence_score_v3"])

    direction_match = to_bool(
        row.get("direction_match_v2")
    )

    ohlcv_direction = str(
        row.get("ohlcv_direction_v2", "")
    ).strip().lower()

    if not direction_match:
        if "uncertain" in ohlcv_direction:
            if (
                final_score >= 0.50
                and structure_score >= 0.45
            ):
                return "LOW"

        return "REJECTED"

    if ohlcv_score == 0.0:
        return "REJECTED"

    if (
        final_score >= 0.78
        and ohlcv_score >= 1.0
        and structure_score >= 0.60
        and confidence_score >= 0.40
    ):
        return "HIGH"

    if (
        final_score >= 0.65
        and ohlcv_score >= 1.0
        and structure_score >= 0.45
    ):
        return "MEDIUM"

    if (
        final_score >= 0.50
        and ohlcv_score >= 0.35
    ):
        return "LOW"

    return "REJECTED"


def assign_decision(row):
    quality = row["quality_v3"]

    if quality == "HIGH":
        return "ACCEPT"

    if quality == "MEDIUM":
        return "REVIEW"

    if quality == "LOW":
        return "WATCHLIST"

    return "REJECT"


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Input CSV not found: {INPUT_CSV}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = pd.read_csv(INPUT_CSV)

    required_columns = [
        "file",
        "score",
        "quality",
        "direction",
        "x_distance",
        "y_distance",
        "ob_conf",
        "fvg_conf",
        "ohlcv_status",
        "ohlcv_direction_v2",
        "direction_match_v2",
        "impulse_body_ratio_v2",
        "local_structure_score",
        "distance_from_prediction",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    score_rows = []

    for _, row in df.iterrows():
        score_rows.append(
            calculate_final_score(row)
        )

    score_df = pd.DataFrame(score_rows)

    result_df = pd.concat(
        [
            df.reset_index(drop=True),
            score_df,
        ],
        axis=1,
    )

    result_df["quality_v3"] = result_df.apply(
        assign_quality,
        axis=1,
    )

    result_df["decision_v3"] = result_df.apply(
        assign_decision,
        axis=1,
    )

    result_df = result_df.sort_values(
        by=[
            "final_score_v3",
            "local_structure_score",
            "score",
        ],
        ascending=False,
    ).reset_index(drop=True)

    result_df["rank_v3"] = (
        result_df.index + 1
    )

    preferred_columns = [
        "rank_v3",
        "file",
        "pair",
        "timeframe",
        "year",
        "direction",
        "ohlcv_direction_v2",
        "direction_match_v2",
        "quality",
        "quality_v3",
        "decision_v3",
        "score",
        "final_score_v3",
        "confidence_score_v3",
        "spatial_score_v3",
        "ohlcv_score_v3",
        "structure_score_v3",
        "alignment_score_v3",
        "ob_conf",
        "fvg_conf",
        "x_distance",
        "y_distance",
        "local_structure_score",
        "impulse_body_ratio_v2",
        "distance_from_prediction",
        "matched_ob_idx",
        "matched_impulse_idx",
        "matched_fvg_idx",
        "start_datetime",
        "end_datetime",
        "clean_image_path",
    ]

    existing_preferred = [
        column
        for column in preferred_columns
        if column in result_df.columns
    ]

    remaining_columns = [
        column
        for column in result_df.columns
        if column not in existing_preferred
    ]

    result_df = result_df[
        existing_preferred + remaining_columns
    ]

    result_df.to_csv(
        OUTPUT_CSV,
        index=False,
    )

    quality_counts = (
        result_df["quality_v3"]
        .value_counts()
        .to_dict()
    )

    decision_counts = (
        result_df["decision_v3"]
        .value_counts()
        .to_dict()
    )

    total_pairs = len(result_df)
    direction_matches = int(
        result_df["direction_match_v2"]
        .apply(to_bool)
        .sum()
    )

    accepted = int(
        (result_df["decision_v3"] == "ACCEPT").sum()
    )

    reviewed = int(
        (result_df["decision_v3"] == "REVIEW").sum()
    )

    watchlist = int(
        (result_df["decision_v3"] == "WATCHLIST").sum()
    )

    rejected = int(
        (result_df["decision_v3"] == "REJECT").sum()
    )

    summary = []

    summary.append(
        "# YOLO11s OB-FVG Pairing Scoring v3"
    )

    summary.append("")
    summary.append("## Status")
    summary.append("")
    summary.append("COMPLETED")

    summary.append("")
    summary.append("## Purpose")
    summary.append("")
    summary.append(
        "Scoring v3 combines YOLO confidence, spatial proximity, "
        "OHLCV direction validation, local structural strength, "
        "and candle-index alignment."
    )

    summary.append("")
    summary.append("## Scoring Weights")
    summary.append("")
    summary.append("- YOLO confidence: 20%")
    summary.append("- Spatial proximity: 15%")
    summary.append("- OHLCV direction validation: 30%")
    summary.append("- Local OB-FVG structure: 25%")
    summary.append("- Candle alignment: 10%")

    summary.append("")
    summary.append("## Result")
    summary.append("")
    summary.append(f"- Total pairs: {total_pairs}")
    summary.append(
        f"- Direction matches: {direction_matches}"
    )
    summary.append(
        f"- Average final score: "
        f"{result_df['final_score_v3'].mean():.4f}"
    )
    summary.append(
        f"- Highest final score: "
        f"{result_df['final_score_v3'].max():.4f}"
    )
    summary.append(
        f"- Lowest final score: "
        f"{result_df['final_score_v3'].min():.4f}"
    )

    summary.append("")
    summary.append("## Quality Distribution")
    summary.append("")

    for quality in [
        "HIGH",
        "MEDIUM",
        "LOW",
        "REJECTED",
    ]:
        summary.append(
            f"- {quality}: "
            f"{quality_counts.get(quality, 0)}"
        )

    summary.append("")
    summary.append("## Decision Distribution")
    summary.append("")
    summary.append(f"- ACCEPT: {accepted}")
    summary.append(f"- REVIEW: {reviewed}")
    summary.append(f"- WATCHLIST: {watchlist}")
    summary.append(f"- REJECT: {rejected}")

    summary.append("")
    summary.append("## Top 10 Ranked Pairs")
    summary.append("")
    summary.append(
        "| Rank | File | Final Score | Quality | "
        "Decision | Direction Match | Structure Score |"
    )

    summary.append(
        "|---:|---|---:|---|---|---|---:|"
    )

    for _, row in result_df.head(10).iterrows():
        summary.append(
            f"| {int(row['rank_v3'])} | "
            f"{row['file']} | "
            f"{float(row['final_score_v3']):.4f} | "
            f"{row['quality_v3']} | "
            f"{row['decision_v3']} | "
            f"{row['direction_match_v2']} | "
            f"{float(row['structure_score_v3']):.4f} |"
        )

    summary.append("")
    summary.append("## Quality Rules")
    summary.append("")
    summary.append(
        "- HIGH: strong OHLCV confirmation, strong structure, "
        "and sufficient model confidence."
    )
    summary.append(
        "- MEDIUM: valid structure with moderate overall strength."
    )
    summary.append(
        "- LOW: structurally plausible but weak confidence or alignment."
    )
    summary.append(
        "- REJECTED: failed OHLCV direction validation or weak final score."
    )

    summary.append("")
    summary.append("## Output")
    summary.append("")
    summary.append(f"- CSV: {OUTPUT_CSV}")

    OUTPUT_SUMMARY.write_text(
        "\n".join(summary),
        encoding="utf-8",
    )

    print("YOLO11s pairing scoring v3 finished.")
    print(f"Total pairs : {total_pairs}")
    print(
        f"HIGH        : "
        f"{quality_counts.get('HIGH', 0)}"
    )
    print(
        f"MEDIUM      : "
        f"{quality_counts.get('MEDIUM', 0)}"
    )
    print(
        f"LOW         : "
        f"{quality_counts.get('LOW', 0)}"
    )
    print(
        f"REJECTED    : "
        f"{quality_counts.get('REJECTED', 0)}"
    )
    print(f"CSV         : {OUTPUT_CSV}")
    print(f"Summary     : {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()


