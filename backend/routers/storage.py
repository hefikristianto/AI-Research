from fastapi import APIRouter

router = APIRouter(
    prefix="/storage",
    tags=["Storage"]
)


@router.get("/test")
def test_storage():
    return {
        "status": "connected",
        "bucket": "chart-screenshots"
    }
