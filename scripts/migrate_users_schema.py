"""
Schema migration script to add verification and password reset columns to users table.
"""
import os
import sys

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, os.path.abspath(__file__)])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import text
from app.core.database import engine

def run_migration():
    print("Running users table schema migration...")
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMP;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR(255);
        """))
        conn.commit()
    print("Migration executed successfully: columns verified/added.")

if __name__ == "__main__":
    run_migration()
