import os
from typing import List, Dict, Set, Optional
from pydantic import BaseModel, Field

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


class ScannedFile(BaseModel):
    relative_path: str
    absolute_path: str
    file_name: str
    extension: str
    size_bytes: int
    line_count: int = 0
    is_binary: bool = False


class FileInventory(BaseModel):
    root_path: str
    total_files: int = 0
    total_lines: int = 0
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
        abs_root = os.path.abspath(repo_path)
        if not os.path.exists(abs_root) or not os.path.isdir(abs_root):
            raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")

        inventory = FileInventory(root_path=abs_root)

        for root, dirs, files in os.walk(abs_root, topdown=True):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs and not d.startswith(".")]

            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, abs_root)

                # Skip broken symlinks or special devices
                if not os.path.isfile(full_path):
                    continue

                try:
                    stat_res = os.stat(full_path)
                    size = stat_res.st_size
                except OSError:
                    continue

                _, ext = os.path.splitext(fname)
                ext = ext.lower()

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

                scanned_file = ScannedFile(
                    relative_path=rel_path,
                    absolute_path=full_path,
                    file_name=fname,
                    extension=ext,
                    size_bytes=size,
                    line_count=line_count,
                    is_binary=is_binary,
                )

                inventory.files.append(scanned_file)
                inventory.total_files += 1
                inventory.total_lines += line_count

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
