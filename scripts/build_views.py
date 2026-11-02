import re

overview_html = """        <!-- ============================================================== -->
        <!-- VIEW 1: REPOSITORY OVERVIEW & LIVING SOFTWARE MODEL            -->
        <!-- ============================================================== -->
        <section id="view-overview" class="content-view-panel space-y-8" style="display:none;" aria-label="Project Overview &amp; Health Dashboard">

          <!-- Loading State Skeleton -->
          <div id="ov-loading-state" class="hidden space-y-6 animate-pulse" aria-live="polite">
            <div class="h-20 bg-[#F1F5F9] rounded-2xl"></div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div class="h-24 bg-[#F1F5F9] rounded-xl"></div>
              <div class="h-24 bg-[#F1F5F9] rounded-xl"></div>
              <div class="h-24 bg-[#F1F5F9] rounded-xl"></div>
              <div class="h-24 bg-[#F1F5F9] rounded-xl"></div>
            </div>
            <div class="h-48 bg-[#F1F5F9] rounded-2xl"></div>
          </div>

          <!-- Error State Banner -->
          <div id="ov-error-state" class="hidden p-6 rounded-2xl bg-[#FEF2F2] border border-[#FECACA] text-center space-y-3" role="alert">
            <div class="w-12 h-12 mx-auto rounded-full bg-[#FEE2E2] text-[#DC2626] flex items-center justify-center">
              <span class="material-symbols-outlined text-[24px]">error</span>
            </div>
            <h3 class="text-base font-bold text-[#991B1B]">Unable to Load Project Overview</h3>
            <p id="ov-error-message" class="text-xs text-[#B91C1C] max-w-md mx-auto">There was an issue communicating with the TwinCore backend.</p>
            <button class="px-4 py-2 rounded-full bg-[#DC2626] hover:bg-[#B91C1C] text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer" type="button" onclick="window.TwinApp.loadOverviewData()">
              Retry Loading
            </button>
          </div>

          <!-- Main Dashboard Content Container -->
          <div id="ov-content-container" class="space-y-8">

            <!-- 1. Repository Header & Synchronized Model Status -->
            <div class="flex flex-col lg:flex-row lg:items-end justify-between gap-6 pb-2 border-b border-[#E2E8F0]">
              <div class="space-y-1.5 max-w-3xl">
                <div class="flex items-center flex-wrap gap-2 text-xs font-medium text-[#64748B]">
                  <span id="ov-repo-name" class="font-bold text-[#0F172A] text-sm">Connected Repository</span>
                  <span>/</span>
                  <span id="ov-branch" class="font-mono text-[#0071e3] font-semibold">main</span>
                  <span>/</span>
                  <span id="ov-commit" class="font-mono text-[#64748B]">HEAD</span>
                  <span id="ov-model-live-indicator-badge" class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">
                    <span class="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-ping"></span>
                    <span>Model Synchronized</span>
                  </span>
                </div>
                <h1 id="ov-header-title" class="text-2xl sm:text-3xl font-bold text-[#0F172A] tracking-tight">Project Overview &amp; Architecture</h1>
                <p id="ov-purpose-text" class="text-xs sm:text-sm text-[#475569] leading-relaxed">
                  Loading repository summary and detected code purpose...
                </p>
              </div>

              <!-- Action Navigation -->
              <div class="flex items-center flex-wrap gap-2.5">
                <button id="ov-btn-investigate" class="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white hover:bg-[#F8FAFC] text-[#0F172A] border border-[#CBD5E1] shadow-2xs hover:shadow-xs transition-all text-xs font-semibold cursor-pointer" type="button" onclick="window.TwinApp.investigateOverview();">
                  <span id="ov-btn-investigate-icon" class="material-symbols-outlined text-[16px] text-[#0071e3]">health_and_safety</span>
                  <span id="ov-btn-investigate-label">Health Assessment</span>
                  <span id="ov-incidents-badge" class="ml-0.5 px-1.5 py-0.5 rounded-full bg-[#EFF6FF] text-[#0071e3] text-[10px] font-bold">Verified</span>
                </button>

                <button id="ov-btn-docs" class="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white hover:bg-[#F8FAFC] text-[#0F172A] border border-[#CBD5E1] shadow-2xs hover:shadow-xs transition-all text-xs font-semibold cursor-pointer" type="button" onclick="window.TwinApp.switchPrimaryView('docs');">
                  <span class="material-symbols-outlined text-[16px] text-[#0071e3]">menu_book</span>
                  <span>Docs &amp; System Map</span>
                </button>

                <button id="ov-btn-report" class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#0071e3] hover:bg-[#0059b5] text-white shadow-2xs hover:shadow-xs transition-all text-xs font-semibold cursor-pointer" type="button" onclick="window.TwinApp.switchPrimaryView('report');">
                  <span class="material-symbols-outlined text-[16px]">fact_check</span>
                  <span>Full Project Report</span>
                </button>
              </div>
            </div>

            <!-- Dynamic State Alert Banner (Truthful Repository Status) -->
            <div id="ov-state-banner" class="rounded-2xl border p-4 sm:p-5 shadow-xs transition-all" style="display:none;"></div>

            <!-- 2. SECTION: TECH STACK, ENTRY POINTS, APIS & DATABASES (EVIDENCE-BACKED) -->
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              
              <!-- Tech Stack & Entrypoints (6 cols) -->
              <div class="lg:col-span-6 twin-card p-6 space-y-5 border border-[#E2E8F0]">
                <div class="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
                  <div class="flex items-center gap-2.5">
                    <span class="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#0071e3] flex items-center justify-center shrink-0">
                      <span class="material-symbols-outlined text-[18px]">terminal</span>
                    </span>
                    <div>
                      <h2 class="text-sm sm:text-base font-bold text-[#0F172A]">Tech Stack &amp; Entry Points</h2>
                      <p class="text-[11px] text-[#64748B]">Detected runtimes, frameworks, and primary execution files</p>
                    </div>
                  </div>
                  <button class="text-xs text-[#0071e3] hover:underline font-semibold" onclick="window.TwinApp.switchPrimaryView('components');" type="button">Catalog →</button>
                </div>

                <!-- Languages & Frameworks Badges -->
                <div class="space-y-2">
                  <div class="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Detected Languages &amp; Tools</div>
                  <div id="ov-languages-container" class="flex flex-wrap gap-1.5">
                    <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#F1F5F9] text-[#64748B]">Detecting stack...</span>
                  </div>
                </div>

                <!-- Primary Entry Points List -->
                <div class="space-y-2 pt-2 border-t border-[#F8FAFC]">
                  <div class="flex items-center justify-between text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
                    <span>Execution Entry Points</span>
                    <span id="ov-entry-count" class="font-mono text-[#0071e3]">0</span>
                  </div>
                  <div id="ov-entry-points-list" class="space-y-1.5 text-xs max-h-48 overflow-y-auto custom-scrollbar">
                    <div class="text-xs text-[#64748B] italic">Analyzing execution entry points...</div>
                  </div>
                </div>
              </div>

              <!-- Discovered Services, APIs & Database Storage (6 cols) -->
              <div class="lg:col-span-6 twin-card p-6 space-y-5 border border-[#E2E8F0]">
                <div class="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
                  <div class="flex items-center gap-2.5">
                    <span class="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#0071e3] flex items-center justify-center shrink-0">
                      <span class="material-symbols-outlined text-[18px]">api</span>
                    </span>
                    <div>
                      <h2 class="text-sm sm:text-base font-bold text-[#0F172A]">Interfaces &amp; Storage Entities</h2>
                      <p class="text-[11px] text-[#64748B]">Discovered HTTP route contracts and database schemas</p>
                    </div>
                  </div>
                  <button class="text-xs text-[#0071e3] hover:underline font-semibold" onclick="window.TwinApp.switchPrimaryView('docs');" type="button">System Map →</button>
                </div>

                <!-- Discovered APIs List -->
                <div class="space-y-2">
                  <div class="flex items-center justify-between text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
                    <span>Discovered HTTP API Routes</span>
                    <span id="ov-api-count" class="font-mono text-[#059669]">0</span>
                  </div>
                  <div id="ov-apis-list" class="space-y-1 text-xs max-h-36 overflow-y-auto custom-scrollbar">
                    <div class="text-xs text-[#64748B] italic">Analyzing declared routes...</div>
                  </div>
                </div>

                <!-- Discovered Databases & Models -->
                <div class="space-y-2 pt-2 border-t border-[#F8FAFC]">
                  <div class="flex items-center justify-between text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
                    <span>Database Entities &amp; Schemas</span>
                    <span id="ov-db-count" class="font-mono text-[#7C3AED]">0</span>
                  </div>
                  <div id="ov-database-list" class="space-y-1 text-xs max-h-36 overflow-y-auto custom-scrollbar">
                    <div class="text-xs text-[#64748B] italic">Analyzing data models...</div>
                  </div>
                </div>
              </div>

            </div>

            <!-- 3. SECTION: REPOSITORY INVENTORY & HONEST OBSERVABILITY DISCLOSURE -->
            <div class="twin-card p-6 space-y-4 border border-[#E2E8F0]">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-[#F1F5F9]">
                <div>
                  <h2 class="text-base font-bold text-[#0F172A] tracking-tight">Repository Inventory &amp; Analysis Scope</h2>
                  <p class="text-xs text-[#64748B]">Syntactic code facts extracted directly from current immutable snapshot.</p>
                </div>
                <div class="flex items-center gap-2">
                  <span id="ov-test-status-badge" class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#FEF2F2] text-[#DC2626]">UNKNOWN / NOT MEASURED</span>
                </div>
              </div>

              <!-- 4 Stat Counters -->
              <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                  <div class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Discovered Files</div>
                  <div id="ov-components-count" class="text-xl font-bold text-[#0F172A] font-mono mt-0.5">--</div>
                  <p id="ov-components-sub" class="text-[11px] text-[#64748B] mt-1 truncate">Source files in tree</p>
                </div>
                <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                  <div class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Extracted Symbols</div>
                  <div id="ov-apis-count" class="text-xl font-bold text-[#0F172A] font-mono mt-0.5">--</div>
                  <p id="ov-apis-sub" class="text-[11px] text-[#64748B] mt-1 truncate">Classes, methods, routes</p>
                </div>
                <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                  <div class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Indexed Relationships</div>
                  <div id="ov-deps-count" class="text-xl font-bold text-[#0F172A] font-mono mt-0.5">--</div>
                  <p id="ov-deps-sub" class="text-[11px] text-[#64748B] mt-1 truncate">Calls, imports, inheritance</p>
                </div>
                <div class="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                  <div class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Automated Tests</div>
                  <div id="ov-tests-count" class="text-xl font-bold text-[#0F172A] font-mono mt-0.5">--</div>
                  <p id="ov-tests-sub" class="text-[11px] text-[#DC2626] font-semibold mt-1 truncate">0 / 5 Linked</p>
                </div>
              </div>

              <!-- Honest Disclaimer on Unknown Coverage -->
              <div class="p-3.5 rounded-xl bg-[#EFF6FF] border border-[#BFDBFE] text-xs text-[#1E40AF] flex items-start gap-2.5">
                <span class="material-symbols-outlined text-[18px] text-[#2563EB] shrink-0 mt-0.5">policy</span>
                <span id="ov-tests-explanation" class="leading-relaxed">
                  <strong>Honest Observability Principle:</strong> 0 automated tests were discovered or linked to code entities in this repository snapshot. Unknown test coverage does NOT prove that code modifications are safe.
                </span>
              </div>
            </div>

            <!-- 4. SECTION: DO NEXT (PRIORITIZED REPOSITORY ACTION LIST) -->
            <section aria-labelledby="section-donext-heading" class="twin-card p-6 space-y-5 border border-[#E2E8F0]">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-[#F1F5F9]">
                <div>
                  <h2 id="section-donext-heading" class="text-base font-bold text-[#0F172A] tracking-tight">Do Next</h2>
                  <p class="text-xs text-[#64748B]">
                    Prioritized recommendations derived directly from this repository's confirmed findings, dependency hotspots, and coverage gaps.
                  </p>
                </div>
                <div class="flex items-center gap-2 text-[11px] font-medium text-[#64748B]">
                  <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-[#EF4444]"></span> High Priority</span>
                  <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-[#F59E0B]"></span> Medium Priority</span>
                  <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-[#3B82F6]"></span> Low Priority</span>
                </div>
              </div>

              <!-- Prioritized Actions Queue -->
              <div id="ov-do-next-list" class="space-y-3">
                <!-- Dynamically populated by TwinApp.renderDoNextList() -->
                <div class="p-4 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
                  Evaluating prioritized actions for your project...
                </div>
              </div>
            </section>

            <!-- 5. SECTION: RECENT CHANGES & DETAILED TWIN INTELLIGENCE -->
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

              <!-- LEFT: Recent Changes & Verified Impact (8 cols) -->
              <div class="lg:col-span-8 space-y-6">

                <!-- Recent Git Changes Card -->
                <div class="twin-card p-6 space-y-4 border border-[#E2E8F0]">
                  <div class="flex items-center justify-between">
                    <div>
                      <h2 class="text-base font-bold text-[#0F172A] tracking-tight">Recent Changes</h2>
                      <p class="text-xs text-[#64748B]">Git commit history and verified or predicted blast-radius consequences.</p>
                    </div>
                    <button class="text-xs text-[#0071e3] hover:text-[#0059b5] font-semibold cursor-pointer" onclick="window.TwinApp.switchPrimaryView('changes');" type="button">
                      Compare Snapshots →
                    </button>
                  </div>

                  <!-- Dynamic Git Commits List -->
                  <div id="ov-recent-commits-list" class="space-y-2.5 max-h-80 overflow-y-auto custom-scrollbar">
                    <div class="p-4 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
                      Loading Git commit history...
                    </div>
                  </div>
                </div>

                <!-- Latest Change Impact Card -->
                <div class="twin-card p-6 space-y-4 border border-[#E2E8F0]">
                  <div class="flex items-center justify-between">
                    <div>
                      <h3 class="text-base font-bold text-[#0F172A] tracking-tight">Latest Change Impact</h3>
                      <p class="text-xs text-[#64748B]">Deterministic causal propagation between compared snapshots.</p>
                    </div>
                    <button class="text-xs text-[#0071e3] hover:text-[#0059b5] font-semibold cursor-pointer" onclick="window.TwinApp.switchPrimaryView('impact');" type="button">
                      View Full Report →
                    </button>
                  </div>
                  <div id="ov-impact-container">
                    <!-- Injected by twin.js -->
                  </div>
                </div>

                <!-- Macro Architecture Packages Grid & Conformance Alert -->
                <div class="twin-card p-6 space-y-4 border border-[#E2E8F0]">
                  <div class="flex items-center justify-between">
                    <div>
                      <h3 class="text-base font-bold text-[#0F172A] tracking-tight">Macro Architecture Packages</h3>
                      <p class="text-xs text-[#64748B]">Structural clustering across top-level project folders.</p>
                    </div>
                    <button class="text-xs text-[#0071e3] hover:text-[#0059b5] font-semibold cursor-pointer" onclick="window.TwinApp.switchPrimaryView('architecture');" type="button">
                      Explore Graph →
                    </button>
                  </div>
                  <div id="ov-packages-grid" class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <!-- Populated dynamically -->
                  </div>
                </div>

              </div>

              <!-- RIGHT: Operational Status & Telemetry Stream (4 cols) -->
              <div class="lg:col-span-4 space-y-6">

                <!-- Operational Status Card -->
                <div id="ov-active-incident-card" class="twin-card p-6 relative overflow-hidden border border-[#E2E8F0]">
                  <div id="ov-incident-stripe" class="absolute left-0 top-0 bottom-0 w-1.5 bg-[#94A3B8]"></div>
                  <div class="flex items-center justify-between pb-2 border-b border-[#F1F5F9]">
                    <span id="ov-incident-status-pill" class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#F1F5F9] text-[#475569]">
                      <span id="ov-incident-pulse" class="w-1.5 h-1.5 rounded-full bg-[#94A3B8]"></span>
                      <span id="ov-incident-status">Operational Status</span>
                    </span>
                    <span id="ov-incident-time" class="text-[10px] text-[#64748B]">Telemetry active</span>
                  </div>
                  <div class="mt-3 space-y-1">
                    <h3 id="ov-incident-title" class="text-sm font-bold text-[#0F172A]">Production Health Normal</h3>
                    <p id="ov-incident-desc" class="text-xs text-[#64748B] leading-relaxed">No critical operational failures or anomalous exceptions detected.</p>
                  </div>
                  <div class="mt-4 pt-3 border-t border-[#F1F5F9] flex items-center justify-between">
                    <span id="ov-incident-evidence" class="text-[10px] text-[#64748B] font-mono">0 alerts</span>
                    <button class="text-xs text-[#0071e3] hover:underline font-semibold cursor-pointer" onclick="window.TwinApp.switchPrimaryView('incidents');" type="button">Incidents →</button>
                  </div>
                </div>

                <!-- Ask Software AI Quick Box -->
                <div class="p-5 rounded-2xl bg-gradient-to-br from-[#FAF5FF] via-white to-[#F5F3FF] border border-[#DDD6FE] shadow-2xs space-y-3">
                  <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-lg bg-[#DDD6FE] text-[#6D28D9] flex items-center justify-center shrink-0">
                      <span class="material-symbols-outlined text-[20px]">neurology</span>
                    </div>
                    <div class="flex flex-col">
                      <span class="text-xs font-bold text-[#581C87]">Ask Software Intelligence</span>
                      <span class="text-[11px] text-[#7E22CE]/80">Natural-language architecture queries</span>
                    </div>
                  </div>
                  <button class="w-full py-2 px-3 rounded-xl bg-white border border-[#DDD6FE] hover:bg-[#FAF5FF] text-[#6D28D9] text-xs font-semibold shadow-2xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer" onclick="window.TwinApp.switchPrimaryView('ask');" type="button">
                    <span>Ask Twin Intelligence</span>
                    <span class="material-symbols-outlined text-[16px]">arrow_forward</span>
                  </button>
                </div>

                <!-- Live Telemetry Stream Box -->
                <div class="twin-card p-5 space-y-3 border border-[#E2E8F0]">
                  <div class="flex items-center justify-between">
                    <h4 class="text-xs font-bold text-[#0F172A] uppercase tracking-wider">Runtime Telemetry Stream</h4>
                    <button class="text-[11px] text-[#0071e3] font-semibold cursor-pointer" onclick="window.TwinApp.switchPrimaryView('runtime');" type="button">View All →</button>
                  </div>
                  <div id="ov-runtime-feed" class="space-y-2">
                    <!-- Injected by twin.js -->
                  </div>
                </div>

              </div>

            </div>

          </div>

        </section>

        <!-- ============================================================== -->
        <!-- VIEW: REPOSITORY DOCUMENTATION (DOCS)                         -->
        <!-- ============================================================== -->
        <section id="view-docs" class="content-view-panel space-y-6" style="display:none;" aria-label="Repository Documentation">
          <!-- Header Bar -->
          <div class="twin-card p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 border border-[#E2E8F0]">
            <div>
              <div class="flex items-center gap-2">
                <span class="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#0071e3] flex items-center justify-center shrink-0">
                  <span class="material-symbols-outlined text-[18px]">menu_book</span>
                </span>
                <h1 class="text-xl font-bold text-[#0F172A] tracking-tight">Repository Documentation</h1>
                <span id="docs-repo-pill" class="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">-</span>
              </div>
              <p class="text-xs text-[#64748B] mt-1.5 leading-relaxed">
                Living technical reference, system topology, primary execution flows, API contracts, and architectural components.
              </p>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="window.TwinApp.loadDocsView()" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white hover:bg-[#F8FAFC] text-[#0F172A] text-xs font-semibold shadow-2xs transition-colors cursor-pointer" type="button">
                <span class="material-symbols-outlined text-[15px] text-[#0071e3]">sync</span>
                <span>Refresh Docs</span>
              </button>
              <button onclick="window.TwinApp.switchPrimaryView('report')" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0071e3] hover:bg-[#0059b5] text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer" type="button">
                <span class="material-symbols-outlined text-[15px]">fact_check</span>
                <span>Full Audit Report</span>
              </button>
            </div>
          </div>

          <!-- Split Two-Column Layout (Matching Repowise Reference) -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            
            <!-- LEFT NAVIGATION MENU (3 cols) -->
            <div class="lg:col-span-3 twin-card p-4 space-y-4 border border-[#E2E8F0] max-h-[calc(100vh-14rem)] overflow-y-auto custom-scrollbar">
              <div class="space-y-1">
                <div class="text-[10px] uppercase font-bold text-[#94A3B8] tracking-wider px-2 py-1">Overview</div>
                <button onclick="window.TwinApp.selectDocsCategory('overview')" class="docs-nav-item active w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-semibold bg-[#EFF6FF] text-[#0071e3] transition-colors text-left cursor-pointer" data-docs-cat="overview" type="button">
                  <div class="flex items-center gap-2 truncate">
                    <span class="material-symbols-outlined text-[16px]">overview</span>
                    <span class="truncate">Repository Overview</span>
                  </div>
                  <span class="text-[10px] text-[#0071e3] font-bold">1</span>
                </button>
                <button onclick="window.TwinApp.selectDocsCategory('flows')" class="docs-nav-item w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition-colors text-left cursor-pointer" data-docs-cat="flows" type="button">
                  <div class="flex items-center gap-2 truncate">
                    <span class="material-symbols-outlined text-[16px]">alt_route</span>
                    <span class="truncate">Execution Flows</span>
                  </div>
                  <span id="docs-count-flows" class="text-[10px] text-[#94A3B8] font-mono">0</span>
                </button>
              </div>

              <div class="space-y-1 pt-2 border-t border-[#F1F5F9]">
                <div class="text-[10px] uppercase font-bold text-[#94A3B8] tracking-wider px-2 py-1">Interface &amp; API</div>
                <button onclick="window.TwinApp.selectDocsCategory('routes')" class="docs-nav-item w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition-colors text-left cursor-pointer" data-docs-cat="routes" type="button">
                  <div class="flex items-center gap-2 truncate">
                    <span class="material-symbols-outlined text-[16px]">api</span>
                    <span class="truncate">API Routes</span>
                  </div>
                  <span id="docs-count-routes" class="text-[10px] text-[#94A3B8] font-mono">0</span>
                </button>
                <button onclick="window.TwinApp.selectDocsCategory('middleware')" class="docs-nav-item w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition-colors text-left cursor-pointer" data-docs-cat="middleware" type="button">
                  <div class="flex items-center gap-2 truncate">
                    <span class="material-symbols-outlined text-[16px]">shield</span>
                    <span class="truncate">Middleware</span>
                  </div>
                  <span id="docs-count-middleware" class="text-[10px] text-[#94A3B8] font-mono">0</span>
                </button>
              </div>

              <div class="space-y-1 pt-2 border-t border-[#F1F5F9]">
                <div class="text-[10px] uppercase font-bold text-[#94A3B8] tracking-wider px-2 py-1">Application Architecture</div>
                <button onclick="window.TwinApp.selectDocsCategory('services')" class="docs-nav-item w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition-colors text-left cursor-pointer" data-docs-cat="services" type="button">
                  <div class="flex items-center gap-2 truncate">
                    <span class="material-symbols-outlined text-[16px]">dns</span>
                    <span class="truncate">Services &amp; Handlers</span>
                  </div>
                  <span id="docs-count-services" class="text-[10px] text-[#94A3B8] font-mono">0</span>
                </button>
                <button onclick="window.TwinApp.selectDocsCategory('models')" class="docs-nav-item w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition-colors text-left cursor-pointer" data-docs-cat="models" type="button">
                  <div class="flex items-center gap-2 truncate">
                    <span class="material-symbols-outlined text-[16px]">database</span>
                    <span class="truncate">Data Models &amp; DB</span>
                  </div>
                  <span id="docs-count-models" class="text-[10px] text-[#94A3B8] font-mono">0</span>
                </button>
                <button onclick="window.TwinApp.selectDocsCategory('files')" class="docs-nav-item w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition-colors text-left cursor-pointer" data-docs-cat="files" type="button">
                  <div class="flex items-center gap-2 truncate">
                    <span class="material-symbols-outlined text-[16px]">description</span>
                    <span class="truncate">Auto-documented Files</span>
                  </div>
                  <span id="docs-count-files" class="text-[10px] text-[#94A3B8] font-mono">0</span>
                </button>
              </div>
            </div>

            <!-- RIGHT CONTENT PANE (9 cols) -->
            <div class="lg:col-span-9 space-y-6">
              <!-- Content View for Selected Category (Injected dynamically) -->
              <div id="docs-category-content" class="space-y-6">
                <!-- Dynamically rendered by renderDocsCategoryContent -->
              </div>
            </div>

          </div>
        </section>

        <!-- ============================================================== -->
        <!-- VIEW: REPOSITORY ANALYSIS & HEALTH STATISTICS (STATS)           -->
        <!-- ============================================================== -->
        <section id="view-stats" class="content-view-panel space-y-6" style="display:none;" aria-label="Repository Statistics &amp; Metrics">
          <!-- Header Bar -->
          <div class="twin-card p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 border border-[#E2E8F0]">
            <div>
              <div class="flex items-center gap-2">
                <span class="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#0071e3] flex items-center justify-center shrink-0">
                  <span class="material-symbols-outlined text-[18px]">bar_chart</span>
                </span>
                <h1 class="text-xl font-bold text-[#0F172A] tracking-tight">Repository Analysis &amp; Health Statistics</h1>
                <span id="stats-repo-pill" class="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">-</span>
              </div>
              <p class="text-xs text-[#64748B] mt-1.5 leading-relaxed">
                Deterministic calculation formulas, 9-dimensional architectural scorecard, coverage of the analysis itself, and code distributions.
              </p>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="window.TwinApp.loadStatsView()" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white hover:bg-[#F8FAFC] text-[#0F172A] text-xs font-semibold shadow-2xs transition-colors cursor-pointer" type="button">
                <span class="material-symbols-outlined text-[15px] text-[#0071e3]">sync</span>
                <span>Refresh Stats</span>
              </button>
              <button onclick="window.TwinApp.switchPrimaryView('discovery')" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0071e3] hover:bg-[#0059b5] text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer" type="button">
                <span class="material-symbols-outlined text-[15px]">explore</span>
                <span>Run Discovery Assessment</span>
              </button>
            </div>
          </div>

          <!-- Top Metric Cards -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="twin-card p-4 space-y-1.5 border border-[#E2E8F0]">
              <div class="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Discovered Files</div>
              <div id="stats-file-count" class="text-2xl font-bold text-[#0F172A] font-mono">0</div>
              <div id="stats-ast-cov" class="text-[11px] text-[#059669] font-medium">0% AST Coverage</div>
            </div>
            <div class="twin-card p-4 space-y-1.5 border border-[#E2E8F0]">
              <div class="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Extracted Symbols</div>
              <div id="stats-symbol-count" class="text-2xl font-bold text-[#0F172A] font-mono">0</div>
              <div class="text-[11px] text-[#64748B]">Classes, methods, routes</div>
            </div>
            <div class="twin-card p-4 space-y-1.5 border border-[#E2E8F0]">
              <div class="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Indexed Relationships</div>
              <div id="stats-rel-count" class="text-2xl font-bold text-[#0F172A] font-mono">0</div>
              <div class="text-[11px] text-[#64748B]">Calls, imports, inheritance</div>
            </div>
            <div class="twin-card p-4 space-y-1.5 border border-[#E2E8F0]">
              <div class="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Automated Tests</div>
              <div id="stats-test-count" class="text-2xl font-bold text-[#0F172A] font-mono">0</div>
              <div id="stats-test-status" class="text-[11px] text-[#DC2626] font-semibold">UNKNOWN / NOT MEASURED</div>
            </div>
          </div>

          <!-- 9-Dimensional Architecture Scorecard with Formulas & Explanations -->
          <div class="twin-card p-6 space-y-6 border border-[#E2E8F0]">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#F1F5F9]">
              <div>
                <h2 class="text-base font-bold text-[#0F172A] tracking-tight">9-Dimensional Health Scorecard &amp; Calculation Formulas</h2>
                <p class="text-xs text-[#64748B]">Transparent, formula-backed explanations of each architectural dimension. Unknown states are clearly separated from confirmed passes.</p>
              </div>
              <span id="stats-overall-score-pill" class="px-3 py-1 rounded-full text-xs font-bold font-mono bg-[#F8FAFC] text-[#0F172A] border border-[#E2E8F0]">Overall: N/A</span>
            </div>

            <!-- Scorecard Grid (9 Dimensions) -->
            <div id="stats-scorecard-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <!-- Populated dynamically by twin.js renderStatsScorecard() -->
            </div>
          </div>

          <!-- Honest Observability & Analysis Coverage Disclosure -->
          <div class="twin-card p-6 space-y-4 border border-[#E2E8F0]">
            <h3 class="text-sm font-bold text-[#0F172A] flex items-center gap-2">
              <span class="material-symbols-outlined text-[18px] text-[#0071e3]">fact_check</span>
              <span>Analysis Coverage &amp; Uncertainty Disclosure</span>
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div class="p-4 rounded-xl bg-[#ECFDF5] border border-[#A7F3D0] space-y-1.5">
                <span class="font-bold text-[#065F46] flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-[#10B981]"></span> Confirmed Facts</span>
                <p id="stats-confirmed-desc" class="text-[#047857] text-[11px] leading-relaxed">
                  Direct AST syntactic structures, concrete function declarations, and deterministic graph edges verified in repository snapshot.
                </p>
              </div>
              <div class="p-4 rounded-xl bg-[#FEF3C7] border border-[#FDE68A] space-y-1.5">
                <span class="font-bold text-[#92400E] flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-[#F59E0B]"></span> Derived Inferences</span>
                <p id="stats-derived-desc" class="text-[#B45309] text-[11px] leading-relaxed">
                  Call chains, topological blast radius, and potential change-impact propagation calculated across knowledge graph paths.
                </p>
              </div>
              <div class="p-4 rounded-xl bg-[#FEF2F2] border border-[#FECACA] space-y-1.5">
                <span class="font-bold text-[#991B1B] flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-[#EF4444]"></span> Unknown / Not Analyzed</span>
                <p id="stats-unknown-desc" class="text-[#B91C1C] text-[11px] leading-relaxed">
                  Unlinked test coverage, dynamic imports, or uninstrumented third-party binaries. Never interpreted as proof of zero impact.
                </p>
              </div>
            </div>
          </div>
        </section>
"""

