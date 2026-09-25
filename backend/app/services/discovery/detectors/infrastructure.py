from typing import List, Dict
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import InfrastructureStat, EvidenceItem, EvidenceType


class InfrastructureDetector:
    """Detects infrastructure and CI/CD technologies deterministically without executing them."""

    def detect(self, inventory: FileInventory) -> List[InfrastructureStat]:
        infra_dict: Dict[str, InfrastructureStat] = {}

        for f in inventory.files:
            lower = f.file_name.lower()
            rel_lower = f.relative_path.lower()

            # Docker
            if "dockerfile" in lower:
                self._add_infra(infra_dict, "docker", 1.0, f.relative_path,
                                f"Container build definition: {f.file_name}", "file_existence:dockerfile")
            # Docker Compose
            if lower.startswith("docker-compose") or lower in {"compose.yaml", "compose.yml"}:
                self._add_infra(infra_dict, "docker-compose", 1.0, f.relative_path,
                                f"Multi-container orchestration: {f.file_name}", "file_existence:docker_compose")
            # Kubernetes
            if "k8s" in rel_lower or "kubernetes" in rel_lower or lower.endswith((".k8s.yaml", ".k8s.yml")):
                self._add_infra(infra_dict, "kubernetes", 0.95, f.relative_path,
                                f"Kubernetes manifest: {f.file_name}", "path_match:k8s")
            # Helm
            if lower == "chart.yaml":
                self._add_infra(infra_dict, "helm", 1.0, f.relative_path,
                                "Helm chart definition Chart.yaml", "file_existence:helm_chart")
            # Terraform
            if lower.endswith(".tf"):
                self._add_infra(infra_dict, "terraform", 1.0, f.relative_path,
                                f"Terraform infrastructure file: {f.file_name}", "extension:tf")
            # GitHub Actions
            if ".github/workflows" in rel_lower and lower.endswith((".yml", ".yaml")):
                self._add_infra(infra_dict, "github-actions", 1.0, f.relative_path,
                                f"GitHub Actions workflow: {f.file_name}", "path_match:github_actions")
            # GitLab CI
            if lower == ".gitlab-ci.yml":
                self._add_infra(infra_dict, "gitlab-ci", 1.0, f.relative_path,
                                "GitLab CI pipeline configuration", "file_existence:gitlab_ci")
            # Jenkins
            if "jenkinsfile" in lower:
                self._add_infra(infra_dict, "jenkins", 1.0, f.relative_path,
                                f"Jenkins pipeline definition: {f.file_name}", "file_existence:jenkinsfile")

        return list(infra_dict.values())

    def _add_infra(self, infra_dict: Dict[str, InfrastructureStat], name: str,
                   confidence: float, file_path: str, snippet: str, rule: str):
        if name not in infra_dict:
            infra_dict[name] = InfrastructureStat(
                name=name,
                confidence=confidence,
                evidence=[]
            )
        infra_dict[name].evidence.append(EvidenceItem(
            evidence_type=EvidenceType.OBSERVED,
            file_path=file_path,
            snippet=snippet,
            confidence=confidence,
            detection_rule=rule
        ))
