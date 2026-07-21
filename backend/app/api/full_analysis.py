from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from PIL import Image
from PIL import UnidentifiedImageError

from app.api.analysis import cnn_service
from app.api.detection import yolo_service
from app.schemas.full_analysis import (
    FullAnalysisResponse,
)
from app.services.annotated_chart_service import (
    AnnotatedChartService,
)
from app.services.analysis_target_datetime_service import (
    AnalysisTargetDatetimeService,
)
from app.services.chart_metadata_service import (
    ChartMetadataService,
)
from app.services.chart_plot_geometry_service import (
    ChartPlotGeometryService,
)
from app.services.live_context_scoring_service import (
    LiveContextScoringService,
)
from app.services.live_execution_gate_service import (
    LiveExecutionGateService,
)
from app.services.live_htf_volatility_scoring_service import (
    LiveHTFVolatilityScoringService,
)
from app.services.live_htf_volatility_service import (
    LiveHTFVolatilityService,
)
from app.services.live_market_structure_service import (
    LiveMarketStructureService,
)
from app.services.live_price_conversion_service import (
    CanonicalOHLCVPriceConversionService,
)
from app.services.live_session_risk_service import (
    LiveSessionRiskService,
)
from app.services.live_setup_scoring_service import (
    LiveSetupScoringService,
)
from app.services.ob_fvg_pairing_service import (
    OBFVGPairingService,
)
from app.services.ohlcv_context_service import (
    OHLCVContextService,
)
from app.services.public_recommendation_service import (
    PublicRecommendationService,
)


router = APIRouter(
    prefix="/api/analysis",
    tags=["Analysis"],
)

metadata_service = ChartMetadataService()

analysis_target_service = (
    AnalysisTargetDatetimeService()
)

plot_geometry_service = ChartPlotGeometryService()

pairing_service = OBFVGPairingService(
    max_x_distance=0.12,
    max_y_distance=0.20,
)

scoring_service = LiveSetupScoringService(
    minimum_ob_confidence=0.05,
    minimum_fvg_confidence=0.005,
)

ohlcv_service = OHLCVContextService()

structure_service = LiveMarketStructureService(
    swing_strength=2,
    liquidity_tolerance_atr=0.15,
)

context_scoring_service = (
    LiveContextScoringService()
)

htf_volatility_service = (
    LiveHTFVolatilityService()
)

htf_volatility_scoring_service = (
    LiveHTFVolatilityScoringService()
)

session_risk_service = (
    LiveSessionRiskService()
)

execution_gate_service = (
    LiveExecutionGateService()
)

price_conversion_service = (
    CanonicalOHLCVPriceConversionService()
)