with open("backend/app/static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Replace <section id="view-overview" ...> </section> with overview_html
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

html = html[:box_start] + overview_html + "\n        " + html[box_end:]
print("Replaced view-overview and inserted view-docs and view-stats.")

# Also update Smart CI Targeter in view-tests
ci_old_pattern = r'<div id="ti-ci-quick-actions" class="bg-gradient-to-r from-\[#0F172A\] to-\[#1E293B\][\s\S]*?<!-- Explanatory Banner for Unknown Coverage -->'
ci_new_block = """<div id="ti-ci-quick-actions" class="twin-card p-5 space-y-4 rounded-2xl border border-[#E2E8F0] bg-white text-[#0F172A] shadow-xs">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <span class="inline-flex items-center justify-center w-6 h-6 rounded-lg bg-emerald-50 text-emerald-600 text-xs font-bold border border-emerald-200">⚡️</span>
                  <span class="text-xs font-bold tracking-wide uppercase text-[#0F172A]">Smart CI Targeter</span>
                  <span id="ti-roi-badge" class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">92% Faster CI</span>
                </div>
                <p id="ti-roi-desc" class="text-xs text-[#64748B]">Run only the impacted tests in local terminal or automated GitHub Actions PR workflow.</p>
              </div>

              <!-- Quick Copy Action Buttons -->
              <div class="flex items-center gap-2 shrink-0">
                <button id="btn-copy-pytest" type="button" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-[#F8FAFC] text-[#0F172A] text-xs font-semibold border border-[#CBD5E1] shadow-2xs transition-all cursor-pointer">
                  <span class="material-symbols-outlined text-[15px] text-amber-500">content_copy</span>
                  <span>Copy pytest</span>
                </button>
                <button id="btn-copy-jest" type="button" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-[#F8FAFC] text-[#0F172A] text-xs font-semibold border border-[#CBD5E1] shadow-2xs transition-all cursor-pointer">
                  <span class="material-symbols-outlined text-[15px] text-sky-500">terminal</span>
                  <span>Copy jest</span>
                </button>
                <button id="btn-copy-pr-md" type="button" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-all cursor-pointer">
                  <span class="material-symbols-outlined text-[15px]">markdown</span>
                  <span>Copy PR Sticky</span>
                </button>
              </div>
            </div>

            <!-- Savings Metrics Ribbon -->
            <div class="grid grid-cols-3 gap-2 pt-2 border-t border-[#F1F5F9] text-center">
              <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                <span class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Test Suite Skip Rate</span>
                <div id="ti-roi-skip-rate" class="text-lg font-bold text-emerald-600 mt-0.5">--%</div>
              </div>
              <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                <span class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Estimated Time Saved</span>
                <div id="ti-roi-time-saved" class="text-lg font-bold text-sky-600 mt-0.5">-- mins</div>
              </div>
              <div class="p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                <span class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Est. Runner Cost Saved</span>
                <div id="ti-roi-cost-saved" class="text-lg font-bold text-indigo-600 mt-0.5">-- USD</div>
              </div>
            </div>
          </div>

          <!-- Explanatory Banner for Unknown Coverage -->"""

ci_match = re.search(ci_old_pattern, html)
if ci_match:
    html = html[:ci_match.start()] + ci_new_block + html[ci_match.end():]
    print("Updated Smart CI Targeter styling.")
else:
    print("Notice: Smart CI Targeter pattern was already clean or not matched.")

with open("backend/app/static/index.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Saved complete updated index.html.")
