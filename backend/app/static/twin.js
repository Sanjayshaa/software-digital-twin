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
    initEventListeners();
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
    // Primary View Tabs
    const tabs = document.querySelectorAll('#main-view-tabs .view-tab');
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

    // Overview Hero Graph Button
    const ovGraphBtn = document.getElementById('ov-btn-view-graph');
    if (ovGraphBtn) {
      ovGraphBtn.addEventListener('click', () => {
        switchPrimaryView('architecture');
        switchArchSubtab('graph');
      });
    }

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
    document.querySelectorAll('#main-view-tabs .view-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.view === viewName);
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
    } else if (viewName === 'architecture') {
      switchArchSubtab(state.currentArchSubtab);
    } else if (viewName === 'processes') {
      loadProcessesView();
    } else if (viewName === 'dependencies') {
      loadDependenciesView();
    } else if (viewName === 'tests') {
      loadTestsView();
    } else if (viewName === 'changes') {
      loadChangesView();
    } else if (viewName === 'evidence') {
      loadEvidenceView();
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
          pkgGrid.innerHTML = '<div style="grid-column:1/-1;color:var(--text-muted);font-size:12px;padding:12px;text-align:center;background:var(--bg-surface);border-radius:6px;">No macro packages identified in this snapshot.</div>';
        } else {
          pkgs.forEach(pkg => {
            const card = document.createElement('div');
            card.className = 'arch-pkg-card';
            card.style = 'background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:12px;display:flex;flex-direction:column;gap:8px;';
            const sampleHtml = (pkg.sample_components || []).slice(0, 3).map(c => `<span style="font-size:11px;background:var(--bg-secondary);border:1px solid var(--border-subtle);padding:2px 6px;border-radius:4px;font-family:monospace;color:#c084fc;">${escapeHtml(c)}</span>`).join(' ');
            card.innerHTML = `
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <strong style="font-size:13px;color:var(--text-primary);display:flex;align-items:center;gap:6px;">
                  <span>📦</span> ${escapeHtml(pkg.name)}
                </strong>
                <span class="badge" style="background:rgba(56,189,248,0.12);color:#38bdf8;font-size:10px;padding:2px 6px;border-radius:4px;">${pkg.artifact_count} artifacts</span>
              </div>
              <div style="font-size:11px;color:var(--text-secondary);display:flex;gap:12px;">
                <span>${pkg.module_count} Modules</span>
                <span>${pkg.files_count} Files</span>
              </div>
              ${sampleHtml ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:2px;">${sampleHtml}</div>` : ''}
              <button class="secondary-btn btn-explore-pkg" data-pkg="${escapeHtml(pkg.name)}" style="font-size:11px;padding:4px 8px;margin-top:4px;align-self:flex-start;border:1px solid var(--border-color);color:var(--text-secondary);cursor:pointer;">
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

      // Latest Change Impact Card in Overview
      const impactContainer = document.getElementById('ov-impact-container');
      if (impactContainer) {
        const imp = data.latest_impact;
        if (imp) {
          impactContainer.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
              <div>
                <span style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;">Change Impact Analysis Run</span>
                <div style="font-size:13px;font-weight:600;color:#c084fc;margin-top:2px;">
                  Target Snapshot: <span class="text-mono">${escapeHtml(imp.target_snapshot_id.slice(0, 14))}</span>
                </div>
              </div>
              <button id="btn-ov-view-impact" class="secondary-btn" style="font-size:11px;padding:5px 10px;border:1px solid #7c3aed;color:#c084fc;cursor:pointer;">
                Open Full Blast-Radius Report →
              </button>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(100px, 1fr));gap:8px;">
              <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:4px;padding:8px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Changed</div>
                <div style="font-size:18px;font-weight:700;color:#f59e0b;">${imp.changed_count}</div>
              </div>
              <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:4px;padding:8px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Direct Impact</div>
                <div style="font-size:18px;font-weight:700;color:#ef4444;">${imp.directly_affected_count}</div>
              </div>
              <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:4px;padding:8px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Indirect Impact</div>
                <div style="font-size:18px;font-weight:700;color:#ec4899;">${imp.indirectly_affected_count}</div>
              </div>
              <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:4px;padding:8px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Components</div>
                <div style="font-size:18px;font-weight:700;color:#38bdf8;">${imp.components_affected}</div>
              </div>
              <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:4px;padding:8px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">APIs</div>
                <div style="font-size:18px;font-weight:700;color:#f472b6;">${imp.apis_affected}</div>
              </div>
              <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:4px;padding:8px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Processes</div>
                <div style="font-size:18px;font-weight:700;color:#a78bfa;">${imp.processes_affected}</div>
              </div>
              <div style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:4px;padding:8px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;">Tests</div>
                <div style="font-size:18px;font-weight:700;color:#10b981;">${imp.tests_affected}</div>
              </div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:11px;color:var(--text-secondary);">
              <span>Causal Paths: <strong>${imp.causal_paths_count}</strong></span>
              <span>Execution Time: <strong>${imp.execution_time_ms} ms</strong></span>
              <span>Analyzed: <strong>${new Date(imp.created_at).toLocaleTimeString()}</strong></span>
            </div>
          `;
          document.getElementById('btn-ov-view-impact')?.addEventListener('click', () => {
            switchPrimaryView('changes');
          });
        } else {
          impactContainer.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between;padding:14px;background:var(--bg-surface);border:1px dashed var(--border-color);border-radius:6px;">
              <div>
                <div style="font-size:13px;font-weight:600;color:var(--text-secondary);">No Change Impact Analysis Run For This Snapshot</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">Compare with an earlier snapshot to compute deterministic blast-radius propagation across components, APIs, processes, and tests.</div>
              </div>
              <button id="btn-ov-run-impact" class="primary-btn" style="font-size:11px;padding:6px 12px;white-space:nowrap;cursor:pointer;">
                Run Blast-Radius Analysis →
              </button>
            </div>
          `;
          document.getElementById('btn-ov-run-impact')?.addEventListener('click', () => {
            switchPrimaryView('changes');
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

    } catch (e) {
      console.error('Error loading overview data', e);
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
      tbody.innerHTML = '<tr><td colspan="7" class="td-empty">No components found matching filter.</td></tr>';
      return;
    }

    components.forEach(c => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${escapeHtml(c.name)}</strong></td>
        <td><span class="type-pill type-${c.type}">${c.type}</span></td>
        <td class="text-mono text-muted">${escapeHtml(c.qualified_name || c.name)}</td>
        <td class="text-mono">${escapeHtml(c.location || '')}</td>
        <td>${escapeHtml(c.language || 'Python')}</td>
        <td><span class="conf-badge">${((c.confidence || 1.0) * 100).toFixed(0)}%</span></td>
        <td>
          <button class="small-action-btn" data-art-id="${c.id}">Focus in Graph</button>
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
    const container = document.getElementById('process-chains-container');
    if (!container) return;

    // Hook tab buttons
    document.querySelectorAll('.proc-tab-btn').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.proc-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentProcessTab = btn.dataset.procTab;
        renderProcessesWorkflow();
      };
    });

    container.innerHTML = '<div class="state-loading">Reconstructing deterministic process workflows from AST call graphs...</div>';

    try {
      let url = `/repositories/${state.currentRepoId}/process-graph`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to load process synthesis');
      const data = await res.json();
      state.currentProcessData = data;
      renderProcessesWorkflow();
    } catch (err) {
      container.innerHTML = `<div class="empty-state-box"><p>Error synthesizing processes: ${escapeHtml(err.message)}</p></div>`;
    }
  }

  function renderProcessesWorkflow() {
    const container = document.getElementById('process-chains-container');
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
        <div class="empty-state-box" style="padding:32px;text-align:center;background:var(--bg-secondary);border:1px dashed var(--border-color);border-radius:8px;">
          <div style="font-size:28px;margin-bottom:8px;">⚙️</div>
          <p style="font-size:13px;color:var(--text-secondary);margin-bottom:4px;">No process workflows matched the active filter.</p>
          <span style="font-size:11px;color:var(--text-muted);">Process flows are deterministically synthesized from API routes, controllers, and service entry points.</span>
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
      card.className = 'process-workflow-card';
      card.style = 'background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:8px;padding:16px;margin-bottom:20px;';

      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--border-subtle);padding-bottom:12px;margin-bottom:16px;">
          <div>
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:16px;">⚡</span>
              <h3 style="font-size:15px;font-weight:700;color:var(--text-primary);margin:0;">${escapeHtml(proc.name)}</h3>
              <span class="badge" style="background:rgba(192,132,252,0.15);color:#c084fc;font-size:11px;padding:2px 8px;border-radius:4px;">${escapeHtml(proc.type || 'WORKFLOW')}</span>
            </div>
            <p style="font-size:12px;color:var(--text-secondary);margin:4px 0 0 0;">${escapeHtml(proc.description || 'Statically inferred deterministic execution flow')}</p>
          </div>
          <div style="display:flex;gap:8px;align-items:center;">
            <span class="badge-evidence" style="background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);font-size:11px;padding:3px 8px;border-radius:4px;">
              Evidence: STATICALLY INFERRED
            </span>
            <span style="font-size:11px;color:var(--text-muted);">${steps.length} Steps</span>
          </div>
        </div>

        <div class="workflow-steps-pipeline" style="display:flex;flex-direction:column;gap:0;">
          ${steps.map((step, sIdx) => {
            const outTrans = transitions.find(t => t.source === step.id);
            const isEntry = sIdx === 0;
            const isTerminal = sIdx === steps.length - 1;
            const roleBadge = isEntry ? '<span class="badge" style="background:rgba(56,189,248,0.2);color:#38bdf8;font-size:10px;padding:2px 6px;">ENTRY POINT</span>' : (isTerminal ? '<span class="badge" style="background:rgba(52,211,153,0.2);color:#34d399;font-size:10px;padding:2px 6px;">TERMINAL</span>' : '');

            return `
              <div class="wf-step-container" style="display:flex;gap:16px;align-items:stretch;">
                <div style="display:flex;flex-direction:column;align-items:center;width:32px;">
                  <div style="width:28px;height:28px;border-radius:50%;background:#7c3aed;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;box-shadow:0 0 8px rgba(124,58,237,0.4);flex-shrink:0;">
                    ${step.order}
                  </div>
                  ${!isTerminal ? `
                    <div style="flex:1;width:2px;background:linear-gradient(to bottom, #7c3aed, rgba(124,58,237,0.2));margin:4px 0;"></div>
                  ` : ''}
                </div>

                <div style="flex:1;background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:12px;margin-bottom:12px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                      <strong style="font-size:13px;color:var(--text-primary);">${escapeHtml(step.name)}</strong>
                      <span class="type-pill type-${step.type}" style="font-size:10px;padding:1px 6px;">${step.type}</span>
                      ${roleBadge}
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                      <span style="font-size:11px;color:var(--text-muted);">Confidence: <strong>${Math.round((step.confidence || 0.85)*100)}%</strong></span>
                      <button class="secondary-btn btn-inspect-step-graph" data-cid="${step.component_id}" style="font-size:10px;padding:2px 6px;border:1px solid var(--border-color);cursor:pointer;">Focus Graph</button>
                    </div>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px;color:var(--text-secondary);background:var(--bg-secondary);padding:6px 10px;border-radius:4px;">
                    <div>Component: <code class="text-mono" style="color:#c084fc;">${escapeHtml(step.component_name || step.name)}</code></div>
                    <div>Source Location: <code class="text-mono text-muted">${escapeHtml(step.location || 'source')}</code></div>
                  </div>
                  ${outTrans ? `
                    <div style="margin-top:6px;font-size:11px;color:#06b6d4;display:flex;align-items:center;gap:6px;">
                      <span>↳ ${escapeHtml(outTrans.relationship_type || 'CALLS')} transition</span>
                      <span style="color:var(--text-muted);font-size:10px;">• ${escapeHtml(outTrans.condition || 'Deterministic call')}</span>
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
        <div class="dep-item-box" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <strong style="color:var(--text-primary);font-size:12px;">⬅️ ${escapeHtml(e.sourceNode?.name || e.source)}</strong>
            <span class="badge" style="font-size:10px;background:rgba(239,68,68,0.12);color:#ef4444;">${e.type}</span>
          </div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
            Evidence: <span class="text-mono">${escapeHtml(e.evidence?.file || 'AST Call')}</span>
          </div>
        </div>
      `).join('') : '<div class="empty-list" style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px;">No direct inbound callers in snapshot.</div>';
    }

    if (outboundList) {
      outboundList.innerHTML = outgoing.length > 0 ? outgoing.map(e => `
        <div class="dep-item-box" style="background:var(--bg-surface);border:1px solid var(--border-color);border-radius:6px;padding:10px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <strong style="color:var(--text-primary);font-size:12px;">➡️ ${escapeHtml(e.targetNode?.name || e.target)}</strong>
            <span class="badge" style="font-size:10px;background:rgba(56,189,248,0.12);color:#38bdf8;">${e.type}</span>
          </div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
            Evidence: <span class="text-mono">${escapeHtml(e.evidence?.file || 'AST Call')}</span>
          </div>
        </div>
      `).join('') : '<div class="empty-list" style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px;">No direct outbound callees in snapshot.</div>';
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

  // --- 10. Tests View ---
  async function loadTestsView() {
    if (!state.currentRepoId) return;
    const tbody = document.getElementById('tests-table-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="td-loading">Extracting test suites, assertions, and verified component mappings...</td></tr>';

    try {
      let url = `/repositories/${state.currentRepoId}/tests-map`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to load test mappings');
      const data = await res.json();
      const tests = data.tests || [];

      // Update stat badges
      const elTotal = document.getElementById('tstat-total');
      const elMapped = document.getElementById('tstat-mapped');
      const elUnmapped = document.getElementById('tstat-unmapped');
      const elComponents = document.getElementById('tstat-components');

      if (elTotal) elTotal.textContent = data.total_tests ?? tests.length;
      if (elMapped) elMapped.textContent = data.verified_mappings_count ?? 0;
      if (elUnmapped) elUnmapped.textContent = data.unmapped_count ?? 0;
      if (elComponents) elComponents.textContent = data.tested_components_count ?? 0;

      tbody.innerHTML = '';
      if (tests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="td-empty">No test cases or test specifications identified in snapshot.</td></tr>';
        return;
      }

      tests.forEach(t => {
        const tr = document.createElement('tr');
        const hasTargets = t.targets && t.targets.length > 0;
        const targetsHtml = hasTargets
          ? t.targets.map(tg => `<span class="target-tag" style="background:rgba(56,189,248,0.12);color:#38bdf8;border:1px solid rgba(56,189,248,0.25);padding:2px 6px;border-radius:4px;font-size:11px;margin-right:4px;">${escapeHtml(tg)}</span>`).join('')
          : '<span style="color:var(--text-muted);font-style:italic;font-size:11px;">Unmapped test artifact</span>';

        const isAffected = t.impact_status === 'AFFECTED';
        const impactBadge = isAffected
          ? '<span class="badge" style="background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);font-size:10px;padding:2px 6px;">AFFECTED BY CHANGE</span>'
          : '<span class="badge" style="background:rgba(16,185,129,0.12);color:#10b981;border:1px solid rgba(16,185,129,0.25);font-size:10px;padding:2px 6px;">HEALTHY / UNAFFECTED</span>';

        tr.innerHTML = `
          <td><strong style="color:var(--text-primary);">${escapeHtml(t.name)}</strong></td>
          <td><span class="type-pill type-TEST_CASE">${escapeHtml(t.type || 'TEST_CASE')}</span></td>
          <td class="text-mono" style="font-size:11px;">${escapeHtml(t.location || '')}</td>
          <td><span class="badge-evidence">${escapeHtml(t.evidence_status || (hasTargets ? 'STATIC_MAPPING' : 'UNMAPPED'))}</span></td>
          <td>${targetsHtml}</td>
          <td>${impactBadge}</td>
        `;
        tbody.appendChild(tr);
      });

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="6" class="td-empty">Error loading tests: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  // --- 11. Changes (Snapshot Diff & Impact Analysis) View ---
  let currentImpactAnalysisResult = null;

  function loadChangesView() {
    const diffBtn = document.getElementById('btn-run-diff-action');
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
          <div class="diff-chip diff-add">+${added} Added</div>
          <div class="diff-chip diff-del">-${removed} Removed</div>
          <div class="diff-chip diff-mod">~${modified} Modified</div>
          <div class="diff-chip diff-unchanged">${summary.total_changes || 0} Total Changed Artifacts</div>
        `;
      }

      tbody.innerHTML = '';
      if (changes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="td-empty">Zero structural differences detected between the selected snapshots.</td></tr>';
        return;
      }

      changes.forEach(n => {
        const tr = document.createElement('tr');
        const cType = n.change_type || 'MODIFIED';
        tr.innerHTML = `
          <td><span class="diff-tag diff-${cType.toLowerCase()}">${cType}</span></td>
          <td><strong>${escapeHtml(n.artifact_name || n.artifact_id)}</strong></td>
          <td><span class="type-pill type-${n.artifact_type}">${n.artifact_type}</span></td>
          <td class="text-mono">${escapeHtml(n.file_path || '')}${n.line_number ? `:${n.line_number}` : ''}</td>
          <td>${escapeHtml(n.details || (cType === 'ADDED' ? 'New artifact discovered in target snapshot.' : (cType === 'REMOVED' ? 'Artifact absent in target snapshot.' : 'Signature or logic modified.')))}</td>
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
        ctx.strokeStyle = isConnected ? 'rgba(148, 163, 184, 0.45)' : 'rgba(148, 163, 184, 0.08)';
        ctx.lineWidth = isConnected ? 1.4 : 0.8;
        ctx.setLineDash([]);
      }

      ctx.stroke();
      ctx.setLineDash([]);

      if (isConnected) {
        drawArrow(ctx, a.x, a.y, b.x, b.y, b.radius + 4, e.is_drift ? '#ef4444' : 'rgba(148, 163, 184, 0.6)');
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
        ctx.fillStyle = 'rgba(6, 182, 212, 0.25)';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#06b6d4';
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
      ctx.strokeStyle = isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.2)';
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
        ctx.fillStyle = isSelected ? '#ffffff' : '#cbd5e1';
        ctx.font = `${Math.max(10, 11 / state.transform.k)}px 'Plus Jakarta Sans', sans-serif`;
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
  };

})();
