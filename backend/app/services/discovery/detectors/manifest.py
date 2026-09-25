import os
from typing import Tuple, List
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import (
    BuildSystemStat,
    PackageManagerStat,
    EvidenceItem,
    EvidenceType,
)


class ManifestDetector:
    """Detects build systems and package managers deterministically from repository manifests."""

    def detect(self, inventory: FileInventory) -> Tuple[List[BuildSystemStat], List[PackageManagerStat]]:
        build_systems: List[BuildSystemStat] = []
        package_managers: List[PackageManagerStat] = []

        manifest_names = {f.file_name.lower(): f for f in inventory.files}

        # Java Build & Package
        if "pom.xml" in manifest_names:
            f = manifest_names["pom.xml"]
            build_systems.append(BuildSystemStat(
                name="maven",
                build_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="pom.xml manifest present",
                    confidence=1.0,
                    detection_rule="file_existence:pom.xml"
                )]
            ))
            package_managers.append(PackageManagerStat(
                name="maven",
                manifest_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="pom.xml declared dependencies",
                    confidence=1.0,
                    detection_rule="file_existence:pom.xml"
                )]
            ))

        if "build.gradle" in manifest_names or "build.gradle.kts" in manifest_names:
            f = manifest_names.get("build.gradle") or manifest_names.get("build.gradle.kts")
            build_systems.append(BuildSystemStat(
                name="gradle",
                build_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet=f"{f.file_name} present",
                    confidence=1.0,
                    detection_rule=f"file_existence:{f.file_name}"
                )]
            ))
            package_managers.append(PackageManagerStat(
                name="gradle",
                manifest_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet=f"{f.file_name} present",
                    confidence=1.0,
                    detection_rule=f"file_existence:{f.file_name}"
                )]
            ))

        # Node / JS Package & Build
        if "package.json" in manifest_names:
            f = manifest_names["package.json"]
            # Check package manager lockfiles
            pm_name = "npm"
            if "pnpm-lock.yaml" in manifest_names:
                pm_name = "pnpm"
            elif "yarn.lock" in manifest_names:
                pm_name = "yarn"
            elif "bun.lockb" in manifest_names:
                pm_name = "bun"

            package_managers.append(PackageManagerStat(
                name=pm_name,
                manifest_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet=f"package.json managed by {pm_name}",
                    confidence=1.0,
                    detection_rule=f"manifest:{pm_name}"
                )]
            ))
            build_systems.append(BuildSystemStat(
                name=pm_name,
                build_file=f.relative_path,
                confidence=0.95,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="npm scripts in package.json",
                    confidence=0.95,
                    detection_rule="manifest:package.json"
                )]
            ))

        # Python Build & Package
        if "pyproject.toml" in manifest_names or "requirements.txt" in manifest_names or "setup.py" in manifest_names or "pipfile" in manifest_names:
            ref_f = (
                manifest_names.get("pyproject.toml")
                or manifest_names.get("requirements.txt")
                or manifest_names.get("setup.py")
                or manifest_names.get("pipfile")
            )
            pm_name = "pip"
            if "poetry.lock" in manifest_names:
                pm_name = "poetry"
            elif "pipfile" in manifest_names:
                pm_name = "pipenv"

            package_managers.append(PackageManagerStat(
                name=pm_name,
                manifest_file=ref_f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=ref_f.relative_path,
                    snippet=f"Python dependency manifest: {ref_f.file_name}",
                    confidence=1.0,
                    detection_rule=f"file_existence:{ref_f.file_name}"
                )]
            ))

        # Go
        if "go.mod" in manifest_names:
            f = manifest_names["go.mod"]
            build_systems.append(BuildSystemStat(
                name="go-build",
                build_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="go.mod manifest",
                    confidence=1.0,
                    detection_rule="file_existence:go.mod"
                )]
            ))
            package_managers.append(PackageManagerStat(
                name="go-modules",
                manifest_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="go.mod modules declaration",
                    confidence=1.0,
                    detection_rule="file_existence:go.mod"
                )]
            ))

        # Rust
        if "cargo.toml" in manifest_names:
            f = manifest_names["cargo.toml"]
            build_systems.append(BuildSystemStat(
                name="cargo",
                build_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="Cargo.toml present",
                    confidence=1.0,
                    detection_rule="file_existence:Cargo.toml"
                )]
            ))
            package_managers.append(PackageManagerStat(
                name="cargo",
                manifest_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="Cargo.toml dependency manifest",
                    confidence=1.0,
                    detection_rule="file_existence:Cargo.toml"
                )]
            ))

        # C / C++ CMake & Make
        if "cmakelists.txt" in manifest_names:
            f = manifest_names["cmakelists.txt"]
            build_systems.append(BuildSystemStat(
                name="cmake",
                build_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="CMakeLists.txt build specification",
                    confidence=1.0,
                    detection_rule="file_existence:CMakeLists.txt"
                )]
            ))
        elif "makefile" in manifest_names:
            f = manifest_names["makefile"]
            build_systems.append(BuildSystemStat(
                name="make",
                build_file=f.relative_path,
                confidence=1.0,
                evidence=[EvidenceItem(
                    evidence_type=EvidenceType.OBSERVED,
                    file_path=f.relative_path,
                    snippet="Makefile build configuration",
                    confidence=1.0,
                    detection_rule="file_existence:Makefile"
                )]
            ))

        return build_systems, package_managers
