from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from app.schemas.decision import (
    DecisionDetailResponse,
    DecisionListResponse,
    DecisionSummaryResponse,
)
from app.services.decision_result_service import (
    DecisionResultService,
)


router = APIRouter(
    prefix="/api/decisions",
    tags=["Decisions"],
)

service = DecisionResultService()


@router.get(
    "/summary",
    response_model=DecisionSummaryResponse,
)
def get_decision_summary():
    try:
        return service.get_summary()

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@router.get(
    "",
    response_model=DecisionListResponse,
)
def list_decisions(
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    status: str | None = Query(
        default=None,
    ),
    pair: str | None = Query(
        default=None,
    ),
    timeframe: str | None = Query(
        default=None,
    ),
):
    try:
        results = service.list_results(
            limit=limit,
            status=status,
            pair=pair,
            timeframe=timeframe,
        )

        return {
            "total": len(results),
            "results": results,
        }

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@router.get(
    "/{image_id}",
    response_model=DecisionDetailResponse,
)
def get_decision(
    image_id: str,
):
    try:
        result = service.get_result(
            image_id
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Decision result tidak ditemukan: "
                    f"{image_id}"
                ),
            )

        return {
            "result": result,
        }

    except HTTPException:
        raise

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
