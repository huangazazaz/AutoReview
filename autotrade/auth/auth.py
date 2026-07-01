"""Password hashing and JWT token management."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Optional

import jwt

# JWT secret — prefer env var, fall back to a hardcoded default (change in production!)
_JWT_SECRET = os.environ.get("JWT_SECRET", "backtestlab-jwt-secret-change-me")
_JWT_ALGORITHM = "HS256"
_TOKEN_EXPIRE_SECONDS = 7 * 24 * 3600  # 7 days


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt.

    Returns a string in the format:  algorithm$iterations$salt$hash
    """
    algorithm = "pbkdf2_sha256"
    iterations = 600_000
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{algorithm}${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password against an encoded hash."""
    try:
        algorithm, iterations_str, salt_hex, hash_hex = encoded.split("$", 3)
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        actual_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return actual_hash == expected_hash
    except (ValueError, AttributeError):
        return False


def create_token(user_id: str, username: str) -> str:
    """Create a JWT token for the given user."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + _TOKEN_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token. Returns payload dict or None."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
