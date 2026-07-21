from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FullAnalysisResponse(BaseModel):
    filename: str
    content_type: str
    width: int
    height: int
    metadata: dict[str, Any]
    chart_geometry: dict[str, Any]
    regime: dict[str, Any]
    detection: dict[str, Any]
    pairing: dict[str, Any]
    scoring: dict[str, Any]
    ohlcv_context: dict[str, Any]
    market_structure: dict[str, Any]
    context_scoring: dict[str, Any]
    htf_volatility: dict[str, Any]
    advanced_scoring: dict[str, Any]
    price_conversion: dict[str, Any]
    session_risk: dict[str, Any]
    execution_gate: dict[str, Any]
    recommendation: dict[str, Any]
    annotated_chart: dict[str, Any]
    pipeline_status: str
