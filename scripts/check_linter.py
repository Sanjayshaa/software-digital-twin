import subprocess

res = subprocess.run(["ps", "aux"], capture_output=True, text=True)
for line in res.stdout.splitlines():
    if any(k in line.lower() for k in ["pyrefly", "pyright", "language", "lsp"]):
        print(line)
