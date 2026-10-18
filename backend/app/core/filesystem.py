"""
Phase 8.6.3 — Filesystem Isolation & Workspace Containment Service.

Provides:
1. Canonical path resolution and boundary containment verification.
2. Prevention of arbitrary filesystem ingestion (SEC-01).
3. Symlink escape detection preventing traversal outside authorized roots.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, List
from fastapi import HTTPException, status
from app.core.config import settings

# Base repository root of the application
_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_default_allowed_roots() -> List[Path]:
    """Returns canonical resolved allowed workspace roots."""
    roots = [
        _DEFAULT_PROJECT_ROOT.resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]
    # Add any explicitly configured roots from settings/env
    for custom in settings.ALLOWED_WORKSPACE_ROOTS:
        if custom and custom.strip():
            roots.append(Path(custom.strip()).resolve())
    return roots


def validate_safe_local_path(
    candidate_path: str,
    allowed_roots: Optional[List[Path]] = None,
) -> str:
    """
    Validates that candidate_path:
    1. Is a non-empty string.
    2. Exists on the local filesystem and is a directory.
    3. Resolves to a canonical path strictly contained within an approved workspace root.
    4. Is not a sensitive system directory (/etc, /var, /usr, /System, etc.).
    5. Does not escape via symlink or directory traversal.

    Returns:
        Canonical absolute path string.

    Raises:
        HTTPException(400) if validation fails.
    """
    if not candidate_path or not isinstance(candidate_path, str) or not candidate_path.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local path must be a non-empty string.",
        )

    raw_path = candidate_path.strip()
    try:
        candidate = Path(raw_path).resolve(strict=True)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Local path does not exist or is not a directory: '{raw_path}'",
        )
    except (PermissionError, RuntimeError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path resolution error: {str(exc)}",
        )

    if not candidate.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Local path does not exist or is not a directory: '{raw_path}'",
        )

    # Disallow sensitive root/system directories unconditionally
    forbidden_system_dirs = {
        Path("/"),
        Path("/etc"),
        Path("/var"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/System"),
        Path("/Library"),
        Path("/private"),
        Path("/private/etc"),
        Path("/private/var"),
    }
    if candidate in forbidden_system_dirs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access denied: system directories cannot be onboarded as repositories.",
        )

    # Containment check against allowed roots
    roots = allowed_roots if allowed_roots is not None else get_default_allowed_roots()
    is_contained = False
    for root in roots:
        try:
            candidate.relative_to(root)
            is_contained = True
            break
        except ValueError:
            continue

    if not is_contained:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access denied: path is outside the authorized workspace root.",
        )

    return str(candidate)
