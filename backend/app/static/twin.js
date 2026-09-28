/**
 * Digital Twin — Software Architecture & Structural Intelligence Platform
 * Product Frontend Engine: Overview, Architecture Graph Workspace, Components,
 * APIs, Processes, Dependencies, Tests, Snapshot Diff, Evidence, and Onboarding.
 */

(function () {
  'use strict';

  // Global State
  const state = {
    repositories: [],
    currentRepoId: null,
    currentRepoData: null,
    snapshots: [],
    currentSnapshotId: null,
    diffSnapshotId: null,

    currentPrimaryView: 'overview',
    currentArchSubtab: 'graph',
    currentLevel: 2,
    depth: 2,
    focusNodeId: null,
    selectedNodeId: null,
    selectedEdgeId: null,
    impactMode: false,
    impactRootId: null,

    // Graph Data
    rawGraph: { nodes: [], edges: [], summary: {} },
    nodes: [],
    edges: [],
    nodeMap: new Map(),
    adjList: new Map(),

    // Components cache
    componentsList: [],

    // Physics & Canvas
    canvas: null,
    ctx: null,
    width: 0,
    height: 0,
    dpr: window.devicePixelRatio || 1,
    transform: { x: 0, y: 0, k: 1 },
    isDraggingCanvas: false,
    dragStart: { x: 0, y: 0 },
    draggedNode: null,
    physicsEnabled: true,
    animFrameId: null,

    // Colors
    colors: {
      CLASS: '#38bdf8',
      METHOD: '#818cf8',
      FUNCTION: '#818cf8',
      MODULE: '#34d399',
      PACKAGE: '#2dd4bf',
      DIRECTORY: '#14b8a6',
      API_ENDPOINT: '#f472b6',
      SERVICE: '#a78bfa',
      TEST_CASE: '#fbbf24',
      TEST_SUITE: '#f59e0b',
      DATABASE_TABLE: '#fb923c',
      DATABASE: '#ea580c',
      EXTERNAL_DEPENDENCY: '#64748b',
      DEFAULT: '#94a3b8',
      DRIFT: '#ef4444',
      IMPACT: '#f59e0b',
    },
  };

  // --- Initializer ---
  window.addEventListener('DOMContentLoaded', () => {
    initCanvas();
    initNavigation();
    initModal();
    initCommandPalette();
    initAskSoftware();
    initEventListeners();
    initPhase5Handlers();
    fetchRepositories();
  });

  function initCanvas() {
    state.canvas = document.getElementById('twin-canvas');
    if (!state.canvas) return;
    state.ctx = state.canvas.getContext('2d');
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
  }

  function resizeCanvas() {
    if (!state.canvas) return;
    const parent = state.canvas.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    state.width = rect.width;
    state.height = rect.height;
    state.canvas.width = state.width * state.dpr;
    state.canvas.height = state.height * state.dpr;
    state.ctx.scale(state.dpr, state.dpr);
    if (!state.transform.x && !state.transform.y) {
      state.transform.x = state.width / 2;
      state.transform.y = state.height / 2;
    }
  }

  // --- 1. Navigation & View Switching ---
  function initNavigation() {
    // Primary View Tabs across sidebar and panels
    const tabs = document.querySelectorAll('.view-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const view = tab.dataset.view;
        switchPrimaryView(view);
      });
    });

    // Architecture Sub-Tabs
    const subtabs = document.querySelectorAll('.sub-tab');
    subtabs.forEach(st => {
      st.addEventListener('click', () => {
        const subtab = st.dataset.subtab;
        switchArchSubtab(subtab);
      });
    });

    // Overview Hero & Action Buttons
    document.getElementById('ov-btn-view-graph')?.addEventListener('click', () => {
      switchPrimaryView('architecture');
      switchArchSubtab('graph');
    });

    document.getElementById('ov-btn-explore')?.addEventListener('click', () => {
      switchPrimaryView('components');
    });

    document.getElementById('ov-btn-analyze')?.addEventListener('click', () => {
      switchPrimaryView('impact');
    });

    // Header Quick Action & Sidebar Buttons
    document.getElementById('top-btn-connect-repo')?.addEventListener('click', openConnectModal);
    document.getElementById('sidebar-repo-card')?.addEventListener('click', openConnectModal);
    document.getElementById('top-btn-ingest-runtime')?.addEventListener('click', openIngestModal);
    document.getElementById('top-btn-create-incident')?.addEventListener('click', openCreateIncidentModal);
    document.getElementById('top-search-btn')?.addEventListener('click', () => window.openCommandPalette?.());

    // Theme toggle
    document.getElementById('btn-toggle-theme')?.addEventListener('click', () => {
      document.body.classList.toggle('theme-light');
    });

    // Level Selector
    document.querySelectorAll('.level-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.level-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.currentLevel = parseInt(btn.dataset.level, 10);
        loadGraph();
      });
    });

    // Neighborhood Depth Slider
    const depthRange = document.getElementById('depth-range');
    if (depthRange) {
      depthRange.addEventListener('input', (e) => {
        state.depth = parseInt(e.target.value, 10);
        const depthDisplay = document.getElementById('depth-display');
        if (depthDisplay) depthDisplay.textContent = state.depth;
      });
      depthRange.addEventListener('change', () => loadGraph());
    }

    // Sidebar Tabs inside Architecture Graph
    document.querySelectorAll('.sb-tab').forEach(btn => {
      btn.addEventListener('click', () => switchSidebarTab(btn.dataset.sbTab));
    });

    // Repo and Snapshot Selectors in Header
    const repoSelect = document.getElementById('repo-select');
    if (repoSelect) {
      repoSelect.addEventListener('change', (e) => {
        state.currentRepoId = e.target.value;
        loadSnapshotsForRepo(state.currentRepoId);
      });
    }

    const snapSelect = document.getElementById('snapshot-select');
    if (snapSelect) {
      snapSelect.addEventListener('change', (e) => {
        state.currentSnapshotId = e.target.value;
        refreshActiveView();
      });
    }

    // Re-analyze action button
    const reanalyzeBtn = document.getElementById('btn-reanalyze');
    if (reanalyzeBtn) {
      reanalyzeBtn.addEventListener('click', () => {
        if (!state.currentRepoId) return;
        const activeRepo = state.repositories.find(r => r.id === state.currentRepoId);
        if (activeRepo && activeRepo.local_path) {
          triggerOnboarding(activeRepo.local_path, activeRepo.name);
        } else {
          openConnectModal();
        }
      });
    }
  }

  function switchPrimaryView(viewName) {
    state.currentPrimaryView = viewName;
    document.querySelectorAll('.view-tab').forEach(t => {
      const isTarget = t.dataset.view === viewName;
      t.classList.toggle('active', isTarget);
      if (isTarget) {
        t.className = 'view-tab active w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] text-white shadow-xs transition-all';
      } else {
        t.className = 'view-tab w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-all';
      }
    });

    // Hide all view panels
    document.querySelectorAll('.content-view-panel').forEach(p => {
      p.style.display = 'none';
    });

    // If no repo selected, show no-repo hero
    if (!state.currentRepoId && state.repositories.length === 0) {
      const noRepoView = document.getElementById('view-no-repo');
      if (noRepoView) noRepoView.style.display = 'block';
      return;
    }

    // Show target view panel
    const targetPanel = document.getElementById(`view-${viewName}`);
    if (targetPanel) {
      targetPanel.style.display = 'block';
    }

    // Execute view-specific loaders
    if (viewName === 'overview') {
      loadOverviewData();
    } else if (viewName === 'components') {
      loadComponentsData();
    } else if (viewName === 'architecture') {
      switchArchSubtab(state.currentArchSubtab || 'graph');
    } else if (viewName === 'processes') {
      loadProcessesView();
    } else if (viewName === 'dependencies') {
      loadDependenciesView();
    } else if (viewName === 'tests') {
      loadTestsView();
    } else if (viewName === 'changes') {
      loadChangesView();
    } else if (viewName === 'impact') {
      loadChangesView();
      executeChangeImpactAnalysis();
    } else if (viewName === 'evidence') {
      loadEvidenceView();
    } else if (viewName === 'runtime') {
      loadRuntimeView();
    } else if (viewName === 'incidents') {
      loadIncidentsView();
    } else if (viewName === 'ask') {
      setTimeout(() => document.getElementById('ask-query-input')?.focus(), 50);
    }
  }

  function switchArchSubtab(subtabName) {
    state.currentArchSubtab = subtabName;
    document.querySelectorAll('.sub-tab').forEach(st => {
      st.classList.toggle('active', st.dataset.subtab === subtabName);
    });

    document.querySelectorAll('.subview-panel').forEach(sp => {
      sp.style.display = 'none';
    });

    const activeSubpanel = document.getElementById(`subview-arch-${subtabName}`);
    if (activeSubpanel) {
      activeSubpanel.style.display = subtabName === 'graph' ? 'flex' : 'block';
    }

    if (subtabName === 'graph') {
      setTimeout(() => {
        resizeCanvas();
        loadGraph();
      }, 50);
    } else if (subtabName === 'components') {
      loadComponentsData();
    } else if (subtabName === 'apis') {
      loadApisData();
    } else if (subtabName === 'drift') {
      loadDriftData();
    }
  }

  function refreshActiveView() {
    if (state.currentPrimaryView === 'overview') {
      loadOverviewData();
    } else if (state.currentPrimaryView === 'architecture') {
      if (state.currentArchSubtab === 'graph') {
        loadGraph();
        loadFileTree();
      } else if (state.currentArchSubtab === 'components') {
        loadComponentsData();
      } else if (state.currentArchSubtab === 'apis') {
        loadApisData();
      } else if (state.currentArchSubtab === 'drift') {
        loadDriftData();
      }
    } else if (state.currentPrimaryView === 'processes') {
      loadProcessesView();
    } else if (state.currentPrimaryView === 'dependencies') {
      loadDependenciesView();
    } else if (state.currentPrimaryView === 'tests') {
      loadTestsView();
    } else if (state.currentPrimaryView === 'changes') {
      loadChangesView();
    } else if (state.currentPrimaryView === 'evidence') {
      loadEvidenceView();
    } else if (state.currentPrimaryView === 'runtime') {
      loadRuntimeView();
    } else if (state.currentPrimaryView === 'incidents') {
      loadIncidentsView();
    }
  }

  // --- 2. Onboarding Modal & Local Ingestion Workflow ---
  function initModal() {
    const modal = document.getElementById('modal-onboard');
    const openBtn = document.getElementById('btn-open-connect-modal');
    const heroBtn = document.getElementById('hero-btn-connect-local');
    const closeBtn = document.getElementById('modal-close-btn');
    const cancelBtn = document.getElementById('modal-cancel-btn');
    const submitBtn = document.getElementById('modal-submit-btn');

    if (openBtn) openBtn.addEventListener('click', openConnectModal);
    if (heroBtn) heroBtn.addEventListener('click', openConnectModal);
    if (closeBtn) closeBtn.addEventListener('click', closeConnectModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeConnectModal);

    // Modal Provider Tabs (Local, GitHub, Archive)
    document.querySelectorAll('.m-prov-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.m-prov-tab').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.modal-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const prov = btn.dataset.prov;
        const panel = document.getElementById(`modal-panel-${prov}`);
        if (panel) panel.classList.add('active');

        // Disable submit button on unreleased providers
        if (submitBtn) {
          submitBtn.disabled = prov !== 'local';
          submitBtn.style.opacity = prov === 'local' ? '1' : '0.5';
        }
      });
    });

    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        const pathInput = document.getElementById('input-local-path');
        const nameInput = document.getElementById('input-repo-name');
        const pathVal = pathInput ? pathInput.value.trim() : '';
        const nameVal = nameInput ? nameInput.value.trim() : '';

        if (!pathVal) {
          showOnboardError('Please provide an absolute or relative directory path.');
          return;
        }

        triggerOnboarding(pathVal, nameVal);
      });
    }
  }

  function openConnectModal() {
    const modal = document.getElementById('modal-onboard');
    if (!modal) return;
    modal.style.display = 'flex';
    hideOnboardError();
    const progBox = document.getElementById('onboard-progress-box');
    if (progBox) progBox.style.display = 'none';
    const submitBtn = document.getElementById('modal-submit-btn');
    if (submitBtn) submitBtn.disabled = false;
  }

  function closeConnectModal() {
    const modal = document.getElementById('modal-onboard');
    if (modal) modal.style.display = 'none';
  }

  function openIngestModal() {
    const modal = document.getElementById('modal-ingest-runtime');
    if (modal) modal.style.display = 'flex';
  }

  function closeIngestModal() {
    const modal = document.getElementById('modal-ingest-runtime');
    if (modal) modal.style.display = 'none';
  }

  function openCreateIncidentModal() {
    const modal = document.getElementById('modal-create-incident');
    if (modal) modal.style.display = 'flex';
  }

  function closeCreateIncidentModal() {
    const modal = document.getElementById('modal-create-incident');
    if (modal) modal.style.display = 'none';
  }

  window.openConnectModal = openConnectModal;
  window.closeConnectModal = closeConnectModal;
  window.openIngestModal = openIngestModal;
  window.closeIngestModal = closeIngestModal;
  window.openCreateIncidentModal = openCreateIncidentModal;
  window.closeCreateIncidentModal = closeCreateIncidentModal;

  function showOnboardError(msg) {
    const errBox = document.getElementById('onboard-error-box');
    if (errBox) {
      errBox.style.display = 'block';
      errBox.textContent = msg;
    }
  }

  function hideOnboardError() {
    const errBox = document.getElementById('onboard-error-box');
    if (errBox) errBox.style.display = 'none';
  }

  async function triggerOnboarding(localPath, repoName = '') {
    openConnectModal();
    hideOnboardError();

    const progBox = document.getElementById('onboard-progress-box');
    const submitBtn = document.getElementById('modal-submit-btn');
    if (progBox) progBox.style.display = 'block';
    if (submitBtn) submitBtn.disabled = true;

    // Animate real progress indicators
    const stepIds = ['prog-step-1', 'prog-step-2', 'prog-step-3', 'prog-step-4', 'prog-step-5', 'prog-step-6', 'prog-step-7'];
    stepIds.forEach((id, i) => {
      const el = document.getElementById(id);
      if (el) {
        el.style.opacity = '0.4';
        setTimeout(() => { if (el) el.style.opacity = '1'; }, i * 250);
      }
    });

    try {
      const res = await fetch('/repositories/onboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          local_path: localPath,
          name: repoName || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Analysis failed' }));
        throw new Error(errData.detail || 'Analysis execution error');
      }

      const result = await res.json();
      const newRepoId = result.repository?.id || result.repository_id;
      setTimeout(async () => {
        closeConnectModal();
        await fetchRepositories(newRepoId);
        switchPrimaryView('overview');
      }, 700);

    } catch (err) {
      console.error('Onboarding error', err);
      showOnboardError(err.message || 'Failed to analyze repository. Check filesystem path.');
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  // --- 3. Repository Discovery & Loading ---
  async function fetchRepositories(preferredRepoId = null) {
    const repoSelect = document.getElementById('repo-select');
    if (!repoSelect) return;
    repoSelect.innerHTML = '';

    const urlParams = new URLSearchParams(window.location.search);
    const paramRepo = preferredRepoId || urlParams.get('repo');
    const paramSnap = urlParams.get('snapshot');

    let loadedRepos = [];
    try {
      const res = await fetch('/repositories');
      if (res.ok) {
        loadedRepos = await res.json();
      }
    } catch (err) {
      console.warn('Failed to load /repositories', err);
    }

    state.repositories = loadedRepos;

    if (loadedRepos.length > 0) {
      loadedRepos.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = `${r.name || r.id} (${r.default_branch || 'main'})`;
        repoSelect.appendChild(opt);
      });

      const matched = loadedRepos.find(r => r.id === paramRepo || r.name === paramRepo);
      state.currentRepoId = matched ? matched.id : loadedRepos[0].id;
      repoSelect.value = state.currentRepoId;

      await loadSnapshotsForRepo(state.currentRepoId, paramSnap);
      switchPrimaryView(state.currentPrimaryView || 'overview');
    } else {
      const opt = document.createElement('option');
      opt.value = 'default';
      opt.textContent = 'No Repositories Available';
      repoSelect.appendChild(opt);
      state.currentRepoId = null;
      switchPrimaryView('overview');
    }
  }

  async function loadSnapshotsForRepo(repoId, preferredSnapId = null) {
    try {
      const res = await fetch(`/repositories/${repoId}/graph/snapshots`);
      const snapSelect = document.getElementById('snapshot-select');
      const diffBaseSelect = document.getElementById('diff-base-select');
      const diffTargetSelect = document.getElementById('diff-target-select');
      const sbDiffSelect = document.getElementById('diff-snapshot-select');

      if (snapSelect) snapSelect.innerHTML = '';
      if (diffBaseSelect) diffBaseSelect.innerHTML = '';
      if (diffTargetSelect) diffTargetSelect.innerHTML = '';
      if (sbDiffSelect) sbDiffSelect.innerHTML = '';

      if (res.ok) {
        state.snapshots = await res.json();
        state.snapshots.forEach((s, idx) => {
          const label = `${s.id.slice(0, 10)} (${s.commit_hash.slice(0, 7)}) [${s.artifacts_count} arts]`;

          if (snapSelect) {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = label;
            snapSelect.appendChild(opt);
          }

          if (diffBaseSelect) {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = label;
            diffBaseSelect.appendChild(opt);
          }

          if (diffTargetSelect) {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = label;
            diffTargetSelect.appendChild(opt);
          }

          if (sbDiffSelect) {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = label;
            sbDiffSelect.appendChild(opt);
          }
        });

        if (state.snapshots.length > 0) {
          state.currentSnapshotId = preferredSnapId || state.snapshots[0].id;
          if (snapSelect) snapSelect.value = state.currentSnapshotId;

          if (state.snapshots.length > 1) {
            state.diffSnapshotId = state.snapshots[1].id;
            if (diffTargetSelect) diffTargetSelect.value = state.diffSnapshotId;
            if (sbDiffSelect) sbDiffSelect.value = state.diffSnapshotId;
          }
        }
      }

      loadFileTree();
      refreshActiveView();
    } catch (e) {
      console.error('Error loading snapshots', e);
      refreshActiveView();
    }
  }

  // Global Twin Context Strip Updater
  function updateGlobalTwinContext(data) {
    if (!data) return;
    const repo = data.repository || state.repositories.find(r => r.id === state.currentRepoId);
    const snap = data.snapshot;
    const m = data.metrics || {};

    const elRepo = document.getElementById('strip-repo-name');
    const elBranch = document.getElementById('strip-branch-name');
    const elSnap = document.getElementById('strip-snap-id');
    const elCommit = document.getElementById('strip-commit-hash');
    const elFiles = document.getElementById('strip-files-count');
    const elArts = document.getElementById('strip-artifacts-count');
    const elRels = document.getElementById('strip-relationships-count');
    const elStatus = document.getElementById('strip-sync-status') || document.getElementById('strip-twin-status');

    if (elRepo) elRepo.textContent = repo?.name || 'Software Digital Twin';
    if (elBranch) elBranch.textContent = snap?.branch_name || repo?.default_branch || 'main';
    if (elSnap) elSnap.textContent = (snap?.id || state.currentSnapshotId || 'snap_latest').slice(0, 14);
    if (elCommit) elCommit.textContent = (snap?.commit_hash || 'HEAD').slice(0, 8);
    if (elFiles) elFiles.textContent = m.files ?? 0;
    if (elArts) elArts.textContent = m.artifacts ?? 0;
    if (elRels) elRels.textContent = m.relationships ?? 0;
    if (elStatus) elStatus.innerHTML = '<span class="status-pulse"></span> SYNCHRONIZED';
  }

  // --- 4. Overview View Data Loader (Engineering Command Center) ---
  async function loadOverviewData() {
    if (!state.currentRepoId) return;

    try {
      let url = `/repositories/${state.currentRepoId}/overview`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      state.currentRepoData = data;

      // Update Global Twin Context Strip
      updateGlobalTwinContext(data);

      // Populate Header Context
      const nameEl = document.getElementById('ov-repo-name');
      const branchEl = document.getElementById('ov-branch');
      const snapEl = document.getElementById('ov-snapshot');
      const commitEl = document.getElementById('ov-commit');
      const pathEl = document.getElementById('ov-path');

      if (nameEl) nameEl.textContent = data.repository?.name || 'Software Digital Twin';
      if (branchEl) branchEl.textContent = data.snapshot?.branch_name || data.repository?.default_branch || 'main';
      if (snapEl) snapEl.textContent = (data.snapshot?.id || '').slice(0, 14);
      if (commitEl) commitEl.textContent = (data.snapshot?.commit_hash || '').slice(0, 8);
      if (pathEl) pathEl.textContent = data.repository?.local_path || '-';

      // Real Metrics Grid
      const m = data.metrics || {};
      const filesEl = document.getElementById('metric-files');
      const artsEl = document.getElementById('metric-artifacts');
      const relsEl = document.getElementById('metric-relationships');
      const testsEl = document.getElementById('metric-tests');
      const procsEl = document.getElementById('metric-processes');
      const apisEl = document.getElementById('metric-apis');
      const driftEl = document.getElementById('metric-drift');

      if (filesEl) filesEl.textContent = m.files ?? 0;
      if (artsEl) artsEl.textContent = m.artifacts ?? 0;
      if (relsEl) relsEl.textContent = m.relationships ?? 0;
      if (testsEl) testsEl.textContent = m.tests ?? 0;
      if (procsEl) procsEl.textContent = m.processes ?? 0;
      if (apisEl) apisEl.textContent = m.apis ?? 0;
      if (driftEl) {
        driftEl.textContent = m.violations ?? 0;
        driftEl.className = `metric-value ${m.violations > 0 ? 'text-red' : 'text-green'}`;
      }

      // Component Breakdown Grid
      const breakdownGrid = document.getElementById('comp-breakdown-grid');
      if (breakdownGrid) {
        breakdownGrid.innerHTML = '';
        const bd = data.component_breakdown || {};
        const items = [
          { label: 'Classes', val: bd.CLASS || 0, icon: '🏛️' },
          { label: 'Modules', val: bd.MODULE || 0, icon: '📦' },
          { label: 'Functions', val: (bd.FUNCTION || 0) + (bd.METHOD || 0), icon: '⚡' },
          { label: 'APIs', val: bd.API_ENDPOINT || 0, icon: '⇄' },
          { label: 'Tests', val: (bd.TEST_CASE || 0) + (bd.TEST_SUITE || 0), icon: '🧪' },
        ];

        items.forEach(it => {
          const card = document.createElement('div');
          card.className = 'comp-dist-item';
          card.innerHTML = `
            <div class="comp-item-header">
              <span>${it.icon} ${it.label}</span>
              <strong class="comp-val">${it.val}</strong>
            </div>
          `;
          breakdownGrid.appendChild(card);
        });
      }

      // Architecture Macro Packages Grid
      const pkgGrid = document.getElementById('ov-packages-grid');
      if (pkgGrid) {
        pkgGrid.innerHTML = '';
        const pkgs = data.architecture_packages || [];
        if (pkgs.length === 0) {
          pkgGrid.innerHTML = '<div class="col-span-full p-4 text-center text-xs text-[#64748B] bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">No macro packages identified in this snapshot.</div>';
        } else {
          pkgs.forEach(pkg => {
            const card = document.createElement('div');
            card.className = 'bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 flex flex-col justify-between space-y-3';
            const sampleHtml = (pkg.sample_components || []).slice(0, 3).map(c => `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-white border border-[#E2E8F0] text-[#6D28D9]">${escapeHtml(c)}</span>`).join(' ');
            card.innerHTML = `
              <div class="flex items-center justify-between">
                <strong class="text-xs font-bold text-[#0F172A] flex items-center gap-1.5">
                  <span>📦</span> ${escapeHtml(pkg.name)}
                </strong>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#E0F2FE] text-[#0369A1] border border-[#BAE6FD]">${pkg.artifact_count} artifacts</span>
              </div>
              <div class="text-xs text-[#64748B] flex gap-3">
                <span>${pkg.module_count} Modules</span>
                <span>${pkg.files_count} Files</span>
              </div>
              ${sampleHtml ? `<div class="flex flex-wrap gap-1 mt-1">${sampleHtml}</div>` : ''}
              <button class="btn-explore-pkg inline-flex items-center gap-1 text-xs text-[#0071e3] hover:text-[#0059b5] font-semibold mt-1" data-pkg="${escapeHtml(pkg.name)}">
                Explore in Architecture Graph →
              </button>
            `;
            pkgGrid.appendChild(card);
          });

          pkgGrid.querySelectorAll('.btn-explore-pkg').forEach(btn => {
            btn.onclick = () => {
              switchPrimaryView('architecture');
              switchArchSubtab('graph');
              const searchInput = document.getElementById('graph-search-input');
              if (searchInput) {
                searchInput.value = btn.dataset.pkg;
                performGraphSearch(btn.dataset.pkg);
              }
            };
          });
        }
      }

      // Dynamic Architecture Flow Pipeline
      const flowList = document.getElementById('ov-flow-nodes-list');
      if (flowList) {
        const pkgs = data.architecture_packages || [];
        if (pkgs.length === 0) {
          flowList.innerHTML = '<div class="w-full text-center py-6 text-xs text-[#64748B]">No architectural packages detected in this snapshot.</div>';
        } else {
          const topPkgs = pkgs.slice(0, 5);
          const icons = ['devices', 'router', 'receipt_long', 'memory', 'database'];
          const colors = [
            { bg: '#F0F9FF', text: '#0284C7', border: '#BAE6FD', badgeBg: '#E0F2FE', badgeText: '#0369A1' },
            { bg: '#ECFDF5', text: '#059669', border: '#A7F3D0', badgeBg: '#D1FAE5', badgeText: '#047857' },
            { bg: '#FFFBEB', text: '#D97706', border: '#FED7AA', badgeBg: '#FEF3C7', badgeText: '#B45309' },
            { bg: '#EEF2FF', text: '#4F46E5', border: '#C7D2FE', badgeBg: '#E0E7FF', badgeText: '#4338CA' },
            { bg: '#FAF5FF', text: '#7C3AED', border: '#DDD6FE', badgeBg: '#EDE9FE', badgeText: '#6D28D9' },
          ];

          flowList.innerHTML = topPkgs.map((pkg, i) => {
            const col = colors[i % colors.length];
            const icon = icons[i % icons.length];
            const nodeHtml = `
              <div class="flex-1 bg-white border border-[${col.border}]/80 p-3 rounded-lg shadow-2xs flex flex-col items-center text-center">
                <div class="w-8 h-8 rounded-full bg-[${col.bg}] text-[${col.text}] flex items-center justify-center">
                  <span class="material-symbols-outlined text-[18px]">${icon}</span>
                </div>
                <span class="text-xs font-bold text-[#0F172A] mt-1 truncate max-w-[120px]">${escapeHtml(pkg.name)}</span>
                <span class="text-[10px] text-[#64748B]">${pkg.total_artifacts} artifacts</span>
                <span class="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[${col.badgeBg}] text-[${col.badgeText}] text-[10px] font-semibold border border-[${col.border}]">
                  ${pkg.modules || pkg.module_count || 1} modules
                </span>
              </div>
            `;
            const arrowHtml = (i < topPkgs.length - 1)
              ? `<div class="flex items-center text-[#94A3B8]"><span class="material-symbols-outlined text-[18px]">trending_flat</span></div>`
              : '';
            return nodeHtml + arrowHtml;
          }).join('');
        }
      }

      // Latest Change Impact Card in Overview
      const impactContainer = document.getElementById('ov-impact-container');
      if (impactContainer) {
        const imp = data.latest_impact;
        if (imp) {
          impactContainer.innerHTML = `
            <div class="flex items-center justify-between mb-3">
              <div>
                <span class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Change Impact Analysis Run</span>
                <div class="text-xs font-bold text-[#6D28D9] mt-0.5">
                  Target Snapshot: <span class="font-mono text-[#0F172A]">${escapeHtml(imp.target_snapshot_id.slice(0, 14))}</span>
                </div>
              </div>
              <button id="btn-ov-view-impact" class="px-3 py-1.5 rounded-lg bg-[#FAF5FF] hover:bg-[#F3E8FF] border border-[#DDD6FE] text-[#6D28D9] text-xs font-semibold transition-colors">
                Open Full Blast-Radius Report →
              </button>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
              <div class="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Changed</div>
                <div class="text-lg font-bold text-[#F59E0B] mt-0.5">${imp.changed_count}</div>
              </div>
              <div class="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Direct</div>
                <div class="text-lg font-bold text-[#EF4444] mt-0.5">${imp.directly_affected_count}</div>
              </div>
              <div class="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Indirect</div>
                <div class="text-lg font-bold text-[#EC4899] mt-0.5">${imp.indirectly_affected_count}</div>
              </div>
              <div class="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Components</div>
                <div class="text-lg font-bold text-[#3B82F6] mt-0.5">${imp.components_affected}</div>
              </div>
              <div class="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">APIs</div>
                <div class="text-lg font-bold text-[#8B5CF6] mt-0.5">${imp.apis_affected}</div>
              </div>
              <div class="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Processes</div>
                <div class="text-lg font-bold text-[#06B6D4] mt-0.5">${imp.processes_affected}</div>
              </div>
              <div class="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Tests</div>
                <div class="text-lg font-bold text-[#10B981] mt-0.5">${imp.tests_affected}</div>
              </div>
            </div>
            <div class="flex items-center justify-between text-xs text-[#64748B] pt-2 border-t border-[#F1F5F9] mt-3">
              <span>Causal Paths: <strong class="text-[#0F172A]">${imp.causal_paths_count}</strong></span>
              <span>Execution Time: <strong class="text-[#0F172A]">${imp.execution_time_ms} ms</strong></span>
              <span>Analyzed: <strong class="text-[#0F172A]">${new Date(imp.created_at).toLocaleTimeString()}</strong></span>
            </div>
          `;
          document.getElementById('btn-ov-view-impact')?.addEventListener('click', () => {
            switchPrimaryView('impact');
          });
        } else {
          impactContainer.innerHTML = `
            <div class="p-4 rounded-xl bg-[#F8FAFC] border border-dashed border-[#E2E8F0] flex items-center justify-between">
              <div>
                <div class="text-xs font-bold text-[#0F172A]">No Change Impact Analysis Run For This Snapshot</div>
                <div class="text-[11px] text-[#64748B] mt-0.5">Compare with an earlier snapshot to compute deterministic blast-radius propagation across components, APIs, processes, and tests.</div>
              </div>
              <button id="btn-ov-run-impact" class="px-3.5 py-1.5 rounded-lg bg-[#0071e3] hover:bg-[#0059b5] text-white text-xs font-semibold shadow-xs shrink-0">
                Run Blast-Radius Analysis →
              </button>
            </div>
          `;
          document.getElementById('btn-ov-run-impact')?.addEventListener('click', () => {
            switchPrimaryView('impact');
          });
        }
      }

      // Evidence Overview Summary Metrics
      const evFiles = document.getElementById('ev-sum-files');
      const evArts = document.getElementById('ev-sum-artifacts');
      const evRels = document.getElementById('ev-sum-relationships');
      const evTests = document.getElementById('ev-sum-tests');
      const evProcs = document.getElementById('ev-sum-processes');
      const evRuns = document.getElementById('ev-sum-runs');

      if (evFiles) evFiles.textContent = m.files ?? 0;
      if (evArts) evArts.textContent = m.artifacts ?? 0;
      if (evRels) evRels.textContent = m.relationships ?? 0;
      if (evTests) evTests.textContent = m.tests ?? 0;
      if (evProcs) evProcs.textContent = m.processes ?? 0;
      if (evRuns) evRuns.textContent = state.snapshots.length || 1;

      // Conformance Banner
      const confAlert = document.getElementById('conformance-alert-box');
      const confTitle = document.getElementById('conf-title');
      const confDesc = document.getElementById('conf-desc');
      const confIcon = document.getElementById('conf-icon');

      if (confAlert && confTitle && confDesc && confIcon) {
        if ((m.violations || 0) > 0) {
          confAlert.className = 'conformance-banner alert-drift';
          confIcon.textContent = '⚠️';
          confTitle.textContent = `${m.violations} Architecture Drift Violation(s) Detected`;
          confDesc.textContent = 'Active dependencies cross declared architectural boundaries. Review under Architecture → Conformance & Drift.';
        } else {
          confAlert.className = 'conformance-banner alert-ok';
          confIcon.textContent = '✓';
          confTitle.textContent = '100% Architecture Conformance';
          confDesc.textContent = 'No baseline violations. All dependencies strictly comply with defined architecture boundaries.';
        }
      }

      // Analysis Pipeline Status
      const pipeTestVal = document.getElementById('pipe-test-val');
      const pipeProcVal = document.getElementById('pipe-proc-val');
      const pipeArchVal = document.getElementById('pipe-arch-val');

      if (pipeTestVal) pipeTestVal.textContent = data.analysis_status?.test_mapping || 'Complete';
      if (pipeProcVal) pipeProcVal.textContent = data.analysis_status?.process_mapping || 'Statically Inferred';
      if (pipeArchVal) pipeArchVal.textContent = data.analysis_status?.architecture_validation || 'Evaluated';

      // Latest Run Box
      const runAnalyzers = document.getElementById('ov-run-analyzers');
      const runTime = document.getElementById('ov-run-time');
      if (runAnalyzers) {
        const az = data.latest_run?.analyzers || ['python_treesitter', 'dependency_mapper'];
        runAnalyzers.textContent = Array.isArray(az) ? az.join(', ') : az;
      }
      if (runTime) {
        runTime.textContent = data.latest_run?.completed_at ? new Date(data.latest_run.completed_at).toLocaleString() : 'Just now';
      }

      // Update Stitch Hero Metric Cards
      const ovCompCount = document.getElementById('ov-components-count');
      const ovCompSub = document.getElementById('ov-components-sub');
      const ovApisCount = document.getElementById('ov-apis-count');
      const ovApisSub = document.getElementById('ov-apis-sub');
      const ovDepsCount = document.getElementById('ov-deps-count');
      const ovDepsSub = document.getElementById('ov-deps-sub');
      const ovTestsCount = document.getElementById('ov-tests-count');
      const ovTestsSub = document.getElementById('ov-tests-sub');

      const bd = data.component_breakdown || {};
      if (ovCompCount) ovCompCount.textContent = m.artifacts ?? 0;
      if (ovCompSub) ovCompSub.textContent = `${bd.MODULE || 0} modules · ${bd.CLASS || 0} classes`;
      if (ovApisCount) ovApisCount.textContent = m.apis ?? 0;
      if (ovApisSub) ovApisSub.textContent = `${m.apis ?? 0} endpoints registered`;
      if (ovDepsCount) ovDepsCount.textContent = m.relationships ?? 0;
      if (ovDepsSub) ovDepsSub.textContent = 'Static, semantic & call edges';
      if (ovTestsCount) ovTestsCount.textContent = m.tests ?? 0;
      if (ovTestsSub) ovTestsSub.textContent = `${m.tests ?? 0} suites & cases mapped`;

      // Update sidebar & breadcrumb repo info
      const sbRepoName = document.getElementById('sidebar-repo-name');
      const sbBranchName = document.getElementById('sidebar-branch-name');
      const ovRepoBreadcrumb = document.getElementById('ov-repo-breadcrumb');
      if (sbRepoName) sbRepoName.textContent = data.repository?.name || 'Local Repository';
      if (sbBranchName) sbBranchName.textContent = data.snapshot?.branch_name || data.repository?.default_branch || 'main';
      if (ovRepoBreadcrumb) ovRepoBreadcrumb.textContent = data.repository?.name || 'Local Repository';

      // Load Live Real Incidents for Overview Banner & Badges
      loadOverviewIncidents(state.currentRepoId);

      // Load Live Real Runtime Telemetry for Overview Feed
      loadOverviewRuntime(state.currentRepoId);

    } catch (e) {
      console.error('Error loading overview data', e);
    }
  }

  async function loadOverviewIncidents(repoId) {
    if (!repoId) return;
    try {
      const res = await fetch(`/repositories/${repoId}/incidents`);
      if (!res.ok) return;
      const incidents = await res.json();

      const sbBadge = document.getElementById('sidebar-incidents-badge');
      const ovBadge = document.getElementById('ov-incidents-badge');
      if (sbBadge) sbBadge.textContent = incidents.length;
      if (ovBadge) ovBadge.textContent = `${incidents.length} Active`;

      const card = document.getElementById('ov-active-incident-card');
      const stripeEl = document.getElementById('ov-incident-stripe');
      const pillEl = document.getElementById('ov-incident-status-pill');
      const pulseEl = document.getElementById('ov-incident-pulse');
      const titleEl = document.getElementById('ov-incident-title');
      const descEl = document.getElementById('ov-incident-desc');
      const statusEl = document.getElementById('ov-incident-status');
      const targetEl = document.getElementById('ov-incident-target');
      const badgesContainer = document.getElementById('ov-incident-badges');
      const confEl = document.getElementById('ov-incident-confidence');
      const invBtn = document.getElementById('ov-btn-investigate');
      const viewIncidentsBtn = document.getElementById('ov-btn-view-incidents');

      if (incidents.length > 0) {
        const inc = incidents[0];
        state.activeIncidentId = inc.id;

        if (card) {
          card.className = "bg-[#FFF1F2]/80 border border-[#FECDD3] rounded-xl p-6 shadow-xs hover:shadow-md transition-all relative overflow-hidden";
        }
        if (stripeEl) stripeEl.className = "absolute left-0 top-0 bottom-0 w-1.5 bg-[#E11D48]";
        if (pillEl) pillEl.className = "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#FFE4E6] text-[#BE123C] text-[11px] font-bold border border-[#FDA4AF]/60";
        if (pulseEl) pulseEl.className = "w-2 h-2 rounded-full bg-[#E11D48] animate-pulse";
        if (statusEl) statusEl.textContent = `Needs Attention · ${(inc.severity || 'SEV-1').toUpperCase()}`;

        if (titleEl) {
          titleEl.textContent = inc.title;
          titleEl.className = "text-lg font-bold text-[#881337] tracking-tight";
        }
        if (descEl) {
          descEl.textContent = inc.description || 'Deterministic causal correlation and evidence available for analysis.';
          descEl.className = "text-xs text-[#9F1239]/90 mt-1 leading-relaxed";
        }
        if (targetEl) targetEl.textContent = inc.affected_component_name || 'Component root';

        if (badgesContainer) {
          const evCount = inc.evidence_ids ? inc.evidence_ids.length : 0;
          badgesContainer.innerHTML = `
            <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/90 border border-[#FECDD3] text-[#BE123C] text-xs font-medium shadow-2xs">
              <span class="material-symbols-outlined text-[16px] text-[#E11D48]">error</span>
              <span>${evCount} linked evidence item${evCount === 1 ? '' : 's'}</span>
            </div>
            <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/90 border border-[#FED7AA] text-[#C2410C] text-xs font-medium shadow-2xs">
              <span class="material-symbols-outlined text-[16px] text-[#EA580C]">flag</span>
              <span>Status: ${(inc.status || 'OPEN').toUpperCase()}</span>
            </div>
          `;
        }

        if (confEl) confEl.textContent = 'Confidence: 100% verified';

        const doInvestigate = () => {
          switchPrimaryView('incidents');
          investigateIncident(inc.id);
        };
        if (invBtn) invBtn.onclick = doInvestigate;
        if (viewIncidentsBtn) viewIncidentsBtn.onclick = doInvestigate;

      } else {
        state.activeIncidentId = null;

        if (card) {
          card.className = "bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-6 shadow-xs hover:shadow-md transition-all relative overflow-hidden";
        }
        if (stripeEl) stripeEl.className = "absolute left-0 top-0 bottom-0 w-1.5 bg-[#10B981]";
        if (pillEl) pillEl.className = "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#ECFDF5] text-[#059669] text-[11px] font-bold border border-[#A7F3D0]";
        if (pulseEl) pulseEl.className = "w-2 h-2 rounded-full bg-[#10B981]";
        if (statusEl) statusEl.textContent = 'All Systems Operational';

        if (titleEl) {
          titleEl.textContent = 'No Active Incidents';
          titleEl.className = "text-lg font-bold text-[#0F172A] tracking-tight";
        }
        if (descEl) {
          descEl.textContent = 'No open incidents recorded in this environment. System running cleanly.';
          descEl.className = "text-xs text-[#64748B] mt-1 leading-relaxed";
        }
        if (targetEl) targetEl.textContent = 'Clean Environment';

        if (badgesContainer) {
          badgesContainer.innerHTML = `
            <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-[#E2E8F0] text-[#059669] text-xs font-medium shadow-2xs">
              <span class="material-symbols-outlined text-[16px] text-[#10B981]">check_circle</span>
              <span>0 active anomalies · 0 open incidents</span>
            </div>
          `;
        }

        if (confEl) confEl.textContent = 'Status: Verified Healthy';

        const doViewIncidents = () => {
          switchPrimaryView('incidents');
        };
        if (invBtn) invBtn.onclick = doViewIncidents;
        if (viewIncidentsBtn) viewIncidentsBtn.onclick = doViewIncidents;
      }
    } catch (e) {
      console.warn('Failed to load overview incidents', e);
    }
  }

  async function loadOverviewRuntime(repoId) {
    if (!repoId) return;
    try {
      const res = await fetch(`/repositories/${repoId}/runtime-events?limit=4`);
      if (!res.ok) return;
      const events = await res.json();

      const sbRuntimeBadge = document.getElementById('sidebar-runtime-badge');
      if (sbRuntimeBadge) sbRuntimeBadge.textContent = events.length;

      const feed = document.getElementById('ov-runtime-feed');
      if (!feed) return;

      if (events.length === 0) {
        feed.innerHTML = `
          <div class="text-xs text-on-surface-variant p-4 text-center border border-dashed border-outline-variant/30 rounded-xl">
            No runtime telemetry ingested yet. Use the <strong>+ Ingest</strong> button to correlate traces, error spikes, and APM metrics.
          </div>
        `;
        return;
      }

      feed.innerHTML = events.slice(0, 3).map(ev => {
        const isError = ev.severity === 'error' || ev.severity === 'critical';
        const sevColor = isError ? 'text-red-400 bg-red-500/10 border-red-500/20' : 'text-blue-400 bg-blue-500/10 border-blue-500/20';
        return `
          <div class="flex items-center justify-between p-3 rounded-xl bg-surface-container-low border border-outline-variant/20 hover:border-outline-variant/40 transition-colors">
            <div class="flex items-center gap-3">
              <span class="px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold border ${sevColor}">${escapeHtml(ev.event_type)}</span>
              <div>
                <div class="text-xs font-semibold text-on-surface">${escapeHtml(ev.component_name || 'System Event')}</div>
                <div class="text-[10px] text-on-surface-variant font-mono mt-0.5">${new Date(ev.timestamp).toLocaleTimeString()} · Env: ${escapeHtml(ev.environment || 'production')}</div>
              </div>
            </div>
            <div class="text-right">
              <span class="text-xs font-mono font-bold ${ev.latency_ms > 500 ? 'text-amber-400' : 'text-emerald-400'}">${ev.latency_ms ? ev.latency_ms + 'ms' : '-'}</span>
              <div class="text-[10px] text-on-surface-variant">${ev.error_count > 0 ? `<span class="text-red-400 font-bold">${ev.error_count} errs</span>` : '0 errs'}</div>
            </div>
          </div>
        `;
      }).join('');
    } catch (e) {
      console.warn('Failed to load overview runtime feed', e);
    }
  }

  function initCommandPalette() {
    const modal = document.getElementById('modal-command-palette');
    const input = document.getElementById('cmd-palette-input');
    const results = document.getElementById('cmd-palette-results');
    const searchBtn = document.getElementById('top-search-btn');

    function openPalette() {
      if (!modal) return;
      modal.style.display = 'flex';
      if (input) {
        input.value = '';
        input.focus();
        renderPaletteResults('');
      }
    }

    function closePalette() {
      if (modal) modal.style.display = 'none';
    }

    searchBtn?.addEventListener('click', openPalette);
    document.getElementById('cmd-palette-close-btn')?.addEventListener('click', closePalette);

    modal?.addEventListener('click', (e) => {
      if (e.target === modal) closePalette();
    });

    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (modal && modal.style.display === 'flex') {
          closePalette();
        } else {
          openPalette();
        }
      } else if (e.key === 'Escape') {
        closePalette();
        closeConnectModal();
        closeIngestModal();
        closeCreateIncidentModal();
      }
    });

    input?.addEventListener('input', (e) => {
      renderPaletteResults(e.target.value.trim().toLowerCase());
    });

    function renderPaletteResults(query) {
      if (!results) return;
      const views = [
        { name: 'Architecture Overview', icon: 'dashboard', view: 'overview', desc: 'System metrics, active incident, and macro packages' },
        { name: 'Components & Artifacts', icon: 'category', view: 'components', desc: 'Modules, classes, functions, and services' },
        { name: 'Architecture Topology Graph', icon: 'schema', view: 'architecture', desc: 'Interactive Canvas with L1/L2/L3 zoom and inspector' },
        { name: 'Dependency Matrix', icon: 'account_tree', view: 'dependencies', desc: 'Inbound, outbound, and circular dependencies' },
        { name: 'Process Twin & Business Flows', icon: 'account_tree', view: 'processes', desc: 'Discovered end-to-end workflows and steps' },
        { name: 'Snapshot Comparison', icon: 'compare_arrows', view: 'changes', desc: 'Deterministic structural differences across git commits' },
        { name: 'Change Impact & Blast-Radius', icon: 'radar', view: 'impact', desc: 'Multi-hop propagation paths and affected test suites' },
        { name: 'Test Impact & Verification', icon: 'science', view: 'tests', desc: 'Test coverage, suite status, and affected test cases' },
        { name: 'Incident Intelligence', icon: 'troubleshoot', view: 'incidents', desc: 'Triage active production incidents and causal paths' },
        { name: 'Runtime Telemetry Stream', icon: 'stream', view: 'runtime', desc: 'Live traces, error spikes, and performance telemetry' },
        { name: 'Evidence Ledger', icon: 'receipt_long', view: 'evidence', desc: 'Multi-source factual audit records' },
        { name: 'Ask Software Intelligence', icon: 'auto_awesome', view: 'ask', desc: 'Deterministic natural language software inquiry' },
      ];

      let items = views.filter(v => !query || v.name.toLowerCase().includes(query) || v.desc.toLowerCase().includes(query));

      if (query && state.rawGraph && state.rawGraph.nodes) {
        const matchedNodes = state.rawGraph.nodes.filter(n => n.name && n.name.toLowerCase().includes(query)).slice(0, 5);
        matchedNodes.forEach(n => {
          items.push({
            name: `Inspect Node: ${n.name}`,
            icon: 'hub',
            view: 'architecture',
            nodeId: n.id,
            desc: `Type: ${n.type} · ${n.path || 'Root'}`
          });
        });
      }

      if (items.length === 0) {
        results.innerHTML = `<div class="p-6 text-center text-xs text-on-surface-variant">No matching commands or components found for "${escapeHtml(query)}"</div>`;
        return;
      }

      results.innerHTML = items.map((item, idx) => `
        <div class="cmd-item flex items-center justify-between p-3 rounded-xl hover:bg-surface-container-high/60 cursor-pointer transition-colors group" data-idx="${idx}">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-on-surface-variant group-hover:text-primary transition-colors">
              <span class="material-symbols-outlined text-[18px]">${item.icon}</span>
            </div>
            <div>
              <div class="text-xs font-semibold text-on-surface group-hover:text-primary transition-colors">${escapeHtml(item.name)}</div>
              <div class="text-[11px] text-on-surface-variant line-clamp-1">${escapeHtml(item.desc)}</div>
            </div>
          </div>
          <span class="material-symbols-outlined text-[14px] text-on-surface-variant group-hover:translate-x-0.5 transition-transform">arrow_forward</span>
        </div>
      `).join('');

      results.querySelectorAll('.cmd-item').forEach(el => {
        const idx = parseInt(el.dataset.idx, 10);
        const item = items[idx];
        el.addEventListener('click', () => {
          closePalette();
          if (item.nodeId) {
            switchPrimaryView('architecture');
            switchArchSubtab('graph');
            setTimeout(() => focusOnNode(item.nodeId), 150);
          } else if (item.view) {
            switchPrimaryView(item.view);
          }
        });
      });
    }

    window.openCommandPalette = openPalette;
    window.closeCommandPalette = closePalette;
  }

  function initAskSoftware() {
    const input = document.getElementById('ask-query-input');
    const submitBtn = document.getElementById('btn-ask-submit');
    const resultsContainer = document.getElementById('ask-results-container');

    document.querySelectorAll('.ask-prompt-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        const prompt = pill.dataset.prompt;
        if (input && prompt) {
          input.value = prompt;
          runSoftwareQuery(prompt);
        }
      });
    });

    submitBtn?.addEventListener('click', () => {
      const q = input?.value?.trim();
      if (q) runSoftwareQuery(q);
    });

    input?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const q = input.value.trim();
        if (q) runSoftwareQuery(q);
      }
    });

    async function runSoftwareQuery(query) {
      if (!resultsContainer) return;
      resultsContainer.innerHTML = `
        <div class="flex items-center justify-center p-12 text-on-surface-variant gap-3">
          <span class="material-symbols-outlined animate-spin text-primary">progress_activity</span>
          <span class="text-xs font-mono">Synthesizing twin graph, telemetry, and evidence for: "${escapeHtml(query)}"...</span>
        </div>
      `;

      const qLower = query.toLowerCase();
      const repoId = state.currentRepoId;
      const snapId = state.currentSnapshotId;

      try {
        if (qLower.includes('incident') || qLower.includes('triage') || qLower.includes('outage') || qLower.includes('failure')) {
          const res = await fetch(`/repositories/${repoId}/incidents`);
          const incidents = res.ok ? await res.json() : [];
          if (incidents.length === 0) {
            resultsContainer.innerHTML = `
              <div class="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 space-y-3">
                <div class="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                  <span class="material-symbols-outlined">check_circle</span> Zero Active Incidents
                </div>
                <p class="text-xs text-on-surface-variant">The software digital twin reports zero open production incidents. All monitored services and components are within normal operating parameters.</p>
              </div>
            `;
          } else {
            resultsContainer.innerHTML = `
              <div class="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 space-y-4">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2 text-red-400 font-semibold text-sm">
                    <span class="material-symbols-outlined">warning</span> Found ${incidents.length} Tracked Incident(s)
                  </div>
                  <button class="px-3 py-1 rounded-lg bg-red-600/20 text-red-400 text-xs font-medium border border-red-500/30" onclick="window.TwinApp.switchPrimaryView('incidents')">Open Triage View →</button>
                </div>
                <div class="space-y-3">
                  ${incidents.map(inc => `
                    <div class="p-3 bg-surface-container rounded-xl border border-outline-variant/20 flex items-center justify-between">
                      <div>
                        <div class="text-xs font-bold text-on-surface">${escapeHtml(inc.title)}</div>
                        <div class="text-[11px] text-on-surface-variant mt-0.5">${escapeHtml(inc.description || 'Target: ' + (inc.affected_component_name || 'Component root'))}</div>
                      </div>
                      <button class="px-2.5 py-1 rounded-lg bg-primary hover:bg-blue-600 text-white text-[11px] font-semibold" onclick="window.TwinApp.investigateIncident('${inc.id}')">Investigate Causal Path</button>
                    </div>
                  `).join('')}
                </div>
              </div>
            `;
          }
        } else if (qLower.includes('blast radius') || qLower.includes('impact') || qLower.includes('change')) {
          resultsContainer.innerHTML = `
            <div class="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 space-y-4">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-primary font-semibold text-sm">
                  <span class="material-symbols-outlined">radar</span> Change Impact Intelligence
                </div>
                <button class="px-3 py-1 rounded-lg bg-primary text-white text-xs font-semibold" onclick="window.TwinApp.switchPrimaryView('impact')">Run Full Blast-Radius →</button>
              </div>
              <p class="text-xs text-on-surface-variant">Deterministic change detection computes structural diffs between Git snapshots and propagates causal dependency paths through the architecture graph to identify directly and indirectly affected components, APIs, process steps, and test suites.</p>
            </div>
          `;
        } else {
          let url = `/repositories/${repoId}/components`;
          if (snapId) url += `?snapshot_id=${snapId}`;
          const res = await fetch(url);
          const data = res.ok ? await res.json() : { components: [] };
          const components = data.components || [];
          const matches = components.filter(c =>
            c.name.toLowerCase().includes(qLower) ||
            (c.qualified_name && c.qualified_name.toLowerCase().includes(qLower)) ||
            (c.location && c.location.toLowerCase().includes(qLower))
          ).slice(0, 10);

          if (matches.length > 0) {
            resultsContainer.innerHTML = `
              <div class="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 space-y-4">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2 text-cyan-400 font-semibold text-sm">
                    <span class="material-symbols-outlined">category</span> Matched ${matches.length} Architectural Component(s)
                  </div>
                  <button class="px-3 py-1 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-xs text-on-surface" onclick="window.TwinApp.switchPrimaryView('components')">View All in Catalog →</button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  ${matches.map(c => `
                    <div class="p-3 bg-surface-container rounded-xl border border-outline-variant/20 hover:border-primary/40 transition-colors">
                      <div class="flex items-center justify-between">
                        <span class="text-xs font-bold text-on-surface">${escapeHtml(c.name)}</span>
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">${escapeHtml(c.type)}</span>
                      </div>
                      <div class="text-[11px] text-on-surface-variant font-mono mt-1 truncate">${escapeHtml(c.location || c.qualified_name || '-')}</div>
                    </div>
                  `).join('')}
                </div>
              </div>
            `;
          } else {
            resultsContainer.innerHTML = `
              <div class="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 space-y-3">
                <div class="flex items-center gap-2 text-on-surface font-semibold text-sm">
                  <span class="material-symbols-outlined">search</span> Query Result
                </div>
                <p class="text-xs text-on-surface-variant">No exact components matched "${escapeHtml(query)}". Try querying about active incidents, blast radius, specific module names, or run a full snapshot comparison.</p>
              </div>
            `;
          }
        }
      } catch (err) {
        resultsContainer.innerHTML = `
          <div class="bg-surface-container-low border border-red-500/30 rounded-2xl p-6 space-y-2 text-red-400 text-xs">
            <div class="font-bold flex items-center gap-2"><span class="material-symbols-outlined">error</span> Query Failed</div>
            <p>${escapeHtml(err.message)}</p>
          </div>
        `;
      }
    }
  }

  // --- 5. Components Sub-View ---
  async function loadComponentsData() {
    if (!state.currentRepoId) return;
    const tbody = document.getElementById('components-table-body');
    const countDisplay = document.getElementById('components-count-display');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="td-loading">Querying Digital Twin structural artifacts...</td></tr>';

    try {
      let url = `/repositories/${state.currentRepoId}/components`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to load components');
      const data = await res.json();
      state.componentsList = data.components || [];

      if (countDisplay) {
        countDisplay.textContent = `${state.componentsList.length} components`;
      }

      renderComponentsTable(state.componentsList);

      // Search Filter Setup
      const searchInput = document.getElementById('components-search-input');
      if (searchInput) {
        searchInput.oninput = (e) => {
          const q = e.target.value.toLowerCase().trim();
          const filtered = state.componentsList.filter(c =>
            c.name.toLowerCase().includes(q) ||
            (c.qualified_name && c.qualified_name.toLowerCase().includes(q)) ||
            (c.location && c.location.toLowerCase().includes(q))
          );
          renderComponentsTable(filtered);
        };
      }
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="td-empty">Error loading components: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  function renderComponentsTable(components) {
    const tbody = document.getElementById('components-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (components.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="p-6 text-center text-[#64748B]">No components found matching filter.</td></tr>';
      return;
    }

    components.forEach(c => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-[#F8FAFC] transition-colors';
      tr.innerHTML = `
        <td class="p-3.5 font-bold text-[#0F172A]">${escapeHtml(c.name)}</td>
        <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">${c.type}</span></td>
        <td class="p-3.5 font-mono text-xs text-[#64748B]">${escapeHtml(c.qualified_name || c.name)}</td>
        <td class="p-3.5 font-mono text-xs text-[#475569]">${escapeHtml(c.location || '')}</td>
        <td class="p-3.5 text-[#475569]">${escapeHtml(c.language || 'Python')}</td>
        <td class="p-3.5"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">${((c.confidence || 1.0) * 100).toFixed(0)}%</span></td>
        <td class="p-3.5">
          <button class="px-2.5 py-1 rounded-lg bg-[#F1F5F9] hover:bg-[#E2E8F0] text-[#0F172A] text-xs font-medium transition-colors" data-art-id="${c.id}">Focus in Graph</button>
        </td>
      `;

      tr.querySelector('button')?.addEventListener('click', () => {
        switchPrimaryView('architecture');
        switchArchSubtab('graph');
        setTimeout(() => focusOnNode(c.id), 100);
      });

      tbody.appendChild(tr);
    });
  }

  // --- 6. APIs Sub-View ---
  async function loadApisData() {
    if (!state.currentRepoId) return;
    const tbody = document.getElementById('apis-table-body');
    const countDisplay = document.getElementById('apis-count-display');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="5" class="td-loading">Scanning exposed HTTP endpoints...</td></tr>';

    try {
      let url = `/repositories/${state.currentRepoId}/components`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to load APIs');
      const data = await res.json();
      const apis = (data.components || []).filter(c => c.type === 'API_ENDPOINT');

      if (countDisplay) countDisplay.textContent = `${apis.length} endpoints`;

      renderApisTable(apis);

      const searchInput = document.getElementById('apis-search-input');
      if (searchInput) {
        searchInput.oninput = (e) => {
          const q = e.target.value.toLowerCase().trim();
          const filtered = apis.filter(a =>
            a.name.toLowerCase().includes(q) ||
            (a.location && a.location.toLowerCase().includes(q))
          );
          renderApisTable(filtered);
        };
      }
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="td-empty">Error loading APIs: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  function renderApisTable(apis) {
    const tbody = document.getElementById('apis-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (apis.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="td-empty">No API endpoints detected in this snapshot.</td></tr>';
      return;
    }

    apis.forEach(a => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong class="text-cyan">${escapeHtml(a.name)}</strong></td>
        <td>${escapeHtml(a.qualified_name || 'REST Route')}</td>
        <td class="text-mono">${escapeHtml(a.location || '')}</td>
        <td><span class="badge-evidence">AST_ROUTE_DECORATOR</span></td>
        <td><span class="conf-badge">${((a.confidence || 1.0) * 100).toFixed(0)}%</span></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // --- 7. Architecture Conformance & Drift Sub-View ---
  async function loadDriftData() {
    if (!state.currentRepoId) return;
    const tbody = document.getElementById('drift-table-body');
    const headerEl = document.getElementById('drift-summary-header');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="td-loading">Evaluating architectural boundary rules...</td></tr>';

    try {
      let url = `/repositories/${state.currentRepoId}/overview`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to load drift evaluation');
      const data = await res.json();
      const violations = data.violations || [];

      if (headerEl) {
        if (violations.length === 0) {
          headerEl.innerHTML = `
            <div class="drift-stat-banner green-banner">
              <div class="stat-big">0</div>
              <div>
                <strong>System In Conformance</strong>
                <p>All component interactions respect layered domain boundaries.</p>
              </div>
            </div>
          `;
        } else {
          headerEl.innerHTML = `
            <div class="drift-stat-banner red-banner">
              <div class="stat-big">${violations.length}</div>
              <div>
                <strong>Architecture Drift Detected</strong>
                <p>${violations.length} interaction(s) violate declared architectural rules.</p>
              </div>
            </div>
          `;
        }
      }

      tbody.innerHTML = '';
      if (violations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="td-empty">No architectural violations detected. System complies with baseline.</td></tr>';
        return;
      }

      violations.forEach(v => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><span class="badge-severity sev-${(v.severity || 'HIGH').toLowerCase()}">${v.severity || 'HIGH'}</span></td>
          <td><strong>${escapeHtml(v.category || 'LAYER_VIOLATION')}</strong></td>
          <td class="text-mono">${escapeHtml(v.source)}</td>
          <td class="text-mono">${escapeHtml(v.target)}</td>
          <td>${escapeHtml(v.expected_rule || 'Disallowed import')}</td>
          <td class="text-mono text-muted">${escapeHtml(v.location || v.actual_evidence || '')}</td>
        `;
        tbody.appendChild(tr);
      });

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="6" class="td-empty">Error evaluating drift: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  // --- 8. Processes View (Visual Workflows) ---
  let currentProcessTab = 'all';

  async function loadProcessesView() {
    if (!state.currentRepoId) return;
    const container = document.getElementById('processes-container') || document.getElementById('process-chains-container');
    if (!container) return;

    // Hook filter buttons
    document.querySelectorAll('.proc-filter-btn').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.proc-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentProcessTab = btn.dataset.filter || 'all';
        renderProcessesWorkflow();
      };
    });

    container.innerHTML = '<div class="p-8 text-center text-xs text-[#64748B]">Synthesizing deterministic process workflows from AST call graphs...</div>';

    try {
      // First check if Phase 5 discovered processes exist
      let pUrl = `/repositories/${state.currentRepoId}/processes`;
      if (state.currentSnapshotId) pUrl += `?snapshot_id=${state.currentSnapshotId}`;

      const pRes = await fetch(pUrl);
      if (pRes.ok) {
        const pList = await pRes.json();
        if (pList && pList.length > 0) {
          const nodes = [];
          const edges = [];
          pList.forEach(p => {
            (p.steps || []).forEach(s => {
              nodes.push({
                id: s.id,
                process_id: p.id,
                order: s.step_order,
                name: s.name,
                type: s.step_type || s.artifact_type || 'STEP',
                component_name: s.artifact_name || s.name,
                component_id: s.artifact_id,
                location: s.file_path ? `${s.file_path}${s.line_number ? ':' + s.line_number : ''}` : 'source',
                confidence: s.confidence,
                evidence_status: s.evidence_status
              });
            });
            (p.transitions || []).forEach(t => {
              edges.push({
                id: t.id,
                process_id: p.id,
                source: t.from_step_id,
                target: t.to_step_id,
                relationship_type: t.transition_type,
                condition: t.evidence_status
              });
            });
          });
          state.currentProcessData = { processes: pList, nodes, edges };
          renderProcessesWorkflow();
          return;
        }
      }

      // Fall back to process-graph
      let url = `/repositories/${state.currentRepoId}/process-graph`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to load process synthesis');
      const data = await res.json();
      state.currentProcessData = data;
      renderProcessesWorkflow();
    } catch (err) {
      container.innerHTML = `<div class="p-6 text-center text-xs text-[#BE123C] bg-[#FFF1F2] rounded-xl border border-[#FECDD3]">Error synthesizing processes: ${escapeHtml(err.message)}</div>`;
    }
  }

  function renderProcessesWorkflow() {
    const container = document.getElementById('processes-container') || document.getElementById('process-chains-container');
    if (!container || !state.currentProcessData) return;

    const data = state.currentProcessData;
    let processes = data.processes || [];
    const allNodes = data.nodes || [];
    const allEdges = data.edges || [];

    // Filter by tab
    if (currentProcessTab === 'app') {
      processes = processes.filter(p => !p.type?.includes('TEST') && !p.name?.toLowerCase().includes('test'));
    } else if (currentProcessTab === 'test') {
      processes = processes.filter(p => p.type?.includes('TEST') || p.name?.toLowerCase().includes('test'));
    }

    if (processes.length === 0) {
      container.innerHTML = `
        <div class="p-8 text-center bg-white border border-dashed border-[#E2E8F0] rounded-xl">
          <div class="text-2xl mb-2">⚙️</div>
          <p class="font-bold text-sm text-[#0F172A] mb-1">No process workflows matched the active filter.</p>
          <span class="text-xs text-[#64748B]">Process flows are deterministically synthesized from API routes, controllers, and service entry points.</span>
        </div>
      `;
      return;
    }

    container.innerHTML = '';

    processes.forEach((proc) => {
      // Find steps for this process
      const steps = allNodes.filter(n => n.process_id === proc.id).sort((a, b) => a.order - b.order);
      const transitions = allEdges.filter(e => e.process_id === proc.id);

      const card = document.createElement('div');
      card.className = 'bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-xs mb-4';

      card.innerHTML = `
        <div class="flex items-center justify-between pb-3 border-b border-[#E2E8F0] mb-4">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-base">⚡</span>
              <h3 class="text-sm font-bold text-[#0F172A]">${escapeHtml(proc.name)}</h3>
              <span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#FAF5FF] text-[#6D28D9] border border-[#DDD6FE]">${escapeHtml(proc.type || 'WORKFLOW')}</span>
            </div>
            <p class="text-xs text-[#64748B] mt-0.5">${escapeHtml(proc.description || 'Statically inferred deterministic execution flow')}</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#FFFBEB] text-[#B45309] border border-[#FDE68A]">
              STATICALLY INFERRED
            </span>
            <span class="text-xs text-[#64748B]">${steps.length} Steps</span>
          </div>
        </div>

        <div class="flex flex-col gap-0">
          ${steps.map((step, sIdx) => {
            const outTrans = transitions.find(t => t.source === step.id);
            const isEntry = sIdx === 0;
            const isTerminal = sIdx === steps.length - 1;
            const roleBadge = isEntry ? '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#E0F2FE] text-[#0369A1] border border-[#BAE6FD]">ENTRY POINT</span>' : (isTerminal ? '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#D1FAE5] text-[#047857] border border-[#A7F3D0]">TERMINAL</span>' : '');

            return `
              <div class="flex gap-4 items-stretch">
                <div class="flex flex-col items-center w-8 shrink-0">
                  <div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center font-bold text-xs shadow-xs shrink-0">
                    ${step.order}
                  </div>
                  ${!isTerminal ? `
                    <div class="flex-1 w-0.5 bg-[#CBD5E1] my-1"></div>
                  ` : ''}
                </div>

                <div class="flex-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3.5 mb-3">
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <strong class="text-xs font-bold text-[#0F172A]">${escapeHtml(step.name)}</strong>
                      <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">${step.type}</span>
                      ${roleBadge}
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-[11px] text-[#64748B]">Confidence: <strong class="text-[#0F172A]">${Math.round((step.confidence || 0.85)*100)}%</strong></span>
                      <button class="btn-inspect-step-graph px-2 py-0.5 rounded text-[10px] font-medium bg-white hover:bg-[#F1F5F9] border border-[#E2E8F0] text-[#0F172A] transition-colors" data-cid="${step.component_id}">Focus Graph</button>
                    </div>
                  </div>
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs bg-white p-2 rounded-lg border border-[#E2E8F0]">
                    <div><span class="text-[#64748B]">Component:</span> <code class="font-mono text-[#4F46E5]">${escapeHtml(step.component_name || step.name)}</code></div>
                    <div><span class="text-[#64748B]">Location:</span> <code class="font-mono text-[#64748B]">${escapeHtml(step.location || 'source')}</code></div>
                  </div>
                  ${outTrans ? `
                    <div class="mt-2 text-xs text-[#0284C7] flex items-center gap-1.5 font-medium">
                      <span>↳ ${escapeHtml(outTrans.relationship_type || 'CALLS')} transition</span>
                      <span class="text-[#64748B] text-[11px] font-normal">• ${escapeHtml(outTrans.condition || 'Deterministic call')}</span>
                    </div>
                  ` : ''}
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `;

      container.appendChild(card);
    });

    container.querySelectorAll('.btn-inspect-step-graph').forEach(btn => {
      btn.onclick = () => {
        if (btn.dataset.cid) {
          switchPrimaryView('architecture');
          switchArchSubtab('graph');
          setTimeout(() => focusOnNode(btn.dataset.cid), 100);
        }
      };
    });
  }

  // --- 9. Dependencies View (Dynamic Explorer) ---
  let selectedDepComponentId = null;

  async function loadDependenciesView() {
    if (!state.currentRepoId) return;

    // Load components and graph edges if not cached
    if (state.componentsList.length === 0) {
      try {
        const res = await fetch(`/repositories/${state.currentRepoId}/components?snapshot_id=${state.currentSnapshotId || ''}`);
        if (res.ok) {
          const d = await res.json();
          state.componentsList = d.components || [];
        }
      } catch (e) {}
    }

    if (state.edges.length === 0) {
      try {
        const gRes = await fetch(`/repositories/${state.currentRepoId}/graph?snapshot_id=${state.currentSnapshotId || ''}&level=2`);
        if (gRes.ok) {
          const gData = await gRes.json();
          state.rawGraph = gData;
          processGraphData(gData);
        }
      } catch (e) {}
    }

    // Populate dropdown with default "Select a component..." placeholder
    const select = document.getElementById('dep-component-select');
    if (select) {
      select.innerHTML = '<option value="">-- Select a component to explore --</option>';
      state.componentsList.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = `${c.name} (${c.type}) — ${c.location || ''}`;
        select.appendChild(opt);
      });

      select.onchange = (e) => {
        if (e.target.value) {
          selectDependencyComponent(e.target.value);
        } else {
          showDependencyEmptyState();
        }
      };
    }

    // Setup component search filter input
    const searchInput = document.getElementById('dep-search-input');
    if (searchInput) {
      searchInput.oninput = (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (select) {
          Array.from(select.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const matches = opt.textContent.toLowerCase().includes(query);
            opt.style.display = matches ? '' : 'none';
          });
        }
      };
    }

    // Setup depth slider
    const depthSlider = document.getElementById('dep-depth-slider');
    const depthVal = document.getElementById('dep-depth-val');
    if (depthSlider) {
      depthSlider.oninput = (e) => {
        if (depthVal) depthVal.textContent = e.target.value;
        if (selectedDepComponentId) {
          renderDependencyMatrix(selectedDepComponentId);
        }
      };
    }

    // Render Quick-Explore category chips (Most Connected, Isolated)
    renderDependencyQuickPicks();

    // If already has selection, keep it; otherwise show "Select a component" prompt
    if (selectedDepComponentId) {
      if (select) select.value = selectedDepComponentId;
      renderDependencyMatrix(selectedDepComponentId);
    } else {
      showDependencyEmptyState();
    }
  }

  function renderDependencyQuickPicks() {
    const bar = document.getElementById('dep-quick-pick-pills') || document.getElementById('dep-quick-pick-bar') || document.getElementById('dep-quick-picks-bar');
    if (!bar) return;

    // Calculate degree for all components
    const degreeMap = new Map();
    state.edges.forEach(e => {
      degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
      degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
    });

    const componentsWithDegree = state.componentsList.map(c => ({
      ...c,
      degree: degreeMap.get(c.id) || 0,
    }));

    // Most Connected (top 3)
    const mostConnected = [...componentsWithDegree].sort((a, b) => b.degree - a.degree).filter(c => c.degree > 0).slice(0, 3);

    // Isolated (degree === 0, top 2)
    const isolated = componentsWithDegree.filter(c => c.degree === 0).slice(0, 2);

    bar.innerHTML = `
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:6px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Quick Explore Categories:</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
        <span style="font-size:11px;color:var(--text-secondary);">Most Connected:</span>
        ${mostConnected.map(c => `
          <button class="chip-btn dep-pick-chip" data-cid="${c.id}" style="background:rgba(124,58,237,0.15);border:1px solid #7c3aed;color:#c084fc;font-size:11px;padding:3px 8px;border-radius:12px;cursor:pointer;">
            ${escapeHtml(c.name)} (${c.degree} links)
          </button>
        `).join('')}

        ${isolated.length > 0 ? `
          <span style="font-size:11px;color:var(--text-secondary);margin-left:8px;">Isolated:</span>
          ${isolated.map(c => `
            <button class="chip-btn dep-pick-chip" data-cid="${c.id}" style="background:rgba(100,116,139,0.15);border:1px solid #64748b;color:#94a3b8;font-size:11px;padding:3px 8px;border-radius:12px;cursor:pointer;">
              ${escapeHtml(c.name)} (0 links)
            </button>
          `).join('')}
        ` : ''}
      </div>
    `;

    bar.querySelectorAll('.dep-pick-chip').forEach(btn => {
      btn.onclick = () => {
        selectDependencyComponent(btn.dataset.cid);
      };
    });
  }

  function showDependencyEmptyState() {
    selectedDepComponentId = null;
    const select = document.getElementById('dep-component-select');
    if (select) select.value = '';

    const emptyBox = document.getElementById('dep-empty-selection');
    const content = document.getElementById('dep-matrix-content');
    if (emptyBox) emptyBox.style.display = 'block';
    if (content) content.style.display = 'none';
  }

  function selectDependencyComponent(componentId) {
    selectedDepComponentId = componentId;
    const select = document.getElementById('dep-component-select');
    if (select) select.value = componentId;

    const emptyBox = document.getElementById('dep-empty-selection');
    const content = document.getElementById('dep-matrix-content');
    if (emptyBox) emptyBox.style.display = 'none';
    if (content) content.style.display = 'block';

    renderDependencyMatrix(componentId);
  }

  function renderDependencyMatrix(componentId) {
    const inboundList = document.getElementById('dep-inbound-list');
    const outboundList = document.getElementById('dep-outbound-list');
    const inCount = document.getElementById('dep-inbound-count');
    const outCount = document.getElementById('dep-outbound-count');
    const focusContainer = document.getElementById('dep-center-body') || document.getElementById('dep-focus-component');
    const transCard = document.getElementById('dep-transitive-card');
    if (transCard) transCard.style.display = 'block';

    const incoming = state.edges.filter(e => e.target === componentId);
    const outgoing = state.edges.filter(e => e.source === componentId);

    if (inCount) inCount.textContent = `${incoming.length} callers`;
    if (outCount) outCount.textContent = `${outgoing.length} callees`;

    // Center Focus Component Card
    const comp = state.componentsList.find(c => c.id === componentId) || state.nodeMap.get(componentId) || { id: componentId, name: componentId, type: 'COMPONENT' };
    if (focusContainer) {
      focusContainer.innerHTML = `
        <div style="background:var(--bg-surface);border:2px solid #7c3aed;border-radius:8px;padding:16px;box-shadow:0 0 16px rgba(124,58,237,0.2);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span class="type-pill type-${comp.type || 'CLASS'}">${comp.type || 'COMPONENT'}</span>
            <span class="badge" style="background:rgba(6,182,212,0.15);color:#06b6d4;font-size:10px;">DIGITAL TWIN NODE</span>
          </div>
          <h3 style="font-size:16px;font-weight:700;color:#c084fc;margin:0 0 6px 0;">${escapeHtml(comp.name)}</h3>
          <div style="font-size:11px;color:var(--text-muted);font-family:monospace;word-break:break-all;margin-bottom:12px;">
            ${escapeHtml(comp.qualified_name || comp.location || comp.id)}
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px;background:var(--bg-secondary);padding:8px 12px;border-radius:6px;">
            <div>In-Degree: <strong style="color:#ef4444;">${incoming.length}</strong></div>
            <div>Out-Degree: <strong style="color:#38bdf8;">${outgoing.length}</strong></div>
          </div>
          <button id="btn-dep-focus-canvas" class="primary-btn" style="width:100%;margin-top:12px;font-size:11px;padding:6px 0;cursor:pointer;">
            Inspect in Architecture Canvas →
          </button>
        </div>
      `;

      document.getElementById('btn-dep-focus-canvas')?.addEventListener('click', () => {
        switchPrimaryView('architecture');
        switchArchSubtab('graph');
        setTimeout(() => focusOnNode(componentId), 100);
      });
    }

    if (inboundList) {
      inboundList.innerHTML = incoming.length > 0 ? incoming.map(e => `
        <div class="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] flex items-center justify-between mb-2">
          <div>
            <strong class="text-xs font-bold text-[#0F172A] flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[16px] text-[#4F46E5]">arrow_back</span>
              ${escapeHtml(e.sourceNode?.name || e.source)}
            </strong>
            <div class="text-[11px] text-[#64748B] mt-1">
              Evidence: <span class="font-mono text-[#0F172A]">${escapeHtml(e.evidence?.file || 'AST Call')}</span>
            </div>
          </div>
          <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">${e.type}</span>
        </div>
      `).join('') : '<div class="p-6 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-xl border border-dashed border-[#E2E8F0]">No direct inbound callers in snapshot.</div>';
    }

    if (outboundList) {
      outboundList.innerHTML = outgoing.length > 0 ? outgoing.map(e => `
        <div class="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] flex items-center justify-between mb-2">
          <div>
            <strong class="text-xs font-bold text-[#0F172A] flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[16px] text-[#0284C7]">arrow_forward</span>
              ${escapeHtml(e.targetNode?.name || e.target)}
            </strong>
            <div class="text-[11px] text-[#64748B] mt-1">
              Evidence: <span class="font-mono text-[#0F172A]">${escapeHtml(e.evidence?.file || 'AST Call')}</span>
            </div>
          </div>
          <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#F0F9FF] text-[#0284C7] border border-[#BAE6FD]">${e.type}</span>
        </div>
      `).join('') : '<div class="p-6 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-xl border border-dashed border-[#E2E8F0]">No direct outbound callees in snapshot.</div>';
    }

    // Transitive Dependencies (2 hops)
    const transList = document.getElementById('dep-transitive-list');
    if (transList) {
      const hop1Sources = new Set(incoming.map(e => e.source));
      const hop1Targets = new Set(outgoing.map(e => e.target));
      const hop2Sources = new Set();
      const hop2Targets = new Set();

      state.edges.forEach(e => {
        if (hop1Sources.has(e.target) && e.source !== componentId && !hop1Sources.has(e.source)) {
          hop2Sources.add(e.sourceNode?.name || e.source);
        }
        if (hop1Targets.has(e.source) && e.target !== componentId && !hop1Targets.has(e.target)) {
          hop2Targets.add(e.targetNode?.name || e.target);
        }
      });

      const totalTransitive = hop2Sources.size + hop2Targets.size;
      transList.innerHTML = totalTransitive > 0 ? `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:12px;">
          <div>
            <span style="font-weight:600;color:var(--text-secondary);">2-Hop Upstream Callers (${hop2Sources.size}):</span>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">
              ${Array.from(hop2Sources).map(s => `<span class="badge" style="background:var(--bg-surface);border:1px solid var(--border-color);color:#f59e0b;padding:2px 6px;">${escapeHtml(s)}</span>`).join('')}
            </div>
          </div>
          <div>
            <span style="font-weight:600;color:var(--text-secondary);">2-Hop Downstream Callees (${hop2Targets.size}):</span>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">
              ${Array.from(hop2Targets).map(t => `<span class="badge" style="background:var(--bg-surface);border:1px solid var(--border-color);color:#34d399;padding:2px 6px;">${escapeHtml(t)}</span>`).join('')}
            </div>
          </div>
        </div>
      ` : '<div style="font-size:12px;color:var(--text-muted);font-style:italic;">No 2-hop transitive relationships detected for this component.</div>';
    }
  }

  // --- 10. Tests & Verification View (Phase 6 Test Impact Intelligence) ---
  let currentTestImpactResult = null;

  async function loadTestsView() {
    if (!state.currentRepoId) return;

    // 1. Wire up Filter Tabs
    const tabs = document.querySelectorAll('.ti-tab-btn');
    tabs.forEach(t => {
      t.onclick = () => {
        tabs.forEach(b => {
          b.classList.remove('active', 'bg-[#F1F5F9]', 'text-[#0F172A]');
          b.classList.add('text-[#64748B]');
        });
        t.classList.add('active', 'bg-[#F1F5F9]', 'text-[#0F172A]');
        t.classList.remove('text-[#64748B]');

        const targetTab = t.dataset.tiTab;
        const panelAff = document.getElementById('ti-tab-panel-affected');
        const panelUnk = document.getElementById('ti-tab-panel-unknown');
        const panelUnaff = document.getElementById('ti-tab-panel-unaffected');
        const panelCat = document.getElementById('ti-tab-panel-catalog');

        if (panelAff) panelAff.style.display = targetTab === 'affected' ? 'block' : 'none';
        if (panelUnk) panelUnk.style.display = targetTab === 'unknown' ? 'block' : 'none';
        if (panelUnaff) panelUnaff.style.display = targetTab === 'unaffected' ? 'block' : 'none';
        if (panelCat) panelCat.style.display = targetTab === 'catalog' ? 'block' : 'none';
      };
    });

    // 2. Wire up Run Test Impact Button
    const runBtn = document.getElementById('btn-run-test-impact');
    if (runBtn) {
      runBtn.onclick = () => executeTestImpactAnalysis();
    }

    // 3. Load catalog and execute test impact
    await loadTestCatalog();
    await executeTestImpactAnalysis();
  }

  async function executeTestImpactAnalysis() {
    if (!state.currentRepoId) return;
    const banner = document.getElementById('ti-status-banner');
    if (banner) banner.textContent = 'Calculating test impact paths...';

    const affectedList = document.getElementById('ti-affected-tests-list');
    const unknownList = document.getElementById('ti-unknown-coverage-list');
    const unaffectedList = document.getElementById('ti-unaffected-tests-list');

    try {
      const payload = {
        target_snapshot_id: state.currentSnapshotId || (state.snapshots[0] ? state.snapshots[0].id : null),
        base_snapshot_id: state.diffSnapshotId || (state.snapshots[1] ? state.snapshots[1].id : null),
        max_depth: 6,
        include_indirect: true,
        include_unaffected: true,
      };

      if (!payload.target_snapshot_id) {
        if (banner) banner.textContent = 'No snapshots available for analysis.';
        return;
      }

      const res = await fetch(`/repositories/${state.currentRepoId}/test-impact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error('Test impact computation failed');
      }

      const data = await res.json();
      currentTestImpactResult = data;
      const s = data.summary || {};

      // Update metrics
      const elAff = document.getElementById('ti-metric-affected');
      const elDir = document.getElementById('ti-metric-direct');
      const elInd = document.getElementById('ti-metric-indirect');
      const elUna = document.getElementById('ti-metric-unaffected');
      const elUnk = document.getElementById('ti-metric-unknown');

      if (elAff) elAff.textContent = s.potentially_affected_count ?? 0;
      if (elDir) elDir.textContent = s.directly_affected_count ?? 0;
      if (elInd) elInd.textContent = s.indirectly_affected_count ?? 0;
      if (elUna) elUna.textContent = s.unaffected_count ?? 0;
      if (elUnk) elUnk.textContent = s.unknown_coverage_count ?? 0;

      // Update tab counts
      const tabAff = document.getElementById('ti-tab-count-affected');
      const tabUnk = document.getElementById('ti-tab-count-unknown');
      const tabUna = document.getElementById('ti-tab-count-unaffected');

      if (tabAff) tabAff.textContent = s.potentially_affected_count ?? 0;
      if (tabUnk) tabUnk.textContent = s.unknown_coverage_count ?? 0;
      if (tabUna) tabUna.textContent = s.unaffected_count ?? 0;

      if (banner) banner.textContent = `Completed in ${data.execution_time_ms} ms · ${s.potentially_affected_count} tests potentially affected`;

      // Render Affected Tests List
      if (affectedList) {
        const tests = data.affected_tests || [];
        if (tests.length === 0) {
          affectedList.innerHTML = `
            <div class="p-8 text-center bg-white border border-[#E2E8F0] rounded-xl text-xs text-[#059669]">
              <span class="material-symbols-outlined text-2xl text-[#10B981] mb-1">check_circle</span>
              <div class="font-bold text-[#0F172A]">All Mapped Tests Safe</div>
              <p class="text-[#64748B] mt-0.5">No existing tests are affected by changes in this snapshot comparison.</p>
            </div>
          `;
        } else {
          affectedList.innerHTML = tests.map(t => {
            const isDirect = t.classification === 'DIRECTLY_AFFECTED';
            const badgeClass = isDirect
              ? 'bg-[#FFE4E6] text-[#BE123C] border-[#FDA4AF]'
              : 'bg-[#EDE9FE] text-[#6D28D9] border-[#DDD6FE]';
            const badgeLabel = isDirect ? 'Directly Affected' : 'Indirectly Affected';

            // Path arrows
            const pathHtml = (t.impact_path && t.impact_path.length > 1) ? `
              <div class="mt-2.5 p-2.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg overflow-x-auto">
                <div class="text-[10px] uppercase font-bold text-[#64748B] mb-1.5 tracking-wider">Causal Propagation Path:</div>
                <div class="flex items-center gap-1.5 text-[11px] font-mono text-[#0F172A] whitespace-nowrap">
                  ${t.impact_path.map((node, i) => `
                    <span class="px-2 py-0.5 bg-white border border-[#E2E8F0] rounded text-[#0F172A] font-semibold">${escapeHtml(node)}</span>
                    ${i < t.impact_path.length - 1 ? `
                      <span class="text-[#94A3B8] font-bold">→</span>
                      <span class="px-1.5 py-0.5 rounded text-[10px] bg-[#EEF2FF] text-[#4F46E5] font-sans font-bold border border-[#C7D2FE]">${escapeHtml(t.relationships[i] || 'CALLS')}</span>
                      <span class="text-[#94A3B8] font-bold">→</span>
                    ` : ''}
                  `).join('')}
                </div>
              </div>
            ` : '';

            return `
              <div class="p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-2xs space-y-2 hover:border-[#CBD5E1] transition-colors">
                <div class="flex items-start justify-between gap-3">
                  <div class="space-y-0.5">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-bold text-xs text-[#0F172A] flex items-center gap-1">
                        <span>🧪</span> ${escapeHtml(t.test_name)}
                      </span>
                      <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeClass}">${badgeLabel}</span>
                      <span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">${escapeHtml(t.evidence_status)}</span>
                      <span class="text-[10px] text-[#64748B] font-mono">Depth: ${t.depth} hop${t.depth > 1 ? 's' : ''}</span>
                    </div>
                    <div class="text-[11px] font-mono text-[#64748B]">${escapeHtml(t.location)}</div>
                  </div>
                  <span class="text-[11px] text-[#059669] font-semibold bg-[#ECFDF5] px-2 py-0.5 rounded border border-[#A7F3D0] shrink-0">
                    Recommended Execution
                  </span>
                </div>
                <p class="text-xs text-[#475569] leading-relaxed">
                  <strong class="text-[#0F172A]">Why affected:</strong> ${escapeHtml(t.reason)}
                </p>
                ${pathHtml}
              </div>
            `;
          }).join('');
        }
      }

      // Render Unknown Coverage List
      if (unknownList) {
        const unks = data.unknown_coverage || [];
        if (unks.length === 0) {
          unknownList.innerHTML = `
            <div class="p-8 text-center bg-white border border-[#E2E8F0] rounded-xl text-xs text-[#059669]">
              <span class="material-symbols-outlined text-2xl text-[#10B981] mb-1">verified</span>
              <div class="font-bold text-[#0F172A]">100% Changed Entities Have Test Coverage</div>
              <p class="text-[#64748B] mt-0.5">Every modified, added, or removed component has corresponding tests mapped in the digital twin.</p>
            </div>
          `;
        } else {
          unknownList.innerHTML = unks.map(u => `
            <div class="p-4 bg-[#FFFBEB] border border-[#FDE68A] rounded-xl shadow-2xs space-y-1">
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-[#92400E] flex items-center gap-1.5">
                  <span class="material-symbols-outlined text-[16px] text-[#D97706]">warning</span>
                  ${escapeHtml(u.name)} (${escapeHtml(u.artifact_type)})
                </span>
                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#FEF3C7] text-[#B45309] border border-[#FDE68A]">${escapeHtml(u.change_type)}</span>
              </div>
              <div class="text-[11px] font-mono text-[#B45309]">${escapeHtml(u.location)}</div>
              <p class="text-xs text-[#78350F] mt-1">${escapeHtml(u.reason)}</p>
            </div>
          `).join('');
        }
      }

      // Render Unaffected Tests List
      if (unaffectedList) {
        const un = data.unaffected_tests || [];
        if (un.length === 0) {
          unaffectedList.innerHTML = '<div class="p-6 text-center text-xs text-[#64748B]">No unaffected tests in this snapshot.</div>';
        } else {
          unaffectedList.innerHTML = un.map(t => `
            <div class="p-3 bg-white border border-[#E2E8F0] rounded-lg flex items-center justify-between text-xs">
              <div class="flex items-center gap-2">
                <span class="text-[#10B981]">✓</span>
                <strong class="font-mono text-[#0F172A]">${escapeHtml(t.test_name)}</strong>
                <span class="text-[11px] text-[#64748B] font-mono">${escapeHtml(t.location)}</span>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">Unaffected</span>
            </div>
          `).join('');
        }
      }

    } catch (err) {
      if (banner) banner.textContent = `Analysis error: ${err.message}`;
    }
  }

  async function loadTestCatalog() {
    if (!state.currentRepoId) return;
    const tbody = document.getElementById('tests-table-body');
    if (!tbody) return;

    try {
      let url = `/repositories/${state.currentRepoId}/tests-catalog`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      const tests = data.tests || [];

      const countEl = document.getElementById('ti-tab-count-catalog');
      if (countEl) countEl.textContent = tests.length;

      if (tests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="p-6 text-center text-[#64748B]">No test specifications identified in snapshot.</td></tr>';
        return;
      }

      tbody.innerHTML = tests.map(t => {
        const tgHtml = (t.targets && t.targets.length > 0)
          ? t.targets.map(tg => `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#F0F9FF] text-[#0284C7] border border-[#BAE6FD] mr-1">${escapeHtml(tg.name)} (${escapeHtml(tg.relationship)})</span>`).join(' ')
          : '<span class="text-[#64748B] italic">No target component linked</span>';
        return `
          <tr class="hover:bg-[#F8FAFC] transition-colors">
            <td class="p-3.5 font-bold text-[#0F172A] flex items-center gap-1.5">
              <span>🧪</span> ${escapeHtml(t.name)}
            </td>
            <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#FEF3C7] text-[#B45309] border border-[#FDE68A]">${escapeHtml(t.artifact_type)}</span></td>
            <td class="p-3.5 font-mono text-[11px] text-[#475569]">${escapeHtml(t.location)}</td>
            <td class="p-3.5">${tgHtml}</td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="4" class="p-6 text-center text-[#64748B]">Error loading test catalog: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  // --- 11. Changes (Snapshot Diff & Impact Analysis) View ---
  let currentImpactAnalysisResult = null;

  function loadChangesView() {
    const diffBtn = document.getElementById('btn-compute-diff') || document.getElementById('btn-run-diff-action');
    if (diffBtn) {
      diffBtn.onclick = () => executeSnapshotDiff();
    }

    const impactBtn = document.getElementById('btn-run-impact-action');
    if (impactBtn) {
      impactBtn.onclick = () => executeChangeImpactAnalysis();
    }

    const viewGraphBtn = document.getElementById('btn-view-impact-graph');
    if (viewGraphBtn) {
      viewGraphBtn.onclick = () => projectImpactGraph();
    }

    const baseSelect = document.getElementById('diff-base-select');
    const targetSelect = document.getElementById('diff-target-select');

    if (baseSelect && targetSelect) {
      baseSelect.onchange = () => executeSnapshotDiff();
      targetSelect.onchange = () => executeSnapshotDiff();

      // Automatically execute snapshot diff if both base and target are selected
      if (baseSelect.value && targetSelect.value && baseSelect.value !== targetSelect.value) {
        executeSnapshotDiff();
      }
    }

    // Tab handlers in impact panel
    const tabPaths = document.getElementById('tab-impact-paths');
    const tabFindings = document.getElementById('tab-impact-findings');
    const tabCats = document.getElementById('tab-impact-categories');

    if (tabPaths && tabFindings && tabCats) {
      tabPaths.onclick = () => switchImpactTab('paths');
      tabFindings.onclick = () => switchImpactTab('findings');
      tabCats.onclick = () => switchImpactTab('categories');
    }
  }

  function switchImpactTab(activeTab) {
    const tabPaths = document.getElementById('tab-impact-paths');
    const tabFindings = document.getElementById('tab-impact-findings');
    const tabCats = document.getElementById('tab-impact-categories');

    const panePaths = document.getElementById('impact-pane-paths');
    const paneFindings = document.getElementById('impact-pane-findings');
    const paneCats = document.getElementById('impact-pane-categories');

    [tabPaths, tabFindings, tabCats].forEach(t => {
      if (t) {
        t.style.borderBottom = 'none';
        t.style.color = 'var(--text-secondary)';
        t.classList.remove('active');
      }
    });

    [panePaths, paneFindings, paneCats].forEach(p => {
      if (p) p.style.display = 'none';
    });

    if (activeTab === 'paths' && tabPaths && panePaths) {
      tabPaths.style.borderBottom = '2px solid #7c3aed';
      tabPaths.style.color = 'var(--text-primary)';
      tabPaths.classList.add('active');
      panePaths.style.display = 'block';
    } else if (activeTab === 'findings' && tabFindings && paneFindings) {
      tabFindings.style.borderBottom = '2px solid #7c3aed';
      tabFindings.style.color = 'var(--text-primary)';
      tabFindings.classList.add('active');
      paneFindings.style.display = 'block';
    } else if (activeTab === 'categories' && tabCats && paneCats) {
      tabCats.style.borderBottom = '2px solid #7c3aed';
      tabCats.style.color = 'var(--text-primary)';
      tabCats.classList.add('active');
      paneCats.style.display = 'block';
    }
  }

  async function executeChangeImpactAnalysis() {
    const baseSelect = document.getElementById('diff-base-select');
    const targetSelect = document.getElementById('diff-target-select');
    const depthInput = document.getElementById('impact-depth-input');
    const impactContainer = document.getElementById('impact-analysis-container');
    const diffTbody = document.getElementById('diff-table-body');
    const metaSpan = document.getElementById('impact-analysis-meta');

    if (!baseSelect || !targetSelect) return;
    const baseId = baseSelect.value;
    const targetId = targetSelect.value;
    const maxDepth = depthInput ? parseInt(depthInput.value, 10) || 5 : 5;

    if (!baseId || !targetId) {
      alert('Please select both Baseline (A) and Target (B) snapshots.');
      return;
    }

    if (impactContainer) {
      impactContainer.style.display = 'block';
    }
    if (metaSpan) {
      metaSpan.innerHTML = `<span style="color:#a78bfa;">Analyzing blast-radius traversal (depth ≤ ${maxDepth})...</span>`;
    }
    if (diffTbody) {
      diffTbody.innerHTML = '<tr><td colspan="5" class="td-loading">⚡ Running deterministic Change Impact & Blast Radius analysis...</td></tr>';
    }

    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/impact-analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_snapshot_id: baseId,
          target_snapshot_id: targetId,
          max_depth: maxDepth,
          include_tests: true,
          include_processes: true,
          include_apis: true,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Analysis failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      currentImpactAnalysisResult = data;

      // 1. Update Metrics
      const s = data.summary || {};
      document.getElementById('metric-impact-changed').textContent = s.changed || 0;
      document.getElementById('metric-impact-direct').textContent = s.directly_affected || 0;
      document.getElementById('metric-impact-indirect').textContent = s.indirectly_affected || 0;
      document.getElementById('metric-impact-components').textContent = s.affected_components || 0;
      document.getElementById('metric-impact-apis').textContent = s.affected_apis || 0;
      document.getElementById('metric-impact-processes').textContent = s.affected_processes || 0;
      document.getElementById('metric-impact-tests').textContent = s.affected_tests || 0;

      if (metaSpan) {
        metaSpan.innerHTML = `Analysis ID: <strong style="color:var(--text-primary);">${data.analysis_id}</strong> | Execution Time: <strong>${data.execution_time_ms} ms</strong> | Status: <strong style="color:#10b981;">COMPLETED</strong>`;
      }

      // 2. Render Changes into Diff Table
      if (diffTbody) {
        diffTbody.innerHTML = '';
        if (!data.changes || data.changes.length === 0) {
          diffTbody.innerHTML = '<tr><td colspan="5" class="td-empty">Zero structural changes detected between selected snapshots.</td></tr>';
        } else {
          data.changes.forEach(c => {
            const tr = document.createElement('tr');
            const statusClass = c.change_type === 'ADDED' ? 'diff-add' : (c.change_type === 'REMOVED' ? 'diff-del' : 'diff-mod');
            tr.innerHTML = `
              <td><span class="diff-tag ${statusClass}">${c.change_type}</span></td>
              <td>
                <a href="#" onclick="window.TwinApp.inspectNodeByName('${escapeHtml(c.qualified_name)}'); return false;" style="color:#38bdf8;text-decoration:none;font-weight:600;">
                  ${escapeHtml(c.qualified_name)}
                </a>
              </td>
              <td><span class="type-pill type-${c.artifact_type}">${c.artifact_type}</span></td>
              <td class="text-mono" style="font-size:11px;">${escapeHtml(c.source_file || '')}${c.line_start ? `:${c.line_start}-${c.line_end}` : ''}</td>
              <td style="font-size:11px;color:var(--text-secondary);">${escapeHtml(c.evidence?.[0] || c.detection_method)} (${c.is_symbol_level ? 'Symbol Level' : 'File Fallback'})</td>
            `;
            diffTbody.appendChild(tr);
          });
        }
      }

      // 3. Render Causal Impact Paths
      const pathsContainer = document.getElementById('impact-paths-tree');
      const pathsCount = document.getElementById('impact-paths-count');
      if (pathsCount) pathsCount.textContent = (data.paths || []).length;

      if (pathsContainer) {
        pathsContainer.innerHTML = '';
        if (!data.paths || data.paths.length === 0) {
          pathsContainer.innerHTML = '<div style="color:var(--text-muted);padding:16px;text-align:center;">No causal propagation paths identified. Changes do not ripple outward.</div>';
        } else {
          data.paths.forEach((p, idx) => {
            const card = document.createElement('div');
            card.style.cssText = 'background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px 14px;';

            let chainHtml = '';
            for (let i = 0; i < p.nodes.length; i++) {
              const nodeName = p.nodes[i];
              const isRoot = (i === 0);
              const isTarget = (i === p.nodes.length - 1);
              const nodeBg = isRoot ? '#f59e0b22' : (isTarget ? '#ef444422' : 'var(--bg-secondary)');
              const nodeColor = isRoot ? '#f59e0b' : (isTarget ? '#f87171' : '#38bdf8');

              chainHtml += `
                <span onclick="window.TwinApp.inspectNodeByName('${escapeHtml(nodeName)}')" style="cursor:pointer;background:${nodeBg};color:${nodeColor};padding:2px 8px;border-radius:4px;font-weight:600;font-size:11px;border:1px solid var(--border-color);">
                  ${escapeHtml(nodeName)}
                </span>
              `;
              if (i < p.relationships.length) {
                const rel = p.relationships[i] || 'IMPACTS';
                chainHtml += `<span style="color:#a78bfa;font-size:10px;font-weight:700;margin:0 4px;">--[${rel}]--></span>`;
              }
            }

            card.innerHTML = `
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <div style="display:flex;align-items:center;gap:8px;">
                  <span class="badge" style="background:#7c3aed22;color:#c084fc;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;">DEPTH ${p.depth}</span>
                  <span class="badge" style="background:var(--bg-secondary);color:var(--text-secondary);font-size:10px;padding:2px 6px;border-radius:3px;">${p.terminal_type}</span>
                </div>
                <span style="font-size:11px;color:#10b981;font-weight:600;">${(p.confidence * 100).toFixed(0)}% Confidence</span>
              </div>
              <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;margin-top:4px;">
                ${chainHtml}
              </div>
            `;
            pathsContainer.appendChild(card);
          });
        }
      }

      // 4. Render Evidence & Findings Table
      const findingsBody = document.getElementById('impact-findings-body');
      const findingsCount = document.getElementById('impact-findings-count');
      if (findingsCount) findingsCount.textContent = (data.findings || []).length;

      if (findingsBody) {
        findingsBody.innerHTML = '';
        if (!data.findings || data.findings.length === 0) {
          findingsBody.innerHTML = '<tr><td colspan="7" class="td-empty">Zero impact findings generated.</td></tr>';
        } else {
          data.findings.forEach(f => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td><span class="badge" style="background:${f.impact_level === 1 ? '#ef444422' : '#ec489922'};color:${f.impact_level === 1 ? '#ef4444' : '#ec4899'};font-size:10px;padding:2px 6px;">Level ${f.impact_level}</span></td>
              <td><a href="#" onclick="window.TwinApp.inspectNodeByName('${escapeHtml(f.source_qual_name)}'); return false;" style="color:#f59e0b;font-weight:600;text-decoration:none;">${escapeHtml(f.source_qual_name)}</a></td>
              <td><span style="font-family:var(--font-mono);font-size:11px;color:#c084fc;font-weight:700;">${f.relationship_type}</span></td>
              <td><a href="#" onclick="window.TwinApp.inspectNodeByName('${escapeHtml(f.target_qual_name)}'); return false;" style="color:#38bdf8;font-weight:600;text-decoration:none;">${escapeHtml(f.target_qual_name)}</a></td>
              <td><span class="type-pill type-${f.target_type}">${f.target_type}</span></td>
              <td style="color:#10b981;font-weight:600;">${(f.confidence * 100).toFixed(0)}%</td>
              <td style="font-size:11px;color:var(--text-secondary);max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(f.evidence.join(' \n'))}">
                ${escapeHtml(f.evidence[f.evidence.length - 1] || f.detection_method)}
              </td>
            `;
            findingsBody.appendChild(tr);
          });
        }
      }

      // 5. Render Affected Categories Grid
      const catGrid = document.getElementById('impact-categories-grid');
      if (catGrid) {
        catGrid.innerHTML = '';
        const cats = data.affected_categories || {};
        const catLabels = [
          { key: 'affected_components', title: 'Affected Components', color: '#38bdf8' },
          { key: 'affected_services', title: 'Affected Services', color: '#a78bfa' },
          { key: 'affected_apis', title: 'Affected APIs', color: '#f472b6' },
          { key: 'affected_processes', title: 'Affected Processes', color: '#818cf8' },
          { key: 'affected_tests', title: 'Affected Tests', color: '#10b981' },
          { key: 'affected_database_entities', title: 'Affected Database Entities', color: '#fb923c' },
        ];

        catLabels.forEach(cat => {
          const items = cats[cat.key] || [];
          const card = document.createElement('div');
          card.style.cssText = 'background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:12px;';
          card.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;border-bottom:1px solid var(--border-subtle);padding-bottom:6px;">
              <h4 style="font-size:12px;font-weight:700;color:${cat.color};text-transform:uppercase;">${cat.title}</h4>
              <span class="badge" style="background:${cat.color}22;color:${cat.color};font-weight:700;font-size:10px;padding:1px 6px;border-radius:3px;">${items.length}</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:4px;max-height:160px;overflow-y:auto;">
              ${items.length > 0 ? items.map(name => `
                <div onclick="window.TwinApp.inspectNodeByName('${escapeHtml(name)}')" style="cursor:pointer;font-family:var(--font-mono);font-size:11px;color:var(--text-primary);padding:3px 6px;background:var(--bg-secondary);border-radius:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(name)}">
                  • ${escapeHtml(name)}
                </div>
              `).join('') : '<div style="color:var(--text-muted);font-size:11px;">None identified.</div>'}
            </div>
          `;
          catGrid.appendChild(card);
        });
      }

    } catch (err) {
      if (metaSpan) {
        metaSpan.innerHTML = `<span style="color:#ef4444;">Error: ${escapeHtml(err.message)}</span>`;
      }
      if (diffTbody) {
        diffTbody.innerHTML = `<tr><td colspan="5" class="td-empty" style="color:#ef4444;">Analysis failed: ${escapeHtml(err.message)}</td></tr>`;
      }
    }
  }

  async function projectImpactGraph() {
    if (!currentImpactAnalysisResult || !currentImpactAnalysisResult.analysis_id) {
      alert('Please run a change impact analysis first.');
      return;
    }

    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/impact-analysis/${currentImpactAnalysisResult.analysis_id}/graph`);
      if (!res.ok) throw new Error('Failed to retrieve impact graph projection');
      const gData = await res.json();

      // Switch to Architecture view
      switchPrimaryView('architecture');

      // Process impact graph data into canvas
      state.rawGraph = gData;
      processGraphData(gData);
      updateStats(gData);

    } catch (err) {
      alert(`Could not project impact graph: ${err.message}`);
    }
  }

  function inspectNodeByName(nodeName) {
    if (!nodeName) return;
    // Check if node exists in state.nodeMap or state.nodes
    let node = state.nodeMap ? state.nodeMap.get(nodeName) : null;
    if (!node && state.nodes) {
      node = state.nodes.find(n => n.id === nodeName || n.name === nodeName || n.qualified_name === nodeName);
    }

    if (!node) {
      // Synthesize node item for inspector
      node = {
        id: nodeName,
        name: nodeName.split('.').pop() || nodeName,
        qualified_name: nodeName,
        type: nodeName.toLowerCase().includes('test') ? 'TEST_CASE' : (nodeName.includes('/') ? 'API_ENDPOINT' : 'COMPONENT'),
        file: 'source',
        line_start: 1,
        line_end: 1,
        confidence: 0.95,
        location: nodeName,
      };
    }

    inspectNode(node);
  }

  async function executeSnapshotDiff() {
    const baseSelect = document.getElementById('diff-base-select');
    const targetSelect = document.getElementById('diff-target-select');
    const banner = document.getElementById('diff-metrics-banner');
    const tbody = document.getElementById('diff-table-body');

    if (!baseSelect || !targetSelect || !tbody) return;
    const baseId = baseSelect.value;
    const targetId = targetSelect.value;

    if (!baseId || !targetId) {
      return;
    }

    tbody.innerHTML = '<tr><td colspan="5" class="td-loading">Calculating structural snapshot diff...</td></tr>';

    try {
      const url = `/repositories/${state.currentRepoId}/snapshot-diff?base_snapshot_id=${baseId}&target_snapshot_id=${targetId}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to compute diff');
      const data = await res.json();

      const summary = data.summary || {};
      const changes = data.changes || [];
      const added = summary.added || 0;
      const removed = summary.removed || 0;
      const modified = summary.modified || 0;

      if (banner) {
        banner.style.display = 'flex';
        banner.innerHTML = `
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">+${added} Added</span>
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-[#FFF1F2] text-[#BE123C] border border-[#FECDD3]">-${removed} Removed</span>
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-[#FFFBEB] text-[#B45309] border border-[#FDE68A]">~${modified} Modified</span>
          <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">${summary.total_changes || 0} Total Changed Artifacts</span>
        `;
      }

      tbody.innerHTML = '';
      if (changes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-[#64748B]">Zero structural differences detected between the selected snapshots.</td></tr>';
        return;
      }

      changes.forEach(n => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-[#F8FAFC] transition-colors';
        const cType = n.change_type || 'MODIFIED';
        const tagClass = cType === 'ADDED' ? 'bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]' : (cType === 'REMOVED' ? 'bg-[#FFF1F2] text-[#BE123C] border-[#FECDD3]' : 'bg-[#FFFBEB] text-[#B45309] border-[#FDE68A]');

        tr.innerHTML = `
          <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${tagClass}">${cType}</span></td>
          <td class="p-3.5 font-bold text-xs text-[#0F172A]">${escapeHtml(n.artifact_name || n.artifact_id)}</td>
          <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">${n.artifact_type}</span></td>
          <td class="p-3.5 font-mono text-xs text-[#64748B]">${escapeHtml(n.file_path || '')}${n.line_number ? `:${n.line_number}` : ''}</td>
          <td class="p-3.5 text-xs text-[#475569]">${escapeHtml(n.details || (cType === 'ADDED' ? 'New artifact discovered in target snapshot.' : (cType === 'REMOVED' ? 'Artifact absent in target snapshot.' : 'Signature or logic modified.')))}</td>
        `;
        tbody.appendChild(tr);
      });

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="td-empty">Error computing diff: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  // --- 12. Evidence & File Tree View ---
  async function loadEvidenceView() {
    if (!state.currentRepoId) return;
    const treeContainer = document.getElementById('evidence-tree-container');
    const overviewBox = document.getElementById('evidence-overview-state');
    const fileDetailsBox = document.getElementById('evidence-file-details');

    if (overviewBox) overviewBox.style.display = 'flex';
    if (fileDetailsBox) fileDetailsBox.style.display = 'none';

    if (!treeContainer) return;
    treeContainer.innerHTML = '<div class="tree-loading">Loading repository tree...</div>';

    try {
      let url = `/repositories/${state.currentRepoId}/file-tree`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to load file tree');
      const tree = await res.json();
      treeContainer.innerHTML = '';
      renderEvidenceTreeNode(tree, treeContainer);

    } catch (err) {
      treeContainer.innerHTML = `<div class="tree-loading">Error loading tree: ${escapeHtml(err.message)}</div>`;
    }
  }

  function renderEvidenceTreeNode(node, container, depth = 0) {
    if (!node) return;
    const item = document.createElement('div');
    item.className = 'tree-item';
    item.style.paddingLeft = `${depth * 14 + 6}px`;

    const icon = document.createElement('span');
    icon.className = 'tree-icon';
    icon.textContent = node.type === 'directory' ? '📁' : (node.is_test ? '🧪' : '📄');
    item.appendChild(icon);

    const name = document.createElement('span');
    name.textContent = node.name;
    item.appendChild(name);

    if (node.artifacts_count > 0) {
      const badge = document.createElement('span');
      badge.className = 'tree-badge';
      badge.textContent = `${node.artifacts_count} arts`;
      item.appendChild(badge);
    }

    item.addEventListener('click', (e) => {
      e.stopPropagation();
      document.querySelectorAll('#evidence-tree-container .tree-item').forEach(el => el.classList.remove('selected'));
      item.classList.add('selected');
      inspectEvidenceNode(node);
    });

    container.appendChild(item);

    if (node.children && Array.isArray(node.children)) {
      node.children.forEach(child => renderEvidenceTreeNode(child, container, depth + 1));
    }
  }

  function inspectEvidenceNode(node) {
    const overviewBox = document.getElementById('evidence-overview-state');
    const fileDetailsBox = document.getElementById('evidence-file-details');
    if (!fileDetailsBox) return;

    if (overviewBox) overviewBox.style.display = 'none';
    fileDetailsBox.style.display = 'block';

    if (node.type === 'directory') {
      fileDetailsBox.innerHTML = `
        <div class="evidence-card" style="background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:8px;padding:20px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:20px;">📁</span>
              <h3 style="font-size:16px;font-weight:700;color:var(--text-primary);margin:0;">${escapeHtml(node.name)}/</h3>
            </div>
            <button id="btn-ev-back" class="secondary-btn" style="font-size:11px;padding:4px 10px;cursor:pointer;">← Back to Overview</button>
          </div>
          <p style="font-size:12px;color:var(--text-secondary);margin-bottom:16px;">
            Directory Path: <code class="text-mono" style="color:#c084fc;">${escapeHtml(node.path || node.name)}</code>
          </p>
          <div style="font-size:12px;color:var(--text-muted);background:var(--bg-surface);padding:14px;border-radius:6px;">
            Expand this folder in the tree or select a child file to inspect verified AST symbols and localized lines.
          </div>
        </div>
      `;
      document.getElementById('btn-ev-back')?.addEventListener('click', () => {
        fileDetailsBox.style.display = 'none';
        if (overviewBox) overviewBox.style.display = 'flex';
      });
      return;
    }

    // File selected: Find localized symbols in rawGraph
    const fileSymbols = (state.rawGraph?.nodes || []).filter(n => {
      const nFile = n.file || '';
      return nFile === node.path || nFile.endsWith(node.name) || (node.path && nFile.includes(node.path));
    });

    const symbolIds = new Set(fileSymbols.map(s => s.id));
    const fileEdges = (state.rawGraph?.edges || []).filter(e => symbolIds.has(e.source) || symbolIds.has(e.target));

    const symbolsRows = fileSymbols.map(s => `
      <tr>
        <td><strong>${escapeHtml(s.name)}</strong></td>
        <td><span class="type-pill type-${s.type}">${s.type}</span></td>
        <td class="text-mono">${s.line_start || 1} - ${s.line_end || 1}</td>
        <td><span class="badge-evidence">DIRECT_AST</span></td>
        <td><span style="color:#10b981;font-weight:600;">100%</span></td>
        <td class="text-mono text-muted" style="font-size:10px;">${(s.signature_hash || s.id || '').slice(0, 10)}</td>
      </tr>
    `).join('');

    const edgesRows = fileEdges.slice(0, 8).map(e => `
      <tr>
        <td><span class="badge" style="font-size:10px;background:rgba(56,189,248,0.15);color:#38bdf8;">${e.type}</span></td>
        <td class="text-mono">${symbolIds.has(e.source) ? 'Outgoing →' : '← Incoming'}</td>
        <td><strong>${escapeHtml(symbolIds.has(e.source) ? (e.targetNode?.name || e.target) : (e.sourceNode?.name || e.source))}</strong></td>
        <td class="text-mono text-muted" style="font-size:11px;">${escapeHtml(e.evidence?.file || 'AST')}</td>
      </tr>
    `).join('');

    fileDetailsBox.innerHTML = `
      <div class="evidence-card" style="background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:8px;padding:20px;display:flex;flex-direction:column;gap:16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border-subtle);padding-bottom:12px;">
          <div>
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:20px;">${node.is_test ? '🧪' : '📄'}</span>
              <h3 style="font-size:16px;font-weight:700;color:var(--text-primary);margin:0;">${escapeHtml(node.name)}</h3>
              <span class="badge" style="background:rgba(6,182,212,0.15);color:#06b6d4;font-size:11px;padding:2px 8px;">
                ${escapeHtml(node.language || 'source').toUpperCase()}
              </span>
              ${node.is_test ? '<span class="badge" style="background:rgba(251,191,36,0.15);color:#fbbf24;font-size:11px;padding:2px 8px;">TEST SPECIFICATION</span>' : ''}
            </div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:4px;font-family:monospace;">
              ${escapeHtml(node.path || node.name)}
            </div>
          </div>
          <div style="display:flex;gap:8px;">
            <button id="btn-ev-back" class="secondary-btn" style="font-size:11px;padding:6px 12px;cursor:pointer;">← Evidence Overview</button>
            ${node.primary_artifact_id ? '<button id="btn-ev-focus" class="primary-btn" style="font-size:11px;padding:6px 12px;cursor:pointer;">Inspect in Graph →</button>' : ''}
          </div>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:10px;">
          <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Artifacts</div>
            <div style="font-size:18px;font-weight:700;color:#c084fc;">${node.artifacts_count || fileSymbols.length}</div>
          </div>
          <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Lines of Code</div>
            <div style="font-size:18px;font-weight:700;color:#38bdf8;">${node.line_count || '-'}</div>
          </div>
          <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Typed Edges</div>
            <div style="font-size:18px;font-weight:700;color:#34d399;">${fileEdges.length}</div>
          </div>
          <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Verification</div>
            <div style="font-size:14px;font-weight:700;color:#10b981;margin-top:3px;">VERIFIED</div>
          </div>
        </div>

        <!-- AST Symbols in this file -->
        <div style="margin-top:6px;">
          <h4 style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px;display:flex;align-items:center;gap:6px;">
            <span>⚡</span> Extracted AST Symbols (${fileSymbols.length})
          </h4>
          <div class="table-responsive" style="max-height:260px;overflow-y:auto;">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Symbol Name</th>
                  <th>Type</th>
                  <th>Lines</th>
                  <th>Evidence</th>
                  <th>Confidence</th>
                  <th>Signature Hash</th>
                </tr>
              </thead>
              <tbody>
                ${symbolsRows || '<tr><td colspan="6" class="td-empty">No low-level AST symbols extracted in this file.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>

        ${fileEdges.length > 0 ? `
          <div>
            <h4 style="font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px;display:flex;align-items:center;gap:6px;">
              <span>⇄</span> Structural Relationships (${fileEdges.length})
            </h4>
            <div class="table-responsive" style="max-height:200px;overflow-y:auto;">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Direction</th>
                    <th>Connected Target/Source</th>
                    <th>Source Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  ${edgesRows}
                </tbody>
              </table>
            </div>
          </div>
        ` : ''}
      </div>
    `;

    document.getElementById('btn-ev-back')?.addEventListener('click', () => {
      fileDetailsBox.style.display = 'none';
      if (overviewBox) overviewBox.style.display = 'flex';
    });

    document.getElementById('btn-ev-focus')?.addEventListener('click', () => {
      if (node.primary_artifact_id) {
        switchPrimaryView('architecture');
        switchArchSubtab('graph');
        setTimeout(() => focusOnNode(node.primary_artifact_id), 100);
      }
    });
  }

  // --- 13. File Tree for Graph Sidebar ---
  async function loadFileTree() {
    if (!state.currentRepoId) return;
    const treeContainer = document.getElementById('file-tree-container');
    if (!treeContainer) return;
    treeContainer.innerHTML = '<div class="tree-loading">Loading file structure...</div>';

    try {
      let url = `/repositories/${state.currentRepoId}/file-tree`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;
      const res = await fetch(url);
      if (res.ok) {
        const tree = await res.json();
        treeContainer.innerHTML = '';
        renderTreeNode(tree, treeContainer);
      }
    } catch (err) {
      treeContainer.innerHTML = '<div class="tree-loading">Unable to load file tree.</div>';
    }
  }

  function renderTreeNode(node, container, depth = 0) {
    if (!node) return;
    const item = document.createElement('div');
    item.className = 'tree-item';
    item.style.paddingLeft = `${depth * 14 + 6}px`;

    const icon = document.createElement('span');
    icon.className = 'tree-icon';
    icon.textContent = node.type === 'directory' ? '📁' : (node.is_test ? '🧪' : '📄');
    item.appendChild(icon);

    const name = document.createElement('span');
    name.textContent = node.name;
    item.appendChild(name);

    if (node.artifacts_count > 0) {
      const badge = document.createElement('span');
      badge.className = 'tree-badge';
      badge.textContent = `${node.artifacts_count} arts`;
      item.appendChild(badge);
    }

    item.addEventListener('click', (e) => {
      e.stopPropagation();
      document.querySelectorAll('#file-tree-container .tree-item').forEach(el => el.classList.remove('selected'));
      item.classList.add('selected');

      if (node.primary_artifact_id) {
        focusOnNode(node.primary_artifact_id);
      }
    });

    container.appendChild(item);

    if (node.children && Array.isArray(node.children)) {
      node.children.forEach(child => renderTreeNode(child, container, depth + 1));
    }
  }

  // --- 14. Graph Engine & Physics Simulation ---
  async function loadGraph() {
    if (!state.currentRepoId) return;

    let url = `/repositories/${state.currentRepoId}/graph?level=${state.currentLevel}&depth=${state.depth}`;
    if (state.currentSnapshotId) url += `&snapshot_id=${state.currentSnapshotId}`;
    if (state.focusNodeId) url += `&focus=${encodeURIComponent(state.focusNodeId)}`;
    if (state.impactMode && state.impactRootId) url += `&impact_artifact_id=${encodeURIComponent(state.impactRootId)}`;

    // Read checkboxes
    const testsCb = document.getElementById('toggle-tests');
    const extCb = document.getElementById('toggle-external');
    const incTests = testsCb ? testsCb.checked : true;
    const incExt = extCb ? extCb.checked : false;
    url += `&include_tests=${incTests}&include_external_dependencies=${incExt}`;

    const checkedTypes = Array.from(document.querySelectorAll('#type-filter-grid input:checked')).map(cb => cb.value);
    const checkedRels = Array.from(document.querySelectorAll('#rel-filter-grid input:checked')).map(cb => cb.value);
    const allTypesCount = document.querySelectorAll('#type-filter-grid input').length;
    const allRelsCount = document.querySelectorAll('#rel-filter-grid input').length;

    if (checkedTypes.length > 0 && checkedTypes.length < allTypesCount) {
      url += `&artifact_types=${encodeURIComponent(checkedTypes.join(','))}`;
    }
    if (checkedRels.length > 0 && checkedRels.length < allRelsCount) {
      url += `&relationship_types=${encodeURIComponent(checkedRels.join(','))}`;
    }

    try {
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        state.rawGraph = data;
        processGraphData(data);
        updateStats(data);
      }
    } catch (err) {
      console.error('Failed to load graph projection', err);
    }
  }

  function processGraphData(data) {
    state.nodeMap.clear();
    state.adjList.clear();

    const activeTypes = new Set(Array.from(document.querySelectorAll('#type-filter-grid input:checked')).map(cb => cb.value));
    const activeRels = new Set(Array.from(document.querySelectorAll('#rel-filter-grid input:checked')).map(cb => cb.value));

    const rawNodes = (data.nodes || []).filter(n => activeTypes.size === 0 || activeTypes.has(n.type));
    const rawEdges = (data.edges || []).filter(e => activeRels.size === 0 || activeRels.has(e.type));

    const existingPos = new Map();
    state.nodes.forEach(n => existingPos.set(n.id, { x: n.x, y: n.y, vx: n.vx, vy: n.vy }));

    // Prepare Nodes
    state.nodes = rawNodes.map((n, idx) => {
      const prev = existingPos.get(n.id);
      const angle = (idx / (rawNodes.length || 1)) * 2 * Math.PI;
      const radius = 180 + Math.random() * 120;
      return {
        ...n,
        x: prev ? prev.x : Math.cos(angle) * radius,
        y: prev ? prev.y : Math.sin(angle) * radius,
        vx: prev ? prev.vx : 0,
        vy: prev ? prev.vy : 0,
        radius: getNodeRadius(n.type, n.in_degree),
      };
    });

    state.nodes.forEach(n => {
      state.nodeMap.set(n.id, n);
      state.adjList.set(n.id, new Set());
    });

    // Prepare Edges
    state.edges = rawEdges.map(e => {
      if (state.adjList.has(e.source)) state.adjList.get(e.source).add(e.target);
      if (state.adjList.has(e.target)) state.adjList.get(e.target).add(e.source);
      return {
        ...e,
        sourceNode: state.nodeMap.get(e.source),
        targetNode: state.nodeMap.get(e.target),
      };
    }).filter(e => e.sourceNode && e.targetNode);

    // Track isolated nodes
    let isolatedCount = 0;
    const connectedNodeIds = new Set();
    state.edges.forEach(e => {
      connectedNodeIds.add(e.source);
      connectedNodeIds.add(e.target);
    });

    state.nodes.forEach(n => {
      if (!connectedNodeIds.has(n.id)) {
        isolatedCount++;
        n.is_isolated = true;
      } else {
        n.is_isolated = false;
      }
    });

    const isolatedCountEl = document.getElementById('isolated-count');
    if (isolatedCountEl) isolatedCountEl.textContent = isolatedCount;

    if (state.hideIsolated) {
      state.nodes = state.nodes.filter(n => !n.is_isolated);
      state.nodeMap.clear();
      state.nodes.forEach(n => state.nodeMap.set(n.id, n));
    }

    // If selected node still present, inspect it
    if (state.selectedNodeId && state.nodeMap.has(state.selectedNodeId)) {
      inspectNode(state.nodeMap.get(state.selectedNodeId));
    } else if (state.nodes.length > 0 && !state.selectedNodeId) {
      inspectNode(state.nodes[0]);
    }

    startPhysics();
    setTimeout(fitToScreen, 120);
  }

  function getNodeRadius(type, inDegree) {
    const base = {
      PACKAGE: 22,
      MODULE: 18,
      CLASS: 15,
      SERVICE: 16,
      API_ENDPOINT: 14,
      METHOD: 10,
      FUNCTION: 10,
      TEST_CASE: 11,
      DATABASE_TABLE: 14,
      EXTERNAL_DEPENDENCY: 9,
    }[type] || 12;
    return Math.min(32, base + Math.min(inDegree || 0, 8) * 1.2);
  }

  function updateStats(data) {
    const statNodes = document.getElementById('stat-nodes');
    const statEdges = document.getElementById('stat-edges');
    const statDrifts = document.getElementById('stat-drifts');
    if (statNodes) statNodes.textContent = (data.nodes || []).length;
    if (statEdges) statEdges.textContent = (data.edges || []).length;
    const driftCount = (data.edges || []).filter(e => e.is_drift).length;
    if (statDrifts) statDrifts.textContent = driftCount;

    if (data.branch_name) {
      const bEl = document.getElementById('branch-name');
      if (bEl) bEl.textContent = data.branch_name;
    }

    const banner = document.getElementById('graph-status-banner');
    if (banner) {
      if (state.impactMode) {
        banner.style.display = 'block';
        banner.textContent = '⚡ CHANGE IMPACT MODE: Propagating blast radius from root component.';
      } else if (state.currentArchSubtab === 'drift' && driftCount > 0) {
        banner.style.display = 'block';
        banner.textContent = `⚠️ ARCHITECTURE DRIFT: ${driftCount} active boundary violation(s) highlighted.`;
      } else {
        banner.style.display = 'none';
      }
    }
  }

  function startPhysics() {
    if (state.animFrameId) cancelAnimationFrame(state.animFrameId);
    let iterations = 0;

    function step() {
      if (state.physicsEnabled && iterations < 350) {
        tickPhysics();
        iterations++;
      }
      render();
      state.animFrameId = requestAnimationFrame(step);
    }
    state.animFrameId = requestAnimationFrame(step);
  }

  function tickPhysics() {
    const nodes = state.nodes;
    const edges = state.edges;
    const kRepel = 1200;
    const kAttract = 0.04;
    const damp = 0.88;

    // 1. Repulsion between all pairs
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distSq = dx * dx + dy * dy + 100;
        const dist = Math.sqrt(distSq);
        const force = kRepel / distSq;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        if (a !== state.draggedNode) {
          a.vx -= fx;
          a.vy -= fy;
        }
        if (b !== state.draggedNode) {
          b.vx += fx;
          b.vy += fy;
        }
      }
    }

    // 2. Spring attraction along edges
    for (let i = 0; i < edges.length; i++) {
      const e = edges[i];
      const a = e.sourceNode;
      const b = e.targetNode;
      if (!a || !b) continue;

      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const targetDist = 90;
      const delta = dist - targetDist;
      const force = delta * kAttract;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;

      if (a !== state.draggedNode) {
        a.vx += fx;
        a.vy += fy;
      }
      if (b !== state.draggedNode) {
        b.vx += fx;
        b.vy += fy;
      }
    }

    // 3. Center gravity & update position
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      if (n === state.draggedNode) continue;
      n.vx -= n.x * 0.003;
      n.vy -= n.y * 0.003;
      n.vx *= damp;
      n.vy *= damp;
      n.x += n.vx;
      n.y += n.vy;
    }
  }

  // --- Rendering (Canvas + Spotlight) ---
  function render() {
    if (!state.ctx) return;
    const ctx = state.ctx;
    ctx.clearRect(0, 0, state.width, state.height);

    ctx.save();
    ctx.translate(state.transform.x, state.transform.y);
    ctx.scale(state.transform.k, state.transform.k);

    const hasSpotlight = state.selectedNodeId !== null;
    const activeNeighborhood = new Set();
    if (hasSpotlight) {
      activeNeighborhood.add(state.selectedNodeId);
      const neighbors = state.adjList.get(state.selectedNodeId);
      if (neighbors) neighbors.forEach(n => activeNeighborhood.add(n));
    }

    // Draw Edges
    state.edges.forEach(e => {
      const a = e.sourceNode;
      const b = e.targetNode;
      if (!a || !b) return;

      const isConnected = !hasSpotlight || (activeNeighborhood.has(a.id) && activeNeighborhood.has(b.id));
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);

      if (e.id === state.selectedEdgeId) {
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 3.5;
        ctx.setLineDash([]);
      } else if (e.is_drift) {
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2.5;
        ctx.setLineDash([4, 4]);
      } else if (e.diff_status === 'NEW') {
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
      } else if (e.diff_status === 'REMOVED') {
        ctx.strokeStyle = '#f43f5e';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([2, 4]);
      } else {
        ctx.strokeStyle = isConnected ? 'rgba(100, 116, 139, 0.65)' : 'rgba(203, 213, 225, 0.25)';
        ctx.lineWidth = isConnected ? 1.4 : 0.8;
        ctx.setLineDash([]);
      }

      ctx.stroke();
      ctx.setLineDash([]);

      if (isConnected) {
        drawArrow(ctx, a.x, a.y, b.x, b.y, b.radius + 4, e.is_drift ? '#ef4444' : 'rgba(100, 116, 139, 0.8)');
      }
    });

    // Draw Nodes
    state.nodes.forEach(n => {
      const isSelected = n.id === state.selectedNodeId;
      const isDimmed = hasSpotlight && !activeNeighborhood.has(n.id);
      const isImpacted = n.is_impacted;

      ctx.save();
      ctx.globalAlpha = isDimmed ? 0.15 : 1.0;

      // Halo for Selected or Impacted nodes
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 6, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(0, 113, 227, 0.18)';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#0071e3';
        ctx.stroke();
      } else if (isImpacted) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 5, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(245, 158, 11, 0.2)';
        ctx.fill();
        ctx.lineWidth = 1.8;
        ctx.strokeStyle = '#f59e0b';
        ctx.stroke();
      }

      // Main Node Circle
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
      const color = state.colors[n.type] || state.colors.DEFAULT;
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = isSelected ? '#0071e3' : 'rgba(15, 23, 42, 0.15)';
      ctx.stroke();

      // Diff Status Indicators
      if (n.diff_status === 'ADDED') {
        drawBadge(ctx, n.x + n.radius - 2, n.y - n.radius + 2, '+', '#10b981');
      } else if (n.diff_status === 'REMOVED') {
        drawBadge(ctx, n.x + n.radius - 2, n.y - n.radius + 2, '-', '#ef4444');
      } else if (n.diff_status === 'MODIFIED') {
        drawBadge(ctx, n.x + n.radius - 2, n.y - n.radius + 2, '~', '#f59e0b');
      }

      // Node Label
      if (!isDimmed || state.transform.k > 1.2) {
        ctx.fillStyle = isSelected ? '#0071e3' : '#0f172a';
        ctx.font = `${isSelected ? '600 ' : '500 '}${Math.max(10, 11 / state.transform.k)}px 'Inter', sans-serif`;
        ctx.textAlign = 'center';
        ctx.fillText(n.name, n.x, n.y + n.radius + 12);
      }

      ctx.restore();
    });

    ctx.restore();
    renderMinimap();
  }

  function drawArrow(ctx, fromX, fromY, toX, toY, offset, color) {
    const dx = toX - fromX;
    const dy = toY - fromY;
    const angle = Math.atan2(dy, dx);
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < offset + 10) return;

    const targetX = toX - Math.cos(angle) * offset;
    const targetY = toY - Math.sin(angle) * offset;
    const headLen = 6;

    ctx.beginPath();
    ctx.moveTo(targetX, targetY);
    ctx.lineTo(targetX - headLen * Math.cos(angle - Math.PI / 6), targetY - headLen * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(targetX - headLen * Math.cos(angle + Math.PI / 6), targetY - headLen * Math.sin(angle + Math.PI / 6));
    ctx.fillStyle = color;
    ctx.fill();
  }

  function drawBadge(ctx, x, y, char, bg) {
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, 2 * Math.PI);
    ctx.fillStyle = bg;
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 9px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(char, x, y);
  }

  function renderMinimap() {
    const mmCanvas = document.getElementById('minimap-canvas');
    if (!mmCanvas) return;
    const mmCtx = mmCanvas.getContext('2d');
    mmCtx.clearRect(0, 0, mmCanvas.width, mmCanvas.height);

    if (state.nodes.length === 0) return;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    state.nodes.forEach(n => {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y);
      maxY = Math.max(maxY, n.y);
    });

    const pad = 80;
    const gW = Math.max(10, maxX - minX + pad * 2);
    const gH = Math.max(10, maxY - minY + pad * 2);
    const scale = Math.min(mmCanvas.width / gW, mmCanvas.height / gH);

    mmCtx.save();
    mmCtx.translate(mmCanvas.width / 2, mmCanvas.height / 2);
    mmCtx.scale(scale, scale);
    mmCtx.translate(-(minX + maxX) / 2, -(minY + maxY) / 2);

    state.nodes.forEach(n => {
      mmCtx.beginPath();
      mmCtx.arc(n.x, n.y, 4, 0, 2 * Math.PI);
      mmCtx.fillStyle = state.colors[n.type] || '#94a3b8';
      mmCtx.fill();
    });

    const vpLeft = (-state.transform.x) / state.transform.k;
    const vpTop = (-state.transform.y) / state.transform.k;
    const vpW = state.width / state.transform.k;
    const vpH = state.height / state.transform.k;

    mmCtx.strokeStyle = '#06b6d4';
    mmCtx.lineWidth = 2 / scale;
    mmCtx.strokeRect(vpLeft, vpTop, vpW, vpH);

    mmCtx.restore();
  }

  // --- Inspector Panels ---
  function inspectNode(node) {
    state.selectedNodeId = node.id;
    const focusPill = document.getElementById('focus-info-pill');
    const focusName = document.getElementById('focus-name');
    const resetFocusBtn = document.getElementById('reset-focus-btn');
    if (focusPill) focusPill.style.display = 'inline';
    if (focusName) focusName.textContent = node.name;
    if (resetFocusBtn) resetFocusBtn.style.display = 'inline-flex';

    const panel = document.getElementById('inspector-content');
    if (!panel) return;
    const incoming = state.edges.filter(e => e.target === node.id);
    const outgoing = state.edges.filter(e => e.source === node.id);
    const relatedTests = incoming.concat(outgoing).filter(e => e.type === 'TESTS' || e.sourceNode?.type === 'TEST_CASE');

    panel.innerHTML = `
      <div class="inspector-badge-row">
        <span class="inspector-badge" style="background:${state.colors[node.type]}22; color:${state.colors[node.type]}">${node.type}</span>
        <span class="inspector-badge layer-badge">${node.logical_layer || 'CORE'}</span>
        ${node.diff_status && node.diff_status !== 'UNCHANGED' ? `<span class="inspector-badge" style="background:#10b98122; color:#10b981">${node.diff_status}</span>` : ''}
      </div>

      <div class="inspector-section">
        <h4 class="sec-title">Identity & Source Location</h4>
        <table class="prop-table">
          <tr><td class="prop-key">Name:</td><td class="prop-val">${escapeHtml(node.name)}</td></tr>
          <tr><td class="prop-key">Qualified:</td><td class="prop-val">${escapeHtml(node.qualified_name || node.name)}</td></tr>
          <tr><td class="prop-key">Language:</td><td class="prop-val">${node.language || 'Python'}</td></tr>
          <tr><td class="prop-key">File:</td><td class="prop-val">${escapeHtml(node.file || 'unknown')}</td></tr>
          <tr><td class="prop-key">Lines:</td><td class="prop-val">${node.line_start || 1} - ${node.line_end || 1}</td></tr>
          <tr><td class="prop-key">Confidence:</td><td class="prop-val">${((node.confidence || 1.0) * 100).toFixed(0)}%</td></tr>
        </table>
      </div>

      ${node.is_impacted ? `
        <div class="impact-hero-card">
          <div style="font-size:11px; font-weight:700; color:var(--accent-amber)">IMPACT BLAST RADIUS PROPAGATION</div>
          <div class="impact-score-num">Depth ${node.impact_depth}</div>
          <ul class="impact-list">
            ${(node.impact_reasons || []).map(r => `<li>• ${escapeHtml(r)}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      <div class="inspector-section">
        <h4 class="sec-title">Dependencies (${incoming.length} in / ${outgoing.length} out)</h4>
        <table class="prop-table">
          <tr><td class="prop-key">Callers:</td><td class="prop-val">${incoming.map(e => e.sourceNode?.name).join(', ') || 'None'}</td></tr>
          <tr><td class="prop-key">Calls/Uses:</td><td class="prop-val">${outgoing.map(e => e.targetNode?.name).join(', ') || 'None'}</td></tr>
        </table>
      </div>

      <div class="inspector-section">
        <h4 class="sec-title">Validated Tests (${relatedTests.length})</h4>
        <div style="font-size:11px; font-family:var(--font-mono); color:var(--text-secondary)">
          ${relatedTests.length > 0 ? relatedTests.map(t => `<div>🧪 ${escapeHtml(t.sourceNode?.name || t.targetNode?.name)}</div>`).join('') : '<div style="color:var(--text-muted)">No direct test mapping attached.</div>'}
        </div>
      </div>

      <div class="inspector-section">
        <h4 class="sec-title">Verified Evidence (Digital Twin)</h4>
        <div class="code-snippet-box">${escapeHtml(node.location || `${node.file}:${node.line_start || 1}`)}</div>
      </div>

      <div style="margin-top:16px;">
        <button id="btn-run-impact" class="primary-btn" style="width:100%; background:var(--accent-amber)">Run Change Impact Analysis</button>
      </div>
    `;

    document.getElementById('btn-run-impact')?.addEventListener('click', () => {
      triggerImpactAnalysis(node.id);
    });
  }

  function inspectEdge(edge) {
    state.selectedEdgeId = edge.id;
    const panel = document.getElementById('inspector-content');
    if (!panel) return;
    panel.innerHTML = `
      <div class="inspector-badge-row">
        <span class="inspector-badge" style="background:#6366f122; color:#6366f1">${edge.type}</span>
        ${edge.is_drift ? `<span class="inspector-badge" style="background:#ef444422; color:#ef4444">DRIFT VIOLATION</span>` : ''}
      </div>

      ${edge.is_drift ? `
        <div class="drift-alert-box">
          <div class="drift-alert-title">⚠️ ${escapeHtml(edge.drift_details?.category || 'LAYER_VIOLATION')} (${edge.drift_details?.severity || 'HIGH'})</div>
          <div style="font-size:11px; color:#cbd5e1; margin-bottom:6px;">${escapeHtml(edge.drift_details?.expected_rule || 'Boundary violation')}</div>
          <div class="code-snippet-box" style="color:#ef4444">${escapeHtml(edge.drift_details?.actual_evidence || '')}</div>
        </div>
      ` : ''}

      <div class="inspector-section">
        <h4 class="sec-title">Relationship Path</h4>
        <table class="prop-table">
          <tr><td class="prop-key">Source:</td><td class="prop-val">${escapeHtml(edge.sourceNode?.name || edge.source)}</td></tr>
          <tr><td class="prop-key">Target:</td><td class="prop-val">${escapeHtml(edge.targetNode?.name || edge.target)}</td></tr>
          <tr><td class="prop-key">Semantic:</td><td class="prop-val">${edge.type}</td></tr>
          <tr><td class="prop-key">Detection:</td><td class="prop-val">${edge.detection_method || 'ast_call_expression'}</td></tr>
          <tr><td class="prop-key">Confidence:</td><td class="prop-val">${((edge.confidence || 1.0) * 100).toFixed(0)}%</td></tr>
        </table>
      </div>

      <div class="inspector-section">
        <h4 class="sec-title">Source Evidence</h4>
        <div style="font-size:11px; color:var(--text-muted)">Location: ${escapeHtml(edge.evidence?.file || '')}:${edge.evidence?.line || 1}</div>
        <div class="code-snippet-box">${escapeHtml(edge.evidence?.snippet || '')}</div>
      </div>
    `;
  }

  function triggerImpactAnalysis(rootArtifactId) {
    state.impactMode = true;
    state.impactRootId = rootArtifactId;
    const impactBtn = document.getElementById('impact-mode-btn');
    if (impactBtn) impactBtn.classList.add('active');
    loadGraph();
  }

  function focusOnNode(nodeId) {
    const node = state.nodeMap.get(nodeId);
    if (!node) {
      state.focusNodeId = nodeId;
      loadGraph();
      return;
    }
    state.selectedNodeId = node.id;
    state.transform.x = state.width / 2 - node.x * state.transform.k;
    state.transform.y = state.height / 2 - node.y * state.transform.k;
    inspectNode(node);
  }

  function switchSidebarTab(tabName) {
    document.querySelectorAll('.sb-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.sb-panel').forEach(p => p.classList.remove('active'));
    const targetTab = document.querySelector(`[data-sb-tab="${tabName}"]`);
    const targetPanel = document.getElementById(`sb-panel-${tabName}`);
    if (targetTab) targetTab.classList.add('active');
    if (targetPanel) targetPanel.classList.add('active');
  }

  function zoomBy(factor) {
    state.transform.k *= factor;
  }

  function fitToScreen() {
    if (state.nodes.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    state.nodes.forEach(n => {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y);
      maxY = Math.max(maxY, n.y);
    });

    const pad = 60;
    const gW = Math.max(50, maxX - minX + pad * 2);
    const gH = Math.max(50, maxY - minY + pad * 2);
    const scale = Math.min(state.width / gW, state.height / gH, 1.8);

    state.transform.k = scale;
    state.transform.x = state.width / 2 - ((minX + maxX) / 2) * scale;
    state.transform.y = state.height / 2 - ((minY + maxY) / 2) * scale;
  }

  function distToSegment(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lenSq = dx * dx + dy * dy;
    if (lenSq === 0) return Math.hypot(px - x1, py - y1);
    let t = ((px - x1) * dx + (py - y1) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
  }

  // --- Event Listeners Initialization ---
  function initEventListeners() {
    const canvas = state.canvas;
    if (!canvas) return;

    // Controls
    document.getElementById('zoom-in-btn')?.addEventListener('click', () => zoomBy(1.25));
    document.getElementById('zoom-out-btn')?.addEventListener('click', () => zoomBy(0.8));
    document.getElementById('fit-screen-btn')?.addEventListener('click', fitToScreen);
    document.getElementById('btn-fit-view')?.addEventListener('click', fitToScreen);
    const onToggleIsolated = () => {
      state.hideIsolated = !state.hideIsolated;
      document.getElementById('toggle-isolated-btn')?.classList.toggle('active', state.hideIsolated);
      document.getElementById('btn-toggle-isolated')?.classList.toggle('active', state.hideIsolated);
      processGraphData(state.rawGraph);
    };
    document.getElementById('toggle-isolated-btn')?.addEventListener('click', onToggleIsolated);
    document.getElementById('btn-toggle-isolated')?.addEventListener('click', onToggleIsolated);
    document.getElementById('toggle-physics-btn')?.addEventListener('click', () => {
      state.physicsEnabled = !state.physicsEnabled;
      document.getElementById('toggle-physics-btn')?.classList.toggle('active', state.physicsEnabled);
    });

    document.getElementById('impact-mode-btn')?.addEventListener('click', () => {
      state.impactMode = !state.impactMode;
      document.getElementById('impact-mode-btn')?.classList.toggle('active', state.impactMode);
      if (!state.impactMode) {
        state.impactRootId = null;
      } else if (state.selectedNodeId) {
        state.impactRootId = state.selectedNodeId;
      }
      loadGraph();
    });

    document.getElementById('reset-focus-btn')?.addEventListener('click', () => {
      state.selectedNodeId = null;
      state.focusNodeId = null;
      state.impactMode = false;
      document.getElementById('impact-mode-btn')?.classList.remove('active');
      const focusPill = document.getElementById('focus-info-pill');
      const resetBtn = document.getElementById('reset-focus-btn');
      if (focusPill) focusPill.style.display = 'none';
      if (resetBtn) resetBtn.style.display = 'none';
      loadGraph();
    });

    // Theme Toggle
    document.getElementById('theme-toggle-btn')?.addEventListener('click', () => {
      document.body.classList.toggle('theme-light');
      document.body.classList.toggle('theme-dark');
    });

    // Filter Buttons
    document.getElementById('reset-filters-btn')?.addEventListener('click', () => {
      document.querySelectorAll('#type-filter-grid input').forEach(cb => cb.checked = true);
      document.querySelectorAll('#rel-filter-grid input').forEach(cb => cb.checked = true);
      const testsCb = document.getElementById('toggle-tests');
      const extCb = document.getElementById('toggle-external');
      if (testsCb) testsCb.checked = true;
      if (extCb) extCb.checked = false;
      loadGraph();
    });

    document.querySelectorAll('#type-filter-grid input, #rel-filter-grid input').forEach(cb => {
      cb.addEventListener('change', () => loadGraph());
    });

    // Close Inspector
    document.getElementById('close-inspector-btn')?.addEventListener('click', () => {
      const sbRight = document.getElementById('sidebar-right');
      if (sbRight) sbRight.style.display = 'none';
    });

    // Search Input for File Tree
    const searchInput = document.getElementById('tree-search-input');
    const clearSearchBtn = document.getElementById('clear-search-btn');

    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        const q = e.target.value.trim().toLowerCase();
        document.querySelectorAll('#file-tree-container .tree-item').forEach(item => {
          if (!q) {
            item.style.display = 'flex';
          } else {
            const txt = item.textContent.toLowerCase();
            item.style.display = txt.includes(q) ? 'flex' : 'none';
          }
        });

        if (q) {
          const match = state.nodes.find(n =>
            (n.name && n.name.toLowerCase().includes(q)) ||
            (n.qualified_name && n.qualified_name.toLowerCase().includes(q)) ||
            (n.file && n.file.toLowerCase().includes(q))
          );
          if (match) {
            state.selectedNodeId = match.id;
            inspectNode(match);
          }
        }
      });
    }

    if (clearSearchBtn) {
      clearSearchBtn.addEventListener('click', () => {
        if (searchInput) {
          searchInput.value = '';
          document.querySelectorAll('#file-tree-container .tree-item').forEach(item => item.style.display = 'flex');
          searchInput.focus();
        }
      });
    }

    // Canvas Pan & Zoom
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
      const mouseX = e.clientX - canvas.getBoundingClientRect().left;
      const mouseY = e.clientY - canvas.getBoundingClientRect().top;

      state.transform.x = mouseX - (mouseX - state.transform.x) * zoomFactor;
      state.transform.y = mouseY - (mouseY - state.transform.y) * zoomFactor;
      state.transform.k *= zoomFactor;
    });

    canvas.addEventListener('mousedown', (e) => {
      const mouseX = (e.clientX - canvas.getBoundingClientRect().left - state.transform.x) / state.transform.k;
      const mouseY = (e.clientY - canvas.getBoundingClientRect().top - state.transform.y) / state.transform.k;

      // Check node hit
      const hitNode = state.nodes.find(n => {
        const dx = n.x - mouseX;
        const dy = n.y - mouseY;
        return dx * dx + dy * dy <= n.radius * n.radius;
      });

      if (hitNode) {
        state.draggedNode = hitNode;
        state.selectedEdgeId = null;
        const sbRight = document.getElementById('sidebar-right');
        if (sbRight) sbRight.style.display = 'flex';
        inspectNode(hitNode);
      } else {
        // Check edge hit
        const hitEdge = state.edges.find(edge => {
          if (!edge.sourceNode || !edge.targetNode) return false;
          const dist = distToSegment(mouseX, mouseY, edge.sourceNode.x, edge.sourceNode.y, edge.targetNode.x, edge.targetNode.y);
          return dist <= 8 / Math.min(1.5, Math.max(0.5, state.transform.k));
        });

        if (hitEdge) {
          state.selectedEdgeId = hitEdge.id;
          state.selectedNodeId = null;
          const sbRight = document.getElementById('sidebar-right');
          if (sbRight) sbRight.style.display = 'flex';
          inspectEdge(hitEdge);
        } else {
          state.isDraggingCanvas = true;
          state.dragStart.x = e.clientX - state.transform.x;
          state.dragStart.y = e.clientY - state.transform.y;
        }
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (state.draggedNode) {
        const mouseX = (e.clientX - canvas.getBoundingClientRect().left - state.transform.x) / state.transform.k;
        const mouseY = (e.clientY - canvas.getBoundingClientRect().top - state.transform.y) / state.transform.k;
        state.draggedNode.x = mouseX;
        state.draggedNode.y = mouseY;
        state.draggedNode.vx = 0;
        state.draggedNode.vy = 0;
      } else if (state.isDraggingCanvas) {
        state.transform.x = e.clientX - state.dragStart.x;
        state.transform.y = e.clientY - state.dragStart.y;
      }
    });

    window.addEventListener('mouseup', () => {
      state.draggedNode = null;
      state.isDraggingCanvas = false;
    });
  }

  // --- Phase 5: Runtime Evidence & Incident Intelligence ---
  let runtimeFilters = {
    eventType: '',
    severity: '',
    env: '',
    service: '',
    trace: '',
    limit: 50,
    offset: 0
  };

  async function loadRuntimeView() {
    if (!state.currentRepoId) return;
    const tbody = document.getElementById('runtime-table-body') || document.getElementById('runtime-events-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="p-6 text-center text-[#64748B]">Querying runtime evidence repository...</td></tr>';

    try {
      let queryParams = new URLSearchParams();
      if (state.currentSnapshotId) queryParams.set('snapshot_id', state.currentSnapshotId);
      if (runtimeFilters.eventType) queryParams.set('event_type', runtimeFilters.eventType);
      if (runtimeFilters.severity) queryParams.set('severity', runtimeFilters.severity);
      if (runtimeFilters.env) queryParams.set('environment', runtimeFilters.env);
      if (runtimeFilters.service) queryParams.set('service_name', runtimeFilters.service);
      if (runtimeFilters.trace) queryParams.set('trace_id', runtimeFilters.trace);
      queryParams.set('limit', String(runtimeFilters.limit));
      queryParams.set('offset', String(runtimeFilters.offset));

      const res = await fetch(`/repositories/${state.currentRepoId}/runtime-events?${queryParams.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch runtime events');
      const data = await res.json();

      const totalEl = document.getElementById('metric-runtime-total');
      const corrEl = document.getElementById('metric-runtime-correlated');
      const errEl = document.getElementById('metric-runtime-errors');
      const srvEl = document.getElementById('metric-runtime-services');
      const countEl = document.getElementById('runtime-count-display');

      if (totalEl) totalEl.textContent = data.total ?? 0;
      if (countEl) countEl.textContent = `${data.total ?? 0} events`;

      const events = data.events || [];
      const correlatedCount = events.filter(e => e.component_artifact_id).length;
      const errorCount = events.filter(e => e.severity === 'ERROR' || e.severity === 'CRITICAL' || e.event_type === 'ERROR' || e.event_type === 'EXCEPTION').length;
      const uniqueServices = new Set(events.map(e => e.service_name).filter(Boolean)).size;

      if (corrEl) corrEl.textContent = correlatedCount;
      if (errEl) errEl.textContent = errorCount;
      if (srvEl) srvEl.textContent = uniqueServices;

      if (events.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="p-8 text-center text-[#64748B]">
              <div class="text-2xl mb-2">📡</div>
              <p class="font-bold text-sm text-[#0F172A] mb-1">No runtime evidence recorded yet</p>
              <p class="text-xs text-[#64748B] max-w-md mx-auto mb-4">
                Runtime evidence connects observed telemetry (logs, errors, traces) with structural Digital Twin entities.
              </p>
              <button class="px-3.5 py-1.5 rounded-lg bg-[#0071e3] hover:bg-[#0059b5] text-white text-xs font-semibold shadow-xs" onclick="window.TwinApp.openIngestModal();">+ Ingest Telemetry</button>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = events.map(evt => {
        const isCrit = evt.severity === 'CRITICAL' || evt.severity === 'ERROR';
        const sevBadge = isCrit
          ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FFF1F2] text-[#BE123C] border border-[#FECDD3]">${escapeHtml(evt.severity || 'ERROR')}</span>`
          : `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#F0F9FF] text-[#0369A1] border border-[#BAE6FD]">${escapeHtml(evt.severity || 'INFO')}</span>`;

        const hasCorrelation = !!evt.component_artifact_id;
        const corrBadge = hasCorrelation ?
          `<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">
            ✓ ${escapeHtml(evt.correlated_artifact_name || evt.component_artifact_id.slice(0, 8))} (${Math.round((evt.confidence || 0.85)*100)}%)
          </span>` :
          `<span class="px-2 py-0.5 rounded text-[10px] bg-[#F1F5F9] text-[#64748B] border border-[#E2E8F0]">Uncorrelated</span>`;

        const timeStr = evt.timestamp ? new Date(evt.timestamp).toISOString().replace('T', ' ').slice(0, 19) : '-';
        const msgStr = evt.message || (evt.attributes ? JSON.stringify(evt.attributes) : '-');

        return `
          <tr class="hover:bg-[#F8FAFC] transition-colors">
            <td class="p-3.5">${sevBadge}</td>
            <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">${escapeHtml(evt.event_type)}</span></td>
            <td class="p-3.5 font-mono text-xs text-[#64748B] whitespace-nowrap">${escapeHtml(timeStr)}</td>
            <td class="p-3.5 font-bold text-xs text-[#0F172A]">${escapeHtml(evt.service_name || '-')} <span class="font-normal text-[#64748B]">(${escapeHtml(evt.environment || 'prod')})</span></td>
            <td class="p-3.5">${corrBadge}</td>
            <td class="p-3.5 font-mono text-xs text-[#7C3AED]">${escapeHtml(evt.trace_id || evt.span_id || '-')}</td>
            <td class="p-3.5 text-xs text-[#475569] max-w-xs truncate" title="${escapeHtml(msgStr)}">${escapeHtml(msgStr)}</td>
          </tr>
        `;
      }).join('');

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="td-empty" style="color:#ef4444;">Error loading runtime events: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  async function loadIncidentsView() {
    if (!state.currentRepoId) return;
    const tbody = document.getElementById('incidents-table-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="td-loading">Loading tracked incidents...</td></tr>';

    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/incidents`);
      if (!res.ok) throw new Error('Failed to load incidents');
      const incidents = await res.json();

      const countBadge = document.getElementById('incidents-count-badge');
      if (countBadge) countBadge.textContent = `${incidents.length} INCIDENTS`;

      if (incidents.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="td-empty" style="padding:32px;text-align:center;">
              <div style="font-size:28px;margin-bottom:8px;">🛡️</div>
              <p style="font-weight:600;color:var(--text-primary);margin-bottom:4px;">No active incidents recorded</p>
              <p style="font-size:12px;color:var(--text-secondary);max-width:500px;margin:0 auto 12px auto;">
                Declare a production or staging incident to trigger deterministic causal investigation against recent changes, runtime telemetry, and the Digital Twin process graph.
              </p>
              <button class="primary-btn" onclick="document.getElementById('modal-create-incident').style.display='flex';" style="font-size:12px;padding:6px 14px;background:#ef4444;">+ Declare Incident</button>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = incidents.map(inc => {
        const isCrit = inc.severity === 'critical' || inc.severity === 'high';
        const sevBadge = isCrit
          ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FFF1F2] text-[#BE123C] border border-[#FECDD3]">${escapeHtml(inc.severity.toUpperCase())}</span>`
          : `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FFFBEB] text-[#B45309] border border-[#FDE68A]">${escapeHtml(inc.severity.toUpperCase())}</span>`;
        const timeStr = inc.detected_at ? new Date(inc.detected_at).toISOString().replace('T', ' ').slice(0, 19) : '-';
        const evCount = inc.evidence_ids ? inc.evidence_ids.length : 0;

        return `
          <tr class="hover:bg-[#F8FAFC] transition-colors">
            <td class="p-3.5">${sevBadge}</td>
            <td class="p-3.5">
              <div class="font-bold text-xs text-[#0F172A]">${escapeHtml(inc.title)}</div>
              ${inc.description ? `<p class="text-[11px] text-[#64748B] mt-0.5 leading-snug">${escapeHtml(inc.description)}</p>` : ''}
              <div class="text-[10px] text-[#94A3B8] font-mono mt-1">Env: ${escapeHtml(inc.environment || 'production')}</div>
            </td>
            <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">${escapeHtml(inc.status.toUpperCase())}</span></td>
            <td class="p-3.5 font-mono text-xs text-[#64748B]">${escapeHtml(timeStr)}</td>
            <td class="p-3.5">${inc.affected_component_name ? `<span class="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[#FAF5FF] text-[#6D28D9] border border-[#DDD6FE]">${escapeHtml(inc.affected_component_name)}</span>` : '<span class="text-xs text-[#94A3B8]">Unassigned</span>'}</td>
            <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-medium bg-[#F0F9FF] text-[#0284C7] border border-[#BAE6FD]">${evCount} events</span></td>
            <td class="p-3.5">
              <button class="btn-investigate-incident px-2.5 py-1.5 rounded-lg bg-[#4F46E5] hover:bg-[#4338CA] text-white text-xs font-semibold shadow-xs transition-all flex items-center gap-1" data-iid="${inc.id}">
                <span>⚡ Causal Paths</span>
              </button>
            </td>
          </tr>
        `;
      }).join('');

      tbody.querySelectorAll('.btn-investigate-incident').forEach(btn => {
        btn.onclick = () => investigateIncident(btn.dataset.iid);
      });

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="td-empty" style="color:#ef4444;">Error loading incidents: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  async function investigateIncident(incidentId) {
    if (!state.currentRepoId || !incidentId) return;
    const ws = document.getElementById('incident-investigation-workspace');
    const container = document.getElementById('investigation-report-container');
    if (!ws || !container) return;

    ws.style.display = 'block';
    container.innerHTML = `
      <div style="text-align:center;padding:24px;">
        <span class="spinner-small"></span>
        <div style="margin-top:8px;font-size:13px;color:var(--text-secondary);">Executing deterministic investigation engine... Correlating evidence, recent changes, call chains, and processes...</div>
      </div>
    `;

    ws.scrollIntoView({ behavior: 'smooth' });

    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/incidents/${incidentId}/investigate`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Investigation failed: ' + (await res.text()));
      const inv = await res.json();

      renderInvestigationResult(inv);
    } catch (err) {
      container.innerHTML = `
        <div class="error-banner">
          <strong>Investigation Error:</strong> ${escapeHtml(err.message)}
        </div>
      `;
    }
  }

  function renderInvestigationResult(inv) {
    const container = document.getElementById('investigation-report-container');
    if (!container) return;

    const inc = inv.incident;
    const sevColor = inc.severity === 'critical' ? '#ef4444' : (inc.severity === 'high' ? '#f97316' : (inc.severity === 'medium' ? '#fbbf24' : '#38bdf8'));

    const observedEv = inv.observed_evidence || [];
    const recentChanges = inv.candidate_recent_changes || [];
    const affectedProcs = inv.affected_processes || [];
    const causalPaths = inv.candidate_causal_paths || [];
    const relatedTests = inv.related_tests || [];
    const uncertainties = inv.uncertainties || [];

    container.innerHTML = `
      <!-- Header -->
      <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--border-subtle);padding-bottom:14px;margin-bottom:16px;">
        <div>
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:20px;">🎯</span>
            <h3 style="font-size:16px;font-weight:700;color:var(--text-primary);margin:0;">
              Investigation: ${escapeHtml(inc.title)}
            </h3>
            <span class="badge" style="background:${sevColor}22;color:${sevColor};font-size:11px;font-weight:700;padding:2px 8px;">
              ${escapeHtml(inc.severity.toUpperCase())}
            </span>
            <span class="badge" style="background:rgba(124,58,237,0.15);color:#c084fc;font-size:11px;padding:2px 8px;">
              Candidate Causal Paths Generated
            </span>
          </div>
          <div style="font-size:12px;color:var(--text-secondary);margin-top:6px;">
            Repository ID: <code class="text-mono">${escapeHtml(inv.repository_id)}</code> • Snapshot: <code class="text-mono">${escapeHtml(inv.snapshot_id || 'latest')}</code>
          </div>
        </div>
        <button class="secondary-btn" id="btn-reinvestigate-action" style="font-size:11px;padding:6px 12px;">
          ↻ Re-Investigate
        </button>
      </div>

      <!-- Investigation Metrics Strip -->
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:10px;margin-bottom:18px;">
        <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:600;">Observed Events</div>
          <div style="font-size:20px;font-weight:700;color:#38bdf8;margin-top:2px;">${observedEv.length}</div>
        </div>
        <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:600;">Affected Entities</div>
          <div style="font-size:20px;font-weight:700;color:#10b981;margin-top:2px;">${inv.affected_entities.length}</div>
        </div>
        <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:600;">Candidate Changes</div>
          <div style="font-size:20px;font-weight:700;color:#f59e0b;margin-top:2px;">${recentChanges.length}</div>
        </div>
        <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:600;">Affected Processes</div>
          <div style="font-size:20px;font-weight:700;color:#a78bfa;margin-top:2px;">${affectedProcs.length}</div>
        </div>
        <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:600;">Causal Paths</div>
          <div style="font-size:20px;font-weight:700;color:#c084fc;margin-top:2px;">${causalPaths.length}</div>
        </div>
        <div class="metric-card" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center;">
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:600;">Related Tests</div>
          <div style="font-size:20px;font-weight:700;color:#34d399;margin-top:2px;">${relatedTests.length}</div>
        </div>
      </div>

      <!-- Section: Candidate Causal Paths -->
      <div style="margin-bottom:20px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
          <h4 style="font-size:13px;font-weight:700;color:var(--text-primary);letter-spacing:0.5px;text-transform:uppercase;margin:0;">
            CANDIDATE CAUSAL PATHS (EVIDENCE-BACKED)
          </h4>
          <span class="badge" style="background:rgba(245,158,11,0.15);color:#f59e0b;font-size:10px;padding:2px 8px;">
            Deterministic Static & Evidence Correlation
          </span>
        </div>
        <p style="font-size:12px;color:var(--text-secondary);margin:0 0 12px 0;">
          <strong>Architectural Guarantee:</strong> Paths represent evidence-backed candidate relationships derived from runtime error signatures, snapshot diffs, and AST call graphs. The system reports <em>potentially related based on evidence paths</em> rather than asserting unverified root cause truth.
        </p>

        ${causalPaths.length === 0 ? `
          <div style="background:var(--bg-surface);border:1px dashed var(--border-color);border-radius:6px;padding:16px;text-align:center;font-size:12px;color:var(--text-muted);">
            No candidate causal paths could be established. Ingest runtime events with service/file/symbol attributes matching the codebase to generate deterministic correlations.
          </div>
        ` : causalPaths.map((cp, idx) => `
          <div class="causal-path-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <div style="display:flex;align-items:center;gap:8px;">
                <span class="badge" style="background:#7c3aed;color:#fff;font-weight:700;font-size:11px;padding:2px 8px;">PATH #${idx + 1}</span>
                <span style="font-size:12px;font-weight:600;color:var(--text-primary);">${escapeHtml(cp.relationship || 'CALLS_INTO')}</span>
              </div>
              <div style="font-size:11px;color:var(--text-muted);">
                Evidence Confidence: <strong style="color:#10b981;">${Math.round((cp.confidence || 0.85)*100)}%</strong>
              </div>
            </div>

            <!-- Causal Flow Steps -->
            <div class="causal-flow-diagram">
              <div class="causal-step-node">
                <span style="color:#ef4444;font-size:10px;font-weight:700;">INCIDENT EVENT</span>
                <strong>${escapeHtml(cp.runtime_event_type || 'ERROR')}</strong>
                <span class="text-mono text-muted">${escapeHtml(cp.runtime_event_id ? cp.runtime_event_id.slice(0, 8) : 'event')}</span>
              </div>
              <div class="causal-step-arrow">↳</div>
              <div class="causal-step-node">
                <span style="color:#38bdf8;font-size:10px;font-weight:700;">AFFECTED COMPONENT</span>
                <strong>${escapeHtml(cp.component_name || 'Component')}</strong>
                <span class="text-mono text-muted">${escapeHtml(cp.component_id ? cp.component_id.slice(0, 8) : '-')}</span>
              </div>
              ${cp.change_id ? `
                <div class="causal-step-arrow">↳</div>
                <div class="causal-step-node">
                  <span style="color:#f59e0b;font-size:10px;font-weight:700;">RECENT CHANGE</span>
                  <strong>${escapeHtml(cp.change_type || 'MODIFIED')}</strong>
                  <span class="text-mono text-muted">${escapeHtml(cp.change_id.slice(0, 8))}</span>
                </div>
              ` : ''}
              ${cp.process_id ? `
                <div class="causal-step-arrow">↳</div>
                <div class="causal-step-node">
                  <span style="color:#a78bfa;font-size:10px;font-weight:700;">PROCESS FLOW</span>
                  <strong>${escapeHtml(cp.process_name || 'Workflow')}</strong>
                </div>
              ` : ''}
            </div>

            <div style="font-size:12px;color:var(--text-secondary);line-height:1.5;">
              ${escapeHtml(cp.explanation || 'Evidence path established across call graph and change detection.')}
            </div>
          </div>
        `).join('')}
      </div>

      <!-- Two-Column Breakdown: Observed Evidence & Recent Changes -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px;">
        <!-- Observed Evidence -->
        <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:12px;">
          <h4 style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;margin:0 0 8px 0;">
            Observed Evidence (${observedEv.length})
          </h4>
          ${observedEv.length === 0 ? '<div style="font-size:11px;color:var(--text-muted);">No linked runtime events</div>' : `
            <div style="display:flex;flex-direction:column;gap:6px;max-height:220px;overflow-y:auto;">
              ${observedEv.map(e => `
                <div style="background:var(--bg-secondary);padding:6px 8px;border-radius:4px;font-size:11px;">
                  <div style="display:flex;justify-content:space-between;color:var(--text-primary);font-weight:600;">
                    <span>${escapeHtml(e.event_type)} [${escapeHtml(e.severity)}]</span>
                    <span class="text-mono" style="color:var(--text-muted);">${escapeHtml(e.timestamp ? new Date(e.timestamp).toISOString().slice(11, 19) : '')}</span>
                  </div>
                  <div style="color:var(--text-secondary);margin-top:2px;">${escapeHtml(e.message || '-')}</div>
                  ${e.trace_id ? `<div class="text-mono" style="color:#a78bfa;font-size:10px;">trace: ${escapeHtml(e.trace_id)}</div>` : ''}
                </div>
              `).join('')}
            </div>
          `}
        </div>

        <!-- Candidate Recent Changes -->
        <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:12px;">
          <h4 style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;margin:0 0 8px 0;">
            Candidate Recent Changes (${recentChanges.length})
          </h4>
          ${recentChanges.length === 0 ? '<div style="font-size:11px;color:var(--text-muted);">No recent changes detected in prior snapshot</div>' : `
            <div style="display:flex;flex-direction:column;gap:6px;max-height:220px;overflow-y:auto;">
              ${recentChanges.map(c => `
                <div style="background:var(--bg-secondary);padding:6px 8px;border-radius:4px;font-size:11px;">
                  <div style="display:flex;justify-content:space-between;color:var(--text-primary);font-weight:600;">
                    <span style="color:#f59e0b;">${escapeHtml(c.change_type || 'CHANGE')}</span>
                    <span class="text-mono" style="color:var(--text-muted);">${escapeHtml(c.file_path || '')}</span>
                  </div>
                  <div style="color:var(--text-secondary);margin-top:2px;">Symbol: <code>${escapeHtml(c.symbol_name || c.artifact_id || '-')}</code></div>
                </div>
              `).join('')}
            </div>
          `}
        </div>
      </div>

      <!-- Affected Processes & Related Tests -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px;">
        <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:12px;">
          <h4 style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;margin:0 0 8px 0;">
            Affected Processes (${affectedProcs.length})
          </h4>
          ${affectedProcs.length === 0 ? '<div style="font-size:11px;color:var(--text-muted);">No process workflows intersect this component</div>' : `
            <div style="display:flex;flex-direction:column;gap:6px;">
              ${affectedProcs.map(p => `
                <div style="background:var(--bg-secondary);padding:6px 8px;border-radius:4px;font-size:11px;display:flex;justify-content:space-between;align-items:center;">
                  <strong>⚡ ${escapeHtml(p.name || p.id)}</strong>
                  <span class="badge" style="background:rgba(167,139,250,0.15);color:#a78bfa;font-size:10px;">${escapeHtml(p.type || 'WORKFLOW')}</span>
                </div>
              `).join('')}
            </div>
          `}
        </div>

        <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:12px;">
          <h4 style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;margin:0 0 8px 0;">
            Related Tests (${relatedTests.length})
          </h4>
          ${relatedTests.length === 0 ? '<div style="font-size:11px;color:var(--text-muted);">No test suites directly cover affected component</div>' : `
            <div style="display:flex;flex-direction:column;gap:6px;max-height:180px;overflow-y:auto;">
              ${relatedTests.map(t => `
                <div style="background:var(--bg-secondary);padding:6px 8px;border-radius:4px;font-size:11px;display:flex;justify-content:space-between;align-items:center;">
                  <span>🧪 ${escapeHtml(t.name || t.id)}</span>
                  <span class="badge" style="background:rgba(16,185,129,0.15);color:#10b981;font-size:10px;">Impacted Test</span>
                </div>
              `).join('')}
            </div>
          `}
        </div>
      </div>

      <!-- Section: Uncertainties & Evidence Limitations -->
      <div class="uncertainty-box">
        <strong style="color:#ef4444;text-transform:uppercase;font-size:11px;letter-spacing:0.5px;">
          ⚠️ Uncertainties & Evidence Limitations
        </strong>
        <ul>
          ${uncertainties.map(u => `<li>${escapeHtml(u)}</li>`).join('')}
        </ul>
      </div>
    `;

    document.getElementById('btn-reinvestigate-action')?.addEventListener('click', () => {
      investigateIncident(inc.id);
    });
  }

  function initPhase5Handlers() {
    // Process discovery button
    const discBtn = document.getElementById('btn-discover-processes');
    if (discBtn) {
      discBtn.addEventListener('click', async () => {
        if (!state.currentRepoId) return;
        discBtn.disabled = true;
        discBtn.textContent = '⚡ Discovering...';
        try {
          const res = await fetch(`/repositories/${state.currentRepoId}/processes/discover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ snapshot_id: state.currentSnapshotId || null })
          });
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          alert(`Process Discovery Completed: Found ${data.processes_discovered} workflows, ${data.steps_created} steps, ${data.transitions_created} transitions.`);
          loadProcessesView();
        } catch (err) {
          alert('Process discovery failed: ' + err.message);
        } finally {
          discBtn.disabled = false;
          discBtn.textContent = '⚡ Run Process Discovery';
        }
      });
    }

    // Ingest Runtime modal
    const openIngestBtn = document.getElementById('btn-open-ingest-modal');
    const modalIngest = document.getElementById('modal-ingest-runtime');
    const closeIngestBtn = document.getElementById('modal-ingest-close-btn');
    const cancelIngestBtn = document.getElementById('modal-ingest-cancel-btn');
    const submitIngestBtn = document.getElementById('modal-ingest-submit-btn');

    if (openIngestBtn && modalIngest) {
      openIngestBtn.addEventListener('click', () => modalIngest.style.display = 'flex');
      closeIngestBtn?.addEventListener('click', () => modalIngest.style.display = 'none');
      cancelIngestBtn?.addEventListener('click', () => modalIngest.style.display = 'none');

      submitIngestBtn?.addEventListener('click', async () => {
        if (!state.currentRepoId) return;
        const env = document.getElementById('input-ingest-env')?.value || 'production';
        const fileInput = document.getElementById('input-ingest-file');
        const rawJson = document.getElementById('input-ingest-json')?.value || '';
        const statusBox = document.getElementById('ingest-status-box');
        const errorBox = document.getElementById('ingest-error-box');

        if (statusBox) statusBox.style.display = 'none';
        if (errorBox) errorBox.style.display = 'none';

        let eventsList = [];

        try {
          if (fileInput?.files?.length) {
            const file = fileInput.files[0];
            const text = await file.text();
            if (file.name.endsWith('.jsonl')) {
              eventsList = text.trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
            } else {
              const parsed = JSON.parse(text);
              eventsList = Array.isArray(parsed) ? parsed : [parsed];
            }
          } else if (rawJson.trim()) {
            const trimmed = rawJson.trim();
            if (trimmed.startsWith('[')) {
              eventsList = JSON.parse(trimmed);
            } else if (trimmed.startsWith('{')) {
              if (trimmed.includes('\n')) {
                eventsList = trimmed.split('\n').filter(Boolean).map(line => JSON.parse(line));
              } else {
                eventsList = [JSON.parse(trimmed)];
              }
            } else {
              throw new Error('Please enter valid JSON or JSONL format');
            }
          } else {
            throw new Error('Please select a file or paste runtime events');
          }

          submitIngestBtn.disabled = true;
          submitIngestBtn.textContent = 'Ingesting...';

          const res = await fetch(`/repositories/${state.currentRepoId}/runtime-events/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              events: eventsList,
              environment: env,
              snapshot_id: state.currentSnapshotId || null
            })
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(errData.detail || 'Ingestion failed');
          }

          const resData = await res.json();
          modalIngest.style.display = 'none';
          alert(`Runtime Ingestion Complete: ${resData.ingested_count} ingested, ${resData.correlated_count} correlated, ${resData.redacted_count} fields redacted.`);
          loadRuntimeView();

        } catch (err) {
          if (errorBox) {
            errorBox.style.display = 'block';
            errorBox.textContent = err.message;
          } else {
            alert(err.message);
          }
        } finally {
          submitIngestBtn.disabled = false;
          submitIngestBtn.textContent = 'Ingest & Correlate';
        }
      });
    }

    // Runtime filter controls
    document.getElementById('btn-apply-runtime-filters')?.addEventListener('click', () => {
      runtimeFilters.eventType = document.getElementById('runtime-filter-event-type')?.value || '';
      runtimeFilters.severity = document.getElementById('runtime-filter-severity')?.value || '';
      runtimeFilters.env = document.getElementById('runtime-filter-env')?.value || '';
      runtimeFilters.service = document.getElementById('runtime-filter-service')?.value || '';
      runtimeFilters.trace = document.getElementById('runtime-filter-trace')?.value || '';
      loadRuntimeView();
    });

    document.getElementById('btn-reset-runtime-filters')?.addEventListener('click', () => {
      if (document.getElementById('runtime-filter-event-type')) document.getElementById('runtime-filter-event-type').value = '';
      if (document.getElementById('runtime-filter-severity')) document.getElementById('runtime-filter-severity').value = '';
      if (document.getElementById('runtime-filter-env')) document.getElementById('runtime-filter-env').value = '';
      if (document.getElementById('runtime-filter-service')) document.getElementById('runtime-filter-service').value = '';
      if (document.getElementById('runtime-filter-trace')) document.getElementById('runtime-filter-trace').value = '';
      runtimeFilters = { eventType: '', severity: '', env: '', service: '', trace: '', limit: 50, offset: 0 };
      loadRuntimeView();
    });

    document.getElementById('btn-refresh-runtime')?.addEventListener('click', () => loadRuntimeView());
    document.getElementById('btn-refresh-incidents')?.addEventListener('click', () => loadIncidentsView());

    // Create Incident modal
    const openIncBtn = document.getElementById('btn-open-create-incident-modal');
    const modalInc = document.getElementById('modal-create-incident');
    const closeIncBtn = document.getElementById('modal-incident-close-btn');
    const cancelIncBtn = document.getElementById('modal-incident-cancel-btn');
    const submitIncBtn = document.getElementById('modal-incident-submit-btn');

    if (openIncBtn && modalInc) {
      openIncBtn.addEventListener('click', () => modalInc.style.display = 'flex');
      closeIncBtn?.addEventListener('click', () => modalInc.style.display = 'none');
      cancelIncBtn?.addEventListener('click', () => modalInc.style.display = 'none');

      submitIncBtn?.addEventListener('click', async () => {
        if (!state.currentRepoId) return;
        const title = document.getElementById('input-incident-title')?.value || '';
        const severity = document.getElementById('input-incident-severity')?.value || 'high';
        const env = document.getElementById('input-incident-env')?.value || 'production';
        const component = document.getElementById('input-incident-component')?.value || null;
        const desc = document.getElementById('input-incident-desc')?.value || '';
        const errorBox = document.getElementById('incident-error-box');

        if (!title.trim()) {
          if (errorBox) {
            errorBox.style.display = 'block';
            errorBox.textContent = 'Incident title is required';
          }
          return;
        }

        submitIncBtn.disabled = true;
        submitIncBtn.textContent = 'Declaring...';

        try {
          const res = await fetch(`/repositories/${state.currentRepoId}/incidents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title,
              severity,
              environment: env,
              affected_component_name: component,
              description: desc,
              snapshot_id: state.currentSnapshotId || null
            })
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(errData.detail || 'Failed to create incident');
          }

          const newInc = await res.json();
          modalInc.style.display = 'none';
          loadIncidentsView();
          investigateIncident(newInc.id);

        } catch (err) {
          if (errorBox) {
            errorBox.style.display = 'block';
            errorBox.textContent = err.message;
          } else {
            alert(err.message);
          }
        } finally {
          submitIncBtn.disabled = false;
          submitIncBtn.textContent = 'Declare & Investigate';
        }
      });
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  window.TwinApp = {
    state,
    focusOnNode,
    inspectNode,
    inspectNodeByName,
    inspectEdge,
    loadGraph,
    switchPrimaryView,
    switchArchSubtab,
    triggerOnboarding,
    executeChangeImpactAnalysis,
    executeTestImpactAnalysis,
    loadTestsView,
    loadRuntimeView,
    loadIncidentsView,
    investigateIncident,
    openConnectModal,
    openIngestModal,
    openCreateIncidentModal,
    openCommandPalette: () => window.openCommandPalette?.(),
  };

})();
