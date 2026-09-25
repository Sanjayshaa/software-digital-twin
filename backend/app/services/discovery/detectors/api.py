from typing import List, Dict
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import APITechnologyStat, EvidenceItem, EvidenceType


class APIDetector:
    """Detects REST, OpenAPI, GraphQL, gRPC, and SOAP technologies."""

    def detect(self, inventory: FileInventory) -> List[APITechnologyStat]:
        api_techs: Dict[str, APITechnologyStat] = {}

        manifest_map = {f.file_name.lower(): f for f in inventory.files}

        # 1. OpenAPI / Swagger files
        for f in inventory.files:
            lower = f.file_name.lower()
            if any(term in lower for term in ["openapi", "swagger"]):
                if lower.endswith((".yaml", ".yml", ".json")):
                    self._add_api(api_techs, "openapi", 1.0, f.relative_path,
                                  f"OpenAPI specification file: {f.file_name}", "file_existence:openapi_spec")
            if lower.endswith((".proto", ".protodecls")):
                self._add_api(api_techs, "grpc", 1.0, f.relative_path,
                              f"gRPC protocol buffer definition: {f.file_name}", "file_existence:proto")
            if lower.endswith((".wsdl", ".xsd")):
                self._add_api(api_techs, "soap", 0.95, f.relative_path,
                              f"SOAP WSDL/XSD definition: {f.file_name}", "file_existence:wsdl")

        # 2. GraphQL files
        if ".graphql" in inventory.files_by_ext or ".gql" in inventory.files_by_ext:
            sample_f = (inventory.files_by_ext.get(".graphql") or inventory.files_by_ext.get(".gql"))[0]
            self._add_api(api_techs, "graphql", 1.0, sample_f.relative_path,
                          "GraphQL schema / query file", "extension:graphql")

        # 3. REST Signals in code & manifests
        # Spring Boot RestController
        if any("spring" in f.file_name.lower() or "pom.xml" in f.file_name.lower() for f in inventory.files):
            for f in inventory.files:
                if f.extension == ".java":
                    content = self._read_file(f.absolute_path, max_bytes=16384)
                    if "@RestController" in content or "@RequestMapping" in content or "@GetMapping" in content:
                        self._add_api(api_techs, "rest", 0.99, f.relative_path,
                                      "Spring @RestController detected", "annotation:rest_controller")
                        break

        # FastAPI / Flask REST
        for f in inventory.files:
            if f.extension == ".py":
                content = self._read_file(f.absolute_path, max_bytes=16384)
                if "@app.get" in content or "@router.post" in content or "APIRouter(" in content:
                    self._add_api(api_techs, "rest", 0.99, f.relative_path,
                                  "FastAPI route decorators present", "decorator:fastapi_route")
                    break
                elif "@app.route" in content:
                    self._add_api(api_techs, "rest", 0.98, f.relative_path,
                                  "Flask route decorators present", "decorator:flask_route")
                    break

        # Express REST
        for f in inventory.files:
            if f.extension in {".ts", ".js"}:
                content = self._read_file(f.absolute_path, max_bytes=16384)
                if "router.get(" in content or "app.post(" in content or "@Controller(" in content:
                    self._add_api(api_techs, "rest", 0.99, f.relative_path,
                                  "Express / NestJS HTTP route handlers present", "code_pattern:http_router")
                    break

        return list(api_techs.values())

    def _add_api(self, api_dict: Dict[str, APITechnologyStat], name: str,
                 confidence: float, file_path: str, snippet: str, rule: str):
        if name not in api_dict:
            api_dict[name] = APITechnologyStat(
                name=name,
                confidence=confidence,
                evidence=[]
            )
        api_dict[name].evidence.append(EvidenceItem(
            evidence_type=EvidenceType.OBSERVED,
            file_path=file_path,
            snippet=snippet,
            confidence=confidence,
            detection_rule=rule
        ))

    def _read_file(self, filepath: str, max_bytes: int = 16384) -> str:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_bytes)
        except Exception:
            return ""
