import os
import re
from typing import List, Dict, Optional
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import FrameworkStat, EvidenceItem, EvidenceType


class FrameworkDetector:
    """Detects software frameworks with version extraction and observed vs inferred separation."""

    def detect(self, inventory: FileInventory) -> List[FrameworkStat]:
        frameworks: Dict[str, FrameworkStat] = {}

        manifest_map = {f.file_name.lower(): f for f in inventory.files}

        # 1. Java / Spring Boot detection
        if "pom.xml" in manifest_map:
            pom_file = manifest_map["pom.xml"]
            content = self._read_head(pom_file.absolute_path, max_bytes=65536)
            if "spring-boot" in content:
                version_match = re.search(r"<spring-boot\.version>(.*?)</spring-boot\.version>", content)
                if not version_match:
                    version_match = re.search(r"<version>(3\.[0-9]+\.[0-9]+|2\.[0-9]+\.[0-9]+)</version>", content)
                version = version_match.group(1) if version_match else "3.x"

                frameworks["spring-boot"] = FrameworkStat(
                    name="spring-boot",
                    version=version,
                    confidence=0.99,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=pom_file.relative_path,
                        snippet=f"spring-boot dependency in pom.xml (version: {version})",
                        confidence=0.99,
                        detection_rule="pom_dependency:spring-boot"
                    )]
                )
            elif "org.springframework" in content:
                frameworks["spring"] = FrameworkStat(
                    name="spring",
                    version=None,
                    confidence=0.95,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=pom_file.relative_path,
                        snippet="org.springframework dependency in pom.xml",
                        confidence=0.95,
                        detection_rule="pom_dependency:spring"
                    )]
                )

        if "build.gradle" in manifest_map or "build.gradle.kts" in manifest_map:
            gradle_f = manifest_map.get("build.gradle") or manifest_map.get("build.gradle.kts")
            content = self._read_head(gradle_f.absolute_path, max_bytes=65536)
            if "org.springframework.boot" in content or "spring-boot" in content:
                frameworks["spring-boot"] = FrameworkStat(
                    name="spring-boot",
                    version="3.x",
                    confidence=0.99,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=gradle_f.relative_path,
                        snippet="spring-boot plugin/dependency in Gradle",
                        confidence=0.99,
                        detection_rule="gradle_dependency:spring-boot"
                    )]
                )

        # 2. Python Frameworks (FastAPI, Flask, Django)
        py_manifests = [f for f in inventory.files if f.file_name.lower() in {"requirements.txt", "pyproject.toml", "setup.py"}]
        for mf in py_manifests:
            content = self._read_head(mf.absolute_path, max_bytes=65536).lower()
            if "fastapi" in content:
                v_match = re.search(r"fastapi[>=~^<]*([0-9]+\.[0-9]+(\.[0-9]+)?)", content)
                frameworks["fastapi"] = FrameworkStat(
                    name="fastapi",
                    version=v_match.group(1) if v_match else None,
                    confidence=0.99,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=mf.relative_path,
                        snippet=f"fastapi declared in {mf.file_name}",
                        confidence=0.99,
                        detection_rule=f"manifest:{mf.file_name}"
                    )]
                )
            if "flask" in content and "flask" not in frameworks:
                v_match = re.search(r"flask[>=~^<]*([0-9]+\.[0-9]+(\.[0-9]+)?)", content)
                frameworks["flask"] = FrameworkStat(
                    name="flask",
                    version=v_match.group(1) if v_match else None,
                    confidence=0.98,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=mf.relative_path,
                        snippet=f"flask declared in {mf.file_name}",
                        confidence=0.98,
                        detection_rule=f"manifest:{mf.file_name}"
                    )]
                )
            if "django" in content and "django" not in frameworks:
                v_match = re.search(r"django[>=~^<]*([0-9]+\.[0-9]+(\.[0-9]+)?)", content)
                frameworks["django"] = FrameworkStat(
                    name="django",
                    version=v_match.group(1) if v_match else None,
                    confidence=0.98,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=mf.relative_path,
                        snippet=f"django declared in {mf.file_name}",
                        confidence=0.98,
                        detection_rule=f"manifest:{mf.file_name}"
                    )]
                )

        # 3. JavaScript / TypeScript Frameworks (React, Next.js, Express, NestJS, Vue, Angular)
        if "package.json" in manifest_map:
            pkg_f = manifest_map["package.json"]
            content = self._read_head(pkg_f.absolute_path, max_bytes=65536)
            # React
            if '"react"' in content:
                v_match = re.search(r'"react":\s*"[\^~]?([0-9]+(\.[0-9]+)?)', content)
                frameworks["react"] = FrameworkStat(
                    name="react",
                    version=v_match.group(1) if v_match else None,
                    confidence=0.99,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=pkg_f.relative_path,
                        snippet="react dependency in package.json",
                        confidence=0.99,
                        detection_rule="package_dependency:react"
                    )]
                )
            # Next.js
            if '"next"' in content:
                frameworks["nextjs"] = FrameworkStat(
                    name="nextjs",
                    version=None,
                    confidence=0.99,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=pkg_f.relative_path,
                        snippet="next dependency in package.json",
                        confidence=0.99,
                        detection_rule="package_dependency:next"
                    )]
                )
            # Express
            if '"express"' in content:
                frameworks["express"] = FrameworkStat(
                    name="express",
                    version=None,
                    confidence=0.99,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=pkg_f.relative_path,
                        snippet="express dependency in package.json",
                        confidence=0.99,
                        detection_rule="package_dependency:express"
                    )]
                )
            # NestJS
            if '"@nestjs/core"' in content:
                frameworks["nestjs"] = FrameworkStat(
                    name="nestjs",
                    version=None,
                    confidence=0.99,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=pkg_f.relative_path,
                        snippet="@nestjs/core dependency in package.json",
                        confidence=0.99,
                        detection_rule="package_dependency:nestjs"
                    )]
                )

        # 4. Go Frameworks (Gin, Fiber)
        if "go.mod" in manifest_map:
            gomod_f = manifest_map["go.mod"]
            content = self._read_head(gomod_f.absolute_path, max_bytes=32768)
            if "github.com/gin-gonic/gin" in content:
                frameworks["gin"] = FrameworkStat(
                    name="gin",
                    version=None,
                    confidence=0.99,
                    detection_status=EvidenceType.OBSERVED,
                    evidence=[EvidenceItem(
                        evidence_type=EvidenceType.OBSERVED,
                        file_path=gomod_f.relative_path,
                        snippet="gin dependency in go.mod",
                        confidence=0.99,
                        detection_rule="gomod_dependency:gin"
                    )]
                )

        return list(frameworks.values())

    def _read_head(self, filepath: str, max_bytes: int = 65536) -> str:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_bytes)
        except Exception:
            return ""
