import hashlib


def build_artifact_id(
    snapshot_id: str,
    language: str,
    file_path: str,
    artifact_type: str,
    qualified_name: str
) -> str:
    """
    Generates a deterministic, reproducible, stable identifier for an artifact.
    Re-analyzing the same repository snapshot produces the exact same ID.
    """
    norm_path = file_path.replace("\\", "/").strip("/")
    raw = f"{snapshot_id}::{language.lower()}::{norm_path}::{artifact_type.upper()}::{qualified_name}"
    return f"art_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:28]}"


def build_relationship_id(
    snapshot_id: str,
    source_artifact_id: str,
    relationship_type: str,
    target_artifact_id: str
) -> str:
    """
    Generates a deterministic stable identifier for a relationship edge.
    """
    raw = f"{snapshot_id}::{source_artifact_id}::{relationship_type.upper()}::{target_artifact_id}"
    return f"rel_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:28]}"
