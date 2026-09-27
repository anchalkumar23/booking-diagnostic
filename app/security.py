"""Password hashing and JWT helpers. Plain functions, no classes needed."""
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Precomputed once so a login for a non-existent email still pays bcrypt's
# cost -- otherwise "unknown email" returns near-instantly while "wrong
# password" takes bcrypt's ~100ms, leaking which emails are registered.
_DUMMY_HASH = _pwd_context.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    return _pwd_context.verify(password, hashed or _DUMMY_HASH)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the user_id encoded in the token, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
