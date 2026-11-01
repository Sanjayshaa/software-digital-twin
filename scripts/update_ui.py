import re

with open("backend/app/static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update Sidebar Navigation
# Find <nav id="sidebar-nav" ... > ... </nav>
nav_pattern = r'(<nav id="sidebar-nav"[^>]*>)([\s\S]*?)(</nav>)'
nav_match = re.search(nav_pattern, html)
if not nav_match:
    print("ERROR: sidebar-nav not found!")
    exit(1)

new_nav_inner = """
        <!-- Section: Project -->
        <div class="space-y-1">
          <div class="px-2.5 py-1 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">Project</div>
          <button data-view="overview" class="view-tab active w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] text-white shadow-xs transition-all" title="Overview (Project Summary &amp; Key Findings)" aria-label="Overview">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">grid_view</span>
              <span class="sidebar-text-label">Overview</span>
            </div>
          </button>
          <button data-view="report" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Full Project Report &amp; Markdown Export" aria-label="Report">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">fact_check</span>
              <span class="sidebar-text-label">Report</span>
            </div>
          </button>
          <button data-view="docs" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Repository Documentation &amp; System Map" aria-label="Docs">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">menu_book</span>
              <span class="sidebar-text-label">Docs</span>
            </div>
          </button>
          <button data-view="stats" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Repository Analysis &amp; Health Statistics" aria-label="Stats">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">bar_chart</span>
              <span class="sidebar-text-label">Stats</span>
            </div>
          </button>
        </div>

        <!-- Section: Explore & Quality -->
        <div class="space-y-1">
          <div class="px-2.5 py-1 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">Explore</div>
          <button data-view="discovery" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Project Discovery &amp; Technical Health Assessment" aria-label="Discovery &amp; Health">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">explore</span>
              <span class="sidebar-text-label">Discovery &amp; Health</span>
            </div>
            <span id="badge-discovery-status" class="sidebar-badge-label text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 uppercase">Health</span>
          </button>
          <button data-view="architecture" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Architecture (Knowledge Graph)" aria-label="Architecture">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">account_tree</span>
              <span class="sidebar-text-label">Architecture</span>
            </div>
          </button>
          <button data-view="dependencies" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Dependencies &amp; Coupling" aria-label="Dependencies">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">polyline</span>
              <span class="sidebar-text-label">Dependencies</span>
            </div>
          </button>
          <button data-view="components" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Components &amp; Symbol Catalog" aria-label="Components">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">deployed_code</span>
              <span class="sidebar-text-label">Components</span>
            </div>
          </button>
        </div>

        <!-- Section: Change -->
        <div class="space-y-1">
          <div class="px-2.5 py-1 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">Change</div>
          <button data-view="changes" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Commits &amp; History" aria-label="Commits &amp; History">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">history</span>
              <span class="sidebar-text-label">Commits &amp; History</span>
            </div>
          </button>
          <button data-view="impact" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Change Impact &amp; Blast Radius" aria-label="Change Impact">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">radar</span>
              <span class="sidebar-text-label">Change Impact</span>
            </div>
          </button>
          <button data-view="simulation" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="What-If Simulation" aria-label="What-If Simulation">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px] text-[#0071e3]">science</span>
              <span class="sidebar-text-label">What-If</span>
            </div>
          </button>
        </div>

        <!-- Section: Verify -->
        <div class="space-y-1">
          <div class="px-2.5 py-1 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">Verify</div>
          <button data-view="tests" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Targeted Test Impact" aria-label="Tests">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px]">check_circle</span>
              <span class="sidebar-text-label">Tests</span>
            </div>
          </button>
        </div>

        <!-- Section: Operate -->
        <div class="space-y-1">
          <div class="px-2.5 py-1 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">Operate</div>
          <button data-view="incidents" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Operational Incidents" aria-label="Incidents">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px] text-[#E11D48]">warning</span>
              <span class="sidebar-text-label">Incidents</span>
            </div>
            <span id="sidebar-incidents-badge" class="sidebar-badge-label px-1.5 py-0.5 rounded-full bg-[#FFE4E6] text-[#BE123C] text-[10px] font-bold">0</span>
          </button>
          <button data-view="runtime" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Runtime Telemetry" aria-label="Runtime">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px] text-[#0284C7]">dynamic_feed</span>
              <span class="sidebar-text-label">Runtime</span>
            </div>
            <span id="sidebar-runtime-badge" class="sidebar-badge-label px-1.5 py-0.5 rounded-full bg-[#E0F2FE] text-[#0369A1] text-[10px] font-bold">0</span>
          </button>
        </div>

        <!-- Section: Intelligence -->
        <div class="space-y-1">
          <div class="px-2.5 py-1 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">Intelligence</div>
          <button data-view="ask" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Ask Twin Intelligence" aria-label="Ask Twin">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px] text-[#7C3AED]">neurology</span>
              <span class="sidebar-text-label">Ask Twin</span>
            </div>
          </button>
        </div>

        <!-- Section: Explanation & Walkthrough -->
        <div class="space-y-1">
          <div class="px-2.5 py-1 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">Explanation</div>
          <button data-view="demo" class="view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all" title="Interactive Demo &amp; Pipeline Architecture" aria-label="Demo &amp; Pipeline">
            <div class="flex items-center gap-2.5">
              <span class="material-symbols-outlined text-[18px] text-[#0071e3]">play_circle</span>
              <span class="sidebar-text-label">Demo &amp; Pipeline</span>
            </div>
            <span class="sidebar-badge-label text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 uppercase">Interactive</span>
          </button>
        </div>
"""

html = html[:nav_match.start(2)] + new_nav_inner + html[nav_match.end(2):]
print("Updated sidebar nav.")

# 2. Extract and remove workflow-pipeline-bar from global location
bar_pattern = r'(<!-- =+ -->\s*<!-- COMPLETE TWINCORE WORKFLOW PIPELINE INDICATOR[\s\S]*?<div id="workflow-pipeline-bar"[\s\S]*?</div>\s*</div>)'
bar_match = re.search(bar_pattern, html)
pipeline_bar_html = ""
if bar_match:
    pipeline_bar_html = bar_match.group(0)
    # Remove from global position
    html = html[:bar_match.start()] + html[bar_match.end():]
    print("Extracted and removed global workflow-pipeline-bar.")
else:
    print("WARNING: workflow-pipeline-bar not found globally!")

# 3. Insert pipeline_bar_html inside <section id="view-demo">
demo_pattern = r'(<section id="view-demo"[^>]*>)'
demo_match = re.search(demo_pattern, html)
if demo_match and pipeline_bar_html:
    html = html[:demo_match.end()] + "\n\n          " + pipeline_bar_html + "\n" + html[demo_match.end():]
    print("Inserted workflow-pipeline-bar into view-demo.")

with open("backend/app/static/index.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Saved stage 1 of index.html.")
