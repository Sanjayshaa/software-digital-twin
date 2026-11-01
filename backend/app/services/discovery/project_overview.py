"""
Project Overview Intelligence & Deep Repository Understanding.
Extracts project purpose from README/manifests, organizes the tech stack,
identifies entry points, APIs, services, database entities, and test coverage.
Strictly deterministic with zero fabricated data.
"""

import os
import re
import json
from typing import Dict, Any, List, Optional
from app.models.entities import StructuralArtifact, ArtifactRelationship, Repository


def extract_project_purpose(repo_path: Optional[str], default_name: str = "Project") -> str:
    """
    Extracts a clear, human-readable project purpose/summary from README or manifest files.
    """
    if not repo_path or not os.path.exists(repo_path):
        return f"{default_name} — Connected codebase indexed in TwinCore Software Digital Twin."

    # 1. Try reading package.json description
    pkg_json_path = os.path.join(repo_path, "package.json")
    if os.path.exists(pkg_json_path):
        try:
            with open(pkg_json_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                desc = data.get("description", "").strip()
                if desc and len(desc) > 10:
                    return desc
        except Exception:
            pass

    # 2. Try reading README.md / README.markdown / README.rst / README.txt
    for fname in ["README.md", "readme.md", "README.markdown", "README.rst", "README.txt"]:
        readme_path = os.path.join(repo_path, fname)
        if os.path.exists(readme_path):
            try:
                with open(readme_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                lines = content.splitlines()
                para_lines = []
                in_code_block = False

                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        continue

                    # Skip badges, HTML tags, or markdown headers
                    if not stripped:
                        if para_lines:
                            break
                        continue
                    if stripped.startswith("#") or stripped.startswith("![") or stripped.startswith("[!") or stripped.startswith("<"):
                        continue
                    if stripped.startswith("===") or stripped.startswith("---"):
                        continue

                    para_lines.append(stripped)

                if para_lines:
                    text = " ".join(para_lines).strip()
                    if len(text) > 20:
                        return text[:350] + ("..." if len(text) > 350 else "")
            except Exception:
                pass

    # 3. Try reading pyproject.toml
    pyproject_path = os.path.join(repo_path, "pyproject.toml")
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                m = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
                if m and len(m.group(1).strip()) > 10:
                    return m.group(1).strip()
        except Exception:
            pass

    return f"{default_name} — Software Digital Twin representation with structural AST and knowledge graph intelligence."


def extract_entry_points(repo_path: Optional[str], artifacts: List[StructuralArtifact]) -> List[Dict[str, str]]:
    """
    Identifies primary entry points (server roots, web apps, CLI entry points, config entry points).
    """
    entry_points = []
    seen = set()

    # Look for well-known entry files
    common_entry_patterns = [
        ("server.cjs", "Backend Server (CommonJS Entry Point)"),
        ("server.js", "Backend Server (Node.js Entry Point)"),
        ("src/index.tsx", "Frontend Client (React/TypeScript Entry Point)"),
        ("src/index.jsx", "Frontend Client (React Entry Point)"),
        ("src/main.ts", "Frontend Client (Vite/TypeScript Entry Point)"),
        ("src/main.tsx", "Frontend Client (Vite/React Entry Point)"),
        ("src/App.tsx", "Frontend Root Application Component"),
        ("src/App.jsx", "Frontend Root Application Component"),
        ("main.py", "Application Entry Point (Python)"),
        ("app.py", "Web Application Entry Point (Python)"),
        ("backend/main.py", "Backend API Server (FastAPI/Python Entry Point)"),
        ("backend/app/main.py", "Backend API Server (FastAPI Entry Point)"),
        ("manage.py", "Django Management CLI Entry Point"),
        ("Dockerfile", "Container Build Specification"),
        ("docker-compose.yml", "Multi-Service Container Orchestration"),
    ]

    if repo_path and os.path.exists(repo_path):
        for rel_file, role in common_entry_patterns:
            full_path = os.path.join(repo_path, rel_file)
            if os.path.exists(full_path) and rel_file not in seen:
                seen.add(rel_file)
                entry_points.append({
                    "file_path": rel_file,
                    "role": role,
                    "type": "FILE",
                })

    # Look for API entry points in artifacts
    for a in artifacts:
        if a.artifact_type in ("API_ENDPOINT", "ROUTE"):
            loc = a.location or ""
            fpath = loc.split(":")[0] if loc else a.name
            if fpath and fpath not in seen:
                seen.add(fpath)
                entry_points.append({
                    "file_path": fpath,
                    "role": f"API Endpoint / Route Definition ({a.name})",
                    "type": "API_ENDPOINT",
                })
            if len(entry_points) >= 8:
                break

    return entry_points


def extract_service_and_api_inventory(artifacts: List[StructuralArtifact]) -> List[Dict[str, Any]]:
    """
    Extracts all detected APIs, HTTP routes, and services with locations and methods.
    """
    endpoints = []
    for a in artifacts:
        if a.artifact_type in ("API_ENDPOINT", "ROUTE"):
            meta = a.metadata_payload if isinstance(a.metadata_payload, dict) else {}
            endpoints.append({
                "id": a.id,
                "name": a.name,
                "qualified_name": a.qualified_name,
                "http_method": meta.get("method") or meta.get("http_method") or "HTTP",
                "path": meta.get("path") or meta.get("route") or a.name,
                "location": a.location or "<unknown>",
                "confidence": a.confidence,
            })
    return endpoints[:50]


def extract_database_entities(artifacts: List[StructuralArtifact]) -> List[Dict[str, Any]]:
    """
    Extracts detected database entities, tables, and ORM models.
    """
    entities = []
    for a in artifacts:
        if a.artifact_type in ("DATABASE_ENTITY", "TABLE", "MODEL", "SCHEMA"):
            entities.append({
                "id": a.id,
                "name": a.name,
                "qualified_name": a.qualified_name,
                "location": a.location or "<unknown>",
            })
    return entities[:40]


def extract_test_inventory_and_coverage(
    artifacts: List[StructuralArtifact],
    relationships: List[ArtifactRelationship]
) -> Dict[str, Any]:
    """
    Accurately computes discovered tests, mapped linkages, and coverage status.
    """
    test_artifacts = [a for a in artifacts if a.artifact_type in ("TEST_CASE", "TEST_SUITE")]
    test_rels = [r for r in relationships if (r.relationship_type or "").upper() == "TESTS"]
    tested_targets = {r.target_artifact_id for r in test_rels}

    total_tests = len(test_artifacts)
    linked_tests = len(test_rels)

    if total_tests == 0:
        coverage_status = "UNKNOWN / NOT MEASURED"
        status_message = "0 automated tests discovered in repository. AST test coverage cannot be calculated."
        coverage_ratio = 0.0
    else:
        coverage_ratio = round(len(tested_targets) / max(len(artifacts), 1), 2)
        coverage_status = "MEASURED"
        status_message = f"{total_tests} test suites/cases discovered; {linked_tests} test linkages mapped."

    return {
        "total_tests": total_tests,
        "linked_tests": linked_tests,
        "tested_components_count": len(tested_targets),
        "coverage_ratio": coverage_ratio,
        "coverage_status": coverage_status,
        "status_message": status_message,
        "test_artifacts": [{"id": t.id, "name": t.name, "location": t.location} for t in test_artifacts[:15]],
    }

