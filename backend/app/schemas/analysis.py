from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RegimePredictionResponse(BaseModel):
    filename: str
    content_type: str
    width: int
    height: int
    prediction: dict[str, Any]
