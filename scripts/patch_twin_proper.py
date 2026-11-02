import re
import os

with open("backend/app/static/twin.js", "r", encoding="utf-8") as f:
    js = f.read()

print(f"Original lines: {len(js.splitlines())}")

# 1. Update validViews
old_vv = """    const validViews = [
      'overview', 'discovery', 'architecture', 'dependencies', 'components',
      'changes', 'impact', 'simulation', 'tests', 'incidents', 'runtime', 'evidence', 'ask', 'demo'
    ];"""

new_vv = """    const validViews = [
      'overview', 'discovery', 'architecture', 'dependencies', 'components',
      'changes', 'impact', 'simulation', 'tests', 'incidents', 'runtime', 'evidence', 'ask', 'demo',
      'report', 'docs', 'stats'
    ];"""

if old_vv in js:
    js = js.replace(old_vv, new_vv, 1)
    print("1. Updated validViews.")
else:
    print("WARNING: old_vv not found!")

# 2. Add btn-sidebar-mobile-toggle
old_toggle = """    const sidebarToggleBtn = document.getElementById('btn-sidebar-toggle');
    const sidebarCloseBtn = document.getElementById('btn-close-sidebar-mobile');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');"""

new_toggle = """    const sidebarToggleBtn = document.getElementById('btn-sidebar-toggle');
    const sidebarMobileToggleBtn = document.getElementById('btn-sidebar-mobile-toggle');
    const sidebarCloseBtn = document.getElementById('btn-close-sidebar-mobile');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');

    sidebarMobileToggleBtn?.addEventListener('click', () => {
      toggleMobileSidebar();
    });"""

if old_toggle in js:
    js = js.replace(old_toggle, new_toggle, 1)
    print("2. Added sidebarMobileToggleBtn.")
else:
    print("WARNING: old_toggle not found!")

# 3. Fix top-search-btn click listener
old_search = """    document.getElementById('top-search-btn')?.addEventListener('click', () => {
      if (!state.currentRepoId) {
        showNotification('Connect a codebase to search Twin graphs and artifacts.', 'info');
        return;
      }
      window.openCommandPalette?.();
    });"""

new_search = """    document.getElementById('top-search-btn')?.addEventListener('click', () => {
      window.openCommandPalette?.();
    });"""

if old_search in js:
    js = js.replace(old_search, new_search, 1)
    print("3. Updated top-search-btn listener.")
else:
    print("WARNING: old_search not found!")

# 4. Update switchPrimaryView
old_spv = """    // Show target view panel with safe fallback
    let targetPanel = document.getElementById(`view-${viewName}`);
    if (!targetPanel) {
      targetPanel = document.getElementById('view-overview');
      viewName = 'overview';
      state.currentPrimaryView = 'overview';
    }
    if (targetPanel) {
      targetPanel.style.display = 'block';
    }"""

new_spv = """    // Auto-close mobile drawer when navigating
    if (window.innerWidth < 1024) {
      closeMobileSidebar();
    }

    // Show target view panel with safe fallback
    let targetPanel = document.getElementById(`view-${viewName}`);
    if (!targetPanel) {
      targetPanel = document.getElementById('view-overview');
      viewName = 'overview';
      state.currentPrimaryView = 'overview';
    }
    if (targetPanel) {
      targetPanel.style.display = 'block';
    }"""

if old_spv in js:
    js = js.replace(old_spv, new_spv, 1)
    print("4. Added closeMobileSidebar in switchPrimaryView.")
else:
    print("WARNING: old_spv not found!")

# 5. Add view loaders to switchPrimaryView
old_loaders = """    } else if (viewName === 'discovery') {
      loadDiscoveryView();
    }"""

new_loaders = """    } else if (viewName === 'discovery') {
      loadDiscoveryView();
    } else if (viewName === 'report') {
      loadReportView();
    } else if (viewName === 'docs') {
      loadDocsView();
    } else if (viewName === 'stats') {
      loadStatsView();
    }"""

if old_loaders in js:
    js = js.replace(old_loaders, new_loaders, 1)
    print("5. Added loaders to switchPrimaryView.")
else:
    print("WARNING: old_loaders not found!")

