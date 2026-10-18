"""
Phase 8.6.2 — Core Authentication & Authorization Infrastructure.

Provides:
1. Cryptographically secure password hashing and verification using PBKDF2-HMAC-SHA256.
2. Standard JWT/HMAC-SHA256 signed Bearer token issuance, parsing, expiration, and signature verification.
3. In-memory token revocation list for instantaneous logout/invalidation.
4. AuthenticatedPrincipal model representing verified callers.
5. FastAPI dependencies for authentication and repository object-level authorization.
"""

import hmac
import hashlib
import base64
import json
import time
import secrets
import os
import uuid
from typing import Optional, Dict, Any, Set, Tuple
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.entities import User, Repository


# ====================================================================
# 1. CANONICAL PRINCIPAL MODEL
# ====================================================================

class AuthenticatedPrincipal(BaseModel):
    user_id: str
    username: str = "engineer"
    email: Optional[str] = None
    role: str = "engineer"  # admin, engineer, viewer
    is_authenticated: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role.lower() == "admin"


# ====================================================================
# 2. TOKEN REVOCATION CACHE
# ====================================================================

# Set of revoked token JTIs or token strings
_REVOKED_TOKENS: Set[str] = set()


def revoke_token(token: str) -> None:
    """Marks a token or token identifier as revoked."""
    if token:
        _REVOKED_TOKENS.add(token.strip())


def is_token_revoked(token: str) -> bool:
    """Checks whether a token is revoked."""
    return token.strip() in _REVOKED_TOKENS


# ====================================================================
# 2.1 LOGIN RATE LIMITING & BRUTE-FORCE PROTECTION
# ====================================================================

import threading
from typing import Tuple


class LoginRateLimiter:
    """
    In-memory, thread-safe rate limiter to prevent login brute-forcing.
    Tracks failed attempts per identifier within a rolling time window.
    """

    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 300):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._lock = threading.Lock()
        self._failures: Dict[str, list] = {}

    def is_locked(self, identifier: str) -> Tuple[bool, int]:
        """Returns (is_locked, remaining_seconds)."""
        now = time.time()
        with self._lock:
            attempts = self._failures.get(identifier, [])
            valid_attempts = [t for t in attempts if now - t < self.lockout_seconds]
            self._failures[identifier] = valid_attempts
            if len(valid_attempts) >= self.max_attempts:
                oldest = valid_attempts[0]
                remaining = int(self.lockout_seconds - (now - oldest))
                return True, max(1, remaining)
            return False, 0

    def record_failure(self, identifier: str) -> None:
        now = time.time()
        with self._lock:
            attempts = self._failures.get(identifier, [])
            attempts = [t for t in attempts if now - t < self.lockout_seconds]
            attempts.append(now)
            self._failures[identifier] = attempts

    def record_success(self, identifier: str) -> None:
        with self._lock:
            self._failures.pop(identifier, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.AUTH_MAX_LOGIN_ATTEMPTS,
    lockout_seconds=settings.AUTH_LOCKOUT_SECONDS,
)


# ====================================================================
# 3. PASSWORD HASHING (PBKDF2-HMAC-SHA256)
# ====================================================================

def hash_password(plain_password: str) -> str:
    """Hashes a plaintext password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored PBKDF2 salt$hash string."""
    try:
        if "$" not in hashed_password:
            return False
        salt_hex, key_hex = hashed_password.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        computed_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(computed_key, expected_key)
    except Exception:
        return False


# ====================================================================
# 4. JWT TOKEN ISSUANCE & VERIFICATION
# ====================================================================

def _b64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_url_decode(data_str: str) -> bytes:
    padding = "=" * (-len(data_str) % 4)
    return base64.urlsafe_b64decode((data_str + padding).encode("utf-8"))


