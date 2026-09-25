from typing import List, Dict
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import TestingFrameworkStat, EvidenceItem, EvidenceType


class TestingDetector:
    """Detects testing frameworks deterministically from manifests, configs, and test files."""

    def detect(self, inventory: FileInventory) -> List[TestingFrameworkStat]:
        testing_frameworks: Dict[str, TestingFrameworkStat] = {}

        manifest_map = {f.file_name.lower(): f for f in inventory.files}

        # 1. Java testing (JUnit / TestNG)
        if "pom.xml" in manifest_map:
            pom_f = manifest_map["pom.xml"]
            content = self._read_file(pom_f.absolute_path, max_bytes=65536)
            if "junit" in content.lower():
                self._add_test(testing_frameworks, "junit", 0.99, pom_f.relative_path,
                               "JUnit dependency declared in pom.xml", "maven_dep:junit")
            if "testng" in content.lower():
                self._add_test(testing_frameworks, "testng", 0.99, pom_f.relative_path,
                               "TestNG dependency declared in pom.xml", "maven_dep:testng")

        # 2. Python testing (pytest / unittest)
        for fname in ["pytest.ini", "setup.cfg", "pyproject.toml", "requirements.txt"]:
            if fname in manifest_map:
                f = manifest_map[fname]
                content = self._read_file(f.absolute_path, max_bytes=32768).lower()
                if "pytest" in content or fname == "pytest.ini":
                    self._add_test(testing_frameworks, "pytest", 0.99, f.relative_path,
                                   f"pytest configured in {fname}", f"config:{fname}")
                    break

        # Check for test_*.py or *_test.py
        for f in inventory.files:
            if f.extension == ".py" and (f.file_name.startswith("test_") or f.file_name.endswith("_test.py")):
                if "pytest" not in testing_frameworks and "unittest" not in testing_frameworks:
                    self._add_test(testing_frameworks, "pytest", 0.90, f.relative_path,
                                   f"Python test file naming convention: {f.file_name}", "convention:pytest")
                break

        # 3. JS / TS testing (Vitest / Jest)
        if "package.json" in manifest_map:
            pkg_f = manifest_map["package.json"]
            content = self._read_file(pkg_f.absolute_path, max_bytes=65536).lower()
            if '"vitest"' in content:
                self._add_test(testing_frameworks, "vitest", 0.99, pkg_f.relative_path,
                               "vitest dependency declared in package.json", "npm_dep:vitest")
            elif '"jest"' in content:
                self._add_test(testing_frameworks, "jest", 0.99, pkg_f.relative_path,
                               "jest dependency declared in package.json", "npm_dep:jest")

        # 4. Go test
        for f in inventory.files:
            if f.extension == ".go" and f.file_name.endswith("_test.go"):
                self._add_test(testing_frameworks, "gotest", 1.0, f.relative_path,
                               f"Go testing file: {f.file_name}", "convention:go_test")
                break

        # 5. C/C++ CTest
        if "cmakelists.txt" in manifest_map:
            cmake_f = manifest_map["cmakelists.txt"]
            content = self._read_file(cmake_f.absolute_path, max_bytes=32768).lower()
            if "enable_testing" in content or "add_test" in content:
                self._add_test(testing_frameworks, "ctest", 0.95, cmake_f.relative_path,
                               "CTest enabled in CMakeLists.txt", "cmake:ctest")

        return list(testing_frameworks.values())

    def _add_test(self, test_dict: Dict[str, TestingFrameworkStat], name: str,
                  confidence: float, file_path: str, snippet: str, rule: str):
        if name not in test_dict:
            test_dict[name] = TestingFrameworkStat(
                name=name,
                confidence=confidence,
                evidence=[]
            )
        test_dict[name].evidence.append(EvidenceItem(
            evidence_type=EvidenceType.OBSERVED,
            file_path=file_path,
            snippet=snippet,
            confidence=confidence,
            detection_rule=rule
        ))

    def _read_file(self, filepath: str, max_bytes: int = 32768) -> str:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_bytes)
        except Exception:
            return ""
