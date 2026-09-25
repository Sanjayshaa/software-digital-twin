import os
from typing import List, Set
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import (
    ArchitectureSignal,
    EvidenceItem,
    EvidenceType,
    FrameworkStat,
    InfrastructureStat,
)


class ArchitectureDetector:
    """Detects architectural structural signals based on deterministic evidence."""

    def detect(
        self,
        inventory: FileInventory,
        frameworks: List[FrameworkStat],
        infra: List[InfrastructureStat],
    ) -> List[ArchitectureSignal]:
        signals: List[ArchitectureSignal] = []

        subdirs: Set[str] = set()
        for f in inventory.files:
            parts = f.relative_path.split(os.sep)
            if len(parts) > 1:
                subdirs.add(parts[0].lower())

        manifest_count = len(inventory.manifest_files)
        has_compose = any(i.name == "docker-compose" for i in infra)

        # 1. Microservice-like signal
        service_dirs = {"services", "apps", "microservices", "packages"}
        matched_service_dirs = subdirs.intersection(service_dirs)
        if matched_service_dirs or (has_compose and manifest_count >= 2):
            evidence = []
            if matched_service_dirs:
                evidence.append(EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=list(matched_service_dirs)[0],
                    snippet=f"Dedicated service directories detected: {list(matched_service_dirs)}",
                    confidence=0.85,
                    detection_rule="directory_structure:service_dirs"
                ))
            if has_compose:
                evidence.append(EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=inventory.docker_files[0].relative_path if inventory.docker_files else "docker-compose.yml",
                    snippet="Orchestrated multi-service docker-compose configuration",
                    confidence=0.85,
                    detection_rule="infra_pattern:docker_compose"
                ))

            signals.append(ArchitectureSignal(
                signal="microservice-like structure",
                confidence=0.85,
                summary="Architecture signals suggest a microservice or multi-service topology based on directory separation and multi-service orchestration.",
                evidence=evidence
            ))

        # 2. Frontend / Backend separation
        has_frontend = any(f.name in {"react", "nextjs", "vue", "angular"} for f in frameworks) or {"frontend", "client", "ui"}.intersection(subdirs)
        has_backend = any(f.name in {"fastapi", "flask", "django", "spring-boot", "spring", "express", "nestjs", "gin"} for f in frameworks) or {"backend", "server", "api"}.intersection(subdirs)

        if has_frontend and has_backend:
            signals.append(ArchitectureSignal(
                signal="frontend/backend separation",
                confidence=0.90,
                summary="Architecture signals suggest decoupled frontend and backend layers with dedicated framework/directory boundaries.",
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=None,
                    snippet="Simultaneous detection of UI framework/directory and backend service framework/directory",
                    confidence=0.90,
                    detection_rule="framework_coexistence:frontend_and_backend"
                )]
            ))

        # 3. Modular Monolith vs Monolith
        modular_dirs = {"modules", "domain", "features", "components"}
        if not matched_service_dirs:
            if modular_dirs.intersection(subdirs):
                signals.append(ArchitectureSignal(
                    signal="modular monolith",
                    confidence=0.80,
                    summary="Architecture signals suggest a single deployment unit organized into structured domain/module subdirectories.",
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=list(modular_dirs.intersection(subdirs))[0],
                        snippet=f"Modular subdirectory pattern observed: {list(modular_dirs.intersection(subdirs))}",
                        confidence=0.80,
                        detection_rule="directory_structure:modular_monolith"
                    )]
                ))
            elif not any(s.signal == "microservice-like structure" for s in signals):
                signals.append(ArchitectureSignal(
                    signal="monolith",
                    confidence=0.75,
                    summary="Architecture signals indicate a single unified codebase repository without decoupled service directories.",
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.INFERRED,
                        file_path=None,
                        snippet="Single root manifest and absence of distinct microservice subprojects",
                        confidence=0.75,
                        detection_rule="heuristic:single_root_package"
                    )]
                ))

        # 4. Event-Driven indicators
        event_keywords = {"kafka", "rabbitmq", "amqp", "sqs", "pulsar", "celery", "nats"}
        found_event_evidence = []
        for f in inventory.files:
            if f.file_name.lower() in {"requirements.txt", "pom.xml", "package.json", "docker-compose.yml"}:
                try:
                    with open(f.absolute_path, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read(32768).lower()
                        for kw in event_keywords:
                            if kw in content:
                                found_event_evidence.append(EvidenceItem(
                                    evidence_type=EvidenceType.OBSERVED,
                                    file_path=f.relative_path,
                                    snippet=f"Message broker / event bus reference: '{kw}'",
                                    confidence=0.85,
                                    detection_rule=f"keyword_match:{kw}"
                                ))
                                break
                except Exception:
                    pass

        if found_event_evidence:
            signals.append(ArchitectureSignal(
                signal="event-driven indicators",
                confidence=0.85,
                summary="Architecture signals suggest asynchronous event-driven messaging or queueing patterns.",
                evidence=found_event_evidence
            ))

        return signals
