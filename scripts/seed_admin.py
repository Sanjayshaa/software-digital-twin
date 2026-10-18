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
    from backend.app.core.database import SessionLocal
    from backend.app.models.entities import User
    from backend.app.core.auth import hash_password
except ImportError:
    from app.core.config import settings  # type: ignore[import-not-found]
    from app.core.database import SessionLocal  # type: ignore[import-not-found]
    from app.models.entities import User  # type: ignore[import-not-found]
    from app.core.auth import hash_password  # type: ignore[import-not-found]

def seed_admin_user():
    db = SessionLocal()
    try:
        admin_username = "admin"
        admin_email = "admin@digitaltwin.enterprise"
        admin_password = "AdminEnterprise2026!Secure"

        existing = db.query(User).filter((User.username == admin_username) | (User.email == admin_email)).first()
        if existing:
            print(f"Admin user already exists: {existing.username} ({existing.email}) [Role: {existing.role}]")
            return

        user = User(
            username=admin_username,
            email=admin_email,
            hashed_password=hash_password(admin_password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print("=" * 60)
        print("ENTERPRISE ADMIN USER CREATED SUCCESSFULLY")
        print(f"Username: {user.username}")
        print(f"Email:    {user.email}")
        print(f"Password: {admin_password}")
        print(f"Role:     {user.role}")
        print(f"User ID:  {user.id}")
        print("=" * 60)
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin_user()
