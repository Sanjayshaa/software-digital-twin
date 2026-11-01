import sys
import subprocess

res = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
print(res.stdout)
