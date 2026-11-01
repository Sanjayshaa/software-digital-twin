import os

path = "/Users/sanjay/DIGITAL TWIN /backend/app/static/twin.js"
with open(path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f, 1):
        if "boot-screen" in line or "boot_screen" in line or "boot" in line.lower():
            if any(k in line.lower() for k in ["hide", "dismiss", "remove", "display", "boot-screen", "init"]):
                print(f"{idx}: {line.strip()[:140]}")
