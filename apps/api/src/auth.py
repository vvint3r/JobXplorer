"""Supabase JWT verification middleware.

Supports both RS256 (newer Supabase projects, verified via JWKS) and
HS256 (legacy projects, verified via symmetric JWT secret).
"""

import logging
import uuid
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_db
from .models.user import User

logger = logging.getLogger(__name__)
security = HTTPBearer()


# ── JWKS cache (fetched once per process, refreshed on key-not-found) ─────────

_jwks_cache: dict = {}


async def _get_jwks(jwks_url: str) -> dict:
    """Fetch and cache JWKS from Supabase."""
    if _jwks_cache:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url, timeout=10)
        resp.raise_for_status()
        _jwks_cache.update(resp.json())
    return _jwks_cache


def _get_unverified_header(token: str) -> dict:
    """Decode the JWT header without verifying the signature."""
    return jwt.get_unverified_header(token)


# ── Main dependency ───────────────────────────────────────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify Supabase JWT (RS256 or HS256) and return the corresponding User row.

    Creates the user row on first login (syncs from Supabase Auth).
    """
    settings = get_settings()
    token = credentials.credentials

    try:
        header = _get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg in ("RS256", "ES256"):
            # Asymmetric — verify via Supabase JWKS public key
            jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
            jwks = await _get_jwks(jwks_url)
            kid = header.get("kid")
            key = next(
                (k for k in jwks.get("keys", []) if k.get("kid") == kid),
                None,
            )
            if key is None:
                # Kid not found — clear cache and retry once
                _jwks_cache.clear()
                jwks = await _get_jwks(jwks_url)
                key = next(
                    (k for k in jwks.get("keys", []) if k.get("kid") == kid),
                    None,
                )
            if key is None:
                raise JWTError(f"Public key with kid={kid} not found in JWKS")

            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256", "ES256"],
                audience="authenticated",
            )
        else:
            # Legacy HS256 — verify via symmetric secret
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )

    except JWTError as e:
        logger.warning("JWT decode failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing sub claim")

    user_id = uuid.UUID(sub)
    email = payload.get("email", "")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        # First login — create local user row synced from Supabase Auth
        user = User(id=user_id, email=email)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
