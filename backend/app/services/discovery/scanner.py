import os
from pathlib import Path
from typing import List, Dict, Set, Optional
from pydantic import BaseModel, Field
from app.core.filesystem import compute_file_sha256

DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    ".gradle",
    ".m2",
    "vendor",
    "coverage",
    ".next",
    ".nuget",
}

# Maximum size in bytes to inspect line-by-line (2 MB)
MAX_INSPECTION_FILE_SIZE = 2 * 1024 * 1024
# Maximum total files to scan to prevent resource exhaustion bombs
MAX_TOTAL_FILES = 50_000
# Maximum directory nesting depth
MAX_SCAN_DEPTH = 30
# Maximum file size permitted for scanning (50 MB)
MAX_SINGLE_FILE_SIZE = 50 * 1024 * 1024
# Maximum total repository bytes to scan (500 MB cumulative)
MAX_TOTAL_REPO_BYTES = 500 * 1024 * 1024
# Maximum path length permitted
MAX_PATH_LENGTH = 1024
# Maximum symlink count before pruning
MAX_SYMLINKS_COUNT = 1000
# Maximum scan duration before truncation (120 seconds)
MAX_SCAN_DURATION_SECONDS = 120


class ScannedFile(BaseModel):
    relative_path: str
    absolute_path: str
    file_name: str
    extension: str
    size_bytes: int
    line_count: int = 0
    is_binary: bool = False
    sha256_hash: str


class FileInventory(BaseModel):
    root_path: str
    total_files: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    is_truncated: bool = False
    truncation_reason: Optional[str] = None
    files: List[ScannedFile] = Field(default_factory=list)
    files_by_name: Dict[str, List[ScannedFile]] = Field(default_factory=dict)
    files_by_ext: Dict[str, List[ScannedFile]] = Field(default_factory=dict)
    manifest_files: List[ScannedFile] = Field(default_factory=list)
    docker_files: List[ScannedFile] = Field(default_factory=list)
    ci_cd_files: List[ScannedFile] = Field(default_factory=list)



def is_binary_string(bytes_sample: bytes) -> bool:
    """Deterministic check if file header indicates binary content."""
    text_characters = bytes(range(32, 127)) + b"\n\r\t\b"
    _null_trans = bytes.maketrans(b"", b"")
    if not bytes_sample:
        return False
    if b"\x00" in bytes_sample:
        return True
    # Count non-text bytes
    non_text = bytes_sample.translate(_null_trans, text_characters)
    return len(non_text) / len(bytes_sample) > 0.30


def count_lines_streaming(filepath: str) -> int:
    """Stream file line counting without loading the full file into memory."""
    lines = 0
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                lines += chunk.count(b"\n")
        return lines
    except Exception:
        return 0


