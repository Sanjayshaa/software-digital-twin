path = "/Users/sanjay/DIGITAL TWIN /backend/app/static/index.html"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

import re

stack = []
self_closing = {'br', 'hr', 'img', 'input', 'link', 'meta', 'circle', 'path', 'rect', 'line', 'polygon', 'polyline', 'source'}

for i, line in enumerate(lines, 1):
    # Remove HTML comments
    clean_line = re.sub(r'<!--[\s\S]*?-->', '', line)
    tags = re.findall(r'<(/?[a-zA-Z0-9_-]+)([^>]*)>', clean_line)
    for tag_name, attrs in tags:
        tag_name_lower = tag_name.lower()
        if tag_name_lower in self_closing:
            continue
        if attrs.strip().endswith('/'):
            continue
        if tag_name.startswith('/'):
            name = tag_name[1:].lower()
            if stack and stack[-1][0] == name:
                stack.pop()
            else:
                top = stack[-1] if stack else None
                print(f"Line {i}: Mismatched closing </{name}>! Stack top was {top}")
        else:
            stack.append((tag_name_lower, i, line.strip()[:40]))

print(f"Total unclosed tags on stack: {len(stack)}")
for item in stack[-15:]:
    print("  Unclosed:", item)
