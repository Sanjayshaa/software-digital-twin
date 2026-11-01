import os

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
matches = []

for dirpath, dirnames, filenames in os.walk(root_dir):
    if any(skip in dirpath for skip in [".git", ".venv", "node_modules"]):
        continue
    for f in filenames:
        if f.endswith((".js", ".html", ".ts", ".jsx", ".tsx", ".py")):
            path = os.path.join(dirpath, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                    if "Initializing TwinCore workspace" in content:
                        matches.append((path, "Initializing TwinCore workspace"))
                    elif "initializing" in content.lower() and "workspace" in content.lower():
                        matches.append((path, "initializing/workspace"))
            except Exception:
                pass

for p, m in matches:
    print(f"Found in {p}: {m}")
