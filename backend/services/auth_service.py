from fastapi import HTTPException
from database.supabase import supabase


class AuthService:

    @staticmethod
    def register(full_name: str, email: str, password: str):
        try:
            return supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name
                    }
                }
            })
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def login(email: str, password: str):
        try:
            return supabase.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })
        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))

    @staticmethod
    def get_current_user(authorization: str):
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        token = authorization.replace("Bearer ", "").strip()

        if not token:
            raise HTTPException(status_code=401, detail="Missing token")

        try:
            user_response = supabase.auth.get_user(token)
            user = user_response.user

            profile_response = (
                supabase
                .table("profiles")
                .select("*")
                .eq("user_id", user.id)
                .execute()
            )

            profile = None

            if profile_response.data and len(profile_response.data) > 0:
                profile = profile_response.data[0]
            else:
                created_profile = (
                    supabase
                    .table("profiles")
                    .insert({
                        "user_id": user.id,
                        "full_name": user.user_metadata.get("full_name", ""),
                        "email": user.email,
                        "role": "user"
                    })
                    .execute()
                )

                profile = created_profile.data[0] if created_profile.data else None

            return {
                "user": {
                    "id": user.id,
                    "email": user.email
                },
                "profile": profile
            }

        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))
