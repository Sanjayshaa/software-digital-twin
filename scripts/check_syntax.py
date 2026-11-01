import os

vendor_dir = "/Users/sanjay/DIGITAL TWIN /backend/app/static/vendor"
for f in os.listdir(vendor_dir):
    p = os.path.join(vendor_dir, f)
    print(f"{f}: {os.path.getsize(p)} bytes")
