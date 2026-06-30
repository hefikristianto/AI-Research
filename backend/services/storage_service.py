from uuid import uuid4
from database.supabase import supabase


class StorageService:

    BUCKET = "chart-screenshots"

    @staticmethod
    def upload_image(file):

        filename = f"{uuid4()}.png"

        path = f"charts/{filename}"

        file_bytes = file.file.read()

        supabase.storage.from_(StorageService.BUCKET).upload(
            path,
            file_bytes,
            {
                "content-type": file.content_type
            }
        )

        return path


    @staticmethod
    def save_metadata(
        user_id,
        image_path,
        pair,
        timeframe,
        device,
        market_session
    ):

        response = (
            supabase
            .table("screenshots")
            .insert({
                "user_id": user_id,
                "image_path": image_path,
                "image_url": image_path,
                "pair": pair,
                "timeframe": timeframe,
                "device": device,
                "market_session": market_session,
            })
            .execute()
        )

        return response.data[0]
