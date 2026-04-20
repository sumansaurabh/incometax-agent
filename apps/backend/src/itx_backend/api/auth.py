from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str


@router.post("/login")
def login(payload: LoginRequest) -> dict[str, str]:
    return {"token": f"dev-token-for-{payload.email}"}
