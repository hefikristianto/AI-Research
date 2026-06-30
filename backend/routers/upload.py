from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException

from database.supabase import supabase
from services.storage_service import StorageService

router = APIRouter(
    prefix="/upload",
    tags=["Upload"]
)


def get_user_id_from_token(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.replace("Bearer ", "").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        user_response = supabase.auth.get_user(token)
        return user_response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/")
def upload_chart(
    image: UploadFile = File(...),
    pair: str = Form(...),
    timeframe: str = Form(...),
    device: str = Form(...),
    market_session: str = Form(...),
    authorization: str = Header(default="")
):
    user_id = get_user_id_from_token(authorization)

    image_path = StorageService.upload_image(image)

    screenshot = StorageService.save_metadata(
        user_id=user_id,
        image_path=image_path,
        pair=pair,
        timeframe=timeframe,
        device=device,
        market_session=market_session
    )

    return {
        "success": True,
        "message": "Upload chart success",
        "screenshot_id": screenshot["id"],
        "image_path": image_path,
        "pair": pair,
        "timeframe": timeframe,
        "device": device,
        "market_session": market_session
    }
