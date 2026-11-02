import subprocess
import re
import sys

print("=== CHECKING INDEX.HTML ===")
with open("backend/app/static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Check occurrences of workflow-pipeline-bar
pipeline_bars = [m.start() for m in re.finditer(r'id=["\']workflow-pipeline-bar["\']', html)]
print(f"Occurrences of id='workflow-pipeline-bar': {len(pipeline_bars)}")

# Check occurrences of Workflow Stages role/label
stage_navs = [m.start() for m in re.finditer(r'aria-label=["\']Workflow Stages["\']', html)]
print(f"Occurrences of aria-label='Workflow Stages': {len(stage_navs)}")

# Verify lines before view-no-repo
no_repo_idx = html.find('id="view-no-repo"')
assert no_repo_idx != -1, "view-no-repo not found!"
before_no_repo = html[:no_repo_idx]
assert "Workflow Stages" not in before_no_repo, "ERROR: Workflow Stages found before view-no-repo!"
print("SUCCESS: No rogue pipeline buttons before views!")

# Verify pipeline bar is inside view-demo
demo_idx = html.find('id="view-demo"')
assert demo_idx != -1, "view-demo not found!"
demo_end_idx = html.find('</section>', demo_idx)
demo_content = html[demo_idx:demo_end_idx]
assert 'id="workflow-pipeline-bar"' in demo_content, "ERROR: workflow-pipeline-bar missing from view-demo!"
assert 'id="demo-stage-stepper"' in demo_content, "ERROR: demo-stage-stepper missing from view-demo!"
print("SUCCESS: view-demo properly contains the pipeline bar and demo stepper!")

# Validate HTML tag balance for main sections
open_sections = len(re.findall(r'<section\b', html))
close_sections = len(re.findall(r'</section>', html))
print(f"Sections: open={open_sections}, close={close_sections}")
assert open_sections == close_sections, f"Mismatched section tags: {open_sections} != {close_sections}"

print("\n=== VALIDATING JAVASCRIPT SYNTAX ===")
res = subprocess.run(["node", "-c", "backend/app/static/twin.js"], capture_output=True, text=True)
if res.returncode != 0:
    print("JS Syntax Error:", res.stderr)
    sys.exit(res.returncode)
else:
    print("SUCCESS: twin.js syntax valid!")

print("\n=== RUNNING SIMULATION CORRECTNESS TESTS ===")
res = subprocess.run(["./.venv/bin/python", "-m", "unittest", "backend/tests/test_simulation_correctness_and_evidence.py"], capture_output=True, text=True)
print(res.stderr[-300:] if len(res.stderr) > 300 else res.stderr)
assert res.returncode == 0, "Simulation tests failed!"

print("\n=== RUNNING FRONTEND UX E2E TESTS ===")
res = subprocess.run(["./.venv/bin/python", "backend/tests/test_frontend_ux_e2e.py"], capture_output=True, text=True)
print(res.stdout[-300:] if len(res.stdout) > 300 else res.stdout)
assert res.returncode == 0, "Frontend UX tests failed!"

print("\nALL VERIFICATIONS PASSED!")
