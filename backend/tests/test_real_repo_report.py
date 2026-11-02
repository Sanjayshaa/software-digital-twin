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

from fastapi.testclient import TestClient
from main import app
from app.core.database import get_db
from app.models.entities import Repository

class TestRealRepoReport(unittest.TestCase):
    def test_real_repo_report(self):
        client = TestClient(app)
        db = next(get_db())
        repos = db.query(Repository).all()
        print(f"Total repos in DB: {len(repos)}")
        for r in repos:
            print(f"Repo: {r.id} | name: {r.name}")
            import time
            t0 = time.time()
            res = client.get(f"/repositories/{r.id}/report")
            elapsed = time.time() - t0
            print(f"Status: {res.status_code} in {elapsed:.3f}s")
            if res.status_code != 200:
                print(f"Error: {res.text}")

if __name__ == "__main__":
    unittest.main()
