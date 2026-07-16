from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


CLASSES = ["bearish", "bullish", "sideways"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Membuat manifest CNN dengan training set lebih seimbang."
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "ai/datasets/classification/"
            "market_regime/market_regime_manifest.csv"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "ai/datasets/classification/"
            "market_regime/market_regime_selected_manifest.csv"
        ),
    )

    parser.add_argument(
        "--summary",
        type=Path,
        default=Path(
            "ai/classification/reports/"
            "market_regime_selected_summary.json"
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"Manifest tidak ditemukan: {args.input}"
        )

    manifest = pd.read_csv(args.input)

    required_columns = {
        "sample_id",
        "split",
        "label",
        "include_for_training",
    }

    missing = required_columns - set(manifest.columns)

    if missing:
        raise ValueError(
            f"Kolom manifest tidak lengkap: {sorted(missing)}"
        )

    include_column = manifest["include_for_training"]

    if include_column.dtype == object:
        include_mask = (
            include_column.astype(str)
            .str.strip()
            .str.lower()
            .eq("true")
        )
    else:
        include_mask = include_column.astype(bool)

    eligible = manifest.loc[include_mask].copy()

    train = eligible.loc[
        eligible["split"] == "train"
    ].copy()

    valid = eligible.loc[
        eligible["split"] == "valid"
    ].copy()

    test = eligible.loc[
        eligible["split"] == "test"
    ].copy()

    train_counts = train["label"].value_counts()

    missing_classes = [
        label
        for label in CLASSES
        if label not in train_counts
    ]

    if missing_classes:
        raise RuntimeError(
            f"Kelas train tidak lengkap: {missing_classes}"
        )

    directional_target = int(
        max(
            train_counts.get("bearish", 0),
            train_counts.get("bullish", 0),
        )
    )

    selected_train_parts = []

    for label in CLASSES:
        class_rows = train.loc[
            train["label"] == label
        ].copy()

        if label == "sideways":
            sample_count = min(
                directional_target,
                len(class_rows),
            )

            class_rows = class_rows.sample(
                n=sample_count,
                random_state=args.seed,
            )

        selected_train_parts.append(class_rows)

    selected_train = pd.concat(
        selected_train_parts,
        ignore_index=True,
    )

    selected_train = selected_train.sample(
        frac=1.0,
        random_state=args.seed,
    ).reset_index(drop=True)

    selected = pd.concat(
        [
            selected_train,
            valid,
            test,
        ],
        ignore_index=True,
    )

    selected["selected_for_cnn"] = True

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.summary.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    selected.to_csv(
        args.output,
        index=False,
    )

    distribution = (
        selected.groupby(["split", "label"])
        .size()
        .unstack(fill_value=0)
        .reindex(
            index=["train", "valid", "test"],
            columns=CLASSES,
            fill_value=0,
        )
    )

    summary = {
        "seed": args.seed,
        "strategy": {
            "train": (
                "Keep all bullish and bearish samples, "
                "cap sideways to the largest directional class."
            ),
            "valid": "Keep natural distribution.",
            "test": "Keep natural distribution.",
        },
        "original_train_distribution": {
            key: int(value)
            for key, value in train_counts.to_dict().items()
        },
        "sideways_train_limit": directional_target,
        "selected_distribution": (
            distribution.to_dict(orient="index")
        ),
        "selected_total": int(len(selected)),
    }

    with args.summary.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            summary,
            file,
            indent=2,
        )

    print("")
    print("Selected manifest berhasil dibuat")
    print(f"Output : {args.output}")
    print(f"Summary: {args.summary}")
    print("")
    print(distribution)
    print("")
    print(f"Total selected: {len(selected)}")


if __name__ == "__main__":
    main()
