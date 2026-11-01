import os

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
matches = []

for dirpath, dirnames, filenames in os.walk(root_dir):
    if any(skip in dirpath for skip in [".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"]):
        continue
    for f in filenames:
        if f.endswith(".py"):
            path = os.path.join(dirpath, f)
            with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                for idx, line in enumerate(fp, 1):
                    if "utcnow" in line:
                        matches.append((path, idx, line.strip()))

print(f"Total occurrences of utcnow across workspace: {len(matches)}")
for p, l, text in matches:
    rel = os.path.relpath(p, root_dir)
    print(f"  {rel}:{l}: {text}")

