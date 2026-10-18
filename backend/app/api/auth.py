"""
Phase 8.6.2 — Authentication API Router.

Endpoints:
- POST /api/v1/auth/register: User registration
- POST /api/v1/auth/login: User login / Bearer token issuance
- GET  /api/v1/auth/me: Retrieve current authenticated principal
- POST /api/v1/auth/logout: Revoke token / session invalidation
"""

import re
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.entities import User
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    revoke_token,
    require_authenticated_user,
    AuthenticatedPrincipal,
    login_rate_limiter,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-\.]+$")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: Optional[str] = Field("engineer", max_length=32)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        clean = v.strip()
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", clean):
            raise ValueError("Username may only contain alphanumeric characters, hyphens, underscores, and dots.")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email format.")
        return clean


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user with hashed password."""
    username_clean = req.username.strip()
    email_clean = req.email.strip().lower()

    existing_user = db.query(User).filter((User.username == username_clean) | (User.email == email_clean)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered.",
        )

    hashed_pw = hash_password(req.password)
    user = User(
        username=username_clean,
        email=email_clean,
        hashed_password=hashed_pw,
        role=req.role or "engineer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/login", response_model=AuthTokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates user and returns signed JWT access token with brute-force protection."""
    username_clean = req.username.strip()

    # Check brute-force lockout
    is_locked, remaining_seconds = login_rate_limiter.is_locked(username_clean)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Account temporarily locked for {remaining_seconds} seconds.",
            headers={"Retry-After": str(remaining_seconds)},
        )

    user = db.query(User).filter((User.username == username_clean) | (User.email == username_clean.lower())).first()
    if not user or not verify_password(req.password, user.hashed_password):
        login_rate_limiter.record_failure(username_clean)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Success: clear failure counters
    login_rate_limiter.record_success(username_clean)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        email=user.email,
        expires_in_seconds=expires_in,
    )

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
    )


@router.get("/me", response_model=Dict[str, Any])
@router.get("/session", response_model=Dict[str, Any])
@router.get("/profile", response_model=Dict[str, Any])
def get_me(principal: AuthenticatedPrincipal = Depends(require_authenticated_user)):
    """Returns the current verified caller identity."""
    return {
        "user_id": principal.user_id,
        "username": principal.username,
        "email": principal.email,
        "role": principal.role,
        "is_admin": principal.is_admin,
        "is_authenticated": True,
    }


@router.post("/logout", response_model=Dict[str, Any])
def logout(
    authorization: Optional[str] = Header(None),
    principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
):
    """Revokes the current access token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        revoke_token(token)
    return {"status": "logged_out", "user_id": principal.user_id}
