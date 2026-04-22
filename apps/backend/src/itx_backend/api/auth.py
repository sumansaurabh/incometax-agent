from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from itx_backend.security.request_auth import get_request_auth
from itx_backend.services.auth_runtime import AuthError, auth_runtime

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    device_id: str
    device_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str
    device_id: str
    device_name: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str
    device_id: str


@router.post("/signup")
async def signup(payload: SignupRequest, user_agent: Optional[str] = Header(default=None, alias="User-Agent")) -> dict[str, str]:
    try:
        return await auth_runtime.signup(
            email=payload.email,
            password=payload.password,
            device_id=payload.device_id,
            device_name=payload.device_name,
            user_agent=user_agent,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


@router.post("/login")
async def login(payload: LoginRequest, user_agent: Optional[str] = Header(default=None, alias="User-Agent")) -> dict[str, str]:
    try:
        return await auth_runtime.login(
            email=payload.email,
            password=payload.password,
            device_id=payload.device_id,
            device_name=payload.device_name,
            user_agent=user_agent,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


@router.post("/refresh")
async def refresh(payload: RefreshRequest) -> dict[str, str]:
    try:
        return await auth_runtime.refresh_session(
            refresh_token=payload.refresh_token,
            device_id=payload.device_id,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


@router.post("/revoke")
async def revoke_session() -> dict[str, str]:
    auth = get_request_auth(required=True)
    try:
        await auth_runtime.revoke_session_by_id(
            session_id=auth.session_id,
            device_id=auth.device_id,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    return {"status": "revoked"}


@router.get("/me")
async def me() -> dict[str, object]:
    auth = get_request_auth(required=True)
    return {
        "user_id": auth.user_id,
        "email": auth.email,
        "device_id": auth.device_id,
        "session_id": auth.session_id,
        "sessions": await auth_runtime.list_sessions(auth.user_id),
    }
