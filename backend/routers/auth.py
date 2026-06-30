from fastapi import APIRouter, Header

from schemas.auth_schema import RegisterRequest, LoginRequest
from services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/register")
def register(data: RegisterRequest):
    return AuthService.register(
        data.full_name,
        data.email,
        data.password
    )


@router.post("/login")
def login(data: LoginRequest):
    return AuthService.login(
        data.email,
        data.password
    )


@router.get("/me")
def me(authorization: str = Header(default="")):
    return AuthService.get_current_user(authorization)
