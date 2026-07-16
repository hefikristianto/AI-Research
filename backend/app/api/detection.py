from __future__ import annotations

from io import BytesIO

from fastapi import (
    Query,
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
from PIL import Image
from PIL import UnidentifiedImageError

from app.schemas.detection import (
    DetectionResponse,
)
from app.services.yolo_detection_service import (
    YOLODetectionService,
)


router = APIRouter(
    prefix="/api/analysis",
    tags=["Analysis"],
)

yolo_service = YOLODetectionService(
    confidence_threshold=0.05,
    image_size=640,
)

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post(
    "/detect",
    response_model=DetectionResponse,
)
async def detect_chart_objects(
    file: UploadFile = File(...),
    confidence_threshold: float = Query(
        default=0.25,
        ge=0.001,
        le=1.0,
    ),
):
    content_type = (
        file.content_type
        or "application/octet-stream"
    )

    if content_type not in (
        ALLOWED_CONTENT_TYPES
    ):
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
                "batas 10 MB."
            ),
        )

    try:
        image = Image.open(
            BytesIO(file_bytes)
        )

        image.load()

    except UnidentifiedImageError as error:
        raise HTTPException(
            status_code=400,
            detail="File bukan gambar valid.",
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Gagal membaca gambar: "
                f"{error}"
            ),
        ) from error

    try:
        detection = yolo_service.predict(
            image,
            confidence_threshold=(
                confidence_threshold
            ),
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "YOLO inference gagal: "
                f"{error}"
            ),
        ) from error

    return {
        "filename": (
            file.filename
            or "uploaded_image"
        ),
        "content_type": content_type,
        "width": image.width,
        "height": image.height,
        "detection": detection,
    }
