import os
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

import bcrypt
import jwt


JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30


def hashpwd(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verifypwd(password: str, hashpassword: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashpassword.encode("utf-8"))


def _create_token(sub: str, token_type: Literal["access", "refresh"], expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    return _create_token(str(user_id), "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: UUID) -> str:
    return _create_token(str(user_id), "refresh", timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> dict:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return payload


def create_verification_token(user_id: UUID) -> str:
    return _create_token(str(user_id), "access", timedelta(hours=24))


def create_password_reset_token(user_id: UUID) -> str:
    return _create_token(str(user_id), "access", timedelta(hours=1))
