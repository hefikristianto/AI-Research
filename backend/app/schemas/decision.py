from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DecisionSummaryResponse(BaseModel):
    total_setups: int
    actionable_candidates: int
    average_score: float
    system_status: dict[str, int]
    quality_status: dict[str, int]
    execution_status: dict[str, int]
    source_file: str


class DecisionListResponse(BaseModel):
    total: int
    results: list[dict[str, Any]]


class DecisionDetailResponse(BaseModel):
    result: dict[str, Any]