class RepositoryScanner:
    """High-performance deterministic scanner for repository file inventory."""

    def __init__(self, ignore_dirs: Optional[Set[str]] = None):
        self.ignore_dirs = ignore_dirs or DEFAULT_IGNORE_DIRS

    def scan(self, repo_path: str) -> FileInventory:
        import time
        start_time = time.time()

        abs_root = os.path.abspath(repo_path)
        if not os.path.exists(abs_root) or not os.path.isdir(abs_root):
            raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")

        abs_root_path = Path(abs_root).resolve()
        inventory = FileInventory(root_path=str(abs_root_path))
        symlink_count = 0

        for root, dirs, files in os.walk(abs_root, topdown=True, followlinks=False):
            # Check maximum scan duration
            if time.time() - start_time > MAX_SCAN_DURATION_SECONDS:
                inventory.is_truncated = True
                inventory.truncation_reason = "MAX_SCAN_DURATION_EXCEEDED"
                dirs.clear()
                break

            # Enforce max directory traversal depth
            rel_dir = os.path.relpath(root, abs_root)
            depth = 0 if rel_dir == "." else len(Path(rel_dir).parts)
            if depth >= MAX_SCAN_DEPTH:
                dirs.clear()
                continue

            # Prune ignored directories and symlinked directories in-place
            dirs[:] = [
                d for d in dirs
                if d not in self.ignore_dirs
                and not d.startswith(".")
                and not os.path.islink(os.path.join(root, d))
            ]

            for fname in files:
                if inventory.total_files >= MAX_TOTAL_FILES:
                    inventory.is_truncated = True
                    inventory.truncation_reason = "MAX_TOTAL_FILES_EXCEEDED"
                    break

                full_path = os.path.join(root, fname)

                # Path length check
                if len(full_path) > MAX_PATH_LENGTH:
                    continue

                # Symlink Containment Check: ensure symlinks do not escape repository root
                if os.path.islink(full_path):
                    symlink_count += 1
                    if symlink_count > MAX_SYMLINKS_COUNT:
                        continue
                    try:
                        resolved_target = Path(full_path).resolve()
                        resolved_target.relative_to(abs_root_path)
                    except (ValueError, RuntimeError, OSError):
                        # Symlink points outside repository root! Skip for security.
                        continue

                # Skip broken symlinks, special devices, or unreadable entries
                if not os.path.isfile(full_path):
                    continue

                try:
                    stat_res = os.stat(full_path)
                    size = stat_res.st_size
                except OSError:
                    continue

                # Skip files exceeding safety ceiling
                if size > MAX_SINGLE_FILE_SIZE:
                    continue

                # Cumulative repository bytes ceiling check
                if inventory.total_bytes + size > MAX_TOTAL_REPO_BYTES:
                    inventory.is_truncated = True
                    inventory.truncation_reason = "MAX_TOTAL_REPO_BYTES_EXCEEDED"
                    dirs.clear()
                    break

                rel_path = os.path.relpath(full_path, abs_root)
                _, ext = os.path.splitext(fname)
                ext = ext.lower()

                # Canonical File Content Hash: compute deterministic SHA-256 immediately from bytes
                try:
                    file_sha256 = compute_file_sha256(full_path)
                except Exception:
                    # Skip file if unreadable due to filesystem permissions or concurrent deletion
                    continue

                # Check if binary
                is_binary = False
                line_count = 0
                if size <= MAX_INSPECTION_FILE_SIZE:
                    try:
                        with open(full_path, "rb") as f:
                            sample = f.read(1024)
                            is_binary = is_binary_string(sample)
                        if not is_binary:
                            line_count = count_lines_streaming(full_path)
                    except Exception:
                        is_binary = True
                else:
                    is_binary = True

                scanned_file = ScannedFile(
                    relative_path=rel_path,
                    absolute_path=full_path,
                    file_name=fname,
                    extension=ext,
                    size_bytes=size,
                    line_count=line_count,
                    is_binary=is_binary,
                    sha256_hash=file_sha256,
                )


                inventory.files.append(scanned_file)
                inventory.total_files += 1
                inventory.total_lines += line_count
                inventory.total_bytes += size

                # Index by name
                inventory.files_by_name.setdefault(fname, []).append(scanned_file)

                # Index by extension
                if ext:
                    inventory.files_by_ext.setdefault(ext, []).append(scanned_file)

                # Specific category indexes
                lower_name = fname.lower()
                if lower_name in {
                    "pom.xml", "build.gradle", "settings.gradle", "build.gradle.kts",
                    "package.json", "pyproject.toml", "requirements.txt", "pipfile", "setup.py",
                    "go.mod", "cargo.toml", "cmakelists.txt", "makefile", "composer.json",
                    "gemfile", "pubspec.yaml"
                } or lower_name.endswith(".csproj") or lower_name.endswith(".sln"):
                    inventory.manifest_files.append(scanned_file)

                if "dockerfile" in lower_name or lower_name.startswith("docker-compose"):
                    inventory.docker_files.append(scanned_file)

                if ".github/workflows" in rel_path or lower_name in {".gitlab-ci.yml", "jenkinsfile"}:
                    inventory.ci_cd_files.append(scanned_file)

        return inventory
