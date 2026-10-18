import os
import sys

# Ensure backend and root are on sys.path for direct CLI script execution
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
for path in (BACKEND_DIR, BASE_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from backend.app.core.config import settings
    from backend.app.core.database import engine, Base
    import backend.app.models.entities
except ImportError:
    from app.core.config import settings  # type: ignore[import-not-found]
    from app.core.database import engine, Base  # type: ignore[import-not-found]
    import app.models.entities  # type: ignore[import-not-found]

def init_database():
    print(f"Connecting to database: {settings.POSTGRES_SERVER} / {engine.url.render_as_string(hide_password=True)}")
    print("Creating all Digital Twin relational schema, tables, foreign keys, and indexes...")
    Base.metadata.create_all(bind=engine)
    print("All enterprise tables created successfully!")

if __name__ == "__main__":
    init_database()
