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
from app.models.entities import Repository, RepositorySnapshot

class TestListRepos(unittest.TestCase):
    def test_list(self):
        db = next(get_db())
        repos = db.query(Repository).all()
        lines = []
        for r in repos:
            snaps = db.query(RepositorySnapshot).filter_by(repository_id=r.id).all()
            lines.append(f"REPO: id='{r.id}', name='{r.name}', path='{r.local_path}', snaps={len(snaps)}")
            for s in snaps:
                lines.append(f"   SNAP: id='{s.id}', hash='{s.commit_hash}', branch='{s.branch_name}'")
        with open("scratch/db_repos.txt", "w") as out:
            out.write("\n".join(lines))

if __name__ == "__main__":
    unittest.main()