def create_access_token(
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    role: str = "engineer",
    email: Optional[str] = None,
    expires_in_seconds: Optional[int] = None,
    secret_key: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Issues a cryptographically signed HMAC-SHA256 JWT access token.
    """
    if data:
        user_id = data.get("sub", user_id or "usr_anon")
        username = data.get("username", username or user_id or "engineer")
        role = data.get("role", role)
        email = data.get("email", email)

    user_id = user_id or "usr_anon"
    username = username or "engineer"

    key = (secret_key or settings.SECRET_KEY).encode("utf-8")
    now = int(time.time())
    ttl = expires_in_seconds if expires_in_seconds is not None else (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    exp = now + ttl

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "email": email or f"{username}@digitaltwin.local",
        "iat": now,
        "exp": exp,
        "jti": secrets.token_hex(16),
    }

    header_b64 = _b64_url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64_url_encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(
    token: str,
    secret_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Decodes and verifies an access token.
    Raises HTTPException(401) on invalid signature, malformed structure, expiration, or revocation.
    """
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: invalid segment count",
            headers={"WWW-Authenticate": "Bearer"},
        )

    header_b64, payload_b64, sig_b64 = parts

    try:
        header_bytes = _b64_url_decode(header_b64)
        header = json.loads(header_bytes.decode("utf-8"))
        if header.get("alg") != "HS256":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unsupported algorithm: {header.get('alg')}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify signature
    key = (secret_key or settings.SECRET_KEY).encode("utf-8")
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()

    try:
        actual_sig = _b64_url_decode(sig_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token signature",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not hmac.compare_digest(actual_sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and check payload
    try:
        payload_bytes = _b64_url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    exp = payload.get("exp")
    if exp is not None and int(exp) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


# ====================================================================
# 5. FASTAPI DEPENDENCIES & AUTHORIZATION
# ====================================================================

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[AuthenticatedPrincipal]:
    """
    Extracts authenticated user from Authorization Bearer token if present.
    Returns None if no token provided.
    Raises HTTPException(401) if token is provided but invalid/expired.
    """
    if not credentials or not credentials.credentials:
        return None

    payload = decode_access_token(credentials.credentials)
    return AuthenticatedPrincipal(
        user_id=payload.get("sub", ""),
        username=payload.get("username", "anonymous"),
        email=payload.get("email"),
        role=payload.get("role", "engineer"),
        is_authenticated=True,
    )


def require_authenticated_user(
    principal: Optional[AuthenticatedPrincipal] = Depends(get_current_user_optional),
) -> AuthenticatedPrincipal:
    """
    Enforces that caller has a valid, unexpired Authorization Bearer token.
    """
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: missing or invalid Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def resolve_authorized_repo(
    db: Session,
    repository_id: str,
    principal: Optional[AuthenticatedPrincipal] = None,
) -> Optional[Repository]:
    """
    Authoritatively resolves a repository by ID, name, or local_path,
    enforcing multi-user tenant privacy and role-based access control.

    Rules:
    1. Repositories with environment='TEST' or 'FIXTURE' are accessible for internal test harnesses.
    2. Admin principals have universal read/write access.
    3. Authenticated engineers have access strictly to repositories where repository.owner_id == principal.user_id.
    4. Unauthenticated guests have ZERO access to user repositories (returns None, yielding 404 non-disclosure).
    5. Cross-user access (User B requesting User A's repository) returns None (yielding 404 non-disclosure).
    """
    from sqlalchemy import or_

    repo = (
        db.query(Repository)
        .filter(
            or_(
                Repository.id == repository_id,
                Repository.name == repository_id,
                Repository.local_path == repository_id,
            )
        )
        .first()
    )
    if not repo:
        return None

    # System fixtures without an owner are accessible ONLY during pytest execution
    if repo.owner_id is None and repo.environment in ["TEST", "FIXTURE"]:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return repo
        return None

    # Guest / Unauthenticated: Deny access to any owned repository or user workspace
    if not principal:
        return None

    # Admin: Universal access
    if principal.is_admin:
        return repo

    # Owner: Access allowed strictly to own repository
    if repo.owner_id == principal.user_id:
        return repo

    # Deny cross-user access
    return None


def provision_guest_user(db: Session) -> Tuple[User, str]:
    """
    Provisions an ephemeral, isolated guest identity and returns (user, jwt_token).
    Enforces that anonymous workspaces have an isolated user identity,
    guaranteeing multi-tenant non-disclosure against all other guests and registered users.
    """
    unique_suffix = uuid.uuid4().hex[:12]
    guest_user = User(
        id=f"usr_guest_{unique_suffix}",
        username=f"guest_{unique_suffix}",
        email=f"guest_{unique_suffix}@guest.digitaltwin.local",
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role="guest",
        is_active=True,
    )
    db.add(guest_user)
    db.commit()
    db.refresh(guest_user)
    token = create_access_token(
        user_id=guest_user.id,
        username=guest_user.username,
        role="guest",
    )
    return guest_user, token


def get_authorized_repository(
    repository_id: str,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> Repository:
    """
    Resolves repository by ID or name and enforces ownership-level authorization:
    1. Admin principal has universal access.
    2. Repository with owner_id == principal.user_id is accessible to the owner.
    3. Otherwise, returns 404 NOT FOUND (preventing resource enumeration by unauthorized users).
    """
    repo = resolve_authorized_repo(db=db, repository_id=repository_id, principal=principal)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return repo
