import subprocess

res = subprocess.run(["./.venv/bin/python", "scripts/update_ui.py"], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("ERR:", res.stderr)
