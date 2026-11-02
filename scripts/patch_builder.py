with open("scripts/build_views.py", "r", encoding="utf-8") as f:
    code = f.read()

# Replace the pattern matching
old_logic = """# Replace <section id="view-overview" ...> </section> with overview_html
pattern = r'(<!-- =+ -->\\s*<!-- VIEW 1: [^\\n]*-->\\s*<section id="view-overview"[\\s\\S]*?</section>)'
match = re.search(pattern, html)
if not match:
    print("ERROR: view-overview pattern not found!")
    exit(1)

html = html[:match.start()] + overview_html + html[match.end():]
print("Replaced view-overview and inserted view-docs and view-stats.")"""

new_logic = """# Replace <section id="view-overview" ...> </section> with overview_html
start_marker = '<!-- VIEW 1: STITCH OVERVIEW'
end_marker = '<!-- VIEW: PROJECT DISCOVERY'

start_idx = html.find(start_marker)
# walk back to previous <!-- ====
box_start = html.rfind('<!-- ===', 0, start_idx)
end_idx = html.find(end_marker)
box_end = html.rfind('<!-- ===', 0, end_idx)

if start_idx == -1 or end_idx == -1:
    print("ERROR: markers not found!", start_idx, end_idx)
    exit(1)

html = html[:box_start] + overview_html + "\\n        " + html[box_end:]
print("Replaced view-overview and inserted view-docs and view-stats.")"""

code = code.replace(old_logic, new_logic)
with open("scripts/build_views.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Updated build_views.py.")
