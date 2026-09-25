import os
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.services.discovery.scanner import RepositoryScanner, FileInventory
from app.services.discovery.detectors.language import LanguageDetector
from app.services.discovery.detectors.manifest import ManifestDetector
from app.services.discovery.detectors.framework import FrameworkDetector
from app.services.discovery.detectors.database import DatabaseDetector
from app.services.discovery.detectors.api import APIDetector
from app.services.discovery.detectors.testing import TestingDetector
from app.services.discovery.detectors.infrastructure import InfrastructureDetector
from app.services.discovery.detectors.architecture import ArchitectureDetector
from app.services.discovery.planner import AnalysisPlanner
from app.services.discovery.registry import capability_registry
from app.services.discovery.models import ProjectProfile, AnalysisPlanResult, EvidenceType

from app.models.entities import (
    Technology,
    TechnologyEvidence,
    ProjectTechnology,
    Capability,
    Analyzer as AnalyzerModel,
    ProjectCapability,
    AnalysisPlan,
    Repository as RepositoryModel,
    Project as ProjectModel,
)


class DiscoveryBrainEngine:
    """The central deterministic Software Project Discovery & Intelligence Brain."""

    def __init__(self):
        self.scanner = RepositoryScanner()
        self.lang_detector = LanguageDetector()
        self.manifest_detector = ManifestDetector()
        self.framework_detector = FrameworkDetector()
        self.db_detector = DatabaseDetector()
        self.api_detector = APIDetector()
        self.test_detector = TestingDetector()
        self.infra_detector = InfrastructureDetector()
        self.arch_detector = ArchitectureDetector()
        self.planner = AnalysisPlanner()

    def discover(self, repo_path: str) -> Tuple[ProjectProfile, AnalysisPlanResult]:
        """Perform completely deterministic discovery without requiring DB session."""
        abs_path = os.path.abspath(repo_path)
        inventory: FileInventory = self.scanner.scan(abs_path)

        languages = self.lang_detector.detect(inventory)
        build_systems, package_managers = self.manifest_detector.detect(inventory)
        frameworks = self.framework_detector.detect(inventory)
        databases = self.db_detector.detect(inventory)
        api_technologies = self.api_detector.detect(inventory)
        testing_frameworks = self.test_detector.detect(inventory)
        infrastructure = self.infra_detector.detect(inventory)
        architecture_signals = self.arch_detector.detect(inventory, frameworks, infrastructure)

        profile = ProjectProfile(
            repository_path=abs_path,
            total_files_scanned=inventory.total_files,
            total_lines_of_code=inventory.total_lines,
            languages=languages,
            frameworks=frameworks,
            build_systems=build_systems,
            package_managers=package_managers,
            databases=databases,
            api_technologies=api_technologies,
            testing_frameworks=testing_frameworks,
            infrastructure=infrastructure,
            architecture_signals=architecture_signals,
            raw_inventory={
                "manifest_count": len(inventory.manifest_files),
                "docker_file_count": len(inventory.docker_files),
                "ci_cd_file_count": len(inventory.ci_cd_files),
            }
        )

        plan = self.planner.plan(profile)
        return profile, plan

    def discover_and_persist(
        self,
        db: Session,
        repository_id: str,
        project_id: Optional[str] = None
    ) -> Tuple[ProjectProfile, AnalysisPlanResult]:
        """Runs discovery and commits structured project profile & plan to PostgreSQL."""
        repo = db.query(RepositoryModel).filter_by(id=repository_id).first()
        if not repo:
            raise ValueError(f"Repository with ID '{repository_id}' not found.")

        p_id = project_id or repo.project_id
        profile, plan = self.discover(repo.local_path)

        # 1. Sync Analyzers in DB
        for an in capability_registry.list_analyzers():
            db_analyzer = db.query(AnalyzerModel).filter_by(name=an.name).first()
            if not db_analyzer:
                db_analyzer = AnalyzerModel(
                    name=an.name,
                    display_name=an.display_name,
                    supported_languages=an.supported_languages,
                    supported_frameworks=an.supported_frameworks,
                    capability_level=an.capability_level,
                    is_available=True,
                )
                db.add(db_analyzer)
        db.flush()

        # 2. Persist Languages & Evidence
        for lang in profile.languages:
            tech = self._get_or_create_technology(db, lang.name, "language", f"{lang.name} programming language")
            pt = ProjectTechnology(
                project_id=p_id,
                repository_id=repository_id,
                technology_id=tech.id,
                version=None,
                percentage=lang.percentage,
                confidence=lang.confidence,
                detection_status="OBSERVED",
                metadata_payload={"line_count": lang.line_count, "file_count": lang.file_count},
            )
            db.add(pt)
            for ev in lang.evidence:
                dev = TechnologyEvidence(
                    project_id=p_id,
                    repository_id=repository_id,
                    technology_id=tech.id,
                    evidence_type=ev.evidence_type.value,
                    file_path=ev.file_path,
                    snippet=ev.snippet,
                    confidence=ev.confidence,
                    detection_rule=ev.detection_rule,
                )
                db.add(dev)

        # 3. Persist Frameworks
        for fw in profile.frameworks:
            tech = self._get_or_create_technology(db, fw.name, "framework", f"{fw.name} application framework")
            pt = ProjectTechnology(
                project_id=p_id,
                repository_id=repository_id,
                technology_id=tech.id,
                version=fw.version,
                percentage=0.0,
                confidence=fw.confidence,
                detection_status=fw.detection_status.value,
                metadata_payload={"version": fw.version},
            )
            db.add(pt)
            for ev in fw.evidence:
                dev = TechnologyEvidence(
                    project_id=p_id,
                    repository_id=repository_id,
                    technology_id=tech.id,
                    evidence_type=ev.evidence_type.value,
                    file_path=ev.file_path,
                    snippet=ev.snippet,
                    confidence=ev.confidence,
                    detection_rule=ev.detection_rule,
                )
                db.add(dev)

        # 4. Persist Build Systems & Package Managers
        for bm in profile.build_systems:
            tech = self._get_or_create_technology(db, bm.name, "build_system", f"{bm.name} build system")
            pt = ProjectTechnology(
                project_id=p_id,
                repository_id=repository_id,
                technology_id=tech.id,
                confidence=bm.confidence,
                detection_status="OBSERVED",
                metadata_payload={"build_file": bm.build_file},
            )
            db.add(pt)
            for ev in bm.evidence:
                db.add(TechnologyEvidence(
                    project_id=p_id,
                    repository_id=repository_id,
                    technology_id=tech.id,
                    evidence_type=ev.evidence_type.value,
                    file_path=ev.file_path,
                    snippet=ev.snippet,
                    confidence=ev.confidence,
                    detection_rule=ev.detection_rule,
                ))

        # 5. Persist Databases
        for d in profile.databases:
            tech = self._get_or_create_technology(db, d.name, "database", f"{d.name} database system")
            pt = ProjectTechnology(
                project_id=p_id,
                repository_id=repository_id,
                technology_id=tech.id,
                confidence=d.confidence,
                detection_status=d.detection_status.value,
                metadata_payload={"category": d.category},
            )
            db.add(pt)
            for ev in d.evidence:
                db.add(TechnologyEvidence(
                    project_id=p_id,
                    repository_id=repository_id,
                    technology_id=tech.id,
                    evidence_type=ev.evidence_type.value,
                    file_path=ev.file_path,
                    snippet=ev.snippet,
                    confidence=ev.confidence,
                    detection_rule=ev.detection_rule,
                ))

        # 6. Persist APIs
        for a in profile.api_technologies:
            tech = self._get_or_create_technology(db, a.name, "api", f"{a.name} API technology")
            pt = ProjectTechnology(
                project_id=p_id,
                repository_id=repository_id,
                technology_id=tech.id,
                confidence=a.confidence,
                detection_status="OBSERVED",
                metadata_payload={},
            )
            db.add(pt)
            for ev in a.evidence:
                db.add(TechnologyEvidence(
                    project_id=p_id,
                    repository_id=repository_id,
                    technology_id=tech.id,
                    evidence_type=ev.evidence_type.value,
                    file_path=ev.file_path,
                    snippet=ev.snippet,
                    confidence=ev.confidence,
                    detection_rule=ev.detection_rule,
                ))

        # 7. Persist Testing
        for t in profile.testing_frameworks:
            tech = self._get_or_create_technology(db, t.name, "testing", f"{t.name} testing framework")
            pt = ProjectTechnology(
                project_id=p_id,
                repository_id=repository_id,
                technology_id=tech.id,
                confidence=t.confidence,
                detection_status="OBSERVED",
                metadata_payload={},
            )
            db.add(pt)
            for ev in t.evidence:
                db.add(TechnologyEvidence(
                    project_id=p_id,
                    repository_id=repository_id,
                    technology_id=tech.id,
                    evidence_type=ev.evidence_type.value,
                    file_path=ev.file_path,
                    snippet=ev.snippet,
                    confidence=ev.confidence,
                    detection_rule=ev.detection_rule,
                ))

        # 8. Persist Infrastructure
        for inf in profile.infrastructure:
            tech = self._get_or_create_technology(db, inf.name, "infrastructure", f"{inf.name} infrastructure")
            pt = ProjectTechnology(
                project_id=p_id,
                repository_id=repository_id,
                technology_id=tech.id,
                confidence=inf.confidence,
                detection_status="OBSERVED",
                metadata_payload={},
            )
            db.add(pt)
            for ev in inf.evidence:
                db.add(TechnologyEvidence(
                    project_id=p_id,
                    repository_id=repository_id,
                    technology_id=tech.id,
                    evidence_type=ev.evidence_type.value,
                    file_path=ev.file_path,
                    snippet=ev.snippet,
                    confidence=ev.confidence,
                    detection_rule=ev.detection_rule,
                ))

        # 9. Persist Capabilities
        for cap_spec in plan.supported_capabilities:
            db_cap = db.query(Capability).filter_by(name=cap_spec.capability_name).first()
            if not db_cap:
                db_cap = Capability(
                    name=cap_spec.capability_name,
                    description=cap_spec.description,
                    capability_level=cap_spec.level,
                    category=cap_spec.category,
                )
                db.add(db_cap)
                db.flush()

            an_model = None
            if cap_spec.analyzer_name:
                an_model = db.query(AnalyzerModel).filter_by(name=cap_spec.analyzer_name).first()

            pc = ProjectCapability(
                project_id=p_id,
                repository_id=repository_id,
                capability_id=db_cap.id,
                analyzer_id=an_model.id if an_model else None,
                status=cap_spec.status,
                confidence=1.0,
                details={"description": cap_spec.description},
            )
            db.add(pc)

        # 10. Persist Analysis Plan
        db_plan = AnalysisPlan(
            project_id=p_id,
            repository_id=repository_id,
            status="GENERATED",
            plan_steps=[s.model_dump() for s in plan.steps],
            total_steps=plan.total_steps,
        )
        db.add(db_plan)

        db.commit()
        return profile, plan

    def _get_or_create_technology(self, db: Session, name: str, category: str, description: str) -> Technology:
        tech = db.query(Technology).filter_by(name=name).first()
        if not tech:
            tech = Technology(name=name, category=category, description=description)
            db.add(tech)
            db.flush()
        return tech


discovery_engine = DiscoveryBrainEngine()
