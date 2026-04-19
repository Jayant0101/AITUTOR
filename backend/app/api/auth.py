"""JWT authentication and password hashing utilities."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.debug_log import debug_log

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Production Secret Key handling
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Check for legacy variable name or generate a one-time secret
    SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    
if not SECRET_KEY:
    import secrets
    SECRET_KEY = secrets.token_urlsafe(32)
    import logging
    logging.getLogger(__name__).warning("SECRET_KEY not set in environment. Generating a random one-time key.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h default

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------
def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Dependency that extracts and validates the current user from a JWT."""
    debug_log(hypothesisId="B", message="auth_token_received", data={"token_present": bool(token)})
    try:
        payload = decode_access_token(token)
    except HTTPException:
        debug_log(
            hypothesisId="B",
            message="auth_decode_failed",
            data={"status_code": status.HTTP_401_UNAUTHORIZED},
        )
        raise

    user_id: str | None = payload.get("sub")
    if not user_id:
        debug_log(hypothesisId="B", message="auth_missing_sub_claim", data={})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    # For middleware logging
    from fastapi import Request
    # This is a bit hacky but works for setting request state from dependency
    # A better way is middleware, but we have dependencies for auth
    import inspect
    for frame in inspect.stack():
        if 'request' in frame.frame.f_locals:
            req = frame.frame.f_locals['request']
            if isinstance(req, Request):
                req.state.user_id = user_id
                break

    # user_id is not secret; avoid logging token contents / user email.
    debug_log(hypothesisId="B", message="auth_user_decoded", data={"user_id": user_id})
    return {"user_id": user_id, "email": payload.get("email", "")}
