from typing import Generator
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger(__name__)

# Engine configuration with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_database_schema_compatibility():
    """
    Ensures that PostgreSQL database columns for structural_artifacts, code_symbols,
    artifact_relationships, and files are wide enough for deep qualified names
    and paths, even if Alembic migration was not manually executed.
    """
    try:
        if engine.dialect.name == "postgresql":
            with engine.connect() as conn:
                alter_statements = [
                    "ALTER TABLE structural_artifacts ALTER COLUMN name TYPE VARCHAR(512);",
                    "ALTER TABLE structural_artifacts ALTER COLUMN qualified_name TYPE VARCHAR(2048);",
                    "ALTER TABLE structural_artifacts ALTER COLUMN location TYPE VARCHAR(2048);",
                    "ALTER TABLE code_symbols ALTER COLUMN name TYPE VARCHAR(512);",
                    "ALTER TABLE code_symbols ALTER COLUMN qualified_name TYPE VARCHAR(2048);",
                    "ALTER TABLE artifact_relationships ALTER COLUMN source_location TYPE VARCHAR(2048);",
                    "ALTER TABLE files ALTER COLUMN path TYPE VARCHAR(2048);",
                ]
                for stmt in alter_statements:
                    try:
                        conn.execute(text(stmt))
                        conn.commit()
                    except Exception:
                        conn.rollback()
    except Exception as exc:
        logger.debug("Database schema compatibility check skipped: %s", exc)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


