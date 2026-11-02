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


# Low-value generic identifiers, folder fragments, or stdlib names to ignore in architecture
GENERIC_COMPONENT_EXCLUSIONS = {
    "root", "path", "pathlib", "shutil", "target", "header_pattern", "pattern",
    "os", "sys", "re", "json", "typing", "datetime", "builtins", "unittest",
    "pytest", "none", "null", "undefined", "true", "false", "str", "int", "dict",
    "list", "set", "tuple", "bool", "any", "optional", "union", "self", "cls",
    "args", "kwargs", "config", "constants", "utils", "helpers", "test", "tests",
    "index", "main", "base", "types", "enums", "exceptions", "errors"
}


def extract_project_architecture_glance(
    repo_path: Optional[str],
    artifacts: List[StructuralArtifact],
    relationships: List[ArtifactRelationship]
) -> Dict[str, Any]:
    """
    Extracts evidence-backed Project Architecture at a Glance from real analyzed repository records.
    Filters out generic stdlib/token names (root, path, pathlib, shutil, HEADER_PATTERN) and provides:
    - Detected application layers (Frontend, API, Core Services, Database, External Integrations)
    - Important execution entry points with responsibilities
    - Meaningful internal services/modules with dependency coupling
    - Key dependency flows connecting layers and components
    """
    if not artifacts:
        return {
            "has_architecture": False,
            "architecture_style": "Unknown / Not detected",
            "summary": {
                "detected_layers_count": 0,
                "entry_points_count": 0,
                "major_components_count": 0,
                "key_flows_count": 0,
            },
            "layers": {
                "frontend": {
                    "label": "Frontend & Presentation",
                    "status": "NOT_DETECTED",
                    "count": 0,
                    "description": "No client-side UI components, templates, or views detected.",
                    "items": [],
                },
                "api": {
                    "label": "API & Ingress Boundaries",
                    "status": "NOT_DETECTED",
                    "count": 0,
                    "description": "No HTTP route contracts, RPC endpoints, or controllers detected.",
                    "items": [],
                },
                "services": {
                    "label": "Core Business Logic & Services",
                    "status": "NOT_DETECTED",
                    "count": 0,
                    "description": "No domain services, orchestrators, or business classes detected.",
                    "items": [],
                },
                "storage": {
                    "label": "Data Access & Persistence",
                    "status": "NOT_DETECTED",
                    "count": 0,
                    "description": "No database tables, ORM entities, or data models detected.",
                    "items": [],
                },
                "external": {
                    "label": "External Integrations",
                    "status": "NOT_DETECTED",
                    "count": 0,
                    "description": "No third-party SDKs, cloud clients, or external webhooks detected.",
                    "items": [],
                },
            },
            "entry_points": [],
            "major_components": [],
            "key_flows": [],
        }

    # Map artifact IDs to objects
    art_map = {a.id: a for a in artifacts}

    # Compute in-degree and out-degree connectivity
    in_degree = {}
    out_degree = {}
    for r in relationships:
        out_degree[r.source_artifact_id] = out_degree.get(r.source_artifact_id, 0) + 1
        in_degree[r.target_artifact_id] = in_degree.get(r.target_artifact_id, 0) + 1

    # 1. Classify Layers
    frontend_items = []
    api_items = []
    service_items = []
    storage_items = []
    external_items = []

    frontend_exts = (".tsx", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss")
    frontend_dir_markers = ("frontend", "src/components", "src/views", "src/pages", "static", "templates", "ui")

    for a in artifacts:
        loc = (a.location or "").lower()
        atype = (a.artifact_type or "").upper()
        name_lower = (a.name or "").lower()
        qname_lower = (a.qualified_name or "").lower()

        # Skip generic test cases from business layers
        if atype in ("TEST_CASE", "TEST_SUITE"):
            continue

        # Check Data Access & Storage
        if atype in ("DATABASE_ENTITY", "TABLE", "MODEL", "SCHEMA") or any(m in loc for m in ("models/", "/models/", "entities/", "schemas/", "database/")):
            if name_lower not in GENERIC_COMPONENT_EXCLUSIONS:
                storage_items.append({
                    "id": a.id,
                    "name": a.name,
                    "type": a.artifact_type,
                    "location": a.location or "<unknown>",
                    "node_id": a.id,
                })
            continue

        # Check API & Ingress
        if atype in ("API_ENDPOINT", "ROUTE") or any(m in loc for m in ("api/", "/api/", "routes/", "/routes/", "controllers/")):
            meta = a.metadata_payload if isinstance(a.metadata_payload, dict) else {}
            method = meta.get("method") or meta.get("http_method") or "HTTP"
            path = meta.get("path") or meta.get("route") or a.name
            api_items.append({
                "id": a.id,
                "name": f"{method} {path}" if method != "HTTP" else a.name,
                "type": a.artifact_type,
                "location": a.location or "<unknown>",
                "method": method,
                "path": path,
                "node_id": a.id,
            })
            continue

        # Check Frontend / Presentation
        is_frontend = (
            atype in ("COMPONENT", "REACT_COMPONENT", "VIEW", "PAGE")
            or any(loc.endswith(ext) for ext in frontend_exts)
            or any(marker in loc for marker in frontend_dir_markers)
        )
        if is_frontend:
            if name_lower not in GENERIC_COMPONENT_EXCLUSIONS:
                frontend_items.append({
                    "id": a.id,
                    "name": a.name,
                    "type": a.artifact_type or "COMPONENT",
                    "location": a.location or "<unknown>",
                    "symbol_name": a.name,
                    "node_id": a.id,
                })
            continue

        # Check External Integrations
        is_external = atype in ("EXTERNAL_SERVICE", "INTEGRATION") or any(
            ext in qname_lower or ext in name_lower
            for ext in ("stripe", "boto3", "redis", "celery", "httpx", "requests", "github", "gitlab", "kafka", "rabbitmq", "sendgrid", "gemini", "openai")
        )
        if is_external:
            external_items.append({
                "id": a.id,
                "name": a.name,
                "type": "EXTERNAL",
                "location": a.location or "<external>",
                "node_id": a.id,
            })
            continue

        # Check Core Business Logic / Services
        if atype in ("SERVICE", "CLASS", "INTERFACE") or any(m in loc for m in ("services/", "/services/", "core/", "domain/", "logic/", "managers/")):
            if name_lower not in GENERIC_COMPONENT_EXCLUSIONS:
                service_items.append({
                    "id": a.id,
                    "name": a.name,
                    "type": a.artifact_type,
                    "location": a.location or "<unknown>",
                    "fan_in": in_degree.get(a.id, 0),
                    "fan_out": out_degree.get(a.id, 0),
                    "node_id": a.id,
                })

    # Deduplicate and sort items
    def _dedup_items(items):
        seen_names = set()
        out = []
        for it in items:
            key = it["name"]
            if key not in seen_names:
                seen_names.add(key)
                out.append(it)
        return out

    frontend_items = _dedup_items(frontend_items)
    api_items = _dedup_items(api_items)
    service_items = _dedup_items(service_items)
    storage_items = _dedup_items(storage_items)
    external_items = _dedup_items(external_items)

    layers = {
        "frontend": {
            "label": "Frontend & Presentation",
            "status": "DETECTED" if frontend_items else "NOT_DETECTED",
            "count": len(frontend_items),
            "description": "UI components, client-side views, and presentation templates" if frontend_items else "No frontend UI components or client-side templates detected.",
            "items": frontend_items[:6],
        },
        "api": {
            "label": "API & Ingress Boundaries",
            "status": "DETECTED" if api_items else "NOT_DETECTED",
            "count": len(api_items),
            "description": "Declared HTTP routes, endpoint contracts, and controllers" if api_items else "No declared HTTP or RPC endpoints detected.",
            "items": api_items[:6],
        },
        "services": {
            "label": "Core Business Logic & Services",
            "status": "DETECTED" if service_items else "NOT_DETECTED",
            "count": len(service_items),
            "description": "Domain services, core orchestrators, and internal business logic" if service_items else "No dedicated service layer classes detected.",
            "items": sorted(service_items, key=lambda x: -(x.get("fan_in", 0) + x.get("fan_out", 0)))[:6],
        },
        "storage": {
            "label": "Data Access & Persistence",
            "status": "DETECTED" if storage_items else "NOT_DETECTED",
            "count": len(storage_items),
            "description": "ORM models, database entities, and persistence schemas" if storage_items else "No persistent database entities or schemas detected.",
            "items": storage_items[:6],
        },
        "external": {
            "label": "External Integrations",
            "status": "DETECTED" if external_items else "NOT_DETECTED",
            "count": len(external_items),
            "description": "Third-party APIs, SDK clients, and message broker interfaces" if external_items else "No external third-party SDKs or cloud integrations detected.",
            "items": external_items[:6],
        },
    }

    # Infer architecture style
    detected_count = sum(1 for layer in layers.values() if layer["status"] == "DETECTED")
    if layers["frontend"]["status"] == "DETECTED" and layers["api"]["status"] == "DETECTED" and layers["storage"]["status"] == "DETECTED":
        arch_style = "Multi-Tier Full-Stack Application"
    elif layers["api"]["status"] == "DETECTED" and layers["storage"]["status"] == "DETECTED":
        arch_style = "Layered Backend API & Data Persistence Service"
    elif layers["api"]["status"] == "DETECTED" and layers["services"]["status"] == "DETECTED":
        arch_style = "Modular Microservice / API Gateway"
    elif layers["frontend"]["status"] == "DETECTED" and layers["api"]["status"] == "DETECTED":
        arch_style = "Client-Server Web Application"
    elif layers["frontend"]["status"] == "DETECTED":
        arch_style = "Frontend Single-Page Application (SPA)"
    elif layers["services"]["status"] == "DETECTED":
        arch_style = "Modular Library / Domain Package"
    elif detected_count > 0:
        arch_style = "Modular Application"
    else:
        arch_style = "Unknown / Not detected"

    # 2. Extract Entry Points
    raw_eps = extract_entry_points(repo_path, artifacts)
    entry_points = []
    for ep in raw_eps:
        entry_points.append({
            "file_path": ep["file_path"],
            "role": ep["role"],
            "type": ep.get("type", "FILE"),
        })

    # 3. Major Internal Components (evidence-backed, non-generic)
    candidate_components = []
    for a in artifacts:
        name = (a.name or "").strip()
        name_lower = name.lower()
        if len(name) < 2 or name_lower in GENERIC_COMPONENT_EXCLUSIONS:
            continue
        if a.artifact_type not in ("CLASS", "SERVICE", "MODULE", "PACKAGE", "COMPONENT"):
            continue
        if "/" in name or "\\" in name:
            name = name.split("/")[-1].split("\\")[-1]

        fan_in_count = in_degree.get(a.id, 0)
        fan_out_count = out_degree.get(a.id, 0)
        total_connectivity = fan_in_count + fan_out_count

        candidate_components.append({
            "id": a.id,
            "name": name,
            "qualified_name": a.qualified_name or name,
            "type": a.artifact_type,
            "location": a.location or "<unknown>",
            "in_degree": fan_in_count,
            "out_degree": fan_out_count,
            "connectivity": total_connectivity,
            "role": f"{a.artifact_type.title()} Component with {fan_in_count} callers and {fan_out_count} dependencies",
            "node_id": a.id,
        })

    candidate_components.sort(key=lambda c: -c["connectivity"])
    major_components = []
    seen_comp_names = set()
    for c in candidate_components:
        if c["name"] not in seen_comp_names:
            seen_comp_names.add(c["name"])
            major_components.append(c)
            if len(major_components) >= 8:
                break

    # 4. Key Dependency Flows (Real cross-component topological connections)
    key_flows = []
    seen_flows = set()
    for r in relationships:
        src = art_map.get(r.source_artifact_id)
        tgt = art_map.get(r.target_artifact_id)
        if not src or not tgt or src.id == tgt.id:
            continue
        src_name = src.name.strip()
        tgt_name = tgt.name.strip()
        if src_name.lower() in GENERIC_COMPONENT_EXCLUSIONS or tgt_name.lower() in GENERIC_COMPONENT_EXCLUSIONS:
            continue
        if src.artifact_type in ("TEST_CASE", "TEST_SUITE") or tgt.artifact_type in ("TEST_CASE", "TEST_SUITE"):
            continue

        flow_key = (src_name, tgt_name, r.relationship_type)
        if flow_key not in seen_flows:
            seen_flows.add(flow_key)
            rel_type = (r.relationship_type or "CALLS").upper()
            key_flows.append({
                "source": {
                    "id": src.id,
                    "name": src_name,
                    "type": src.artifact_type,
                    "location": src.location or "<unknown>",
                },
                "target": {
                    "id": tgt.id,
                    "name": tgt_name,
                    "type": tgt.artifact_type,
                    "location": tgt.location or "<unknown>",
                },
                "relation": rel_type,
                "description": f"{src_name} ({src.artifact_type}) {rel_type.lower()} {tgt_name} ({tgt.artifact_type})",
            })
            if len(key_flows) >= 6:
                break

    return {
        "has_architecture": True,
        "architecture_style": arch_style,
        "summary": {
            "detected_layers_count": detected_count,
            "entry_points_count": len(entry_points),
            "major_components_count": len(major_components),
            "key_flows_count": len(key_flows),
        },
        "layers": layers,
        "entry_points": entry_points,
        "major_components": major_components,
        "key_flows": key_flows,
    }

