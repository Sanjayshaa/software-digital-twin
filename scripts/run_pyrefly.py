import subprocess

pyrefly_bin = "/Users/sanjay/.antigravity-ide/extensions/meta.pyrefly-1.4.0-darwin-arm64/bin/pyrefly"

res = subprocess.run([pyrefly_bin, "check", "--min-severity=warn"], capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
print("Return code:", res.returncode)
