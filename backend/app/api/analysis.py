from __future__ import annotations

from io import BytesIO

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
from PIL import Image
from PIL import UnidentifiedImageError

from app.schemas.analysis import RegimePredictionResponse
from app.services.cnn_ensemble_service import CNNEnsembleService


router = APIRouter(
    prefix="/api/analysis",
    tags=["Analysis"],
)

cnn_service = CNNEnsembleService()

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post(
    "/regime",
    response_model=RegimePredictionResponse,
)
async def predict_market_regime(
    file: UploadFile = File(...),
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
            detail="Ukuran file melebihi batas 10 MB.",
        )

    try:
        image = Image.open(BytesIO(file_bytes))
        image.load()

    except UnidentifiedImageError as error:
        raise HTTPException(
            status_code=400,
            detail="File bukan gambar valid.",
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Gagal membaca gambar: {error}",
        ) from error

    try:
        prediction = cnn_service.predict(image)

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "CNN ensemble inference gagal: "
                f"{error}"
            ),
        ) from error

    return {
        "filename": file.filename or "uploaded_image",
        "content_type": content_type,
        "width": image.width,
        "height": image.height,
        "prediction": prediction,
    }