recommendation_service = PublicRecommendationService()

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post(
    "/full",
    response_model=FullAnalysisResponse,
)
async def run_full_analysis(
    file: UploadFile = File(...),
    confidence_threshold: float = Query(
        default=0.25,
        ge=0.001,
        le=1.0,
    ),
    pair: str | None = Query(
        default=None,
    ),
    timeframe: str | None = Query(
        default=None,
    ),
    chart_datetime: str | None = Query(
        default=None,
    ),
    analysis_target_datetime: str | None = Query(
        default=None,
        description=(
            "Optional experiment clock in the same "
            "market/source timezone as chart_datetime. "
            "It changes session evaluation only; OHLCV "
            "cutoff remains chart_datetime."
        ),
    ),
    chart_candles: int = Query(
        default=100,
        ge=30,
        le=500,
    ),
    context_candles: int = Query(
        default=300,
        ge=100,
        le=2000,
    ),
    market_utc_offset_hours: float = Query(
        default=0.0,
        ge=-12.0,
        le=14.0,
    ),
    include_annotated_chart: bool = Query(
        default=True,
        description=(
            "Set false untuk batch audit agar response "
            "tidak membawa PNG base64."
        ),
    ),
    plot_aware_mapping: bool = Query(
        default=False,
        description=(
            "Eksperimen opt-in untuk memetakan koordinat "
            "YOLO terhadap batas plot candle yang terdeteksi."
        ),
    ),
):
    content_type = (
        file.content_type
        or "application/octet-stream"
    )

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Format gambar tidak didukung. "
                "Gunakan PNG, JPG, atau WEBP."
            ),
        )

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="File gambar kosong.",
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "Ukuran file melebihi "
                "batas maksimum 10 MB."
            ),
        )

    try:
        image = Image.open(
            BytesIO(file_bytes)
        )

        image.load()
        image = image.convert("RGB")

    except UnidentifiedImageError as error:
        raise HTTPException(
            status_code=400,
            detail="File bukan gambar valid.",
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "Gagal membaca gambar: "
                f"{error}"
            ),
        ) from error

    try:
        chart_geometry_result = (
            plot_geometry_service.analyze(image)
        )

    except Exception as error:
        chart_geometry_result = {
            "status": "FALLBACK",
            "method": "FULL_IMAGE",
            "reason": "GEOMETRY_SERVICE_ERROR",
            "plot_left_normalized": 0.0,
            "plot_right_normalized": 1.0,
            "confidence": 0.0,
            "error": str(error),
        }

    try:
        metadata_result = (
            metadata_service.resolve(
                filename=file.filename,
                pair=pair,
                timeframe=timeframe,
                chart_datetime=(
                    chart_datetime
                ),
            )
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    try:
        regime_result = (
            cnn_service.predict(image)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "CNN ensemble inference gagal: "
                f"{error}"
            ),
        ) from error

    try:
        detection_result = (
            yolo_service.predict(
                image,
                confidence_threshold=(
                    confidence_threshold
                ),
            )
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "YOLO inference gagal: "
                f"{error}"
            ),
        ) from error

    pairing_result = pairing_service.pair(
        detection_result.get(
            "detections",
            [],
        )
    )

    scoring_result = scoring_service.score(
        pairing_result=pairing_result,
        regime_result=regime_result,
    )

    no_setup = (
        int(
            scoring_result.get(
                "total_setups",
                0,
            )
        )
        == 0
        or scoring_result.get(
            "best_setup"
        )
        is None
    )

    metadata_complete = all(
        [
            metadata_result.get("pair"),
            metadata_result.get(
                "timeframe"
            ),
            (
                metadata_result.get(
                    "chart_datetime"
                )
                or metadata_result.get(
                    "window_start_datetime"
                )
            ),
        ]
    )

    context_window: (
        pd.DataFrame | None
    ) = None

    if metadata_complete:
        try:
            (
                context_window,
                ohlcv_context_result,
            ) = ohlcv_service.load_context(
                pair=metadata_result[
                    "pair"
                ],
                timeframe=metadata_result[
                    "timeframe"
                ],
                window_start_datetime=(
                    metadata_result.get(
                        "window_start_datetime"
                    )
                ),
                chart_datetime=(
                    metadata_result.get(
                        "chart_datetime"
                    )
                ),
                chart_candles=(
                    chart_candles
                ),
                context_candles=(
                    context_candles
                ),
            )

        except Exception as error:
            ohlcv_context_result = {
                "status": "ERROR",
                "error": str(error),
                "pair": metadata_result.get(
                    "pair"
                ),
                "timeframe": (
                    metadata_result.get(
                        "timeframe"
                    )
                ),
            }

    else:
        ohlcv_context_result = {
            "status": "METADATA_REQUIRED",
            "required_fields": [
                "pair",
                "timeframe",
                (
                    "chart_datetime atau "
                    "filename standar AI-TDSS"
                ),
            ],
        }

    context_loaded = (
        ohlcv_context_result.get(
            "status"
        )
        == "LOADED"
        and context_window is not None
    )

    if context_loaded:
        try:
            analysis_clock_result = (
                analysis_target_service.resolve(
                    chart_end_datetime=(
                        ohlcv_context_result[
                            "chart_end_datetime"
                        ]
                    ),
                    timeframe=(
                        metadata_result[
                            "timeframe"
                        ]
                    ),
                    analysis_target_datetime=(
                        analysis_target_datetime
                    ),
                )
            )
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error
    else:
        analysis_clock_result = {
            "status": "SKIPPED",
            "override_requested": (
                analysis_target_datetime
                is not None
            ),
            "effective_datetime": None,
            "datetime_source": None,
            "chart_end_datetime": None,
            "analysis_target_datetime": (
                analysis_target_datetime
            ),
            "anti_lookahead_validated": (
                False
            ),
            "reason": (
                "OHLCV context belum tersedia "
                "untuk memvalidasi analysis target."
            ),
        }

    if context_loaded:
        try:
            structure_result = (
                structure_service.analyze(
                    context_window=(
                        context_window
                    ),
                    chart_candles=(
                        chart_candles
                    ),
                    best_setup=(
                        scoring_result.get(
                            "best_setup"
                        )
                    ),
                    ohlcv_metrics=(
                        ohlcv_context_result.get(
                            "metrics",
                            {},
                        )
                    ),
                )
            )

        except Exception as error:
            structure_result = {
                "status": "ERROR",
                "error": str(error),
            }

    else:
        structure_result = {
            "status": "SKIPPED",
            "reason": (
                "OHLCV context belum tersedia."
            ),
        }

    structure_complete = (
        structure_result.get("status")
        == "STRUCTURE_COMPLETE"
    )

    if (
        structure_complete
        and context_window is not None
    ):
        try:
            chart_window_for_mapping = (
                context_window
                .tail(chart_candles)
                .copy()
                .reset_index(drop=True)
            )

            price_conversion_result = (
                price_conversion_service
                .convert(
                    chart_window=(
                        chart_window_for_mapping
                    ),
                    best_setup=(
                        scoring_result.get(
                            "best_setup"
                        )
                    ),
                    plot_geometry=(
                        chart_geometry_result
                    ),
                    use_plot_geometry=(
                        plot_aware_mapping
                    ),
                )
            )

            if (
                price_conversion_result.get(
                    "status"
                )
                == "MAPPED"
            ):
                structure_result["zone"] = (
                    price_conversion_result
                )

                structure_result[
                    "zone_score"
                ] = float(
                    price_conversion_result.get(
                        "zone_score",
                        0.50,
                    )
                )

                structure_result[
                    "market_structure_score"
                ] = (
                    float(
                        structure_result.get(
                            "alignment_score",
                            0.50,
                        )
                    )
                    * 0.45
                    + float(
                        structure_result.get(
                            "sweep_score",
                            0.50,
                        )
                    )
                    * 0.25
                    + float(
                        price_conversion_result.get(
                            "zone_score",
                            0.50,
                        )
                    )
                    * 0.30
                )

                structure_result[
                    "scoring_integration"
                ] = (
                    "CANONICAL_OHLCV_ZONE_"
                    "APPLIED"
                )

            else:
                structure_result[
                    "canonical_zone_error"
                ] = price_conversion_result

        except Exception as error:
            price_conversion_result = {
                "status": "ERROR",
                "mapping_mode": (
                    "CANONICAL_OHLCV_"
                    "CANDLE_ANCHORED"
                ),
                "mapping_provisional": True,
                "error": str(error),
            }

            structure_result[
                "canonical_zone_error"
            ] = price_conversion_result

    else:
        price_conversion_result = {
            "status": "SKIPPED",
            "mapping_provisional": True,
            "reason": (
                "Structure atau OHLCV belum "
                "tersedia."
            ),
        }

    if no_setup:
        context_scoring_result = {
            "status": "NO_VALID_SETUP",
            "reason": (
                "Tidak ada deteksi atau pasangan "
                "OB-FVG yang lolos threshold."
            ),
            "detector_valid": False,
            "final_decision_ready": False,
        }

    elif structure_complete:
        context_scoring_result = (
            context_scoring_service.score(
                preliminary_scoring=(
                    scoring_result
                ),
                market_structure=(
                    structure_result
                ),
            )
        )

    else:
        context_scoring_result = {
            "status": "SKIPPED",
            "reason": (
                "Market structure belum selesai."
            ),
            "final_decision_ready": False,
        }

    structure_scoring_complete = (
        context_scoring_result.get(
            "status"
        )
        == "STRUCTURE_SCORING_COMPLETE"
    )

    if (
        context_loaded
        and not no_setup
    ):
        try:
            setup_direction = (
                context_scoring_result.get(
                    "setup_direction"
                )
                or scoring_result.get(
                    "best_setup",
                    {},
                ).get(
                    "setup_direction",
                    "unknown",
                )
            )

            htf_volatility_result = (
                htf_volatility_service.analyze(
                    pair=metadata_result[
                        "pair"
                    ],
                    base_timeframe=(
                        metadata_result[
                            "timeframe"
                        ]
                    ),
                    chart_end_datetime=(
                        ohlcv_context_result[
                            "chart_end_datetime"
                        ]
                    ),
                    base_context_window=(
                        context_window
                    ),
                    base_metrics=(
                        ohlcv_context_result.get(
                            "metrics",
                            {},
                        )
                    ),
                    setup_direction=(
                        setup_direction
                    ),
                    ohlcv_service=(
                        ohlcv_service
                    ),
                )
            )

        except Exception as error:
            htf_volatility_result = {
                "status": "ERROR",
                "error": str(error),
            }

    else:
        htf_volatility_result = {
            "status": "SKIPPED",
            "reason": (
                "OHLCV context belum tersedia."
            ),
        }

    htf_volatility_complete = (
        htf_volatility_result.get(
            "status"
        )
        == "HTF_VOLATILITY_COMPLETE"
    )

    if (
        structure_scoring_complete
        and htf_volatility_complete
    ):
        advanced_scoring_result = (
            htf_volatility_scoring_service
            .score(
                context_scoring=(
                    context_scoring_result
                ),
                htf_volatility=(
                    htf_volatility_result
                ),
            )
        )

    else:
        advanced_scoring_result = {
            "status": "SKIPPED",
            "reason": (
                "Structure scoring atau HTF "
                "volatility belum selesai."
            ),
            "final_decision_ready": False,
        }

    advanced_scoring_complete = (
        advanced_scoring_result.get(
            "status"
        )
        == "HTF_VOLATILITY_SCORING_COMPLETE"
    )

    if (
        advanced_scoring_complete
        and context_loaded
        and structure_complete
    ):
        try:
            session_risk_result = (
                session_risk_service.analyze(
                    pair=metadata_result[
                        "pair"
                    ],
                    chart_end_datetime=(
                        ohlcv_context_result[
                            "chart_end_datetime"
                        ]
                    ),
                    analysis_datetime=(
                        analysis_clock_result[
                            "effective_datetime"
                        ]
                    ),
                    analysis_datetime_source=(
                        analysis_clock_result[
                            "datetime_source"
                        ]
                    ),
                    setup_direction=(
                        advanced_scoring_result.get(
                            "setup_direction",
                            "unknown",
                        )
                    ),
                    market_structure=(
                        structure_result
                    ),
                    ohlcv_metrics=(
                        ohlcv_context_result.get(
                            "metrics",
                            {},
                        )
                    ),
                    market_utc_offset_hours=(
                        market_utc_offset_hours
                    ),
                )
            )

        except Exception as error:
            session_risk_result = {
                "status": "ERROR",
                "error": str(error),
            }

    else:
        session_risk_result = {
            "status": "SKIPPED",
            "reason": (
                "Advanced scoring, OHLCV, "
                "atau structure belum selesai."
            ),
        }

    session_risk_complete = (
        session_risk_result.get(
            "status"
        )
        == "SESSION_RISK_COMPLETE"
    )

    if no_setup:
        execution_gate_result = {
            "status": (
                "EXECUTION_GATE_COMPLETE"
            ),
            "decision": "WAIT",
            "execution_status": "NO_SETUP",
            "final_decision_ready": False,
            "setup_direction": "unknown",
            "advanced_score": None,
            "advanced_status": (
                "NOT_APPLICABLE"
            ),
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
            "risk_reward_ratio": None,
            "order_type": None,
            "price_mapping_provisional": (
                False
            ),
            "blockers": [
                "NO_VALID_SETUP"
            ],
            "warnings": [],
            "reasons": [
                "NO_VALID_SETUP"
            ],
        }

    elif (
        advanced_scoring_complete
        and session_risk_complete
    ):
        execution_gate_result = (
            execution_gate_service.evaluate(
                advanced_scoring=(
                    advanced_scoring_result
                ),
                context_scoring=(
                    context_scoring_result
                ),
                htf_volatility=(
                    htf_volatility_result
                ),
                session_risk=(
                    session_risk_result
                ),
                market_structure=(
                    structure_result
                ),
            )
        )

    else:
        execution_gate_result = {
            "status": "SKIPPED",
            "decision": "WAIT",
            "execution_status": (
                "INCOMPLETE"
            ),
            "final_decision_ready": False,
            "reasons": [
                "Advanced scoring atau "
                "session risk belum selesai."
            ],
        }

    # ---------------------------------------------
    # Execution quality normalization
    # ---------------------------------------------
    pre_quality_decision = (
        execution_gate_result.get(
            "decision"
        )
    )

    pre_quality_execution_status = (
        execution_gate_result.get(
            "execution_status"
        )
    )

    pre_quality_final_decision_ready = bool(
        execution_gate_result.get(
            "final_decision_ready",
            False,
        )
    )

    minimum_mapping_confidence = 0.65
    warning_entry_distance_atr = 1.5
    maximum_entry_distance_atr = 3.0

    blockers = list(
        execution_gate_result.get(
            "blockers"
        )
        or []
    )

    warnings = list(
        execution_gate_result.get(
            "warnings"
        )
        or []
    )

    pre_quality_blockers = list(
        blockers
    )
    pre_quality_warnings = list(
        warnings
    )

    mapping_status = (
        price_conversion_result.get(
            "status"
        )
    )

    raw_mapping_confidence = (
        price_conversion_result.get(
            "mapping_confidence"
        )
    )

    mapping_confidence_value = None

    if raw_mapping_confidence is not None:
        mapping_confidence_value = float(
            raw_mapping_confidence
        )

    if (
        mapping_status == "MAPPED"
        and mapping_confidence_value
        is not None
        and mapping_confidence_value
        < minimum_mapping_confidence
        and "LOW_MAPPING_CONFIDENCE"
        not in blockers
    ):
        blockers.append(
            "LOW_MAPPING_CONFIDENCE"
        )

    risk_reward_payload = (
        session_risk_result.get(
            "risk_reward"
        )
        or {}
    )

    raw_entry_distance_atr = (
        risk_reward_payload.get(
            "entry_distance_atr"
        )
    )

    entry_distance_atr = None

    if raw_entry_distance_atr is not None:
        entry_distance_atr = float(
            raw_entry_distance_atr
        )

    if (
        entry_distance_atr is not None
        and entry_distance_atr
        > maximum_entry_distance_atr
    ):
        if (
            "ENTRY_DISTANCE_EXCEEDS_3_ATR"
            not in blockers
        ):
            blockers.append(
                "ENTRY_DISTANCE_EXCEEDS_3_ATR"
            )

    elif (
        entry_distance_atr is not None
        and entry_distance_atr
        > warning_entry_distance_atr
    ):
        if (
            "ENTRY_DISTANCE_ABOVE_1_5_ATR"
            not in warnings
        ):
            warnings.append(
                "ENTRY_DISTANCE_ABOVE_1_5_ATR"
            )

    execution_gate_result[
        "blockers"
    ] = blockers

    execution_gate_result[
        "warnings"
    ] = warnings

    execution_gate_result[
        "mapping_confidence"
    ] = mapping_confidence_value

    execution_gate_result[
        "minimum_mapping_confidence"
    ] = minimum_mapping_confidence

    execution_gate_result[
        "entry_distance_atr"
    ] = entry_distance_atr

    execution_gate_result[
        "maximum_entry_distance_atr"
    ] = maximum_entry_distance_atr

    if blockers:
        current_status = (
            execution_gate_result.get(
                "execution_status"
            )
        )

        execution_gate_result[
            "decision"
        ] = "WAIT"

        execution_gate_result[
            "final_decision_ready"
        ] = False

        if current_status not in {
            "WAIT",
            "INVALID",
            "NO_SETUP",
        }:
            execution_gate_result[
                "execution_status"
            ] = "QUALITY_REVIEW"

        execution_gate_result[
            "reasons"
        ] = blockers

    elif warnings:
        if (
            execution_gate_result.get(
                "decision"
            )
            in {"BUY", "SELL"}
        ):
            execution_gate_result[
                "decision"
            ] = "WAIT"

            execution_gate_result[
                "execution_status"
            ] = "REVIEW"

            execution_gate_result[
                "final_decision_ready"
            ] = False

        execution_gate_result[
            "reasons"
        ] = warnings

    elif (
        execution_gate_result.get(
            "decision"
        )
        == "WAIT"
    ):
        if (
            execution_gate_result.get(
                "execution_status"
            )
            == "REVIEW"
        ):
            warnings.append(
                "EXECUTION_REVIEW_REQUIRED"
            )

            execution_gate_result[
                "warnings"
            ] = warnings

            execution_gate_result[
                "reasons"
            ] = warnings

        else:
            execution_gate_result[
                "reasons"
            ] = [
                "NO_TRADE_DECISION"
            ]

    elif (
        execution_gate_result.get(
            "decision"
        )
        in {"BUY", "SELL"}
        and execution_gate_result.get(
            "final_decision_ready"
        )
    ):
        execution_gate_result[
            "reasons"
        ] = [
            "ALL_EXECUTION_GATES_PASSED"
        ]

    execution_gate_result[
        "quality_normalization"
    ] = {
        "status": "COMPLETE",
        "pre_decision": (
            pre_quality_decision
        ),
        "pre_execution_status": (
            pre_quality_execution_status
        ),
        "pre_final_decision_ready": (
            pre_quality_final_decision_ready
        ),
        "post_decision": (
            execution_gate_result.get(
                "decision"
            )
        ),
        "post_execution_status": (
            execution_gate_result.get(
                "execution_status"
            )
        ),
        "post_final_decision_ready": bool(
            execution_gate_result.get(
                "final_decision_ready",
                False,
            )
        ),
        "status_changed": (
            pre_quality_decision
            != execution_gate_result.get(
                "decision"
            )
            or pre_quality_execution_status
            != execution_gate_result.get(
                "execution_status"
            )
            or pre_quality_final_decision_ready
            != bool(
                execution_gate_result.get(
                    "final_decision_ready",
                    False,
                )
            )
        ),
        "applied": bool(
            blockers
            != pre_quality_blockers
            or warnings
            != pre_quality_warnings
        ),
        "added_blockers": [
            blocker
            for blocker in blockers
            if blocker
            not in pre_quality_blockers
        ],
        "added_warnings": [
            warning
            for warning in warnings
            if warning
            not in pre_quality_warnings
        ],
        "thresholds": {
            "minimum_mapping_confidence": (
                minimum_mapping_confidence
            ),
            "warning_entry_distance_atr": (
                warning_entry_distance_atr
            ),
            "maximum_entry_distance_atr": (
                maximum_entry_distance_atr
            ),
        },
    }

    recommendation_result = recommendation_service.build(
        execution_gate_result
    )

    if include_annotated_chart:
        try:
            annotated_chart_result = (
                AnnotatedChartService.render(
                    image=image,
                    detections=detection_result.get(
                        "detections",
                        [],
                    ),
                    decision=recommendation_result[
                        "decision"
                    ],
                    execution_status=recommendation_result[
                        "execution_status"
                    ],
                )
            )
        except Exception as error:
            annotated_chart_result = {
                "status": "ERROR",
                "error": str(error),
                "rendered_detections": 0,
            }
    else:
        annotated_chart_result = {
            "status": "SKIPPED",
            "reason": (
                "Annotated chart dinonaktifkan "
                "untuk batch audit."
            ),
            "rendered_detections": 0,
        }

    execution_complete = (
        execution_gate_result.get(
            "status"
        )
        == "EXECUTION_GATE_COMPLETE"
    )

    if (
        no_setup
        and execution_complete
    ):
        pipeline_status = (
            "CNN_YOLO_OHLCV_STRUCTURE_"
            "NO_SETUP_WAIT_COMPLETE"
        )

    elif execution_complete:
        pipeline_status = (
            "CNN_YOLO_PAIRING_SCORING_"
            "OHLCV_STRUCTURE_HTF_"
            "VOLATILITY_SESSION_RISK_"
            "EXECUTION_COMPLETE"
        )

    elif advanced_scoring_complete:
        pipeline_status = (
            "CNN_YOLO_PAIRING_SCORING_"
            "OHLCV_STRUCTURE_HTF_"
            "VOLATILITY_SCORING_COMPLETE_"
            "EXECUTION_INCOMPLETE"
        )

    elif structure_scoring_complete:
        pipeline_status = (
            "CNN_YOLO_PAIRING_SCORING_"
            "OHLCV_STRUCTURE_SCORING_"
            "HTF_INCOMPLETE"
        )

    elif structure_complete:
        pipeline_status = (
            "CNN_YOLO_PAIRING_SCORING_"
            "OHLCV_STRUCTURE_COMPLETE_"
            "SCORING_INCOMPLETE"
        )

    elif context_loaded:
        pipeline_status = (
            "CNN_YOLO_PAIRING_SCORING_"
            "OHLCV_COMPLETE_STRUCTURE_"
            "INCOMPLETE"
        )

    else:
        pipeline_status = (
            "CNN_YOLO_PAIRING_SCORING_"
            "OHLCV_INCOMPLETE"
        )

    return {
        "filename": (
            file.filename
            or "uploaded_image"
        ),
        "content_type": content_type,
        "width": image.width,
        "height": image.height,
        "metadata": metadata_result,
        "chart_geometry": (
            chart_geometry_result
        ),
        "regime": regime_result,
        "detection": detection_result,
        "pairing": pairing_result,
        "scoring": scoring_result,
        "ohlcv_context": (
            ohlcv_context_result
        ),
        "analysis_clock": (
            analysis_clock_result
        ),
        "market_structure": (
            structure_result
        ),
        "context_scoring": (
            context_scoring_result
        ),
        "htf_volatility": (
            htf_volatility_result
        ),
        "advanced_scoring": (
            advanced_scoring_result
        ),
        "price_conversion": (
            price_conversion_result
        ),
        "session_risk": (
            session_risk_result
        ),
        "execution_gate": (
            execution_gate_result
        ),
        "recommendation": recommendation_result,
        "annotated_chart": annotated_chart_result,
        "pipeline_status": (
            pipeline_status
        ),
    }
