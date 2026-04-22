from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from itx_backend.config import settings
from itx_backend.db.session import get_pool


PASSWORD_ITERATIONS = 600_000
PASSWORD_ALGO = "pbkdf2_sha256"
PASSWORD_SALT_BYTES = 16


class AuthError(Exception):
    def __init__(self, code: str, status_code: int = 401) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: str
    device_id: str
    session_id: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized or "." not in normalized.split("@", 1)[1]:
        raise AuthError("invalid_email", status_code=400)
    return normalized


def _validate_password(password: str) -> str:
    if password is None or len(password) < 8:
        raise AuthError("password_too_short", status_code=400)
    if len(password) > 128:
        raise AuthError("password_too_long", status_code=400)
    return password


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "${0}${1}${2}${3}".format(
        PASSWORD_ALGO,
        PASSWORD_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def _verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 5 or parts[0] != "" or parts[1] != PASSWORD_ALGO:
        return False
    try:
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3])
        expected = base64.b64decode(parts[4])
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _new_token_pair(session_id: uuid.UUID) -> tuple[str, str, str, str]:
    access_secret = secrets.token_urlsafe(32)
    refresh_secret = secrets.token_urlsafe(32)
    return (
        f"{session_id}.{access_secret}",
        _hash_secret(access_secret),
        f"{session_id}.{refresh_secret}",
        _hash_secret(refresh_secret),
    )


def _parse_token(token: str) -> tuple[uuid.UUID, str]:
    try:
        raw_session_id, secret = token.strip().split(".", 1)
        return uuid.UUID(raw_session_id), secret
    except (ValueError, AttributeError) as exc:
        raise AuthError("invalid_token") from exc


def _session_payload(
    *,
    user_id: uuid.UUID | str,
    email: str,
    device_id: str,
    session_id: uuid.UUID,
    access_token: str,
    refresh_token: str,
    access_expires_at: datetime,
    refresh_expires_at: datetime,
) -> dict[str, str]:
    return {
        "user_id": str(user_id),
        "email": email,
        "device_id": device_id,
        "session_id": str(session_id),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_expires_at": access_expires_at.isoformat(),
        "refresh_expires_at": refresh_expires_at.isoformat(),
    }


async def _issue_session(
    connection,
    *,
    user_id: uuid.UUID,
    email: str,
    device_id: str,
    device_name: Optional[str],
    user_agent: Optional[str],
) -> dict[str, str]:
    session_id = uuid.uuid4()
    access_token, access_secret_hash, refresh_token, refresh_secret_hash = _new_token_pair(session_id)
    now = _utcnow()
    access_expires_at = now + timedelta(seconds=settings.auth_access_ttl_seconds)
    refresh_expires_at = now + timedelta(seconds=settings.auth_refresh_ttl_seconds)

    device_row = await connection.fetchrow(
        "select user_id from auth_devices where device_id = $1",
        device_id,
    )
    if device_row is None:
        await connection.execute(
            """
            insert into auth_devices (id, user_id, device_id, device_name, user_agent)
            values ($1, $2, $3, $4, $5)
            """,
            uuid.uuid4(),
            user_id,
            device_id,
            device_name,
            user_agent,
        )
    else:
        await connection.execute(
            """
            update auth_devices
            set user_id = $2,
                device_name = $3,
                user_agent = $4,
                last_seen_at = now(),
                revoked_at = null
            where device_id = $1
            """,
            device_id,
            user_id,
            device_name,
            user_agent,
        )
        await connection.execute(
            "update auth_sessions set revoked_at = now() where device_id = $1 and revoked_at is null",
            device_id,
        )

    await connection.execute(
        """
        insert into auth_sessions (
            id, user_id, device_id, access_secret_hash, refresh_secret_hash,
            access_expires_at, refresh_expires_at
        )
        values ($1, $2, $3, $4, $5, $6, $7)
        """,
        session_id,
        user_id,
        device_id,
        access_secret_hash,
        refresh_secret_hash,
        access_expires_at,
        refresh_expires_at,
    )

    return _session_payload(
        user_id=user_id,
        email=email,
        device_id=device_id,
        session_id=session_id,
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )


