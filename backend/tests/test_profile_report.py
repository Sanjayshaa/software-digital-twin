import unittest
import os
import sys

if sys.version_info < (3, 11):
    venv_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "python3"))
    if os.path.exists(venv_py):
        os.execv(venv_py, [venv_py, "-m", "unittest"] + sys.argv[1:])

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.database import get_db
from app.models.entities import Repository, User
from app.core.auth import create_access_token
from fastapi.testclient import TestClient
from main import app

class TestAuthCall(unittest.TestCase):
    def test_auth_call(self):
        client = TestClient(app)
        db = next(get_db())
        repo_id = "60c89c21-ecdc-4322-bbd0-3c1d491b7c9c"
        snap_id = "snap_1babcc51effa657c"
        repo = db.query(Repository).filter_by(id=repo_id).first()
        print(f"Repo owner_id: {repo.owner_id}")
        user = db.query(User).filter_by(id=repo.owner_id).first()
        print(f"Owner user: {user.username if user else 'None'}, role: {user.role if user else 'None'}")

        if user:
            token = create_access_token(user_id=user.id, username=user.username, role=user.role)
            headers = {"Authorization": f"Bearer {token}"}
            import time
            t0 = time.time()
            res = client.get(f"/repositories/{repo_id}/report?snapshot_id={snap_id}", headers=headers)
            print(f"Report with auth status: {res.status_code} in {time.time()-t0:.3f}s")
            t1 = time.time()
            res_st = client.get(f"/repositories/{repo_id}/stats?snapshot_id={snap_id}", headers=headers)
            print(f"Stats with auth status: {res_st.status_code} in {time.time()-t1:.3f}s")

if __name__ == "__main__":
    unittest.main()
