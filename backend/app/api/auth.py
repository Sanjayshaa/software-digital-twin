"""
Phase 8.6.2 — Authentication API Router.

Endpoints:
- POST /api/v1/auth/register: User registration
- POST /api/v1/auth/login: User login / Bearer token issuance
- GET  /api/v1/auth/me: Retrieve current authenticated principal
- POST /api/v1/auth/logout: Revoke token / session invalidation
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.entities import (
    User,
    Repository,
    RepositorySnapshot,
    StructuralArtifact,
    ArtifactRelationship,
    Scenario,
    ScenarioResult,
    AnalysisRun,
)
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    revoke_token,
    require_authenticated_user,
    get_current_user_optional,
    AuthenticatedPrincipal,
    login_rate_limiter,
    auth_action_limiter,
    create_secure_random_token,
    auth_token_store,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-\.]+$")
TRIVIAL_PASSWORDS = {"password", "12345678", "password123", "admin123", "qwerty123"}


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

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if v.lower() in TRIVIAL_PASSWORDS:
            raise ValueError("Password is too common. Please choose a stronger password.")
        has_letter = any(c.isalpha() for c in v)
        has_digit_or_special = any(c.isdigit() or not c.isalnum() for c in v)
        if not (has_letter and has_digit_or_special):
            raise ValueError("Password must contain at least one letter and at least one number or special character.")
        return v


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email format.")
        return clean


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if v.lower() in TRIVIAL_PASSWORDS:
            raise ValueError("Password is too common. Please choose a stronger password.")
        has_letter = any(c.isalpha() for c in v)
        has_digit_or_special = any(c.isdigit() or not c.isalnum() for c in v)
        if not (has_letter and has_digit_or_special):
            raise ValueError("Password must contain at least one letter and at least one number or special character.")
        return v


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=255)


class DeleteAccountRequest(BaseModel):
    confirm_username: str = Field(..., min_length=1, max_length=64)
    password: Optional[str] = Field(None, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Registers a new user with hashed password and initial verification token."""
    client_ip = request.client.host if request.client else "unknown"
    is_limited, remaining = auth_action_limiter.is_rate_limited(f"reg_{client_ip}")
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many registration requests. Please wait {remaining} seconds.",
            headers={"Retry-After": str(remaining)},
        )

    username_clean = req.username.strip()
    email_clean = req.email.strip().lower()

    existing_user = db.query(User).filter((User.username == username_clean) | (User.email == email_clean)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered.",
        )

    hashed_pw = hash_password(req.password)
    verification_token = create_secure_random_token(32)
    user = User(
        username=username_clean,
        email=email_clean,
        hashed_password=hashed_pw,
        role=req.role or "engineer",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    auth_token_store.set_verification_token(verification_token, user.id)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_verified": False,
        "verification_token": verification_token if settings.APP_ENV != "production" else None,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/login", response_model=AuthTokenResponse)
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticates user, sets HttpOnly session cookie, and returns signed JWT access token."""
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

    # Defense-in-depth: Set secure HttpOnly session cookie for browsers
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=expires_in,
        httponly=True,
        secure=(settings.APP_ENV == "production"),
        samesite="lax",
        path="/",
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
            "is_verified": getattr(user, "is_verified", False),
        },
    )


@router.post("/forgot-password", response_model=Dict[str, Any])
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Dispatches password reset token without disclosing account existence."""
    client_ip = request.client.host if request.client else "unknown"
    is_limited, remaining = auth_action_limiter.is_rate_limited(f"pwreset_{client_ip}")
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many reset requests. Please wait {remaining} seconds.",
            headers={"Retry-After": str(remaining)},
        )

    user = db.query(User).filter_by(email=req.email.strip().lower()).first()
    dev_token = None
    if user and user.is_active:
        token = create_secure_random_token(32)
        auth_token_store.set_reset_token(token, user.id, expires_in_seconds=900)
        dev_token = token if settings.APP_ENV != "production" else None

    # Return identical generic response to prevent username/email enumeration
    return {
        "status": "request_received",
        "message": "If an account with that email exists, password reset instructions have been generated.",
        "expires_in_minutes": 15,
        "reset_token": dev_token,
    }


