from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]

FINAL_RESULTS_PATH = (
    PROJECT_ROOT
    / "ai"
    / "decision"
    / "reports"
    / "final_execution_candidates.csv"
)


class DecisionResultService:
    def __init__(
        self,
        results_path: Path = FINAL_RESULTS_PATH,
    ) -> None:
        self.results_path = results_path

    def _load_dataframe(self) -> pd.DataFrame:
        if not self.results_path.exists():
            raise FileNotFoundError(
                f"Final decision file tidak ditemukan: "
                f"{self.results_path}"
            )

        dataframe = pd.read_csv(
            self.results_path
        )

        if dataframe.empty:
            raise ValueError(
                "Final decision file kosong."
            )

        return dataframe

    @staticmethod
    def _clean_value(
        value: Any,
    ) -> Any:
        if pd.isna(value):
            return None

        if isinstance(value, bool):
            return value

        if hasattr(value, "item"):
            try:
                return value.item()
            except ValueError:
                pass

        return value

    def list_results(
        self,
        limit: int = 50,
        status: str | None = None,
        pair: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict[str, Any]]:
        dataframe = self._load_dataframe()

        if status:
            dataframe = dataframe[
                dataframe[
                    "final_system_status"
                ]
                .astype(str)
                .str.upper()
                .eq(status.upper())
            ]

        if pair:
            dataframe = dataframe[
                dataframe["pair"]
                .astype(str)
                .str.upper()
                .eq(pair.upper())
            ]

        if timeframe:
            dataframe = dataframe[
                dataframe["timeframe"]
                .astype(str)
                .str.upper()
                .eq(timeframe.upper())
            ]

        dataframe = dataframe.head(
            max(1, min(limit, 500))
        )

        records = []

        for record in dataframe.to_dict(
            orient="records"
        ):
            cleaned = {
                key: self._clean_value(value)
                for key, value in record.items()
            }

            records.append(cleaned)

        return records

    def get_result(
        self,
        image_id: str,
    ) -> dict[str, Any] | None:
        dataframe = self._load_dataframe()

        match = dataframe[
            dataframe["image_id"]
            .astype(str)
            .eq(image_id)
        ]

        if match.empty:
            return None

        record = match.iloc[0].to_dict()

        return {
            key: self._clean_value(value)
            for key, value in record.items()
        }

    def get_summary(
        self,
    ) -> dict[str, Any]:
        dataframe = self._load_dataframe()

        system_status = (
            dataframe[
                "final_system_status"
            ]
            .value_counts()
            .to_dict()
        )

        decision_status = (
            dataframe[
                "decision_v7_1"
            ]
            .value_counts()
            .to_dict()
        )

        execution_status = (
            dataframe[
                "execution_status"
            ]
            .value_counts()
            .to_dict()
        )

        actionable = int(
            dataframe[
                "final_actionable_candidate"
            ]
            .astype(str)
            .str.lower()
            .eq("true")
            .sum()
        )

        average_score = float(
            pd.to_numeric(
                dataframe[
                    "final_score_v7_1"
                ],
                errors="coerce",
            ).mean()
        )

        return {
            "total_setups": int(
                len(dataframe)
            ),
            "actionable_candidates": actionable,
            "average_score": average_score,
            "system_status": system_status,
            "quality_status": decision_status,
            "execution_status": execution_status,
            "source_file": str(
                self.results_path
            ),
        }