# 6. Update Command Palette views
old_cp_views = """    function renderPaletteResults(query) {
      if (!results) return;
      const views = [
        { name: 'Architecture Overview', icon: 'dashboard', view: 'overview', desc: 'System metrics, active incident, and macro packages' },"""

new_cp_views = """    function renderPaletteResults(query) {
      if (!results) return;
      const views = [
        { name: 'Architecture Overview', icon: 'dashboard', view: 'overview', desc: 'System metrics, active incident, and macro architecture at a glance' },
        { name: 'Architecture Report', icon: 'description', view: 'report', desc: 'Developer-readable whole-repository report with Markdown export' },
        { name: 'Living Documentation', icon: 'menu_book', view: 'docs', desc: 'Generated repository docs, route catalog, services, and models' },
        { name: 'Repository Statistics', icon: 'query_stats', view: 'stats', desc: 'Commit timeline, work patterns, and record inventory' },"""

if old_cp_views in js:
    js = js.replace(old_cp_views, new_cp_views, 1)
    print("6. Updated views in initCommandPalette.")
else:
    print("WARNING: old_cp_views not found!")

# 7. New Methods implementation (Report, Docs, Stats)
new_methods = """
  // =========================================================================
  // VIEW: DEVELOPER ARCHITECTURE REPORT (/report)
  // =========================================================================

  function formatInlineMarkdown(text) {
    if (!text) return '';
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-blue-600 dark:text-blue-400 font-mono text-[11px]">$1</code>')
      .replace(/\\*\\*([^\\*]+)\\*\\*/g, '<strong>$1</strong>')
      .replace(/__([^_]+)__/g, '<strong>$1</strong>')
      .replace(/\\*([^\\*]+)\\*/g, '<em>$1</em>')
      .replace(/_([^_]+)_/g, '<em>$1</em>');
  }

  async function loadReportView() {
    if (!state.currentRepoId) return;
    const repoPill = document.getElementById('report-repo-pill');
    const activeRepo = state.repositories?.find(r => r.id === state.currentRepoId);
    if (repoPill) repoPill.textContent = activeRepo ? (activeRepo.name || activeRepo.id) : state.currentRepoId;

    const loadingEl = document.getElementById('report-loading-state');
    const contentEl = document.getElementById('report-content-container');
    const errorEl = document.getElementById('report-error-state');

    if (loadingEl) loadingEl.style.display = 'block';
    if (contentEl) contentEl.style.display = 'none';
    if (errorEl) errorEl.style.display = 'none';

    try {
      let url = `/repositories/${state.currentRepoId}/report`;
      if (state.currentSnapshotId) url += `?snapshot_id=${encodeURIComponent(state.currentSnapshotId)}`;

      const res = await apiFetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);

      const data = await res.json();
      state.currentReportData = data;
      renderReportContent(data);

      if (loadingEl) loadingEl.style.display = 'none';
      if (contentEl) contentEl.style.display = 'block';
    } catch (err) {
      console.error('Failed to load architecture report:', err);
      if (loadingEl) loadingEl.style.display = 'none';
      if (errorEl) {
        errorEl.style.display = 'block';
        const msgEl = document.getElementById('report-error-message');
        if (msgEl) msgEl.textContent = err.message || 'Unable to retrieve repository architecture report.';
      }
    }
  }

  function renderReportContent(data) {
    if (!data) return;

    const purposeEl = document.getElementById('report-purpose-text');
    if (purposeEl) purposeEl.textContent = data.project_purpose || 'No project description available.';

    const techBox = document.getElementById('report-tech-stack-container');
    if (techBox && data.tech_stack) {
      const langs = data.tech_stack.languages || [];
      const frameworks = data.tech_stack.frameworks || [];
      techBox.innerHTML = `
        <div class="flex flex-wrap gap-1.5">
          ${langs.map(l => `<span class="px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-50 dark:bg-blue-950/40 text-[#0071e3] border border-blue-200 dark:border-blue-900">${escapeHtml(l)}</span>`).join('')}
          ${frameworks.map(f => `<span class="px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-800 text-[#475569] dark:text-[#CBD5E1] border border-slate-200 dark:border-slate-700">${escapeHtml(f)}</span>`).join('')}
        </div>
      `;
    }

    const scale = data.size_metrics || data.scale_and_metrics || {};
    const setMetric = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = (val !== undefined && val !== null) ? Number(val).toLocaleString() : '0';
    };
    setMetric('report-metric-files', scale.total_files);
    setMetric('report-metric-loc', scale.lines_of_code);
    setMetric('report-metric-symbols', scale.total_artifacts);
    setMetric('report-metric-deps', scale.total_relationships);

    const layersContainer = document.getElementById('report-layers-container');
    if (layersContainer && data.architecture_layers) {
      layersContainer.innerHTML = data.architecture_layers.map(layer => `
        <div class="p-4 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC]">${escapeHtml(layer.layer || layer.name)}</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${layer.status === 'DETECTED' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400' : 'bg-slate-100 text-slate-500'}">${escapeHtml(layer.status || 'DETECTED')}</span>
          </div>
          <p class="text-xs text-[#64748B] dark:text-[#94A3B8] leading-relaxed">${escapeHtml(layer.description || '')}</p>
          ${layer.components && layer.components.length > 0 ? `
            <div class="flex flex-wrap gap-1 pt-1">
              ${layer.components.map(c => `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">${escapeHtml(c)}</span>`).join('')}
            </div>
          ` : ''}
        </div>
      `).join('');
    }

    const filesTbody = document.getElementById('report-files-tbody');
    if (filesTbody && data.important_files) {
      filesTbody.innerHTML = data.important_files.map(f => `
        <tr class="hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B]/50 transition-colors">
          <td class="px-3.5 py-2.5 font-mono text-xs text-[#0071e3] font-medium">${escapeHtml(f.path)}</td>
          <td class="px-3.5 py-2.5 text-xs text-[#475569] dark:text-[#CBD5E1]">${escapeHtml(f.role || f.responsibility || '-')}</td>
          <td class="px-3.5 py-2.5 font-mono text-xs text-right text-[#64748B]">${escapeHtml(f.symbol_count || f.symbols_count || 0)}</td>
        </tr>
      `).join('');
    }

    const depsTbody = document.getElementById('report-deps-tbody');
    const keyDeps = data.key_dependencies || data.relationships_summary?.key_dependencies || [];
    if (depsTbody) {
      if (keyDeps.length === 0) {
        depsTbody.innerHTML = '<tr><td colspan="4" class="px-4 py-3 text-center text-xs text-[#94A3B8]">No cross-module dependency relationships detected.</td></tr>';
      } else {
        depsTbody.innerHTML = keyDeps.map(d => `
          <tr class="hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B]/50 transition-colors">
            <td class="px-3.5 py-2.5 font-mono text-xs text-[#0F172A] dark:text-[#F8FAFC] font-semibold">${escapeHtml(d.source)}</td>
            <td class="px-3.5 py-2.5 text-center"><span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-50 dark:bg-blue-950/40 text-[#0071e3]">${escapeHtml(d.relation)}</span></td>
            <td class="px-3.5 py-2.5 font-mono text-xs text-[#0F172A] dark:text-[#F8FAFC] font-semibold">${escapeHtml(d.target)}</td>
            <td class="px-3.5 py-2.5 text-xs text-[#64748B] dark:text-[#94A3B8]">${escapeHtml(d.description || '-')}</td>
          </tr>
        `).join('');
      }
    }

    const dbGrid = document.getElementById('report-db-grid');
    if (dbGrid && data.database_entities) {
      if (data.database_entities.length === 0) {
        dbGrid.innerHTML = '<div class="col-span-full p-4 text-center text-xs text-[#94A3B8]">No persistent database entities or schemas detected.</div>';
      } else {
        dbGrid.innerHTML = data.database_entities.map(db => `
          <div class="p-3.5 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] space-y-1.5">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[16px] text-amber-500">database</span>
              <span class="font-mono text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC]">${escapeHtml(db.name)}</span>
            </div>
            ${db.fields && db.fields.length > 0 ? `
              <div class="text-[11px] text-[#64748B] dark:text-[#94A3B8] font-mono truncate">${db.fields.slice(0, 5).join(', ')}${db.fields.length > 5 ? '...' : ''}</div>
            ` : ''}
          </div>
        `).join('');
      }
    }

    const limitsContainer = document.getElementById('report-limitations-container');
    const limits = data.limitations || data.limitations_and_coverage || [];
    if (limitsContainer) {
      limitsContainer.innerHTML = limits.map(l => `
        <li class="flex items-start gap-2 text-xs text-[#475569] dark:text-[#CBD5E1]">
          <span class="material-symbols-outlined text-[16px] text-amber-500 shrink-0 mt-0.5">info</span>
          <span>${formatInlineMarkdown(l)}</span>
        </li>
      `).join('');
    }
  }

  function copyReportMarkdown() {
    const md = state.currentReportData?.report_markdown;
    if (!md) {
      showNotification('No report available to copy.', 'warning');
      return;
    }
    navigator.clipboard.writeText(md).then(() => {
      showNotification('Report Markdown copied to clipboard!', 'success');
      const textSpan = document.getElementById('btn-copy-report-text');
      if (textSpan) {
        textSpan.textContent = 'Copied!';
        setTimeout(() => { textSpan.textContent = 'Copy Markdown'; }, 2000);
      }
    }).catch(err => {
      console.error('Clipboard copy error:', err);
      showNotification('Could not copy report to clipboard.', 'error');
    });
  }

  function downloadReportMarkdown() {
    const md = state.currentReportData?.report_markdown;
    if (!md) {
      showNotification('No report available to download.', 'warning');
      return;
    }
    const repoName = state.currentReportData?.repository?.name || state.currentRepoId || 'repository';
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${repoName}-architecture-report.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showNotification('Report downloaded successfully.', 'success');
  }

  // =========================================================================
  // VIEW: REPOSITORY DOCUMENTATION (DOCS)
  // =========================================================================

  async function loadDocsView() {
    if (!state.currentRepoId) return;
    const repoPill = document.getElementById('docs-repo-pill');
    const activeRepo = state.repositories?.find(r => r.id === state.currentRepoId);
    if (repoPill) repoPill.textContent = activeRepo ? (activeRepo.name || activeRepo.id) : state.currentRepoId;

    try {
      let url = `/repositories/${state.currentRepoId}/docs`;
      if (state.currentSnapshotId) url += `?snapshot_id=${encodeURIComponent(state.currentSnapshotId)}`;

      const res = await apiFetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);

      const data = await res.json();
      state.currentDocsData = data;

      const foldersCount = (data.folder_guide || []).length;
      const flowsCount = (data.startup_flows || []).length;
      const routesCount = (data.routes_and_apis || []).length;
      const servicesCount = (data.services_and_logic || []).length;
      const modelsCount = (data.database_structures || []).length;

      const setBadge = (id, count) => {
        const el = document.getElementById(id);
        if (el) el.textContent = count;
      };
      setBadge('docs-count-folders', foldersCount);
      setBadge('docs-count-flows', flowsCount);
      setBadge('docs-count-routes', routesCount);
      setBadge('docs-count-services', servicesCount);
      setBadge('docs-count-models', modelsCount);

      selectDocsCategory(state.currentDocsCategory || 'overview');
    } catch (err) {
      console.error('Failed to load documentation view:', err);
    }
  }

  function selectDocsCategory(category) {
    state.currentDocsCategory = category;
    document.querySelectorAll('.docs-nav-item').forEach(btn => {
      const isActive = btn.dataset.docsCat === category;
      btn.classList.toggle('active', isActive);
      if (isActive) {
        btn.className = 'docs-nav-item active w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-semibold bg-[#EFF6FF] dark:bg-[#1E293B] text-[#0071e3] transition-colors text-left cursor-pointer';
      } else {
        btn.className = 'docs-nav-item w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B] transition-colors text-left cursor-pointer';
      }
    });

    renderDocsCategoryContent(category);
  }

  function renderDocsCategoryContent(category) {
    const titleEl = document.getElementById('docs-category-title');
    const descEl = document.getElementById('docs-category-desc');
    const contentEl = document.getElementById('docs-category-content');
    const data = state.currentDocsData;
    if (!contentEl) return;

    if (!data) {
      contentEl.innerHTML = '<div class="p-8 text-center text-xs text-[#94A3B8]">Documentation is currently being generated...</div>';
      return;
    }

    if (category === 'overview') {
      if (titleEl) titleEl.textContent = 'Project Purpose & Architectural Scope';
      if (descEl) descEl.textContent = 'High-level business function, domain responsibilities, and system scope.';
      contentEl.innerHTML = `
        <div class="space-y-4">
          <div class="p-4 rounded-xl bg-[#F8FAFC] dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B]">
            <h4 class="text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC] mb-2">Application Purpose</h4>
            <p class="text-xs text-[#475569] dark:text-[#CBD5E1] leading-relaxed">${escapeHtml(data.project_purpose || 'No project description available.')}</p>
          </div>
          ${data.inferred_notes && data.inferred_notes.length > 0 ? `
            <div class="p-4 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 space-y-2">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200">INFERRED ARCHITECTURE</span>
                <span class="text-xs font-bold text-amber-900 dark:text-amber-300">Algorithmic Design Notes</span>
              </div>
              <ul class="space-y-1 text-xs text-amber-800 dark:text-amber-200/90 list-disc list-inside">
                ${data.inferred_notes.map(n => `<li>${formatInlineMarkdown(n)}</li>`).join('')}
              </ul>
            </div>
          ` : ''}
        </div>
      `;
    } else if (category === 'folders') {
      if (titleEl) titleEl.textContent = 'Folder & Module Directory Guide';
      if (descEl) descEl.textContent = 'Structural module boundaries and code layout responsibilities.';
      const items = data.folder_guide || [];
      contentEl.innerHTML = `
        <div class="space-y-3">
          ${items.map(f => `
            <div class="p-3.5 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] flex items-start justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-[16px] text-blue-500">folder</span>
                  <span class="font-mono text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC]">${escapeHtml(f.path)}</span>
                </div>
                <p class="text-xs text-[#64748B] dark:text-[#94A3B8] leading-relaxed">${escapeHtml(f.role)}</p>
              </div>
              <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 shrink-0">${f.file_count} files</span>
            </div>
          `).join('')}
        </div>
      `;
    } else if (category === 'startup') {
      if (titleEl) titleEl.textContent = 'System Execution Startup Flows';
      if (descEl) descEl.textContent = 'Documented step-by-step entry points, boot sequences, and initialization paths.';
      const flows = data.startup_flows || [];
      contentEl.innerHTML = `
        <div class="space-y-4">
          ${flows.map((fl, idx) => `
            <div class="p-4 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] space-y-3">
              <div class="flex items-center justify-between pb-2 border-b border-[#F1F5F9] dark:border-[#1E293B]">
                <div class="flex items-center gap-2">
                  <span class="w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-950 text-[#0071e3] text-xs font-bold flex items-center justify-center">${idx + 1}</span>
                  <span class="font-bold text-xs text-[#0F172A] dark:text-[#F8FAFC]">${escapeHtml(fl.role || fl.entry_point)}</span>
                </div>
                <span class="font-mono text-[11px] text-[#0071e3]">${escapeHtml(fl.location || fl.entry_point)}</span>
              </div>
              <ol class="space-y-2 text-xs text-[#475569] dark:text-[#CBD5E1]">
                ${(fl.steps || []).map((step, sidx) => `
                  <li class="flex items-start gap-2">
                    <span class="text-[#94A3B8] font-mono text-[10px] mt-0.5">${sidx + 1}.</span>
                    <span>${formatInlineMarkdown(step)}</span>
                  </li>
                `).join('')}
              </ol>
            </div>
          `).join('')}
        </div>
      `;
    } else if (category === 'routes') {
      if (titleEl) titleEl.textContent = 'API Routes & Endpoints Catalog';
      if (descEl) descEl.textContent = 'Documented HTTP routing contracts, path methods, and ingress endpoints.';
      const routes = data.routes_and_apis || [];
      contentEl.innerHTML = `
        <div class="space-y-2.5">
          ${routes.map(r => `
            <div class="p-3.5 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] flex items-center justify-between gap-4">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold ${r.method === 'GET' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400' : (r.method === 'POST' ? 'bg-blue-50 text-[#0071e3] dark:bg-blue-950/40' : 'bg-amber-50 text-amber-700')}">${escapeHtml(r.method || 'GET')}</span>
                  <span class="font-mono text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC]">${escapeHtml(r.path || r.name)}</span>
                </div>
                <p class="text-xs text-[#64748B] dark:text-[#94A3B8]">${escapeHtml(r.role || 'API Ingress Route')}</p>
              </div>
              <span class="font-mono text-[11px] text-[#64748B] dark:text-[#94A3B8] shrink-0">${escapeHtml(r.location || '')}</span>
            </div>
          `).join('')}
        </div>
      `;
    } else if (category === 'services') {
      if (titleEl) titleEl.textContent = 'Core Domain Services & Handlers';
      if (descEl) descEl.textContent = 'Encapsulated business logic units and domain service orchestrators.';
      const svcs = data.services_and_logic || [];
      contentEl.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          ${svcs.map(s => `
            <div class="p-3.5 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-[#0F172A] dark:text-[#F8FAFC]">${escapeHtml(s.name)}</span>
                <span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300">${escapeHtml(s.type || 'SERVICE')}</span>
              </div>
              <p class="text-xs text-[#64748B] dark:text-[#94A3B8] leading-relaxed">${escapeHtml(s.role || '')}</p>
              <div class="font-mono text-[10px] text-[#94A3B8] truncate pt-1 border-t border-[#F8FAFC] dark:border-[#1E293B]">${escapeHtml(s.location || s.qualified_name || '')}</div>
            </div>
          `).join('')}
        </div>
      `;
    } else if (category === 'models') {
      if (titleEl) titleEl.textContent = 'Database Structures & Schemas';
      if (descEl) descEl.textContent = 'Database entities, tables, and relational data representations.';
      const models = data.database_structures || [];
      contentEl.innerHTML = `
        <div class="space-y-3">
          ${models.map(m => `
            <div class="p-3.5 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-[16px] text-amber-500">database</span>
                  <span class="font-mono text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC]">${escapeHtml(m.name)}</span>
                </div>
                <span class="font-mono text-[10px] text-[#64748B]">${escapeHtml(m.location || '')}</span>
              </div>
              <p class="text-xs text-[#64748B] dark:text-[#94A3B8]">${escapeHtml(m.role || 'Data Persistence Schema')}</p>
              ${m.fields && m.fields.length > 0 ? `
                <div class="flex flex-wrap gap-1 pt-1 border-t border-[#F8FAFC] dark:border-[#1E293B]">
                  ${m.fields.map(f => `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">${escapeHtml(f)}</span>`).join('')}
                </div>
              ` : ''}
            </div>
          `).join('')}
        </div>
      `;
    } else if (category === 'config') {
      if (titleEl) titleEl.textContent = 'Configuration & Environment Settings';
      if (descEl) descEl.textContent = 'Environment variables, manifests, and runtime settings.';
      const configs = data.config_and_env || [];
      contentEl.innerHTML = `
        <div class="space-y-2">
          ${configs.map(c => `
            <div class="p-3 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] flex items-center justify-between gap-4">
              <span class="font-mono text-xs font-bold text-[#0071e3]">${escapeHtml(c.key || c.name)}</span>
              <span class="text-xs text-[#64748B] dark:text-[#94A3B8] text-right">${escapeHtml(c.description || c.role || '-')}</span>
            </div>
          `).join('')}
        </div>
      `;
    }
  }

  // =========================================================================
  // VIEW: REPOSITORY EVIDENCE & STATS (/stats)
  // =========================================================================

  async function loadStatsView() {
    if (!state.currentRepoId) return;
    const repoPill = document.getElementById('stats-repo-pill');
    const activeRepo = state.repositories?.find(r => r.id === state.currentRepoId);
    if (repoPill) repoPill.textContent = activeRepo ? (activeRepo.name || activeRepo.id) : state.currentRepoId;

    try {
      let url = `/repositories/${state.currentRepoId}/stats`;
      if (state.currentSnapshotId) url += `?snapshot_id=${encodeURIComponent(state.currentSnapshotId)}`;

      const res = await apiFetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);

      const data = await res.json();
      state.currentStatsData = data;
      renderStatsContent(data);
    } catch (err) {
      console.error('Failed to load stats view:', err);
    }
  }

  function renderStatsContent(data) {
    if (!data) return;

    const size = data.size_and_composition || {};
    const setStat = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = (val !== undefined && val !== null) ? Number(val).toLocaleString() : '0';
    };
    setStat('stats-file-count', size.total_files);
    setStat('stats-symbol-count', size.total_artifacts);
    setStat('stats-rel-count', size.total_relationships);

    const linesEl = document.getElementById('stats-lines-count');
    if (linesEl) linesEl.textContent = `${(size.lines_of_code || 0).toLocaleString()} lines of code`;

    const densityEl = document.getElementById('stats-density');
    if (densityEl) densityEl.textContent = `${(size.average_coupling || 0).toFixed(2)} avg coupling`;

    const tl = data.timeline || {};
    setStat('stats-commits-count', tl.total_commits_indexed || 0);

    const spanEl = document.getElementById('stats-history-span');
    if (spanEl) spanEl.textContent = `${tl.history_span_days || 0} days history span`;

    const spanBadge = document.getElementById('stats-timeline-span-badge');
    if (spanBadge) spanBadge.textContent = `${tl.history_span_days || 0} Days Span`;

    const earliestDate = document.getElementById('stats-earliest-date');
    if (earliestDate) earliestDate.textContent = tl.earliest_commit_date || 'Unknown';

    const earliestAuthor = document.getElementById('stats-earliest-author');
    if (earliestAuthor) earliestAuthor.textContent = `${tl.earliest_commit_author || 'Unknown'} · ${tl.earliest_commit_hash || ''}`;

    const latestDate = document.getElementById('stats-latest-date');
    if (latestDate) latestDate.textContent = tl.latest_commit_date || 'Unknown';

    const latestHash = document.getElementById('stats-latest-hash');
    if (latestHash) latestHash.textContent = `commit ${tl.latest_commit_hash || 'HEAD'}`;

    const activityBox = document.getElementById('stats-activity-container');
    if (activityBox && tl.activity_by_month) {
      const entries = Object.entries(tl.activity_by_month);
      const maxCount = Math.max(...entries.map(([, c]) => c), 1);
      activityBox.innerHTML = `
        <div class="flex items-end gap-1.5 h-16 pt-2">
          ${entries.map(([m, c]) => {
            const h = Math.round((c / maxCount) * 100);
            return `
              <div class="flex-1 flex flex-col items-center gap-1 group relative">
                <div class="w-full bg-blue-500 hover:bg-blue-600 rounded-t transition-all" style="height: ${Math.max(h, 8)}%;"></div>
                <span class="text-[9px] text-[#94A3B8] font-mono truncate w-full text-center">${m.slice(5)}</span>
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    const wp = data.work_patterns || {};
    const rangeLabel = document.getElementById('stats-timerange-label');
    if (rangeLabel) rangeLabel.textContent = wp.time_range_label || 'Calculated from indexed Git commit history.';

    const dowBox = document.getElementById('stats-dow-container');
    if (dowBox && wp.commits_by_day_of_week) {
      const dows = Object.entries(wp.commits_by_day_of_week);
      const maxDow = Math.max(...dows.map(([, c]) => c), 1);
      dowBox.innerHTML = dows.map(([day, c]) => {
        const pct = Math.round((c / maxDow) * 100);
        return `
          <div class="p-2 rounded-lg bg-[#F8FAFC] dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] space-y-1">
            <span class="text-[10px] font-bold text-[#64748B] dark:text-[#94A3B8]">${day}</span>
            <div class="text-xs font-mono font-bold text-[#0F172A] dark:text-[#F8FAFC]">${c}</div>
            <div class="w-full bg-[#E2E8F0] dark:bg-[#1E293B] h-1 rounded-full overflow-hidden">
              <div class="bg-[#0071e3] h-1 rounded-full" style="width: ${pct}%;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    const hodBox = document.getElementById('stats-hod-container');
    if (hodBox && wp.commits_by_hour_of_day) {
      const hods = Object.entries(wp.commits_by_hour_of_day);
      const maxHod = Math.max(...hods.map(([, c]) => c), 1);
      hodBox.innerHTML = hods.map(([hRange, c]) => {
        const pct = Math.round((c / maxHod) * 100);
        return `
          <div class="p-2 rounded-lg bg-[#F8FAFC] dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] space-y-1">
            <span class="text-[10px] font-bold text-[#64748B] dark:text-[#94A3B8]">${hRange}</span>
            <div class="text-xs font-mono font-bold text-[#0F172A] dark:text-[#F8FAFC]">${c}</div>
            <div class="w-full bg-[#E2E8F0] dark:bg-[#1E293B] h-1 rounded-full overflow-hidden">
              <div class="bg-indigo-500 h-1 rounded-full" style="width: ${pct}%;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    const langsBox = document.getElementById('stats-languages-container');
    if (langsBox && size.languages_breakdown) {
      langsBox.innerHTML = size.languages_breakdown.map(l => `
        <div class="space-y-1">
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-[#0F172A] dark:text-[#F8FAFC]">${escapeHtml(l.language)}</span>
            <span class="font-mono text-[#64748B] dark:text-[#94A3B8]">${l.percentage}% (${l.symbol_count} symbols)</span>
          </div>
          <div class="w-full bg-[#E2E8F0] dark:bg-[#1E293B] h-1.5 rounded-full overflow-hidden">
            <div class="bg-[#0071e3] h-1.5 rounded-full" style="width: ${l.percentage}%;"></div>
          </div>
        </div>
      `).join('');
    }

    const rec = data.project_records || {};
    const recordsGrid = document.getElementById('stats-records-grid');
    if (recordsGrid) {
      const tiles = [
        { label: 'API Routes', val: rec.routes_detected || 0, icon: 'api' },
        { label: 'Database Entities', val: rec.database_entities_detected || 0, icon: 'database' },
        { label: 'Services & Classes', val: rec.services_and_classes || 0, icon: 'dns' },
        { label: 'Tests Linked', val: rec.tests_linked || 0, icon: 'science' },
        { label: 'Incidents Indexed', val: rec.incidents_declared || 0, icon: 'troubleshoot' },
      ];
      recordsGrid.innerHTML = tiles.map(t => `
        <div class="p-3 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] text-center space-y-1">
          <span class="material-symbols-outlined text-[18px] text-[#0071e3]">${t.icon}</span>
          <div class="text-lg font-bold font-mono text-[#0F172A] dark:text-[#F8FAFC]">${t.val}</div>
          <div class="text-[10px] text-[#64748B] dark:text-[#94A3B8]">${t.label}</div>
        </div>
      `).join('');
    }

    const cov = data.analysis_coverage || {};
    const covBadge = document.getElementById('stats-coverage-badge');
    if (covBadge) covBadge.textContent = `${cov.coverage_percentage || 100}% AST Coverage`;

    const covGrid = document.getElementById('stats-coverage-grid');
    if (covGrid) {
      covGrid.innerHTML = `
        <div class="p-3 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#0F172A] space-y-1">
          <span class="text-[10px] uppercase font-bold text-[#64748B] dark:text-[#94A3B8]">Analyzed Files</span>
          <div class="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400">${cov.files_analyzed || 0} / ${cov.files_total || 0}</div>
        </div>
        <div class="p-3 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#0F172A] space-y-1">
          <span class="text-[10px] uppercase font-bold text-[#64748B] dark:text-[#94A3B8]">AST Parsing Success</span>
          <div class="text-base font-bold font-mono text-[#0071e3]">${cov.ast_parse_success_rate || 100}%</div>
        </div>
        <div class="p-3 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#0F172A] space-y-1">
          <span class="text-[10px] uppercase font-bold text-[#64748B] dark:text-[#94A3B8]">Analysis Engine</span>
          <div class="text-xs font-semibold text-[#0F172A] dark:text-[#F8FAFC] truncate">Tree-Sitter Polyglot AST</div>
        </div>
      `;
    }
  }
"""

# Insert new methods right before "  window.TwinApp = {"
old_twinapp = "  window.TwinApp = {"
if old_twinapp in js:
    js = js.replace(old_twinapp, new_methods + "\n" + old_twinapp, 1)
    print("7. Inserted new view methods before window.TwinApp.")
else:
    print("WARNING: old_twinapp not found!")

# 8. Expose new methods on window.TwinApp
exports = """    loadReportView,
    copyReportMarkdown,
    downloadReportMarkdown,
    loadDocsView,
    selectDocsCategory,
    loadStatsView,
"""

if old_twinapp in js:
    js = js.replace(old_twinapp, old_twinapp + "\n" + exports, 1)
    print("8. Exposed new methods on window.TwinApp.")

# Write back
with open("backend/app/static/twin.js", "w", encoding="utf-8") as f:
    f.write(js)

print(f"Patched twin.js saved! New lines: {len(js.splitlines())}")
assert js.endswith("})();\n") or js.endswith("})();"), "Error: File must end with IIFE closure ();"
print("SUCCESS: Full twin.js integrity verified.")

