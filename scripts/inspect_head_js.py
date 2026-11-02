import subprocess

res = subprocess.run(["git", "show", "HEAD:backend/app/static/twin.js"], capture_output=True, text=True)
head_js = res.stdout
print(f"HEAD twin.js lines: {len(head_js.splitlines())}")

# Let's see what is after the truncated line in HEAD
target = '<span class="badge" style="background:rgba(124,58,237,0.15);color:#c084fc;font-size:11px;padding:2px 8px;'
pos = head_js.find(target)
print(f"Found target in HEAD at pos: {pos}")
if pos != -1:
    print("Next 500 chars in HEAD:")
    print(head_js[pos:pos+500])

