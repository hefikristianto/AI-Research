from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class ChartMetadataService:
    FILE_PATTERN = re.compile(
        r"^(?P<pair>[a-z]+)_"
        r"(?P<timeframe>m5|m15|h1|h4)_"
        r"(?P<year>\d{4})_"
        r"(?P<date>\d{8})_"
        r"(?P<time>\d{6})_"
        r".+$",
        re.IGNORECASE,
    )

    VALID_TIMEFRAMES = {
        "M5",
        "M15",
        "H1",
        "H4",
    }

    @classmethod
    def infer_from_filename(
        cls,
        filename: str | None,
    ) -> dict[str, Any]:
        if not filename:
            return {
                "pair": None,
                "timeframe": None,
                "window_start_datetime": None,
                "metadata_source": "missing",
            }

        stem = Path(filename).stem

        match = cls.FILE_PATTERN.match(stem)

        if match is None:
            return {
                "pair": None,
                "timeframe": None,
                "window_start_datetime": None,
                "metadata_source": "unrecognized_filename",
            }

        pair = match.group("pair").upper()
        timeframe = match.group(
            "timeframe"
        ).upper()

        date_value = match.group("date")
        time_value = match.group("time")

        window_start_datetime = (
            f"{date_value[0:4]}-"
            f"{date_value[4:6]}-"
            f"{date_value[6:8]} "
            f"{time_value[0:2]}:"
            f"{time_value[2:4]}:"
            f"{time_value[4:6]}"
        )

        return {
            "pair": pair,
            "timeframe": timeframe,
            "window_start_datetime": (
                window_start_datetime
            ),
            "metadata_source": "filename",
        }

    @classmethod
    def resolve(
        cls,
        filename: str | None,
        pair: str | None = None,
        timeframe: str | None = None,
        chart_datetime: str | None = None,
    ) -> dict[str, Any]:
        inferred = cls.infer_from_filename(
            filename
        )

        resolved_pair = (
            pair.upper().strip()
            if pair
            else inferred["pair"]
        )

        resolved_timeframe = (
            timeframe.upper().strip()
            if timeframe
            else inferred["timeframe"]
        )

        if (
            resolved_timeframe is not None
            and resolved_timeframe
            not in cls.VALID_TIMEFRAMES
        ):
            raise ValueError(
                "Timeframe tidak didukung. "
                "Gunakan M5, M15, H1, atau H4."
            )

        metadata_source = (
            "query_parameter"
            if pair
            or timeframe
            or chart_datetime
            else inferred["metadata_source"]
        )

        return {
            "pair": resolved_pair,
            "timeframe": resolved_timeframe,
            "chart_datetime": chart_datetime,
            "window_start_datetime": (
                inferred[
                    "window_start_datetime"
                ]
            ),
            "metadata_source": metadata_source,
            "filename": filename,
        }
