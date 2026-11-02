import re

with open("backend/app/static/twin.js", "r", encoding="utf-8") as f:
    js = f.read()

glance_code = """
  // =========================================================================
  // PROJECT ARCHITECTURE AT A GLANCE & SYMBOL NAVIGATION
  // =========================================================================

  function navigateToArchitectureSymbol(symbolName, location) {
    if (!symbolName) return;
    if (state.nodes && state.nodes.length > 0) {
      const match = state.nodes.find(n => n.name === symbolName || n.id === symbolName || (location && n.location === location));
      if (match) {
        switchPrimaryView('architecture');
        setTimeout(() => {
          if (typeof focusOnNode === 'function') focusOnNode(match.id);
          if (typeof inspectNode === 'function') inspectNode(match);
        }, 150);
        return;
      }
    }
    switchPrimaryView('components');
    const compSearch = document.getElementById('component-search-input');
    if (compSearch) {
      compSearch.value = symbolName;
      compSearch.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  function renderProjectArchitectureGlance(glance) {
    if (!glance) return;

    // Render 5 Architectural Boundaries Grid
    const layersGrid = document.getElementById('ov-layers-grid');
    if (layersGrid && glance.layers) {
      const boundaryKeys = ['frontend', 'api', 'services', 'storage', 'external'];
      layersGrid.innerHTML = boundaryKeys.map(k => {
        const b = glance.layers[k] || { label: k, status: 'NOT_DETECTED', count: 0, description: 'Not detected', items: [] };
        const isDetected = b.status === 'DETECTED';
        const statusBadge = isDetected
          ? '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">DETECTED</span>'
          : '<span class="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">NOT DETECTED</span>';

        return `
          <div class="p-3.5 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] space-y-2 flex flex-col justify-between">
            <div class="space-y-1">
              <div class="flex items-center justify-between gap-1">
                <span class="text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC] truncate">${escapeHtml(b.label)}</span>
              </div>
              <p class="text-[11px] text-[#64748B] dark:text-[#94A3B8] leading-relaxed">${escapeHtml(b.description || '')}</p>
            </div>
            <div class="flex items-center justify-between pt-1 border-t border-[#F8FAFC] dark:border-[#1E293B]">
              <span class="text-[11px] font-mono text-[#0071e3] font-semibold">${b.count || 0} symbols</span>
              ${statusBadge}
            </div>
          </div>
        `;
      }).join('');
    }

    // Render Execution Entry Points List
    const entryList = document.getElementById('ov-entry-points-list');
    const entryCount = document.getElementById('ov-entry-count');
    if (entryList && glance.entry_points) {
      if (entryCount) entryCount.textContent = glance.entry_points.length;
      if (glance.entry_points.length === 0) {
        entryList.innerHTML = '<div class="text-xs text-[#94A3B8] italic">No execution entry points detected.</div>';
      } else {
        entryList.innerHTML = glance.entry_points.map(ep => `
          <div class="flex items-center justify-between gap-2 py-1 border-b border-[#F8FAFC] dark:border-[#1E293B] text-xs">
            <div class="flex items-center gap-1.5 truncate">
              <span class="material-symbols-outlined text-[14px] text-[#0071e3]">arrow_right</span>
              <span onclick="window.TwinApp.navigateToArchitectureSymbol('${escapeHtml(ep.name)}', '${escapeHtml(ep.location || '')}')" class="font-mono text-[#0071e3] hover:underline cursor-pointer truncate font-semibold" title="${escapeHtml(ep.name)}">${escapeHtml(ep.name)}</span>
            </div>
            <span class="text-[10px] text-[#64748B] dark:text-[#94A3B8] shrink-0 font-medium">${escapeHtml(ep.role || '-')}</span>
          </div>
        `).join('');
      }
    }

    // Render Major Internal Modules List
    const compList = document.getElementById('ov-major-components-list');
    const compCount = document.getElementById('ov-components-count-badge');
    if (compList && glance.major_components) {
      if (compCount) compCount.textContent = glance.major_components.length;
      if (glance.major_components.length === 0) {
        compList.innerHTML = '<div class="text-xs text-[#94A3B8] italic">No project-level internal modules detected.</div>';
      } else {
        compList.innerHTML = glance.major_components.map(mc => `
          <div class="flex items-center justify-between gap-2 py-1 border-b border-[#F8FAFC] dark:border-[#1E293B] text-xs">
            <div class="flex items-center gap-1.5 truncate">
              <span class="material-symbols-outlined text-[14px] text-purple-500">deployed_code</span>
              <span onclick="window.TwinApp.navigateToArchitectureSymbol('${escapeHtml(mc.name)}', '${escapeHtml(mc.location || '')}')" class="font-mono text-[#0F172A] dark:text-[#F8FAFC] hover:text-[#0071e3] cursor-pointer truncate font-semibold" title="${escapeHtml(mc.name)}">${escapeHtml(mc.name)}</span>
            </div>
            <span class="text-[10px] font-mono text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40 px-1.5 py-0.5 rounded shrink-0">${mc.total_degree || 0} links</span>
          </div>
        `).join('');
      }
    }
  }
"""

# Insert before window.TwinApp
if "function renderProjectArchitectureGlance" not in js:
    twinapp_anchor = "  window.TwinApp = {"
    js = js.replace(twinapp_anchor, glance_code + "\n" + twinapp_anchor, 1)

# Export on window.TwinApp
twinapp_exports = """    navigateToArchitectureSymbol,
    renderProjectArchitectureGlance,
"""
if "navigateToArchitectureSymbol," not in js:
    js = js.replace("  window.TwinApp = {\n", "  window.TwinApp = {\n" + twinapp_exports, 1)

# Call in loadOverviewData
call_anchor = "      updateOverviewStateBanner(data);"
call_replace = "      updateOverviewStateBanner(data);\n      if (data.architecture_glance) renderProjectArchitectureGlance(data.architecture_glance);"
if call_anchor in js and "renderProjectArchitectureGlance(data.architecture_glance)" not in js:
    js = js.replace(call_anchor, call_replace, 1)

with open("backend/app/static/twin.js", "w", encoding="utf-8") as f:
    f.write(js)

print(f"Updated twin.js with architecture glance. Lines: {len(js.splitlines())}")