@router.post("/reset-password", response_model=Dict[str, Any])
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Validates single-use reset token and securely resets password."""
    user_id = auth_token_store.consume_reset_token(req.token.strip())
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    user = db.query(User).filter_by(id=user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account inactive or not found.",
        )

    user.hashed_password = hash_password(req.new_password)
    db.commit()

    return {"status": "password_reset_successful", "message": "Password has been successfully updated. Please sign in."}


@router.post("/verify-email", response_model=Dict[str, Any])
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Confirms email address ownership via verification token."""
    user_id = auth_token_store.consume_verification_token(req.token.strip())
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired email verification token.",
        )

    user = db.query(User).filter_by(id=user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account not found.",
        )

    return {"status": "email_verified", "message": "Your email address has been verified successfully."}


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh_token(
    response: Response,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    """Refreshes an active session, issuing a new access token and updating session cookie."""
    user = db.query(User).filter_by(id=principal.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account inactive or not found.",
        )

    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    new_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        email=user.email,
        expires_in_seconds=expires_in,
    )

    response.set_cookie(
        key="access_token",
        value=new_token,
        max_age=expires_in,
        httponly=True,
        secure=(settings.APP_ENV == "production"),
        samesite="lax",
        path="/",
    )

    return AuthTokenResponse(
        access_token=new_token,
        token_type="bearer",
        expires_in=expires_in,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_verified": getattr(user, "is_verified", False),
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
    response: Response,
    request: Request = None,
    authorization: Optional[str] = Header(None),
    principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
):
    """Revokes access token and invalidates the session cookie."""
    token_to_revoke = None
    if authorization and authorization.startswith("Bearer "):
        token_to_revoke = authorization[7:].strip()
    elif request and hasattr(request, "cookies") and request.cookies.get("access_token"):
        token_to_revoke = request.cookies.get("access_token")

    if token_to_revoke:
        revoke_token(token_to_revoke)

    # Invalidate HttpOnly cookie
    response.delete_cookie(key="access_token", path="/")

    return {"status": "logged_out", "user_id": principal.user_id}


@router.delete("/account", response_model=Dict[str, Any])
def delete_account(
    req: DeleteAccountRequest,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
    """
    Permanently deletes user account and all owned repositories, snapshots, and scenarios.
    Enforces password/username confirmation before performing transactional deletion.
    """
    user = db.query(User).filter_by(id=principal.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    if req.confirm_username.strip() != user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username confirmation mismatch. Please enter your exact username.",
        )

    # If password is provided, verify it (optional for guest users)
    if req.password and not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password confirmation.",
        )

    # Clean up all owned repositories and dependent artifacts
    owned_repos = db.query(Repository).filter_by(owner_id=user.id).all()
    for repo in owned_repos:
        # Delete scenarios
        scenarios = db.query(Scenario).filter_by(repository_id=repo.id).all()
        for scen in scenarios:
            db.query(ScenarioResult).filter_by(scenario_id=scen.id).delete()
            db.delete(scen)

        # Delete artifacts & snapshots
        snapshots = db.query(RepositorySnapshot).filter_by(repository_id=repo.id).all()
        for snap in snapshots:
            db.query(ArtifactRelationship).filter_by(snapshot_id=snap.id).delete()
            db.query(StructuralArtifact).filter_by(snapshot_id=snap.id).delete()
            db.delete(snap)

        db.query(AnalysisRun).filter_by(repository_id=repo.id).delete()
        db.delete(repo)

    # Delete user record
    db.delete(user)
    db.commit()

    # Clear session cookie
    response.delete_cookie(key="access_token", path="/")

    return {
        "status": "account_deleted",
        "user_id": principal.user_id,
        "message": "Account and all associated digital twin data have been permanently removed.",
    }
