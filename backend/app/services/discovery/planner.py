from typing import List, Dict, Any
from app.services.discovery.models import (
    ProjectProfile,
    AnalysisPlanResult,
    AnalysisPlanStep,
    CapabilitySpec,
)
from app.services.discovery.registry import capability_registry, AnalyzerInterface


class AnalysisPlanner:
    """Synthesizes project profile with capability registry to build deterministic analysis plan."""

    def plan(self, profile: ProjectProfile) -> AnalysisPlanResult:
        steps: List[AnalysisPlanStep] = []
        step_counter = 1

        supported_caps: List[CapabilitySpec] = []
        unsupported_caps: List[CapabilitySpec] = []

        # 1. Map language capabilities
        for lang in profile.languages:
            cap = capability_registry.get_capabilities_for_language(lang.name)
            if cap.status in {"SUPPORTED", "PARTIAL"}:
                supported_caps.append(cap)
            else:
                unsupported_caps.append(cap)

            # Create base structural analysis step for supported languages
            if cap.analyzer_name:
                steps.append(
                    AnalysisPlanStep(
                        step_number=step_counter,
                        step_name=f"{lang.name.capitalize()} Code Structure & Symbol Extraction",
                        analyzer_name=cap.analyzer_name,
                        target_technology=lang.name,
                        capability_level=cap.level,
                        description=f"Extract AST, modules, functions, classes, and signatures for {lang.name} ({lang.percentage}% of codebase).",
                        prerequisites=[],
                        evidence_required=[e.file_path for e in lang.evidence if e.file_path],
                    )
                )
                step_counter += 1

        # 2. Build system & Dependency Manifest steps
        for bm in profile.build_systems:
            steps.append(
                AnalysisPlanStep(
                    step_number=step_counter,
                    step_name=f"{bm.name.capitalize()} Dependency Resolution",
                    analyzer_name=f"{bm.name}_dependency_analyzer",
                    target_technology=bm.name,
                    capability_level=2,
                    description=f"Parse manifest {bm.build_file or ''} to construct external dependency tree and package versions.",
                    prerequisites=[],
                    evidence_required=[e.file_path for e in bm.evidence if e.file_path],
                )
            )
            step_counter += 1

        # 3. Framework-specific analysis steps
        for fw in profile.frameworks:
            steps.append(
                AnalysisPlanStep(
                    step_number=step_counter,
                    step_name=f"{fw.name.capitalize()} Architecture & Routing Extraction",
                    analyzer_name=f"{fw.name}_framework_analyzer",
                    target_technology=fw.name,
                    capability_level=3,
                    description=f"Extract {fw.name} annotations, routes, middleware, and dependency injection wiring.",
                    prerequisites=[],
                    evidence_required=[e.file_path for e in fw.evidence if e.file_path],
                )
            )
            step_counter += 1

        # 4. Database schema & entity steps
        for db in profile.databases:
            steps.append(
                AnalysisPlanStep(
                    step_number=step_counter,
                    step_name=f"{db.name.capitalize()} Data Entity Modeling",
                    analyzer_name="database_analyzer",
                    target_technology=db.name,
                    capability_level=2,
                    description=f"Map database tables, columns, relations, and ORM entity references for {db.name}.",
                    prerequisites=[],
                    evidence_required=[e.file_path for e in db.evidence if e.file_path],
                )
            )
            step_counter += 1

        # 5. API endpoint & schema contract steps
        for api in profile.api_technologies:
            steps.append(
                AnalysisPlanStep(
                    step_number=step_counter,
                    step_name=f"{api.name.upper()} Contract & Interface Analysis",
                    analyzer_name="rest_api_analyzer",
                    target_technology=api.name,
                    capability_level=3,
                    description=f"Catalog all {api.name.upper()} endpoints, methods, parameters, and payload schemas.",
                    prerequisites=[],
                    evidence_required=[e.file_path for e in api.evidence if e.file_path],
                )
            )
            step_counter += 1

        # 6. Testing framework & test impact steps
        for tf in profile.testing_frameworks:
            steps.append(
                AnalysisPlanStep(
                    step_number=step_counter,
                    step_name=f"{tf.name.capitalize()} Test Suite & Target Mapping",
                    analyzer_name=f"{tf.name}_test_analyzer",
                    target_technology=tf.name,
                    capability_level=3,
                    description=f"Discover all {tf.name} test files, test methods, and build test-to-component linkage.",
                    prerequisites=[],
                    evidence_required=[e.file_path for e in tf.evidence if e.file_path],
                )
            )
            step_counter += 1

        # 7. Infrastructure & container steps
        for inf in profile.infrastructure:
            if inf.name in {"docker", "docker-compose"}:
                steps.append(
                    AnalysisPlanStep(
                        step_number=step_counter,
                        step_name=f"{inf.name.capitalize()} Container & Service Topology",
                        analyzer_name="docker_analyzer",
                        target_technology=inf.name,
                        capability_level=2,
                        description=f"Extract container build stages, exposed ports, service links, and volume bindings.",
                        prerequisites=[],
                        evidence_required=[e.file_path for e in inf.evidence if e.file_path],
                    )
                )
                step_counter += 1

        # Summary metadata
        summary: Dict[str, Any] = {
            "total_files": profile.total_files_scanned,
            "total_lines": profile.total_lines_of_code,
            "primary_language": profile.languages[0].name if profile.languages else "unknown",
            "frameworks": [f.name for f in profile.frameworks],
            "databases": [d.name for d in profile.databases],
            "testing": [t.name for t in profile.testing_frameworks],
            "architecture_signals": [s.signal for s in profile.architecture_signals],
        }

        return AnalysisPlanResult(
            repository_path=profile.repository_path,
            project_profile_summary=summary,
            total_steps=len(steps),
            steps=steps,
            supported_capabilities=supported_caps,
            unsupported_capabilities=unsupported_caps,
        )
