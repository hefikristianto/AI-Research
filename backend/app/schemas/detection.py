from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DetectionResponse(BaseModel):
    filename: str
    content_type: str
    width: int
    height: int
    detection: dict[str, Any]
    annotated_chart: dict[str, Any]
