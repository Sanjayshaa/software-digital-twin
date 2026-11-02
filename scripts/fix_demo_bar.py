complete_bar = """          <!-- COMPLETE TWINCORE WORKFLOW PIPELINE ARCHITECTURE (EXPLANATION ONLY) -->
          <div id="workflow-pipeline-bar" class="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-xs transition-all">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 px-1">
              <div class="flex items-center gap-2">
                <span class="w-6 h-6 rounded-lg bg-[#EFF6FF] text-[#0071e3] flex items-center justify-center shrink-0">
                  <span class="material-symbols-outlined text-[16px]">account_tree</span>
                </span>
                <span class="text-xs font-bold text-[#0F172A] tracking-tight">TwinCore Complete Workflow Pipeline</span>
                <span class="text-[11px] text-[#64748B] hidden md:inline">— Click any stage to inspect Purpose, Input, Output, and Verifiable Evidence</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0] hidden sm:inline">8 Connected Stages</span>
                <button onclick="window.TwinApp.inspectWorkflowStage('overview')" class="text-xs text-[#0071e3] hover:underline font-semibold flex items-center gap-1 cursor-pointer shrink-0" type="button">
                  <span>Pipeline Architecture</span>
                  <span class="material-symbols-outlined text-[14px]">info</span>
                </button>
              </div>
            </div>
            <!-- 8 Pipeline Stage Buttons (Responsive 2 / 4 / 8 cols) -->
            <div class="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-2 text-center" role="navigation" aria-label="Workflow Stages">
              <button onclick="window.TwinApp.inspectWorkflowStage('repository')" class="workflow-stage-btn group p-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#EFF6FF] hover:border-[#0071e3] transition-all text-left flex flex-col justify-between" type="button" aria-label="Stage 1: Repository Ingestion">
                <div class="flex items-center justify-between">
                  <span class="text-[10px] font-mono font-bold text-[#64748B] group-hover:text-[#0071e3]">01</span>
                  <span class="w-1.5 h-1.5 rounded-full bg-[#10B981]" title="Available"></span>
                </div>
                <div class="text-[11px] font-bold text-[#0F172A] mt-1 group-hover:text-[#0071e3] truncate">Repository</div>
                <div class="text-[9px] text-[#64748B] truncate">Git Ref &amp; Sandbox</div>
              </button>

              <button onclick="window.TwinApp.inspectWorkflowStage('snapshot')" class="workflow-stage-btn group p-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#EFF6FF] hover:border-[#0071e3] transition-all text-left flex flex-col justify-between" type="button" aria-label="Stage 2: Commit Snapshot">
                <div class="flex items-center justify-between">
                  <span class="text-[10px] font-mono font-bold text-[#64748B] group-hover:text-[#0071e3]">02</span>
                  <span class="w-1.5 h-1.5 rounded-full bg-[#10B981]" title="Available"></span>
                </div>
                <div class="text-[11px] font-bold text-[#0F172A] mt-1 group-hover:text-[#0071e3] truncate">Snapshot</div>
                <div class="text-[9px] text-[#64748B] truncate">Immutable SHA</div>
              </button>

              <button onclick="window.TwinApp.inspectWorkflowStage('extraction')" class="workflow-stage-btn group p-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#EFF6FF] hover:border-[#0071e3] transition-all text-left flex flex-col justify-between" type="button" aria-label="Stage 3: Source Extraction">
                <div class="flex items-center justify-between">
                  <span class="text-[10px] font-mono font-bold text-[#64748B] group-hover:text-[#0071e3]">03</span>
                  <span class="w-1.5 h-1.5 rounded-full bg-[#10B981]" title="Available"></span>
                </div>
                <div class="text-[11px] font-bold text-[#0F172A] mt-1 group-hover:text-[#0071e3] truncate">Source Extraction</div>
                <div class="text-[9px] text-[#64748B] truncate">Tree-Sitter AST</div>
              </button>

              <button onclick="window.TwinApp.inspectWorkflowStage('graph')" class="workflow-stage-btn group p-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#EFF6FF] hover:border-[#0071e3] transition-all text-left flex flex-col justify-between" type="button" aria-label="Stage 4: Knowledge Graph">
                <div class="flex items-center justify-between">
                  <span class="text-[10px] font-mono font-bold text-[#64748B] group-hover:text-[#0071e3]">04</span>
                  <span class="w-1.5 h-1.5 rounded-full bg-[#10B981]" title="Available"></span>
                </div>
                <div class="text-[11px] font-bold text-[#0F172A] mt-1 group-hover:text-[#0071e3] truncate">Knowledge Graph</div>
                <div class="text-[9px] text-[#64748B] truncate">Multi-Layer Topology</div>
              </button>

              <button onclick="window.TwinApp.inspectWorkflowStage('impact')" class="workflow-stage-btn group p-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#EFF6FF] hover:border-[#0071e3] transition-all text-left flex flex-col justify-between" type="button" aria-label="Stage 5: Change Impact">
                <div class="flex items-center justify-between">
                  <span class="text-[10px] font-mono font-bold text-[#64748B] group-hover:text-[#0071e3]">05</span>
                  <span class="w-1.5 h-1.5 rounded-full bg-[#10B981]" title="Available"></span>
                </div>
                <div class="text-[11px] font-bold text-[#0F172A] mt-1 group-hover:text-[#0071e3] truncate">Change Impact</div>
                <div class="text-[9px] text-[#64748B] truncate">Blast Radius &amp; Risk</div>
              </button>

              <button onclick="window.TwinApp.inspectWorkflowStage('simulation')" class="workflow-stage-btn group p-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#EFF6FF] hover:border-[#0071e3] transition-all text-left flex flex-col justify-between" type="button" aria-label="Stage 6: What-If Simulation">
                <div class="flex items-center justify-between">
                  <span class="text-[10px] font-mono font-bold text-[#64748B] group-hover:text-[#0071e3]">06</span>
                  <span class="w-1.5 h-1.5 rounded-full bg-[#10B981]" title="Available"></span>
                </div>
                <div class="text-[11px] font-bold text-[#0F172A] mt-1 group-hover:text-[#0071e3] truncate">What-If Sim</div>
                <div class="text-[9px] text-[#64748B] truncate">Virtual Twin Projection</div>
              </button>

              <button onclick="window.TwinApp.inspectWorkflowStage('tests')" class="workflow-stage-btn group p-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#EFF6FF] hover:border-[#0071e3] transition-all text-left flex flex-col justify-between" type="button" aria-label="Stage 7: Test Impact">
                <div class="flex items-center justify-between">
                  <span class="text-[10px] font-mono font-bold text-[#64748B] group-hover:text-[#0071e3]">07</span>
                  <span class="w-1.5 h-1.5 rounded-full bg-[#10B981]" title="Available"></span>
                </div>
                <div class="text-[11px] font-bold text-[#0F172A] mt-1 group-hover:text-[#0071e3] truncate">Test Impact</div>
                <div class="text-[9px] text-[#64748B] truncate">Targeted Selection</div>
              </button>

              <button onclick="window.TwinApp.inspectWorkflowStage('report')" class="workflow-stage-btn group p-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-[#EFF6FF] hover:border-[#0071e3] transition-all text-left flex flex-col justify-between" type="button" aria-label="Stage 8: Evidence Report">
                <div class="flex items-center justify-between">
                  <span class="text-[10px] font-mono font-bold text-[#64748B] group-hover:text-[#0071e3]">08</span>
                  <span class="w-1.5 h-1.5 rounded-full bg-[#10B981]" title="Available"></span>
                </div>
                <div class="text-[11px] font-bold text-[#0F172A] mt-1 group-hover:text-[#0071e3] truncate">Evidence Report</div>
                <div class="text-[9px] text-[#64748B] truncate">Audit Citations &amp; PR</div>
              </button>
            </div>
          </div>
"""

with open("backend/app/static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

import re
old_fragment_pattern = r'<!-- =+ -->\s*<!-- COMPLETE TWINCORE WORKFLOW PIPELINE INDICATOR[\s\S]*?<div id="workflow-pipeline-bar"[\s\S]*?<!-- Demo Top Watermark'

match = re.search(old_fragment_pattern, html)
if match:
    html = html[:match.start()] + complete_bar + "\n\n          <!-- Demo Top Watermark" + html[match.end():]
    with open("backend/app/static/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Replaced incomplete workflow-pipeline-bar in view-demo.")
else:
    print("WARNING: Pattern not matched!")
