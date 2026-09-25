from typing import List, Dict
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import DatabaseStat, EvidenceItem, EvidenceType


class DatabaseDetector:
    """Detects databases from manifests, configs, SQL schemas, and Docker Compose."""

    def detect(self, inventory: FileInventory) -> List[DatabaseStat]:
        databases: Dict[str, DatabaseStat] = {}

        manifest_map = {f.file_name.lower(): f for f in inventory.files}

        # 1. Inspect Docker Compose files
        for df in inventory.docker_files:
            if "compose" in df.file_name.lower():
                content = self._read_file(df.absolute_path).lower()
                if "postgres" in content:
                    self._add_db(databases, "postgresql", "sql", 0.99, EvidenceType.OBSERVED,
                                 df.relative_path, "PostgreSQL service defined in Docker Compose", "docker_compose:postgres")
                if "mysql" in content or "mariadb" in content:
                    self._add_db(databases, "mysql", "sql", 0.99, EvidenceType.OBSERVED,
                                 df.relative_path, "MySQL/MariaDB service in Docker Compose", "docker_compose:mysql")
                if "redis" in content:
                    self._add_db(databases, "redis", "cache", 0.99, EvidenceType.OBSERVED,
                                 df.relative_path, "Redis service in Docker Compose", "docker_compose:redis")
                if "mongo" in content:
                    self._add_db(databases, "mongodb", "nosql", 0.99, EvidenceType.OBSERVED,
                                 df.relative_path, "MongoDB service in Docker Compose", "docker_compose:mongo")

        # 2. Inspect dependency manifests
        # Python
        for fname in ["requirements.txt", "pyproject.toml", "setup.py"]:
            if fname in manifest_map:
                f = manifest_map[fname]
                content = self._read_file(f.absolute_path).lower()
                if any(k in content for k in ["psycopg", "asyncpg", "postgres"]):
                    self._add_db(databases, "postgresql", "sql", 0.98, EvidenceType.OBSERVED,
                                 f.relative_path, f"PostgreSQL driver in {fname}", f"manifest_dep:{fname}")
                if "pymongo" in content or "motor" in content:
                    self._add_db(databases, "mongodb", "nosql", 0.98, EvidenceType.OBSERVED,
                                 f.relative_path, f"MongoDB driver in {fname}", f"manifest_dep:{fname}")
                if "redis" in content:
                    self._add_db(databases, "redis", "cache", 0.98, EvidenceType.OBSERVED,
                                 f.relative_path, f"Redis client in {fname}", f"manifest_dep:{fname}")
                if "sqlite" in content:
                    self._add_db(databases, "sqlite", "sql", 0.95, EvidenceType.OBSERVED,
                                 f.relative_path, f"SQLite dependency in {fname}", f"manifest_dep:{fname}")

        # Java
        if "pom.xml" in manifest_map:
            f = manifest_map["pom.xml"]
            content = self._read_file(f.absolute_path).lower()
            if "postgresql" in content:
                self._add_db(databases, "postgresql", "sql", 0.99, EvidenceType.OBSERVED,
                             f.relative_path, "org.postgresql driver in pom.xml", "maven_dep:postgresql")
            if "mysql-connector" in content:
                self._add_db(databases, "mysql", "sql", 0.99, EvidenceType.OBSERVED,
                             f.relative_path, "mysql-connector-java in pom.xml", "maven_dep:mysql")
            if "spring-boot-starter-data-redis" in content:
                self._add_db(databases, "redis", "cache", 0.99, EvidenceType.OBSERVED,
                             f.relative_path, "spring-data-redis in pom.xml", "maven_dep:redis")
            if "h2database" in content:
                self._add_db(databases, "h2", "sql", 0.95, EvidenceType.OBSERVED,
                             f.relative_path, "com.h2database dependency in pom.xml", "maven_dep:h2")

        # Node.js
        if "package.json" in manifest_map:
            f = manifest_map["package.json"]
            content = self._read_file(f.absolute_path).lower()
            if '"pg"' in content or '"pg-promise"' in content:
                self._add_db(databases, "postgresql", "sql", 0.99, EvidenceType.OBSERVED,
                             f.relative_path, "pg dependency in package.json", "npm_dep:pg")
            if '"mysql"' in content or '"mysql2"' in content:
                self._add_db(databases, "mysql", "sql", 0.99, EvidenceType.OBSERVED,
                             f.relative_path, "mysql dependency in package.json", "npm_dep:mysql")
            if '"mongodb"' in content or '"mongoose"' in content:
                self._add_db(databases, "mongodb", "nosql", 0.99, EvidenceType.OBSERVED,
                             f.relative_path, "mongodb/mongoose dependency in package.json", "npm_dep:mongodb")
            if '"redis"' in content or '"ioredis"' in content:
                self._add_db(databases, "redis", "cache", 0.99, EvidenceType.OBSERVED,
                             f.relative_path, "redis/ioredis dependency in package.json", "npm_dep:redis")

        # 3. Inspect SQL schema files
        if ".sql" in inventory.files_by_ext:
            sql_files = inventory.files_by_ext[".sql"]
            first_sql = sql_files[0]
            # Infer SQL database presence if not already observed
            if not any(db.category == "sql" for db in databases.values()):
                self._add_db(databases, "generic-sql", "sql", 0.90, EvidenceType.INFERRED,
                             first_sql.relative_path, f"{len(sql_files)} SQL schema/migration files found", "schema_files:sql")

        return list(databases.values())

    def _add_db(self, db_dict: Dict[str, DatabaseStat], name: str, category: str,
                confidence: float, status: EvidenceType, file_path: str, snippet: str, rule: str):
        if name not in db_dict:
            db_dict[name] = DatabaseStat(
                name=name,
                category=category,
                confidence=confidence,
                detection_status=status,
                evidence=[]
            )
        db_dict[name].evidence.append(EvidenceItem(
            evidence_type=status,
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
