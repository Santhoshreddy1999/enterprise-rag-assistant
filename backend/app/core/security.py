from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import Settings

_PASSWORD_HASH = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASH.hash("not-a-real-user-password")


class InvalidAccessTokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return _PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    try:
        return _PASSWORD_HASH.verify_and_update(password, password_hash)
    except (TypeError, ValueError):
        return False, None


def consume_dummy_password_check(password: str) -> None:
    """Keep missing-user authentication close to the valid-user timing path."""

    _PASSWORD_HASH.verify(password, _DUMMY_PASSWORD_HASH)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    encoded = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "iat", "exp", "jti", "type"]},
        )
        if payload.get("type") != "access":
            raise InvalidAccessTokenError("unexpected token type")
        return uuid.UUID(str(payload["sub"]))
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError("invalid access token") from exc