class AuthRuntimeService:
    async def signup(
        self,
        *,
        email: str,
        password: str,
        device_id: str,
        device_name: Optional[str],
        user_agent: Optional[str],
    ) -> dict[str, str]:
        normalized_email = _normalize_email(email)
        _validate_password(password)
        normalized_device_id = device_id.strip()
        if not normalized_device_id:
            raise AuthError("device_id_required", status_code=400)

        password_hash = _hash_password(password)
        user_id = uuid.uuid4()

        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                existing = await connection.fetchrow(
                    "select id, password_hash from auth_users where email = $1",
                    normalized_email,
                )
                if existing is not None:
                    if existing["password_hash"]:
                        raise AuthError("email_already_registered", status_code=409)
                    user_id = existing["id"]
                    await connection.execute(
                        """
                        update auth_users
                        set password_hash = $2,
                            password_updated_at = now(),
                            updated_at = now()
                        where id = $1
                        """,
                        user_id,
                        password_hash,
                    )
                else:
                    await connection.execute(
                        """
                        insert into auth_users (id, email, password_hash, password_updated_at)
                        values ($1, $2, $3, now())
                        """,
                        user_id,
                        normalized_email,
                        password_hash,
                    )

                return await _issue_session(
                    connection,
                    user_id=user_id,
                    email=normalized_email,
                    device_id=normalized_device_id,
                    device_name=device_name,
                    user_agent=user_agent,
                )

    async def login(
        self,
        *,
        email: str,
        password: str,
        device_id: str,
        device_name: Optional[str],
        user_agent: Optional[str],
    ) -> dict[str, str]:
        normalized_email = _normalize_email(email)
        if not password:
            raise AuthError("password_required", status_code=400)
        normalized_device_id = device_id.strip()
        if not normalized_device_id:
            raise AuthError("device_id_required", status_code=400)

        pool = await get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                user_row = await connection.fetchrow(
                    "select id, password_hash from auth_users where email = $1",
                    normalized_email,
                )
                if user_row is None or not user_row["password_hash"]:
                    raise AuthError("invalid_credentials")
                if not _verify_password(password, user_row["password_hash"]):
                    raise AuthError("invalid_credentials")

                user_id = user_row["id"]
                await connection.execute(
                    "update auth_users set updated_at = now() where id = $1",
                    user_id,
                )

                return await _issue_session(
                    connection,
                    user_id=user_id,
                    email=normalized_email,
                    device_id=normalized_device_id,
                    device_name=device_name,
                    user_agent=user_agent,
                )

    async def authenticate_access_token(self, access_token: str, device_id: str) -> AuthContext:
        session_id, access_secret = _parse_token(access_token)
        normalized_device_id = device_id.strip()
        if not normalized_device_id:
            raise AuthError("device_id_required", status_code=400)

        pool = await get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                select s.id, s.device_id, s.access_secret_hash, s.access_expires_at, s.revoked_at,
                       d.revoked_at as device_revoked_at,
                       u.id as user_id, u.email
                from auth_sessions s
                join auth_users u on u.id = s.user_id
                join auth_devices d on d.device_id = s.device_id
                where s.id = $1
                """,
                session_id,
            )
            if row is None:
                raise AuthError("session_not_found")
            if row["device_id"] != normalized_device_id:
                raise AuthError("device_mismatch", status_code=403)
            if row["revoked_at"] is not None or row["device_revoked_at"] is not None:
                raise AuthError("session_revoked", status_code=403)
            if row["access_expires_at"] <= _utcnow():
                raise AuthError("access_token_expired")
            if row["access_secret_hash"] != _hash_secret(access_secret):
                raise AuthError("invalid_token")
            await connection.execute(
                "update auth_devices set last_seen_at = now() where device_id = $1",
                normalized_device_id,
            )

        return AuthContext(
            user_id=str(row["user_id"]),
            email=row["email"],
            device_id=normalized_device_id,
            session_id=str(row["id"]),
        )

    async def refresh_session(self, *, refresh_token: str, device_id: str) -> dict[str, str]:
        session_id, refresh_secret = _parse_token(refresh_token)
        normalized_device_id = device_id.strip()
        if not normalized_device_id:
            raise AuthError("device_id_required", status_code=400)

        pool = await get_pool()
        now = _utcnow()
        access_token, access_secret_hash, next_refresh_token, refresh_secret_hash = _new_token_pair(session_id)
        access_expires_at = now + timedelta(seconds=settings.auth_access_ttl_seconds)
        refresh_expires_at = now + timedelta(seconds=settings.auth_refresh_ttl_seconds)

        async with pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow(
                    """
                    select s.id, s.device_id, s.refresh_secret_hash, s.refresh_expires_at, s.revoked_at,
                           d.revoked_at as device_revoked_at,
                           u.id as user_id, u.email
                    from auth_sessions s
                    join auth_users u on u.id = s.user_id
                    join auth_devices d on d.device_id = s.device_id
                    where s.id = $1
                    for update
                    """,
                    session_id,
                )
                if row is None:
                    raise AuthError("session_not_found")
                if row["device_id"] != normalized_device_id:
                    raise AuthError("device_mismatch", status_code=403)
                if row["revoked_at"] is not None or row["device_revoked_at"] is not None:
                    raise AuthError("session_revoked", status_code=403)
                if row["refresh_expires_at"] <= now:
                    raise AuthError("refresh_token_expired")
                if row["refresh_secret_hash"] != _hash_secret(refresh_secret):
                    raise AuthError("invalid_token")

                await connection.execute(
                    """
                    update auth_sessions
                    set access_secret_hash = $2,
                        refresh_secret_hash = $3,
                        access_expires_at = $4,
                        refresh_expires_at = $5,
                        last_refreshed_at = now()
                    where id = $1
                    """,
                    session_id,
                    access_secret_hash,
                    refresh_secret_hash,
                    access_expires_at,
                    refresh_expires_at,
                )
                await connection.execute(
                    "update auth_devices set last_seen_at = now() where device_id = $1",
                    normalized_device_id,
                )

        return _session_payload(
            user_id=row["user_id"],
            email=row["email"],
            device_id=normalized_device_id,
            session_id=session_id,
            access_token=access_token,
            refresh_token=next_refresh_token,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    async def revoke_session(self, *, access_token: Optional[str], device_id: str) -> None:
        if not access_token:
            raise AuthError("authorization_required")
        session_id, _ = _parse_token(access_token)
        normalized_device_id = device_id.strip()
        pool = await get_pool()
        async with pool.acquire() as connection:
            result = await connection.execute(
                """
                update auth_sessions
                set revoked_at = coalesce(revoked_at, now())
                where id = $1 and device_id = $2
                """,
                session_id,
                normalized_device_id,
            )
        if result.endswith("0"):
            raise AuthError("session_not_found", status_code=404)

    async def list_sessions(self, user_id: str) -> list[dict[str, Optional[str]]]:
        pool = await get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                select s.id, s.device_id, d.device_name, s.created_at, s.last_refreshed_at,
                       s.access_expires_at, s.refresh_expires_at, s.revoked_at
                from auth_sessions s
                join auth_devices d on d.device_id = s.device_id
                where s.user_id = $1::uuid
                order by s.created_at desc
                """,
                user_id,
            )
        return [
            {
                "session_id": str(row["id"]),
                "device_id": row["device_id"],
                "device_name": row["device_name"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "last_refreshed_at": row["last_refreshed_at"].isoformat() if row["last_refreshed_at"] else None,
                "access_expires_at": row["access_expires_at"].isoformat() if row["access_expires_at"] else None,
                "refresh_expires_at": row["refresh_expires_at"].isoformat() if row["refresh_expires_at"] else None,
                "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None,
            }
            for row in rows
        ]


auth_runtime = AuthRuntimeService()
