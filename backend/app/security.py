from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

ALGORITHM = "HS256"
passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return passwords.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    return bool(password_hash) and passwords.verify(password, password_hash)


def create_token(subject: str, role: str, token_type: str = "access", **extra: Any) -> str:
    lifetime = timedelta(minutes=settings.access_token_minutes)
    if token_type == "refresh":
        lifetime = timedelta(days=settings.refresh_token_days)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + lifetime,
        **extra,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired session") from exc
    if expected_type and payload.get("type") != expected_type:
        raise ValueError(f"A valid {expected_type} token is required")
    return payload


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()
