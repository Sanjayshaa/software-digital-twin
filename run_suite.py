import sys
import os
import subprocess

venv_pytest = os.path.abspath(".venv/bin/pytest")
args = [venv_pytest] + (sys.argv[1:] if len(sys.argv) > 1 else ["backend/tests/", "-q"])
env = dict(os.environ)
env["POSTGRES_SERVER"] = "127.0.0.1"
env["PYTHONPATH"] = os.path.abspath("backend")

res = subprocess.run(args, env=env, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print(res.stderr, file=sys.stderr)
sys.exit(res.returncode)

