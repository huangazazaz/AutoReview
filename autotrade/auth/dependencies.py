"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Header, status

from autotrade.auth.auth import verify_token
from autotrade.auth.store import get_user_store, UserRecord


class CurrentUser:
    """Simple user info container returned by get_current_user."""

    def __init__(self, record: UserRecord):
        self.id = record.id
        self.username = record.username
        self.created_at = record.created_at


def get_current_user(
    authorization: Optional[str] = Header(None),
) -> CurrentUser:
    """FastAPI dependency: extract and validate the Bearer token.

    Raises HTTPException(401) if the token is missing, invalid, or the user
    doesn't exist.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证格式错误，应为 Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    store = get_user_store()
    record = store.get_by_id(user_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(record)
