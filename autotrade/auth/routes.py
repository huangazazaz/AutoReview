"""Auth API routes — registration, login, user info."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from autotrade.auth.auth import hash_password, verify_password, create_token
from autotrade.auth.dependencies import get_current_user, CurrentUser
from autotrade.auth.store import get_user_store


router = APIRouter(prefix="/auth", tags=["auth"])


# ---- Request / Response models ----

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class AuthResponse(BaseModel):
    token: str
    user: dict


# ---- Routes ----

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    """Register a new user account."""
    store = get_user_store()

    username = req.username.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名不能为空",
        )
    if len(username) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名至少需要2个字符",
        )

    password = req.password
    if len(password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码至少需要4个字符",
        )

    try:
        record = store.create_user(username, hash_password(password))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    token = create_token(record.id, record.username)
    return AuthResponse(
        token=token,
        user={
            "id": record.id,
            "username": record.username,
            "created_at": record.created_at,
        },
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """Authenticate and return a JWT token."""
    store = get_user_store()

    record = store.get_by_username(req.username.strip())
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not verify_password(req.password, record.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_token(record.id, record.username)
    return AuthResponse(
        token=token,
        user={
            "id": record.id,
            "username": record.username,
            "created_at": record.created_at,
        },
    )


@router.get("/me")
def me(current_user: CurrentUser = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "created_at": current_user.created_at,
    }
