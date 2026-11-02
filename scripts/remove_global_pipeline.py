with open("backend/app/static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

import re

# Match lines from <!-- 8 Pipeline Stage Buttons --> down to </div>\n        </div>\n\n        <!-- =====... VIEW 0
pattern = r'<!-- 8 Pipeline Stage Buttons -->[\s\S]*?</div>\s*</div>\s*(?=<!-- =+\s*-->\s*<!-- VIEW 0:)'

match = re.search(pattern, html)
if match:
    html = html[:match.start()] + html[match.end():]
    with open("backend/app/static/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("SUCCESS: Removed global 8 pipeline buttons!")
else:
    print("ERROR: Global pipeline buttons pattern not matched!")

