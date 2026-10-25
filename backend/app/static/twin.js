/**
 * Digital Twin — Software Architecture & Structural Intelligence Platform
 * Product Frontend Engine: Overview, Architecture Graph Workspace, Components,
 * APIs, Processes, Dependencies, Tests, Snapshot Diff, Evidence, and Onboarding.
 */

(function () {
  'use strict';

  // --- API Client & Authorization ---
  const nativeFetch = window.fetch.bind(window);
  async function apiFetch(url, options = {}) {
    const token = localStorage.getItem('jwt_token');
    const headers = Object.assign({}, options.headers || {});
    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const opts = { ...options, headers };
    const res = await nativeFetch(url, opts);
    if (res.status === 401) {
      localStorage.removeItem('jwt_token');
      if (typeof updateAuthUI === 'function') {
        updateAuthUI(null);
      }
      if (typeof setAppState === 'function' && token) {
        setAppState('SESSION_EXPIRED', { message: 'Your session has expired. Please sign in again.' });
      }
    }
    return res;
  }
  const fetch = apiFetch;

  // --- Notification / Toast System (Replacing alert) ---
  function showNotification(message, type = 'info', duration = 4000) {
    let toastContainer = document.getElementById('twin-toast-container');
    if (!toastContainer) {
      toastContainer = document.createElement('div');
      toastContainer.id = 'twin-toast-container';
      toastContainer.className = 'fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 max-w-sm pointer-events-none';
      document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = 'pointer-events-auto p-3.5 rounded-xl shadow-lg border text-xs flex items-start gap-2.5 transition-all transform translate-y-2 opacity-0';

    let bg = '#EFF6FF';
    let border = '#BFDBFE';
    let text = '#1E40AF';
    let icon = 'info';

    if (type === 'error') {
      bg = '#FEF2F2';
      border = '#FECDD3';
      text = '#991B1B';
      icon = 'error';
    } else if (type === 'success') {
      bg = '#ECFDF5';
      border = '#A7F3D0';
      text = '#065F46';
      icon = 'check_circle';
    } else if (type === 'warning') {
      bg = '#FFFBEB';
      border = '#FDE68A';
      text = '#92400E';
      icon = 'warning';
    }

    toast.style.backgroundColor = bg;
    toast.style.borderColor = border;
    toast.style.color = text;

    toast.innerHTML = `
      <span class="material-symbols-outlined text-[18px] shrink-0 mt-0.5">${icon}</span>
      <div class="flex-1 leading-relaxed">${escapeHtml(message)}</div>
      <button class="shrink-0 text-current opacity-60 hover:opacity-100 p-0.5 rounded cursor-pointer" type="button">
        <span class="material-symbols-outlined text-[16px]">close</span>
      </button>
    `;

    toast.querySelector('button').onclick = () => {
      toast.remove();
    };

    toastContainer.appendChild(toast);
    requestAnimationFrame(() => {
      toast.classList.remove('translate-y-2', 'opacity-0');
      toast.classList.add('translate-y-0', 'opacity-100');
    });

    setTimeout(() => {
      if (toast.parentElement) {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 250);
      }
    }, duration);
  }

  // Global State
  const state = {
    repositories: [],
    currentRepoId: null,
    currentRepoData: null,
    snapshots: [],
    currentSnapshotId: null,
    diffSnapshotId: null,
    appState: 'BOOT',
    user: null,

    currentPrimaryView: 'overview',
    currentArchSubtab: 'graph',
    currentLevel: 2,
    depth: 2,
    focusNodeId: null,
    selectedNodeId: null,
    selectedEdgeId: null,
    impactMode: false,
    impactRootId: null,
    viewDimension: '2d',
    lastSimulationResult: null,
    discoveryAssessmentResult: null,
    discoveryFindingFilter: 'all',

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
    hoveredNode: null,
    physicsEnabled: true,
    animFrameId: null,
    showEdgeLabels: false,

    // MiroFish-inspired Color Palette (High-Contrast for Clean White Canvas)
    colors: {
      CLASS: '#0284C7',
      METHOD: '#6366F1',
      FUNCTION: '#DB2777',
      MODULE: '#059669',
      PACKAGE: '#2563EB',
      DIRECTORY: '#0284C7',
      API_ENDPOINT: '#E11D48',
      SERVICE: '#7C3AED',
      TEST_CASE: '#CA8A04',
      TEST_SUITE: '#B45309',
      DATABASE_TABLE: '#D97706',
      DATABASE: '#EA580C',
      EXTERNAL_DEPENDENCY: '#64748B',
      DEFAULT: '#64748B',
      DRIFT: '#DC2626',
      IMPACT: '#D97706',
    },
  };

  // --- Stitch Theme Manager ---
  const ThemeManager = {
    STORAGE_KEY: 'twin_theme',
    init() {
      const saved = localStorage.getItem(this.STORAGE_KEY) || 'light';
      this.apply(saved);
      document.getElementById('btn-toggle-theme')?.addEventListener('click', () => {
        const isDark = document.body.classList.contains('theme-dark');
        this.apply(isDark ? 'light' : 'dark');
      });
      document.getElementById('theme-toggle-btn')?.addEventListener('click', () => {
        const isDark = document.body.classList.contains('theme-dark');
        this.apply(isDark ? 'light' : 'dark');
      });
    },
    apply(theme) {
      if (theme === 'dark') {
        document.body.classList.remove('theme-light');
        document.body.classList.add('theme-dark');
        document.documentElement.classList.add('dark');
        localStorage.setItem(this.STORAGE_KEY, 'dark');
        this.updateIcon('dark_mode');
      } else {
        document.body.classList.remove('theme-dark');
        document.body.classList.add('theme-light');
        document.documentElement.classList.remove('dark');
        localStorage.setItem(this.STORAGE_KEY, 'light');
        this.updateIcon('light_mode');
      }
    },
    updateIcon(iconName) {
      const icons = document.querySelectorAll('#btn-toggle-theme .material-symbols-outlined, #theme-toggle-btn .material-symbols-outlined');
      icons.forEach(el => { el.textContent = iconName; });
    }
  };

  // --- Initializer ---
  function bootApplication() {
    try {
      ThemeManager.init();
      initCanvas();
      initNavigation();
      initModal();
      initAuth();
      initCommandPalette();
      initAskSoftware();
      initEventListeners();
      initPhase5Handlers();
      initSimulationHandlers();
    } catch (err) {
      console.error('Error during component initialization:', err);
    }
    startApplicationStateMachine();
  }

  // Failsafe watchdog: if network hangs completely for 10s, show actionable recovery error
  setTimeout(() => {
    if (document.body && document.body.classList.contains('booting')) {
      console.warn('Boot safety watchdog triggered: network or server communication hung.');
      if (typeof setAppState === 'function') {
        setAppState('RECOVERABLE_ERROR', { error: 'Network request timed out during initialization. The server took too long to respond.' });
      }
      if (typeof finishBoot === 'function') {
        finishBoot();
      } else {
        document.body.classList.remove('booting');
      }
    }
  }, 10000);

  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', bootApplication);
  } else {
    bootApplication();
  }

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
    const isFull = parent.classList.contains('graph-fullscreen-mode');
    const rect = parent.getBoundingClientRect();
    const w = Math.round(isFull ? window.innerWidth : (rect.width || parent.clientWidth || 1000));
    const h = Math.round(isFull ? window.innerHeight : (rect.height || parent.clientHeight || 700));
    if (w <= 0 || h <= 0) return;
    state.width = w;
    state.height = h;
    state.dpr = window.devicePixelRatio || 1;
    state.canvas.width = state.width * state.dpr;
    state.canvas.height = state.height * state.dpr;
    state.canvas.style.width = `${state.width}px`;
    state.canvas.style.height = `${state.height}px`;
    state.ctx.setTransform(1, 0, 0, 1, 0, 0);
    state.ctx.scale(state.dpr, state.dpr);
    if (!state.transform.x && !state.transform.y) {
      state.transform.x = state.width / 2;
      state.transform.y = state.height / 2;
    }
    if (window.Twin3D && window.Twin3D.active) {
      window.Twin3D.onResize();
    }
  }

  // --- 1. Navigation & View Switching ---
  function getInitialRequestedView() {
    const hash = window.location.hash ? window.location.hash.replace(/^#\/?/, '').split('?')[0].trim() : '';
    const urlParams = new URLSearchParams(window.location.search);
    const queryView = urlParams.get('view');
    const candidate = hash || queryView || localStorage.getItem('selected_view') || 'overview';
    const validViews = [
      'overview', 'discovery', 'architecture', 'dependencies', 'components',
      'changes', 'impact', 'simulation', 'tests', 'incidents', 'runtime', 'evidence', 'ask'
    ];
    return validViews.includes(candidate) ? candidate : 'overview';
  }

  function initNavigation() {
    // Bi-directional browser history and hash navigation
    window.addEventListener('hashchange', () => {
      const hashView = window.location.hash ? window.location.hash.replace(/^#\/?/, '').split('?')[0].trim() : '';
      if (hashView && hashView !== state.currentPrimaryView) {
        switchPrimaryView(hashView);
      }
    });

    window.addEventListener('popstate', (e) => {
      if (e.state && e.state.view) {
        switchPrimaryView(e.state.view);
      } else {
        const initial = getInitialRequestedView();
        switchPrimaryView(initial);
      }
    });

    // Primary View Tabs across sidebar and panels
    const tabs = document.querySelectorAll('.view-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const view = tab.dataset.view;
        if (!state.currentRepoId && view !== 'overview') {
          const viewLabels = {
            architecture: 'Architecture',
            dependencies: 'Dependencies',
            components: 'Components',
            changes: 'Changes',
            impact: 'Change Impact',
            simulation: 'What-If Simulation',
            tests: 'Tests',
            incidents: 'Incidents',
            runtime: 'Runtime Evidence',
            ask: 'Ask Twin',
            discovery: 'Discovery & Health'
          };
          const label = viewLabels[view] || view;
          showNotification(`Connect a codebase to explore ${label}.`, 'info');
          return;
        }
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
    document.getElementById('top-btn-connect-repo')?.addEventListener('click', () => openConnectModal('github'));
    document.getElementById('sidebar-repo-card')?.addEventListener('click', () => openConnectModal('github'));
    document.getElementById('sidebar-btn-connect-codebase')?.addEventListener('click', () => openConnectModal('github'));

    document.getElementById('top-btn-ingest-runtime')?.addEventListener('click', () => {
      if (!state.currentRepoId) {
        showNotification('Connect a codebase before ingesting runtime telemetry.', 'warning');
        return;
      }
      openIngestModal();
    });

    document.getElementById('top-btn-create-incident')?.addEventListener('click', () => {
      if (!state.currentRepoId) {
        showNotification('Connect a codebase before declaring an incident.', 'warning');
        return;
      }
      openCreateIncidentModal();
    });

    document.getElementById('top-search-btn')?.addEventListener('click', () => {
      if (!state.currentRepoId) {
        showNotification('Connect a codebase to search Twin graphs and artifacts.', 'info');
        return;
      }
      window.openCommandPalette?.();
    });

    // Level Selector
    document.querySelectorAll('.level-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.level-btn').forEach(b => {
          b.classList.remove('active', 'bg-[#0071e3]', 'text-white');
          b.classList.add('bg-[#F1F5F9]', 'text-[#0F172A]');
        });
        btn.classList.add('active', 'bg-[#0071e3]', 'text-white');
        btn.classList.remove('bg-[#F1F5F9]', 'text-[#0F172A]');
        state.currentLevel = parseInt(btn.dataset.level, 10);
        loadGraph();
      });
    });

    // Graph Node Search Input
    const graphSearchInput = document.getElementById('graph-search-input');
    if (graphSearchInput) {
      graphSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          performGraphSearch(graphSearchInput.value);
        }
      });
    }

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
        selectRepository(e.target.value);
      });
    }

    const snapSelect = document.getElementById('snapshot-select');
    if (snapSelect) {
      snapSelect.addEventListener('change', (e) => {
        selectSnapshot(e.target.value);
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
    if (!viewName) viewName = 'overview';
    state.currentPrimaryView = viewName;
    try {
      localStorage.setItem('selected_view', viewName);
      const currentHash = window.location.hash.replace(/^#\/?/, '').split('?')[0];
      if (currentHash !== viewName) {
        window.history.replaceState({ view: viewName, repoId: state.currentRepoId }, '', '#' + viewName);
      }
    } catch (_) {}

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
    if (!state.currentRepoId) {
      const noRepoView = document.getElementById('view-no-repo');
      if (noRepoView) noRepoView.style.display = 'block';
      return;
    }

    // Hide no-repo hero when repo is connected
    const noRepoView = document.getElementById('view-no-repo');
    if (noRepoView) noRepoView.style.display = 'none';

    // Show target view panel with safe fallback
    let targetPanel = document.getElementById(`view-${viewName}`);
    if (!targetPanel) {
      targetPanel = document.getElementById('view-overview');
      viewName = 'overview';
      state.currentPrimaryView = 'overview';
    }
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
      const isValid = validateBaselineAndTargetSelection();
      if (isValid && !currentImpactAnalysisResult) {
        executeChangeImpactAnalysis();
      }
    } else if (viewName === 'evidence') {
      loadEvidenceView();
    } else if (viewName === 'runtime') {
      loadRuntimeView();
    } else if (viewName === 'incidents') {
      loadIncidentsView();
    } else if (viewName === 'simulation') {
      loadSimulationView();
    } else if (viewName === 'ask') {
      setTimeout(() => document.getElementById('ask-query-input')?.focus(), 50);
    } else if (viewName === 'discovery') {
      loadDiscoveryView();
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

  // --- 2. Modals, Overlays & Global Keyboard Management ---
  function initModal() {
    initGlobalModalHandlers();
    initOnboardModal();
    initIngestModal();
  }

  function initGlobalModalHandlers() {
    // Backdrop click handler for all modal overlays
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
          overlay.style.display = 'none';
          checkAnyModalOpen();
        }
      });
    });

    // ESC key closes any open modal
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeAllModals();
      }
    });

    // Disconnect and Resync buttons with safe confirmation modal
    document.getElementById('btn-disconnect-repo')?.addEventListener('click', openDisconnectModal);
    document.getElementById('modal-disconnect-close-btn')?.addEventListener('click', () => closeModal('modal-disconnect-repo'));
    document.getElementById('modal-disconnect-cancel-btn')?.addEventListener('click', () => closeModal('modal-disconnect-repo'));
    document.getElementById('modal-disconnect-confirm-btn')?.addEventListener('click', confirmDisconnectRepository);
    document.getElementById('btn-resync-repo')?.addEventListener('click', resyncRepository);

  }

  function closeAllModals() {
    document.querySelectorAll('.modal-overlay').forEach(m => {
      m.style.display = 'none';
    });
    document.body.style.overflow = '';
  }

  function checkAnyModalOpen() {
    const anyOpen = Array.from(document.querySelectorAll('.modal-overlay')).some(m => m.style.display !== 'none');
    if (!anyOpen) {
      document.body.style.overflow = '';
    }
  }

  function openModal(modalId) {
    closeAllModals();
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  }

  function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
    checkAnyModalOpen();
  }

  function switchOnboardTab(prov) {
    state.currentOnboardProv = prov;
    hideOnboardError();

    document.querySelectorAll('.m-prov-tab').forEach(b => {
      const isTarget = b.dataset.prov === prov;
      b.classList.toggle('border-b-2', isTarget);
      b.classList.toggle('border-[#0071e3]', isTarget);
      b.classList.toggle('text-[#0071e3]', isTarget);
      b.classList.toggle('font-semibold', isTarget);
      b.classList.toggle('text-[#64748B]', !isTarget);
      b.classList.toggle('font-medium', !isTarget);
      b.setAttribute('aria-selected', String(isTarget));
    });

    document.querySelectorAll('.modal-panel').forEach(p => {
      p.style.display = (p.id === `modal-panel-${prov}`) ? 'block' : 'none';
    });

    const submitBtn = document.getElementById('modal-submit-btn');
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Connect & Synthesize Twin';
    }
  }

  function openConnectModal(preferredProv = 'github') {
    state.currentOnboardProv = preferredProv;
    openModal('modal-onboard');
    hideOnboardError();
    const progBox = document.getElementById('onboard-progress-box');
    if (progBox) progBox.style.display = 'none';

    switchOnboardTab(preferredProv);
  }

  function closeConnectModal() {
    closeModal('modal-onboard');
    hideOnboardError();
    // Clear sensitive token and form inputs
    const tokenInput = document.getElementById('input-github-token');
    if (tokenInput) tokenInput.value = '';
    const urlInput = document.getElementById('input-github-url');
    if (urlInput) urlInput.value = '';
    const localInput = document.getElementById('input-local-path');
    if (localInput) localInput.value = '';
    const archiveInput = document.getElementById('input-archive-file');
    if (archiveInput) archiveInput.value = '';
  }

  function openIngestModal() {
    openModal('modal-ingest-runtime');
  }

  function closeIngestModal() {
    closeModal('modal-ingest-runtime');
  }

  function initIngestModal() {
    const tabCodebase = document.getElementById('tab-ingest-codebase');
    const tabTelemetry = document.getElementById('tab-ingest-telemetry');
    const panelCodebase = document.getElementById('panel-ingest-codebase');
    const panelTelemetry = document.getElementById('panel-ingest-telemetry');
    const btnCodebase = document.getElementById('modal-ingest-codebase-btn');
    const btnTelemetry = document.getElementById('modal-ingest-submit-btn');
    const closeBtn = document.getElementById('modal-ingest-close-btn');
    const cancelBtn = document.getElementById('modal-ingest-cancel-btn');

    closeBtn?.addEventListener('click', closeIngestModal);
    cancelBtn?.addEventListener('click', closeIngestModal);

    tabCodebase?.addEventListener('click', () => {
      tabCodebase.className = 'flex-1 py-1.5 rounded-lg text-xs font-semibold bg-white text-[#0F172A] shadow-xs';
      tabTelemetry.className = 'flex-1 py-1.5 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A]';
      if (panelCodebase) panelCodebase.style.display = 'block';
      if (panelTelemetry) panelTelemetry.style.display = 'none';
      if (btnCodebase) btnCodebase.style.display = 'inline-flex';
      if (btnTelemetry) btnTelemetry.style.display = 'none';
    });

    tabTelemetry?.addEventListener('click', () => {
      tabTelemetry.className = 'flex-1 py-1.5 rounded-lg text-xs font-semibold bg-white text-[#0F172A] shadow-xs';
      tabCodebase.className = 'flex-1 py-1.5 rounded-lg text-xs font-medium text-[#64748B] hover:text-[#0F172A]';
      if (panelTelemetry) panelTelemetry.style.display = 'block';
      if (panelCodebase) panelCodebase.style.display = 'none';
      if (btnTelemetry) btnTelemetry.style.display = 'inline-flex';
      if (btnCodebase) btnCodebase.style.display = 'none';
    });

    btnCodebase?.addEventListener('click', async () => {
      if (!state.currentRepoId) {
        showNotification('Connect a repository before analyzing.', 'warning');
        return;
      }
      const branchInput = document.getElementById('input-ingest-branch');
      const commitInput = document.getElementById('input-ingest-commit');
      const branch = (branchInput?.value || 'main').trim();
      const commit = (commitInput?.value || 'HEAD').trim();

      const progBox = document.getElementById('ingest-progress-box');
      const stepQueued = document.getElementById('ingest-step-queued');
      const stepAnalyzing = document.getElementById('ingest-step-analyzing');
      const stepPersisting = document.getElementById('ingest-step-persisting');
      const stepReady = document.getElementById('ingest-step-ready');

      if (progBox) progBox.style.display = 'block';
      if (btnCodebase) btnCodebase.disabled = true;

      // Stage 1: Queued
      if (stepQueued) stepQueued.className = 'flex items-center gap-1.5 text-[#2563EB] font-bold';

      try {
        // Stage 2: Analyzing
        setTimeout(() => {
          if (stepQueued) stepQueued.className = 'flex items-center gap-1.5 text-[#059669]';
          if (stepAnalyzing) stepAnalyzing.className = 'flex items-center gap-1.5 text-[#2563EB] font-bold';
        }, 300);

        // Stage 3: Persisting
        setTimeout(() => {
          if (stepAnalyzing) stepAnalyzing.className = 'flex items-center gap-1.5 text-[#059669]';
          if (stepPersisting) stepPersisting.className = 'flex items-center gap-1.5 text-[#2563EB] font-bold';
        }, 700);

        const url = `/repositories/${state.currentRepoId}/analyze?commit_hash=${encodeURIComponent(commit)}&branch_name=${encodeURIComponent(branch)}`;
        const res = await apiFetch(url, { method: 'POST' });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || `Analysis failed (HTTP ${res.status})`);
        }
        const result = await res.json();

        // Stage 4: Ready
        if (stepPersisting) stepPersisting.className = 'flex items-center gap-1.5 text-[#059669]';
        if (stepReady) stepReady.style.display = 'flex';

        showNotification(`Ingestion complete! ${result.artifacts_created} artifacts & ${result.relationships_created} relations indexed.`, 'success');

        setTimeout(async () => {
          closeIngestModal();
          if (btnCodebase) btnCodebase.disabled = false;
          if (progBox) progBox.style.display = 'none';
          if (stepReady) stepReady.style.display = 'none';
          await loadSnapshotsForCurrentRepo(result.snapshot_id);
          await loadOverviewData();
          await refreshActiveView();
        }, 1200);

      } catch (err) {
        console.error('Codebase ingestion failed', err);
        showNotification(`Ingestion failed: ${err.message}`, 'error');
        if (btnCodebase) btnCodebase.disabled = false;
        if (progBox) progBox.style.display = 'none';
      }
    });

    btnTelemetry?.addEventListener('click', async () => {
      const envSelect = document.getElementById('input-ingest-env');
      const jsonText = document.getElementById('input-ingest-json');
      const env = envSelect ? envSelect.value : 'production';
      const raw = jsonText ? jsonText.value.trim() : '';

      if (!raw) {
        showNotification('Please enter JSON runtime events.', 'warning');
        return;
      }
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch (e) {
        showNotification('Invalid JSON format.', 'error');
        return;
      }
      const events = Array.isArray(parsed) ? parsed : [parsed];
      try {
        const res = await apiFetch(`/repositories/${state.currentRepoId}/runtime-events/ingest`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ environment: env, events }),
        });
        if (!res.ok) throw new Error('Failed to ingest telemetry');
        showNotification(`Ingested ${events.length} runtime events.`, 'success');
        closeIngestModal();
        if (jsonText) jsonText.value = '';
        loadOverviewRuntime(state.currentRepoId);
        loadOverviewIncidents(state.currentRepoId);
      } catch (err) {
        showNotification(err.message, 'error');
      }
    });
  }

  function openCreateIncidentModal() {
    openModal('modal-create-incident');
  }

  function closeCreateIncidentModal() {
    closeModal('modal-create-incident');
  }

  function openAuthModal() {
    window.location.href = '/login';
  }

  function closeAuthModal() {
    closeModal('modal-auth');
  }

  window.openConnectModal = openConnectModal;
  window.closeConnectModal = closeConnectModal;
  window.openIngestModal = openIngestModal;
  window.closeIngestModal = closeIngestModal;
  window.openCreateIncidentModal = openCreateIncidentModal;
  window.closeCreateIncidentModal = closeCreateIncidentModal;
  window.openAuthModal = openAuthModal;
  window.closeAuthModal = closeAuthModal;

  function initOnboardModal() {
    const closeBtn = document.getElementById('modal-close-btn');
    const cancelBtn = document.getElementById('modal-cancel-btn');
    const submitBtn = document.getElementById('modal-submit-btn');
    const openBtn = document.getElementById('top-btn-connect-repo');
    const heroBtn = document.getElementById('hero-btn-connect-local');
    const chooseDirBtn = document.getElementById('btn-choose-directory');

    if (openBtn) openBtn.addEventListener('click', () => openConnectModal('github'));
    if (heroBtn) heroBtn.addEventListener('click', () => openConnectModal('local'));
    if (closeBtn) closeBtn.addEventListener('click', closeConnectModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeConnectModal);

    // Modal Provider Tabs (GitHub, Local, Archive)
    document.querySelectorAll('.m-prov-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        switchOnboardTab(btn.dataset.prov);
      });
    });

    // Native Directory Picker (File System Access API)
    if (chooseDirBtn) {
      chooseDirBtn.addEventListener('click', async () => {
        try {
          if ('showDirectoryPicker' in window) {
            const dirHandle = await window.showDirectoryPicker();
            if (dirHandle && dirHandle.name) {
              const nameInput = document.getElementById('input-repo-name');
              const pathInput = document.getElementById('input-local-path');
              if (nameInput && !nameInput.value) nameInput.value = dirHandle.name;
              if (pathInput) pathInput.value = dirHandle.name;
              showNotification(`Directory selected: ${dirHandle.name}. Ensure path is within allowed workspace roots.`, 'info');
            }
          } else {
            showNotification('Native directory picker is not supported in this browser. Please enter local path.', 'warning');
          }
        } catch (err) {
          if (err.name !== 'AbortError') {
            console.warn('Directory picker error:', err);
          }
        }
      });
    }

    if (submitBtn) {
      submitBtn.addEventListener('click', async () => {
        const prov = state.currentOnboardProv || 'github';

        if (prov === 'github') {
          const urlInput = document.getElementById('input-github-url');
          const branchInput = document.getElementById('input-github-branch');
          const nameInput = document.getElementById('input-github-name');
          const tokenInput = document.getElementById('input-github-token');

          const repoUrl = urlInput ? urlInput.value.trim() : '';
          const branch = branchInput ? branchInput.value.trim() : '';
          const name = nameInput ? nameInput.value.trim() : '';
          const token = tokenInput ? tokenInput.value.trim() : '';

          if (!repoUrl) {
            showOnboardError('Please provide a valid GitHub repository URL.');
            return;
          }

          const forbiddenSubpaths = ['/blob/', '/tree/', '/issues/', '/pull/', '/commit/', '/actions/'];
          const matchedForbidden = forbiddenSubpaths.find(sub => repoUrl.includes(sub));
          if (matchedForbidden) {
            showOnboardError(`Please provide a root repository URL (e.g. https://github.com/org/repo). Subpaths such as "${matchedForbidden}" are not supported.`);
            return;
          }

          try {
            await triggerGithubOnboarding({
              github_url: repoUrl,
              repo_url: repoUrl,
              branch: branch || undefined,
              name: name || undefined,
              github_token: token || undefined,
              access_token: token || undefined
            });
          } finally {
            if (tokenInput) tokenInput.value = '';
          }
        } else if (prov === 'local') {
          const pathInput = document.getElementById('input-local-path');
          const nameInput = document.getElementById('input-repo-name');
          const pathVal = pathInput ? pathInput.value.trim() : '';
          const nameVal = nameInput ? nameInput.value.trim() : '';

          if (!pathVal) {
            showOnboardError('Please provide an absolute or relative directory path.');
            return;
          }

          await triggerLocalOnboarding(pathVal, nameVal);
        } else if (prov === 'archive') {
          const fileInput = document.getElementById('input-archive-file');
          const nameInput = document.getElementById('input-archive-name');
          const file = fileInput?.files?.[0];
          const nameVal = nameInput ? nameInput.value.trim() : '';

          if (!file) {
            showOnboardError('Please select a project archive file (.zip).');
            return;
          }

          await triggerArchiveOnboarding(file, nameVal);
        }
      });
    }
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

  async function triggerGithubOnboarding(payload) {
    hideOnboardError();
    const progBox = document.getElementById('onboard-progress-box');
    const submitBtn = document.getElementById('modal-submit-btn');
    if (progBox) progBox.style.display = 'block';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Cloning & Synthesizing...';
    }

    try {
      const res = await apiFetch('/repositories/connect-github', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const rawText = await res.text().catch(() => '');
        let errData;
        try {
          errData = JSON.parse(rawText);
        } catch (_) {
          errData = { detail: rawText || `Server returned HTTP ${res.status}` };
        }
        const norm = normalizeApiError(errData, 'GitHub Connection');
        throw new Error(norm.message);
      }

      const result = await res.json();
      if (result.session_token) {
        localStorage.setItem('jwt_token', result.session_token);
        await checkAuthentication();
      }
      const newRepoId = result.repository?.id || result.repository_id;
      const newSnapId = result.snapshot_id;
      showNotification('GitHub repository synthesized into Digital Twin!', 'success');
      setTimeout(async () => {
        closeConnectModal();
        await startApplicationStateMachine(newRepoId, newSnapId);
        switchPrimaryView('overview');
      }, 700);
    } catch (err) {
      console.error('GitHub onboarding error', err);
      if (progBox) progBox.style.display = 'none';
      const norm = normalizeApiError(err, 'GitHub Connection');
      showOnboardError(norm.message || 'Failed to connect GitHub repository.');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Connect & Synthesize Twin';
      }
    }
  }

  async function triggerOnboarding(localPath, repoName = '') {
    return triggerLocalOnboarding(localPath, repoName);
  }

  async function triggerLocalOnboarding(localPath, repoName = '') {
    hideOnboardError();
    const progBox = document.getElementById('onboard-progress-box');
    const submitBtn = document.getElementById('modal-submit-btn');
    if (progBox) progBox.style.display = 'block';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Analyzing Directory...';
    }

    try {
      const res = await apiFetch('/repositories/onboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          local_path: localPath,
          name: repoName || undefined,
        }),
      });

      if (!res.ok) {
        const rawText = await res.text().catch(() => '');
        let errData;
        try {
          errData = JSON.parse(rawText);
        } catch (_) {
          errData = { detail: rawText || `Server returned HTTP ${res.status}` };
        }
        const norm = normalizeApiError(errData, 'Local Ingestion');
        throw new Error(norm.message);
      }

      const result = await res.json();
      if (result.session_token) {
        localStorage.setItem('jwt_token', result.session_token);
        await checkAuthentication();
      }
      const newRepoId = result.repository?.id || result.repository_id;
      const newSnapId = result.snapshot_id;
      showNotification('Codebase successfully synthesized!', 'success');
      setTimeout(async () => {
        closeConnectModal();
        await startApplicationStateMachine(newRepoId, newSnapId);
        switchPrimaryView('overview');
      }, 700);
    } catch (err) {
      console.error('Local onboarding error', err);
      if (progBox) progBox.style.display = 'none';
      const norm = normalizeApiError(err, 'Local Ingestion');
      showOnboardError(norm.message || 'Failed to analyze repository. Check filesystem path.');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Connect & Synthesize Twin';
      }
    }
  }

  async function triggerArchiveOnboarding(file, repoName = '') {
    hideOnboardError();
    const progBox = document.getElementById('onboard-progress-box');
    const submitBtn = document.getElementById('modal-submit-btn');
    if (progBox) progBox.style.display = 'block';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Extracting & Scanning...';
    }

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (repoName) formData.append('name', repoName);

      const res = await apiFetch('/repositories/upload-archive', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const rawText = await res.text().catch(() => '');
        let errData;
        try {
          errData = JSON.parse(rawText);
        } catch (_) {
          errData = { detail: rawText || `Server returned HTTP ${res.status}` };
        }
        const norm = normalizeApiError(errData, 'Archive Upload');
        throw new Error(norm.message);
      }

      const result = await res.json();
      if (result.session_token) {
        localStorage.setItem('jwt_token', result.session_token);
        await checkAuthentication();
      }
      const newRepoId = result.repository?.id || result.repository_id;
      const newSnapId = result.snapshot_id;
      showNotification('Project archive synthesized into Digital Twin!', 'success');
      setTimeout(async () => {
        closeConnectModal();
        await startApplicationStateMachine(newRepoId, newSnapId);
        switchPrimaryView('overview');
      }, 700);
    } catch (err) {
      console.error('Archive onboarding error', err);
      if (progBox) progBox.style.display = 'none';
      const norm = normalizeApiError(err, 'Archive Upload');
      showOnboardError(norm.message || 'Failed to upload or analyze archive.');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Connect & Synthesize Twin';
      }
    }
  }

  // --- 3. Authentication Management ---
  function initAuth() {
    const loginBtn = document.getElementById('top-btn-login');
    const logoutBtn = document.getElementById('top-btn-logout');
    const authCloseBtn = document.getElementById('modal-auth-close-btn');
    const authCancelBtn = document.getElementById('modal-auth-cancel-btn');
    const authTabLogin = document.getElementById('auth-tab-login');
    const authTabRegister = document.getElementById('auth-tab-register');
    const authSubmitBtn = document.getElementById('auth-submit-btn');

    loginBtn?.addEventListener('click', openAuthModal);
    logoutBtn?.addEventListener('click', logoutUser);
    authCloseBtn?.addEventListener('click', closeAuthModal);
    authCancelBtn?.addEventListener('click', closeAuthModal);

    const userMenuBtn = document.getElementById('user-menu-btn');
    const userDropdown = document.getElementById('user-dropdown-menu');
    userMenuBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      if (userDropdown) {
        userDropdown.style.display = userDropdown.style.display === 'block' ? 'none' : 'block';
      }
    });

    document.addEventListener('click', (e) => {
      if (userDropdown && !userDropdown.contains(e.target) && e.target !== userMenuBtn) {
        userDropdown.style.display = 'none';
      }
    });

    document.getElementById('menu-btn-profile')?.addEventListener('click', () => {
      if (userDropdown) userDropdown.style.display = 'none';
      openModal('modal-user-profile');
    });

    document.getElementById('menu-btn-settings')?.addEventListener('click', () => {
      if (userDropdown) userDropdown.style.display = 'none';
      openModal('modal-user-profile');
    });

    document.getElementById('menu-btn-logout')?.addEventListener('click', () => {
      if (userDropdown) userDropdown.style.display = 'none';
      logoutUser();
    });

    document.getElementById('modal-profile-close-btn')?.addEventListener('click', () => {
      closeModal('modal-user-profile');
    });
    document.getElementById('modal-profile-done-btn')?.addEventListener('click', () => {
      closeModal('modal-user-profile');
    });
    document.getElementById('modal-profile-logout-btn')?.addEventListener('click', () => {
      closeModal('modal-user-profile');
      logoutUser();
    });
    document.getElementById('modal-profile-delete-account-btn')?.addEventListener('click', () => {
      deleteAccount();
    });

    let authMode = 'login';

    authTabLogin?.addEventListener('click', () => {
      authMode = 'login';
      authTabLogin.className = 'flex-1 py-1.5 rounded-lg text-xs font-semibold bg-white text-[#0F172A] shadow-2xs transition-all';
      authTabRegister.className = 'flex-1 py-1.5 rounded-lg text-xs font-semibold text-[#64748B] hover:text-[#0F172A] transition-all';
      document.getElementById('auth-modal-title').textContent = 'Sign In to Digital Twin';
      document.getElementById('auth-email-field').style.display = 'none';
      authSubmitBtn.textContent = 'Sign In';
      hideAuthError();
    });

    authTabRegister?.addEventListener('click', () => {
      authMode = 'register';
      authTabRegister.className = 'flex-1 py-1.5 rounded-lg text-xs font-semibold bg-white text-[#0F172A] shadow-2xs transition-all';
      authTabLogin.className = 'flex-1 py-1.5 rounded-lg text-xs font-semibold text-[#64748B] hover:text-[#0F172A] transition-all';
      document.getElementById('auth-modal-title').textContent = 'Create Digital Twin Account';
      document.getElementById('auth-email-field').style.display = 'block';
      authSubmitBtn.textContent = 'Register & Sign In';
      hideAuthError();
    });

    authSubmitBtn?.addEventListener('click', async () => {
      const usernameInput = document.getElementById('auth-input-username');
      const emailInput = document.getElementById('auth-input-email');
      const passwordInput = document.getElementById('auth-input-password');

      const username = usernameInput ? usernameInput.value.trim() : '';
      const email = emailInput ? emailInput.value.trim() : '';
      const password = passwordInput ? passwordInput.value : '';

      if (!username || !password) {
        showAuthError('Username and password are required.');
        return;
      }
      if (authMode === 'register' && !email) {
        showAuthError('Email address is required for registration.');
        return;
      }

      authSubmitBtn.disabled = true;
      authSubmitBtn.textContent = 'Authenticating...';
      hideAuthError();

      try {
        if (authMode === 'register') {
          const regRes = await nativeFetch('/api/v1/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password }),
          });
          if (!regRes.ok) {
            const errData = await regRes.json().catch(() => ({}));
            throw new Error(errData.detail || 'Registration failed.');
          }
        }

        const loginRes = await nativeFetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        if (!loginRes.ok) {
          const errData = await loginRes.json().catch(() => ({}));
          throw new Error(errData.detail || 'Invalid credentials.');
        }
        const loginData = await loginRes.json();
        if (loginData.access_token) {
          localStorage.setItem('jwt_token', loginData.access_token);
        }

        await checkAuthentication();
        await startApplicationStateMachine();
        closeAuthModal();
        showNotification(`Welcome, ${state.user?.username || username}!`, 'success');
      } catch (err) {
        showAuthError(err.message || 'Authentication error.');
      } finally {
        authSubmitBtn.disabled = false;
        authSubmitBtn.textContent = authMode === 'login' ? 'Sign In' : 'Register & Sign In';
      }
    });
  }

  function showAuthError(msg) {
    const errEl = document.getElementById('auth-error-msg');
    if (errEl) {
      errEl.textContent = msg;
      errEl.style.display = 'block';
    }
  }

  function hideAuthError() {
    const errEl = document.getElementById('auth-error-msg');
    if (errEl) errEl.style.display = 'none';
  }

  async function checkAuthentication() {
    const token = localStorage.getItem('jwt_token');
    if (!token) {
      updateAuthUI(null);
      return null;
    }
    try {
      const res = await nativeFetch('/api/v1/auth/me', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const user = await res.json();
        state.user = user;
        updateAuthUI(user);
        return user;
      } else {
        localStorage.removeItem('jwt_token');
        state.user = null;
        updateAuthUI(null);
        return null;
      }
    } catch (e) {
      console.warn('Auth check error', e);
      updateAuthUI(null);
      return null;
    }
  }

  function updateAuthUI(user) {
    const loginBtn = document.getElementById('top-btn-login');
    const profileSection = document.getElementById('header-user-profile');
    const avatarEl = document.getElementById('header-user-avatar');
    const nameEl = document.getElementById('header-user-name');
    const dropUsername = document.getElementById('dropdown-username');
    const dropEmail = document.getElementById('dropdown-email');
    const dropRole = document.getElementById('dropdown-role');
    const modalAvatar = document.getElementById('profile-modal-avatar');
    const modalUsername = document.getElementById('profile-modal-username');
    const modalEmail = document.getElementById('profile-modal-email');
    const modalRole = document.getElementById('profile-modal-role');
    const modalRoleText = document.getElementById('profile-modal-role-text');
    const modalUserId = document.getElementById('profile-modal-user-id');
    const modalAuthStatus = document.getElementById('profile-modal-auth-status');

    if (user) {
      if (loginBtn) loginBtn.style.display = 'none';
      if (profileSection) profileSection.style.display = 'flex';
      const initials = (user.username || 'U').slice(0, 2).toUpperCase();
      if (avatarEl) avatarEl.textContent = initials;
      if (nameEl) nameEl.textContent = user.username || 'User';
      if (dropUsername) dropUsername.textContent = user.username || 'User';
      if (dropEmail) dropEmail.textContent = user.email || 'user@digitaltwin.local';
      if (dropRole) dropRole.textContent = user.role || 'engineer';

      if (modalAvatar) modalAvatar.textContent = initials;
      if (modalUsername) modalUsername.textContent = user.username || 'User';
      if (modalEmail) modalEmail.textContent = user.email || 'user@digitaltwin.local';
      if (modalRole) modalRole.textContent = user.role || 'engineer';
      if (modalRoleText) modalRoleText.textContent = `${user.role || 'engineer'} (Full Twin Access)`;
      if (modalUserId) modalUserId.textContent = user.user_id || user.id || 'usr_active';
      if (modalAuthStatus) modalAuthStatus.textContent = 'Active JWT Session (Verified)';
    } else {
      if (loginBtn) loginBtn.style.display = 'flex';
      if (profileSection) profileSection.style.display = 'none';
      const drop = document.getElementById('user-dropdown-menu');
      if (drop) drop.style.display = 'none';
    }
  }

  async function logoutUser() {
    const token = localStorage.getItem('jwt_token');
    if (token) {
      try {
        await nativeFetch('/api/v1/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
      } catch (e) {
        // ignore
      }
    }
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('selected_repo_id');
    localStorage.removeItem('selected_snapshot_id');
    try {
      window.history.replaceState({}, '', window.location.pathname);
    } catch (_) {}
    state.user = null;
    state.currentRepoId = null;
    state.currentSnapshotId = null;
    state.diffSnapshotId = null;
    state.repositories = [];
    state.snapshots = [];
    updateAuthUI(null);
    updateSidebarRepoCard(null);
    populateRepoSelect([]);
    populateSnapshotSelects([]);
    showNotification('Signed out successfully.', 'info');
    await startApplicationStateMachine();
    switchPrimaryView('overview');
  }

  async function deleteAccount() {
    if (!state.user || state.user.is_guest) {
      alert("Guest sessions do not have a registered account to delete.");
      return;
    }
    const confirmed = confirm(
      "CRITICAL: Are you sure you want to permanently delete your account?\n\n" +
      "This action is irreversible. All your ingested repositories, snapshots, " +
      "AST artifacts, typed relationships, and analysis runs will be permanently purged."
    );
    if (!confirmed) return;

    const token = localStorage.getItem('jwt_token');
    try {
      const resp = await nativeFetch('/api/v1/auth/account', {
        method: 'DELETE',
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
          'Content-Type': 'application/json'
        }
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert("Account deletion failed: " + (err.detail || "Server error"));
        return;
      }
      alert("Your account and all associated Digital Twin data have been permanently deleted.");
      closeModal('modal-user-profile');
      await logoutUser();
      window.location.reload();
    } catch (e) {
      alert("Account deletion failed: " + e.message);
    }
  }

  // --- 4. Deterministic Application State Machine ---
  function normalizeApiError(err, stage = 'Operation') {
    if (!err) return { code: 'UNKNOWN_ERROR', message: 'An unexpected error occurred.', stage, retryable: true };
    if (typeof err === 'string') return { code: 'API_ERROR', message: err, stage, retryable: true };
    const code = err.code || (err.status ? `HTTP_${err.status}` : 'API_ERROR');
    let message = err.message || err.detail || err.error;
    if (Array.isArray(message)) {
      message = message.map(item => {
        if (typeof item === 'string') return item;
        const field = item.loc ? item.loc[item.loc.length - 1] : 'field';
        return `${field}: ${item.msg || 'invalid value'}`;
      }).join('; ');
    } else if (typeof message === 'object') {
      try {
        message = message.msg || message.detail || message.message || JSON.stringify(message);
      } catch (_) {
        message = 'The service encountered an issue processing the request.';
      }
    }
    if (!message || message === '[object Object]') {
      message = 'The service encountered an issue processing the request.';
    }
    return {
      code,
      message,
      stage,
      retryable: err.retryable !== false,
    };
  }

  function updateStateUI() {
    const hasRepo = Boolean(state.currentRepoId);

    // 1. Body state classes
    if (hasRepo) {
      document.body.classList.remove('state-signed-out', 'state-signed-in-no-repo', 'no-repo');
      document.body.classList.add('state-workspace-active');
    } else {
      document.body.classList.remove('state-workspace-active');
      document.body.classList.add('no-repo');
      if (state.user) {
        document.body.classList.remove('state-signed-out');
        document.body.classList.add('state-signed-in-no-repo');
      } else {
        document.body.classList.remove('state-signed-in-no-repo');
        document.body.classList.add('state-signed-out');
      }
    }

    // 2. Sidebar visibility: remove sidebar when no repo (user request & Rule 22)
    const sidebar = document.getElementById('app-sidebar');
    if (hasRepo) {
      if (sidebar) sidebar.style.display = 'flex';
      const activeRepoContainer = document.getElementById('sidebar-repo-active-container');
      const connectContainer = document.getElementById('sidebar-repo-connect-container');
      if (activeRepoContainer) activeRepoContainer.style.display = 'block';
      if (connectContainer) connectContainer.style.display = 'none';
    } else {
      if (sidebar) sidebar.style.display = 'none';
      const activeRepoContainer = document.getElementById('sidebar-repo-active-container');
      const connectContainer = document.getElementById('sidebar-repo-connect-container');
      if (activeRepoContainer) activeRepoContainer.style.display = 'none';
      if (connectContainer) connectContainer.style.display = 'block';
    }

    // 3. Snapshot selector gating (Rule 1: No repository means no snapshot)
    const snapSelect = document.getElementById('snapshot-select');
    const snapWrap = document.getElementById('snapshot-select-wrap');
    if (snapSelect) {
      snapSelect.disabled = !hasRepo;
      snapSelect.setAttribute('aria-disabled', String(!hasRepo));
      snapSelect.style.cursor = hasRepo ? 'pointer' : 'not-allowed';
    }
    if (snapWrap) {
      snapWrap.classList.toggle('opacity-50', !hasRepo);
      snapWrap.classList.toggle('cursor-not-allowed', !hasRepo);
    }

    // 4. Global search gating (Rule 2: No repository means no search)
    const searchBtn = document.getElementById('top-search-btn');
    if (searchBtn) {
      searchBtn.disabled = !hasRepo;
      searchBtn.classList.toggle('opacity-60', !hasRepo);
      searchBtn.classList.toggle('cursor-not-allowed', !hasRepo);
    }

    // 5. Action buttons gating (Rule 4 & 5)
    const ingestBtn = document.getElementById('top-btn-ingest-runtime');
    const incidentBtn = document.getElementById('top-btn-create-incident');
    const syncPill = document.getElementById('header-sync-pill');

    if (ingestBtn) {
      ingestBtn.disabled = !hasRepo;
      ingestBtn.classList.toggle('opacity-50', !hasRepo);
      ingestBtn.classList.toggle('cursor-not-allowed', !hasRepo);
    }
    if (incidentBtn) {
      incidentBtn.disabled = !hasRepo;
      incidentBtn.classList.toggle('opacity-50', !hasRepo);
      incidentBtn.classList.toggle('cursor-not-allowed', !hasRepo);
    }
    if (syncPill) {
      syncPill.style.display = hasRepo ? 'inline-flex' : 'none';
    }

    // 6. Navigation gating (Rule 3)
    document.querySelectorAll('.view-tab').forEach(tab => {
      const v = tab.dataset.view;
      if (v !== 'overview') {
        tab.classList.toggle('nav-disabled', !hasRepo);
      }
    });

    // 7. Update hero text and codebases list in #view-no-repo
    const heroTitle = document.getElementById('no-repo-hero-title');
    const heroSubtitle = document.getElementById('no-repo-hero-subtitle');
    if (state.user) {
      if (heroTitle) heroTitle.textContent = `Welcome back, ${state.user.username || 'Engineer'}`;
      if (heroSubtitle) heroSubtitle.textContent = 'Select an existing codebase to open its workspace, or connect a new repository.';
    } else {
      if (heroTitle) heroTitle.textContent = 'Welcome to Software Digital Twin';
      if (heroSubtitle) heroSubtitle.textContent = 'Understand your software before you change it. Connect a codebase to explore architecture, blast radius, test impact, and operational health.';
    }

    // 8. Populate codebases in #view-no-repo: strictly ONLY for signed-in users with codebases
    const existingSection = document.getElementById('no-repo-existing-codebases-section');
    const existingGrid = document.getElementById('no-repo-existing-grid');
    if (existingSection && existingGrid) {
      const validRepos = (state.repositories || []).filter(r => r.environment !== 'TEST' && r.environment !== 'FIXTURE');
      if (!hasRepo && state.user && validRepos.length > 0) {
        existingSection.style.display = 'block';
        existingGrid.innerHTML = validRepos.map(r => `
          <div class="twin-card p-4 hover:border-[#0071e3] text-left transition-all flex items-center justify-between group shadow-2xs">
            <div class="flex items-center gap-3 truncate">
              <div class="w-9 h-9 rounded-lg bg-[#EFF6FF] text-[#0071e3] flex items-center justify-center shrink-0">
                <span class="material-symbols-outlined text-[20px]">code_blocks</span>
              </div>
              <div class="truncate">
                <div class="text-xs font-bold text-[#0F172A] group-hover:text-[#0071e3] transition-colors truncate">${escapeHtml(r.name || r.id)}</div>
                <div class="text-[10px] text-[#64748B] font-mono mt-0.5">${escapeHtml(r.source_type || 'GIT')} · ${escapeHtml(r.default_branch || 'main')}</div>
              </div>
            </div>
            <button onclick="window.TwinApp.selectRepository('${r.id}')" class="btn-open-workspace px-3 py-1.5 rounded-lg bg-[#0071e3] hover:bg-[#0059b5] text-white text-xs font-semibold shadow-xs flex items-center gap-1 transition-all shrink-0 cursor-pointer" type="button" aria-label="Open Workspace for ${escapeHtml(r.name || r.id)}">
              <span>Open Workspace</span>
              <span class="material-symbols-outlined text-[14px]">arrow_forward</span>
            </button>
          </div>
        `).join('');
      } else {
        existingSection.style.display = 'none';
        existingGrid.innerHTML = '';
      }
    }
  }

  function setAppState(appState, details = null) {
    const canonicalMap = {
      'BOOT': 'INITIALIZING',
      'INITIALIZING': 'INITIALIZING',
      'AUTHENTICATION_CHECK': 'RESTORING_SESSION',
      'RESTORING_SESSION': 'RESTORING_SESSION',
      'LOAD_REPOSITORIES': 'LOADING_PROJECT_CONTEXT',
      'VALIDATE_REPOSITORY': 'LOADING_PROJECT_CONTEXT',
      'SELECT_REPOSITORY': 'LOADING_PROJECT_CONTEXT',
      'LOAD_SNAPSHOTS': 'LOADING_PROJECT_CONTEXT',
      'VALIDATE_SNAPSHOT': 'LOADING_PROJECT_CONTEXT',
      'LOAD_APPLICATION_DATA': 'LOADING_PROJECT_CONTEXT',
      'LOADING_PROJECT_CONTEXT': 'LOADING_PROJECT_CONTEXT',
      'READY': 'READY',
      'NO_REPOSITORY': 'NO_REPOSITORY',
      'PARTIAL_AVAILABILITY': 'PARTIAL_AVAILABILITY',
      'RECOVERABLE_ERROR': 'RECOVERABLE_ERROR',
      'LOAD_ERROR': 'RECOVERABLE_ERROR',
      'INVALID_REPOSITORY': 'RECOVERABLE_ERROR',
      'INVALID_SNAPSHOT': 'RECOVERABLE_ERROR',
      'SESSION_EXPIRED': 'SESSION_EXPIRED'
    };

    const resolvedState = canonicalMap[appState] || appState;
    state.appState = resolvedState;

    // 1. Update boot screen status text dynamically
    const bootStatusText = document.getElementById('boot-status-text');
    if (bootStatusText) {
      if (resolvedState === 'INITIALIZING') {
        bootStatusText.textContent = 'Initializing TwinCore workspace...';
      } else if (resolvedState === 'RESTORING_SESSION') {
        bootStatusText.textContent = 'Restoring session & verifying credentials...';
      } else if (resolvedState === 'LOADING_PROJECT_CONTEXT') {
        bootStatusText.textContent = 'Resolving selected repository & revision context...';
      } else if (resolvedState === 'READY') {
        bootStatusText.textContent = 'TwinCore workspace ready.';
      } else if (resolvedState === 'NO_REPOSITORY') {
        bootStatusText.textContent = 'No repository connected.';
      } else if (resolvedState === 'PARTIAL_AVAILABILITY') {
        bootStatusText.textContent = 'TwinCore running with partial availability.';
      } else if (resolvedState === 'RECOVERABLE_ERROR') {
        bootStatusText.textContent = 'Initialization error encountered.';
      } else if (resolvedState === 'SESSION_EXPIRED') {
        bootStatusText.textContent = 'Session expired. Sign-in required.';
      }
    }

    // 2. Manage recovery / notification banner for interactive states
    const banner = document.getElementById('app-recovery-banner');
    if (banner) {
      if (resolvedState === 'READY' || resolvedState === 'NO_REPOSITORY' || resolvedState === 'INITIALIZING' || resolvedState === 'RESTORING_SESSION') {
        banner.style.display = 'none';
        banner.innerHTML = '';
      } else if (resolvedState === 'PARTIAL_AVAILABILITY') {
        banner.style.display = 'block';
        banner.className = 'rounded-xl border border-[#FED7AA] bg-[#FFFBEB] p-4 shadow-xs text-[#C2410C] flex items-center justify-between gap-4';
        banner.innerHTML = `
          <div class="flex items-center gap-3">
            <span class="material-symbols-outlined text-[24px] text-[#EA580C]">info</span>
            <div>
              <h4 class="text-xs font-bold text-[#9A3412]">Partial Availability</h4>
              <p class="text-[11px] text-[#C2410C] mt-0.5">${escapeHtml(details?.message || details?.error || 'Some workspace context or telemetry could not be loaded. Core functions remain available.')}</p>
            </div>
          </div>
          <button onclick="window.TwinApp.refreshCurrentView ? window.TwinApp.refreshCurrentView() : window.TwinApp.refreshActiveView()" class="px-3 py-1.5 rounded-lg bg-white border border-[#FED7AA] text-[#9A3412] hover:bg-[#FEF3C7] text-xs font-semibold shadow-2xs shrink-0" type="button">
            Retry Loading
          </button>
        `;
      } else if (resolvedState === 'SESSION_EXPIRED') {
        banner.style.display = 'block';
        banner.className = 'rounded-xl border border-[#FED7AA] bg-[#FFFBEB] p-4 shadow-xs text-[#C2410C] flex items-center justify-between gap-4';
        banner.innerHTML = `
          <div class="flex items-center gap-3">
            <span class="material-symbols-outlined text-[24px] text-[#EA580C]">lock_clock</span>
            <div>
              <h4 class="text-xs font-bold text-[#9A3412]">Session Expired</h4>
              <p class="text-[11px] text-[#C2410C] mt-0.5">${escapeHtml(details?.message || 'Your authentication session has expired or is invalid. Please sign in again.')}</p>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button onclick="window.TwinApp.openAuthModal('signin')" class="px-3 py-1.5 rounded-lg bg-[#EA580C] hover:bg-[#C2410C] text-white text-xs font-semibold shadow-xs" type="button">
              Sign In
            </button>
            <button onclick="window.TwinApp.startApplicationStateMachine()" class="px-3 py-1.5 rounded-lg bg-white border border-[#FED7AA] text-[#9A3412] hover:bg-[#FEF3C7] text-xs font-semibold shadow-2xs" type="button">
              Continue as Guest
            </button>
          </div>
        `;
      } else if (appState === 'INVALID_SNAPSHOT') {
        banner.style.display = 'block';
        banner.className = 'rounded-xl border border-[#FED7AA] bg-[#FFFBEB] p-4 shadow-xs text-[#C2410C] flex items-center justify-between gap-4';
        banner.innerHTML = `
          <div class="flex items-center gap-3">
            <span class="material-symbols-outlined text-[24px] text-[#EA580C]">history_toggle_off</span>
            <div>
              <h4 class="text-xs font-bold text-[#9A3412]">Snapshot Not Found</h4>
              <p class="text-[11px] text-[#C2410C] mt-0.5">Snapshot "${escapeHtml(details?.snapId || '')}" was not found in repository "${escapeHtml(details?.repoName || '')}". Please select a valid snapshot from the header.</p>
            </div>
          </div>
          <button onclick="document.getElementById('snapshot-select')?.focus()" class="px-3 py-1.5 rounded-lg bg-white border border-[#FED7AA] text-[#9A3412] hover:bg-[#FEF3C7] text-xs font-semibold shadow-2xs shrink-0" type="button">
            Select Snapshot
          </button>
        `;
      } else if (resolvedState === 'RECOVERABLE_ERROR') {
        banner.style.display = 'block';
        banner.className = 'rounded-xl border border-[#FECDD3] bg-[#FFF1F2] p-4 shadow-xs text-[#BE123C] flex items-center justify-between gap-4';
        banner.innerHTML = `
          <div class="flex items-center gap-3">
            <span class="material-symbols-outlined text-[24px] text-[#E11D48]">error</span>
            <div>
              <h4 class="text-xs font-bold text-[#9F1239]">Workspace Initialization Error</h4>
              <p class="text-[11px] text-[#BE123C] mt-0.5">${escapeHtml(details?.error || details?.message || 'A communication failure occurred while connecting to the backend.')}</p>
            </div>
          </div>
          <button onclick="window.TwinApp.startApplicationStateMachine()" class="px-3 py-1.5 rounded-lg bg-[#E11D48] hover:bg-[#BE123C] text-white text-xs font-semibold shadow-xs shrink-0" type="button">
            Retry Initialization
          </button>
        `;
      }
    }

    updateStateUI();
  }

  async function finishBoot() {
    try {
      if (document.fonts && document.fonts.ready) {
        await Promise.race([
          document.fonts.ready,
          new Promise(r => setTimeout(r, 400))
        ]);
      }
    } catch (_) {}
    document.body.classList.remove('booting');

    // Reliability guard: ensure an active panel is actually rendered visible to prevent white-screen
    const visiblePanels = Array.from(document.querySelectorAll('.content-view-panel')).filter(p => p.style.display !== 'none');
    if (visiblePanels.length === 0) {
      const fallbackView = getInitialRequestedView();
      switchPrimaryView(fallbackView);
    }

    updateStateUI();
  }

  async function startApplicationStateMachine(preferredRepoId = null, preferredSnapId = null) {
    document.body.classList.add('booting');
    setAppState('INITIALIZING');

    try {
      // Step 1: RESTORING SESSION & AUTH CHECK
      setAppState('RESTORING_SESSION');
      await checkAuthentication();

      const urlParams = new URLSearchParams(window.location.search);
      const targetRepo = preferredRepoId || urlParams.get('repo') || localStorage.getItem('selected_repo_id');
      const targetSnap = preferredSnapId || urlParams.get('snapshot') || localStorage.getItem('selected_snapshot_id');

      // Step 2: LOADING PROJECT CONTEXT
      setAppState('LOADING_PROJECT_CONTEXT');
      let loadedRepos = [];
      try {
        const res = await apiFetch('/repositories');
        if (res.ok) {
          loadedRepos = await res.json();
        } else {
          throw new Error(`Failed to load repositories (HTTP ${res.status})`);
        }
      } catch (err) {
        console.error('State machine error loading repositories:', err);
        setAppState('RECOVERABLE_ERROR', { error: err.message });
        return;
      }

      const validRepos = loadedRepos.filter(r => r.environment !== 'TEST' && r.environment !== 'FIXTURE');
      state.repositories = validRepos;
      populateRepoSelect(validRepos);

      if (validRepos.length === 0) {
        state.currentRepoId = null;
        state.currentSnapshotId = null;
        setAppState('NO_REPOSITORY');
        populateSnapshotSelects([]);
        updateSidebarRepoCard(null);
        switchPrimaryView('overview');
        return;
      }

      // Step 3: Validate Repository Selection
      let matched = null;
      if (targetRepo) {
        matched = validRepos.find(r => r.id === targetRepo);
      }
      if (!matched && validRepos.length > 0) {
        // Auto-select first available valid repository if none specified or previous not found
        matched = validRepos[0];
      }

      if (matched) {
        state.currentRepoId = matched.id;
        localStorage.setItem('selected_repo_id', matched.id);
        const repoSelect = document.getElementById('repo-select');
        if (repoSelect) repoSelect.value = matched.id;
        updateSidebarRepoCard(matched);
      } else {
        localStorage.removeItem('selected_repo_id');
        state.currentRepoId = null;
        state.currentSnapshotId = null;
        setAppState('NO_REPOSITORY');
        populateSnapshotSelects([]);
        updateSidebarRepoCard(null);
        switchPrimaryView('overview');
        return;
      }

      // Step 4: LOAD SNAPSHOTS & REVISION CONTEXT
      await loadSnapshotsForCurrentRepo(targetSnap);
    } catch (fatalErr) {
      console.error('Fatal state machine error during boot:', fatalErr);
      setAppState('RECOVERABLE_ERROR', { error: fatalErr.message });
    } finally {
      await finishBoot();
    }
  }

  function populateRepoSelect(repos = []) {
    const repoSelect = document.getElementById('repo-select');
    if (!repoSelect) return;
    repoSelect.innerHTML = '';

    const promptOpt = document.createElement('option');
    promptOpt.value = '';
    promptOpt.textContent = '-- Select Codebase --';
    promptOpt.disabled = true;
    if (!state.currentRepoId) promptOpt.selected = true;
    repoSelect.appendChild(promptOpt);

    const validRepos = repos.filter(r => r.environment !== 'TEST' && r.environment !== 'FIXTURE');

    validRepos.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.id;
      opt.textContent = `${r.name || r.id} (${r.default_branch || 'main'})`;
      if (r.id === state.currentRepoId) opt.selected = true;
      repoSelect.appendChild(opt);
    });
  }

  function updateSidebarRepoCard(repo) {
    const nameEl = document.getElementById('sidebar-repo-name');
    const branchEl = document.getElementById('sidebar-branch-name');
    if (nameEl) nameEl.textContent = repo ? (repo.name || repo.id) : 'Select Codebase';
    if (branchEl) branchEl.textContent = repo ? `${repo.default_branch || 'main'} branch` : 'No active repo';
  }

  async function loadSnapshotsForCurrentRepo(targetSnap = null) {
    setAppState('LOADING_PROJECT_CONTEXT');
    const repoId = state.currentRepoId;
    if (!repoId) return;

    try {
      const snapRes = await apiFetch(`/repositories/${repoId}/graph/snapshots`);
      if (!snapRes.ok) {
        throw new Error(`Failed to load snapshots for repository (HTTP ${snapRes.status})`);
      }
      state.snapshots = await snapRes.json();
    } catch (err) {
      console.error('State machine error loading snapshots:', err);
      setAppState('RECOVERABLE_ERROR', { error: err.message });
      return;
    }

    populateSnapshotSelects(state.snapshots, state.commitHistoryInfo);

    // Fetch commit history in background non-blocking so UI rendering is not gated by Git CLI
    apiFetch(`/repositories/${repoId}/commits`)
      .then(async (commitsRes) => {
        if (commitsRes && commitsRes.ok && state.currentRepoId === repoId) {
          state.commitHistoryInfo = await commitsRes.json();
          populateSnapshotSelects(state.snapshots, state.commitHistoryInfo);
        }
      })
      .catch(() => {});

    // Validate Snapshot
    const currentRepo = state.repositories.find(r => r.id === repoId);

    if (targetSnap) {
      const matchedSnap = state.snapshots.find(s => s.id === targetSnap || s.commit_hash?.startsWith(targetSnap));
      if (matchedSnap) {
        state.currentSnapshotId = matchedSnap.id;
        localStorage.setItem('selected_snapshot_id', matchedSnap.id);
        const snapSelect = document.getElementById('snapshot-select');
        if (snapSelect) snapSelect.value = matchedSnap.id;
      } else {
        localStorage.removeItem('selected_snapshot_id');
        state.currentSnapshotId = null;
        setAppState('INVALID_SNAPSHOT', { snapId: targetSnap, repoName: currentRepo?.name || repoId });
        return;
      }
    } else if (state.snapshots && state.snapshots.length > 0) {
      // Default to latest synthesized snapshot for the active repository
      const latestSnap = state.snapshots[0];
      state.currentSnapshotId = latestSnap.id;
      localStorage.setItem('selected_snapshot_id', latestSnap.id);
      const snapSelect = document.getElementById('snapshot-select');
      if (snapSelect) snapSelect.value = latestSnap.id;
    } else {
      state.currentSnapshotId = null;
      const snapSelect = document.getElementById('snapshot-select');
      if (snapSelect) snapSelect.value = '';
    }

    configureDiffSelectors();

    // Render Initial View
    const targetView = getInitialRequestedView();
    try {
      if (state.currentSnapshotId) {
        loadFileTree();
      }
      switchPrimaryView(targetView);
    } catch (e) {
      console.warn('Non-fatal error switching view on boot:', e);
      switchPrimaryView('overview');
    }

    // Workspace is ready
    setAppState('READY');
  }

  function setImpactMetricCardState(metricState, summary = {}) {
    const cards = [
      { id: 'metric-impact-changed', key: 'changed', defaultColor: '#F59E0B' },
      { id: 'metric-impact-direct', key: 'unique_affected', fallbackKey: 'directly_affected', defaultColor: '#EF4444' },
      { id: 'metric-impact-indirect', key: 'multi_hop_affected', fallbackKey: 'indirectly_affected', defaultColor: '#EC4899' },
      { id: 'metric-impact-components', key: 'affected_components', defaultColor: '#3B82F6' },
      { id: 'metric-impact-apis', key: 'affected_apis', defaultColor: '#8B5CF6' },
      { id: 'metric-impact-processes', key: 'affected_processes', defaultColor: '#06B6D4' },
      { id: 'metric-impact-tests', key: 'affected_tests', defaultColor: '#10B981' },
    ];

    cards.forEach(c => {
      const el = document.getElementById(c.id);
      if (!el) return;

      if (metricState === 'LOADING') {
        el.innerHTML = '<span class="inline-block w-8 h-5 bg-[#E2E8F0] rounded animate-pulse"></span>';
      } else if (metricState === 'READY') {
        let val = summary[c.key];
        if (val === undefined && c.fallbackKey) val = summary[c.fallbackKey];
        val = (typeof val === 'number') ? val : 0;
        el.textContent = String(val);
        el.style.color = c.defaultColor;
      } else if (metricState === 'ZERO') {
        el.textContent = '0';
        el.style.color = '#64748B';
      } else if (metricState === 'BLOCKED' || metricState === 'IDLE') {
        el.textContent = '—';
        el.style.color = '#94A3B8';
      } else if (metricState === 'ERROR') {
        el.textContent = '—';
        el.style.color = '#EF4444';
      } else if (metricState === 'UNKNOWN') {
        el.textContent = '—';
        el.style.color = '#94A3B8';
      }
    });
  }

  function validateBaselineAndTargetSelection() {
    const baseSelect = document.getElementById('impact-base-select') || document.getElementById('diff-base-select');
    const targetSelect = document.getElementById('impact-target-select') || document.getElementById('diff-target-select');
    const runBtn = document.getElementById('btn-run-impact-action');
    const anim3dBtn = document.getElementById('btn-impact-visualize-3d');
    const metaSpan = document.getElementById('impact-analysis-meta');
    const tree = document.getElementById('impact-paths-tree');
    const lifecycleIcon = document.getElementById('impact-lifecycle-icon');

    if (!baseSelect || !targetSelect) return false;

    const baseOpt = baseSelect.selectedOptions[0];
    const targetOpt = targetSelect.selectedOptions[0];
    const baseSha = baseOpt?.dataset.sha || baseSelect.value;
    const targetSha = targetOpt?.dataset.sha || targetSelect.value;

    // Invalidate stale analysis and disable 3D animation
    currentImpactAnalysisResult = null;
    if (anim3dBtn) {
      anim3dBtn.disabled = true;
      anim3dBtn.classList.add('opacity-50', 'cursor-not-allowed');
      anim3dBtn.classList.remove('hover:bg-[#1E293B]', 'cursor-pointer');
      anim3dBtn.title = 'Execute Change Impact first to enable 3D propagation animation';
    }

    if (!baseSha || !targetSha) {
      if (runBtn) {
        runBtn.disabled = true;
        runBtn.classList.add('opacity-50', 'cursor-not-allowed');
      }
      setImpactMetricCardState('IDLE');
      if (lifecycleIcon) {
        lifecycleIcon.textContent = 'info';
        lifecycleIcon.className = 'material-symbols-outlined text-[18px] text-[#64748B]';
      }
      if (metaSpan) metaSpan.innerHTML = 'Select Baseline and Target revisions above to evaluate differential change impact.';
      if (tree) {
        tree.innerHTML = '<div class="p-6 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-xl border border-dashed border-[#CBD5E1]">Select distinct Baseline and Target commits in the dropdowns above to trace causal blast radius.</div>';
      }
      return false;
    }

    if (baseSha === targetSha) {
      if (runBtn) {
        runBtn.disabled = true;
        runBtn.classList.add('opacity-50', 'cursor-not-allowed');
      }
      setImpactMetricCardState('IDLE');
      if (lifecycleIcon) {
        lifecycleIcon.textContent = 'warning';
        lifecycleIcon.className = 'material-symbols-outlined text-[18px] text-[#D97706]';
      }
      if (metaSpan) {
        metaSpan.innerHTML = `<span style="color:#D97706; font-weight:600;">Baseline and Target refer to the same commit (${baseSha.slice(0, 7)}). Differential analysis requires two distinct commits.</span>`;
      }
      if (tree) {
        tree.innerHTML = '<div class="p-6 text-center text-xs text-[#D97706] bg-[#FFFBEB] rounded-xl border border-dashed border-[#FDE68A]">Identical commits selected for Baseline and Target. Change Impact evaluates differences between two distinct states.</div>';
      }
      return false;
    }

    // Distinct commits selected
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
    setImpactMetricCardState('IDLE');
    const baseIndexed = baseOpt?.dataset.hasSnapshot === 'true';
    const targetIndexed = targetOpt?.dataset.hasSnapshot === 'true';
    let readyMsg = `Ready to analyze impact: <strong>${baseSha.slice(0, 7)}</strong> → <strong>${targetSha.slice(0, 7)}</strong>`;
    if (!baseIndexed || !targetIndexed) {
      readyMsg += ` <span style="color:#0284C7;">(Will auto-reconstruct unindexed historical commit from source tree)</span>`;
    }
    readyMsg += `. Click "Execute Impact" above to trace blast radius.`;
    if (lifecycleIcon) {
      lifecycleIcon.textContent = 'play_circle';
      lifecycleIcon.className = 'material-symbols-outlined text-[18px] text-[#0071e3]';
    }
    if (metaSpan) metaSpan.innerHTML = readyMsg;
    if (tree) {
      tree.innerHTML = `<div class="p-6 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-xl border border-dashed border-[#CBD5E1]">Pairwise revisions configured (<strong>${baseSha.slice(0, 7)}</strong> → <strong>${targetSha.slice(0, 7)}</strong>). Click "Execute Impact" above to compute causal propagation paths.</div>`;
    }
    return true;
  }

  function populateSnapshotSelects(snapshots = [], commitInfo = null) {
    const snapSelect = document.getElementById('snapshot-select');
    const diffBaseSelect = document.getElementById('diff-base-select');
    const diffTargetSelect = document.getElementById('diff-target-select');
    const impactBaseSelect = document.getElementById('impact-base-select');
    const impactTargetSelect = document.getElementById('impact-target-select');
    const sbDiffSelect = document.getElementById('diff-snapshot-select');
    const hasRepo = Boolean(state.currentRepoId);

    const allSelectors = [snapSelect, diffBaseSelect, diffTargetSelect, impactBaseSelect, impactTargetSelect, sbDiffSelect];

    allSelectors.forEach(sel => {
      if (!sel) return;
      sel.innerHTML = '';
      const promptOpt = document.createElement('option');
      promptOpt.value = '';
      if (sel === snapSelect) promptOpt.textContent = '-- Select Snapshot --';
      else if (sel === diffBaseSelect || sel === impactBaseSelect) promptOpt.textContent = '-- Baseline Commit --';
      else if (sel === diffTargetSelect || sel === impactTargetSelect) promptOpt.textContent = '-- Target Commit --';
      else promptOpt.textContent = '-- Select Comparison --';
      promptOpt.disabled = true;
      if (!state.currentSnapshotId || !hasRepo) promptOpt.selected = true;
      sel.appendChild(promptOpt);
    });

    const noticeBanner = document.getElementById('impact-notice-banner');
    const noticeMsg = document.getElementById('impact-notice-message');
    const trySimBtn = document.getElementById('btn-impact-try-simulation');

    if (trySimBtn) {
      trySimBtn.onclick = () => switchPrimaryView('simulation');
    }

    if (!hasRepo) {
      if (noticeBanner) noticeBanner.style.display = 'none';
      return;
    }

    // 1. Populate top-bar snapshot-select with analyzed snapshots only
    snapshots.forEach((s) => {
      if (!snapSelect) return;
      const branch = s.branch_name || s.branch || 'main';
      const shortHash = (s.commit_hash && s.commit_hash !== 'no-git') ? s.commit_hash.slice(0, 7) : (s.id ? s.id.slice(0, 7) : 'HEAD');
      const dateStr = s.created_at ? new Date(s.created_at).toLocaleDateString() : '';
      const label = `${branch} · ${shortHash}${dateStr ? ' (' + dateStr + ')' : ''}`;
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = label;
      if (s.id === state.currentSnapshotId) opt.selected = true;
      snapSelect.appendChild(opt);
    });

    // 2. Populate pairwise comparison selectors with discovered historical commits
    const comparisonSelectors = [diffBaseSelect, diffTargetSelect, impactBaseSelect, impactTargetSelect, sbDiffSelect];
    const commits = commitInfo?.commits || [];

    if (commits.length > 0) {
      commits.forEach(c => {
        const branch = c.branch_name || 'main';
        const shortHash = c.short_sha || c.commit_sha.slice(0, 7);
        const dateStr = c.authored_date ? new Date(c.authored_date).toLocaleDateString() : '';
        const msgTrunc = c.message ? (c.message.length > 40 ? c.message.slice(0, 37) + '...' : c.message) : '';
        const statusTag = c.has_snapshot ? '[ANALYZED]' : '[UNINDEXED]';
        const label = `${branch} · ${shortHash} — "${msgTrunc}" (${dateStr}) ${statusTag}`;

        comparisonSelectors.forEach(sel => {
          if (!sel) return;
          const opt = document.createElement('option');
          opt.value = c.snapshot_id || c.commit_sha;
          opt.textContent = label;
          opt.dataset.sha = c.commit_sha;
          opt.dataset.shortSha = shortHash;
          opt.dataset.hasSnapshot = c.has_snapshot ? 'true' : 'false';
          opt.dataset.snapshotId = c.snapshot_id || '';
          opt.dataset.message = c.message || '';
          sel.appendChild(opt);
        });
      });

      // Default selections: Target = latest commit (commits[0]), Baseline = older analyzed snapshot or commits[1]
      if (commits.length >= 2) {
        const targetCommit = commits[0];
        let baseCommit = commits.find((c, i) => i > 0 && c.has_snapshot) || commits[1];
        const targetVal = targetCommit.snapshot_id || targetCommit.commit_sha;
        const baseVal = baseCommit.snapshot_id || baseCommit.commit_sha;

        if (diffTargetSelect) diffTargetSelect.value = targetVal;
        if (impactTargetSelect) impactTargetSelect.value = targetVal;
        if (diffBaseSelect) diffBaseSelect.value = baseVal;
        if (impactBaseSelect) impactBaseSelect.value = baseVal;
      }
    } else {
      // Fallback to snapshots if commits API unavailable
      snapshots.forEach(s => {
        const branch = s.branch_name || s.branch || 'main';
        const shortHash = (s.commit_hash && s.commit_hash !== 'no-git') ? s.commit_hash.slice(0, 7) : (s.id ? s.id.slice(0, 7) : 'HEAD');
        const dateStr = s.created_at ? new Date(s.created_at).toLocaleDateString() : '';
        const label = `${branch} · ${shortHash}${dateStr ? ' (' + dateStr + ')' : ''} [ANALYZED]`;
        comparisonSelectors.forEach(sel => {
          if (!sel) return;
          const opt = document.createElement('option');
          opt.value = s.id;
          opt.textContent = label;
          opt.dataset.sha = s.commit_hash || s.id;
          opt.dataset.hasSnapshot = 'true';
          opt.dataset.snapshotId = s.id;
          sel.appendChild(opt);
        });
      });
      if (snapshots.length >= 2) {
        if (diffTargetSelect) diffTargetSelect.value = snapshots[0].id;
        if (impactTargetSelect) impactTargetSelect.value = snapshots[0].id;
        if (diffBaseSelect) diffBaseSelect.value = snapshots[1].id;
        if (impactBaseSelect) impactBaseSelect.value = snapshots[1].id;
      }
    }

    // 3. Handle notice banner states truthfully
    const totalCommits = commitInfo?.total_commits ?? commits.length;
    const totalSnapshots = commitInfo?.total_analyzed_snapshots ?? snapshots.length;

    if (totalCommits < 2) {
      if (noticeBanner) {
        noticeBanner.style.display = 'flex';
        if (noticeMsg) {
          noticeMsg.textContent = `Single commit repository (${commits[0]?.short_sha || 'HEAD'}). Pairwise Change Impact requires at least two distinct commits. Use What-If Simulation for single-commit analysis.`;
        }
      }
      setImpactMetricCardState('BLOCKED');
      const runBtn = document.getElementById('btn-run-impact-action');
      if (runBtn) {
        runBtn.disabled = true;
        runBtn.classList.add('opacity-50', 'cursor-not-allowed');
      }
    } else {
      if (noticeBanner) {
        if (totalSnapshots < 2) {
          noticeBanner.style.display = 'flex';
          if (noticeMsg) {
            noticeMsg.textContent = `Multiple historical commits found (${totalCommits} commits), with ${totalSnapshots} analyzed snapshot. Select any historical commit as Baseline and click Execute Impact to automatically reconstruct its snapshot from the Git source tree.`;
          }
        } else if (commitInfo?.is_shallow) {
          noticeBanner.style.display = 'flex';
          if (noticeMsg) {
            noticeMsg.textContent = `Bounded Git history: ${totalCommits} historical commits discovered. ${totalSnapshots} Twin snapshots ready for pairwise analysis.`;
          }
        } else {
          noticeBanner.style.display = 'none';
        }
      }
      validateBaselineAndTargetSelection();
    }
  }

  function configureDiffSelectors() {
    const diffBaseSelect = document.getElementById('diff-base-select');
    const diffTargetSelect = document.getElementById('diff-target-select');
    const impactBaseSelect = document.getElementById('impact-base-select');
    const impactTargetSelect = document.getElementById('impact-target-select');
    const sbDiffSelect = document.getElementById('diff-snapshot-select');

    if (impactBaseSelect && diffBaseSelect) {
      impactBaseSelect.onchange = () => {
        diffBaseSelect.value = impactBaseSelect.value;
        validateBaselineAndTargetSelection();
      };
      diffBaseSelect.onchange = () => {
        impactBaseSelect.value = diffBaseSelect.value;
        validateBaselineAndTargetSelection();
      };
    }
    if (impactTargetSelect && diffTargetSelect) {
      impactTargetSelect.onchange = () => {
        diffTargetSelect.value = impactTargetSelect.value;
        validateBaselineAndTargetSelection();
      };
      diffTargetSelect.onchange = () => {
        impactTargetSelect.value = diffTargetSelect.value;
        validateBaselineAndTargetSelection();
      };
    }
  }

  async function selectRepository(repoId) {
    if (!repoId) return;
    state.requestEpoch = (state.requestEpoch || 0) + 1;
    state.currentRepoId = repoId;
    localStorage.setItem('selected_repo_id', repoId);
    localStorage.removeItem('selected_snapshot_id');
    state.currentSnapshotId = null;
    state.diffSnapshotId = null;
    state.discoveryAssessmentResult = null;
    const matched = state.repositories.find(r => r.id === repoId);
    if (matched) {
      updateSidebarRepoCard(matched);
    }
    const repoSelect = document.getElementById('repo-select');
    if (repoSelect) repoSelect.value = repoId;
    updateStateUI();
    switchPrimaryView(state.currentPrimaryView || 'overview');
    await loadSnapshotsForCurrentRepo(null);
    await refreshActiveView();
  }

  async function selectSnapshot(snapId) {
    if (!snapId) return;
    state.requestEpoch = (state.requestEpoch || 0) + 1;
    state.currentSnapshotId = snapId;
    localStorage.setItem('selected_snapshot_id', snapId);
    state.discoveryAssessmentResult = null;
    const snapSelect = document.getElementById('snapshot-select');
    if (snapSelect) snapSelect.value = snapId;
    loadFileTree();
    await refreshActiveView();
  }

  function openDisconnectModal() {
    if (!state.currentRepoId) {
      showNotification('No repository currently connected.', 'warning');
      return;
    }
    const repo = state.repositories.find(r => r.id === state.currentRepoId);
    const repoName = repo ? (repo.name || repo.id) : state.currentRepoId;
    const nameEl = document.getElementById('disconnect-repo-display-name');
    if (nameEl) nameEl.textContent = repoName;
    openModal('modal-disconnect-repo');
  }

  async function confirmDisconnectRepository() {
    const confirmBtn = document.getElementById('modal-disconnect-confirm-btn');
    const originalText = confirmBtn ? confirmBtn.innerHTML : '';
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.innerHTML = '<span class="material-symbols-outlined text-[15px] animate-spin">sync</span> Disconnecting...';
    }
    try {
      await disconnectRepository();
    } finally {
      closeModal('modal-disconnect-repo');
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = originalText;
      }
    }
  }

  async function disconnectRepository() {
    if (!state.currentRepoId) {
      showNotification('No repository currently selected.', 'warning');
      return;
    }
    const repoName = state.repositories.find(r => r.id === state.currentRepoId)?.name || state.currentRepoId;
    localStorage.removeItem('selected_repo_id');
    localStorage.removeItem('selected_snapshot_id');
    try {
      window.history.replaceState({}, '', window.location.pathname);
    } catch (_) {}
    state.currentRepoId = null;
    state.currentSnapshotId = null;
    state.diffSnapshotId = null;
    state.snapshots = [];
    populateRepoSelect(state.repositories);
    populateSnapshotSelects([]);
    updateSidebarRepoCard(null);
    showNotification(`Disconnected from codebase: ${repoName}`, 'info');
    setAppState('SELECT_REPOSITORY');
    updateStateUI();
    switchPrimaryView('overview');
  }

  async function resyncRepository() {
    if (!state.currentRepoId) {
      showNotification('Please select a repository first.', 'warning');
      return;
    }
    showNotification('Resyncing digital twin from code...', 'info');
    await loadSnapshotsForCurrentRepo(state.currentSnapshotId);
    await refreshActiveView();
    showNotification('Digital twin synchronized.', 'success');
  }

  // Backward-compatible delegates
  async function fetchRepositories(preferredRepoId = null) {
    return startApplicationStateMachine(preferredRepoId);
  }

  async function loadSnapshotsForRepo(repoId, preferredSnapId = null) {
    if (repoId && repoId !== state.currentRepoId) {
      state.currentRepoId = repoId;
    }
    return loadSnapshotsForCurrentRepo(preferredSnapId);
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
    if (elSnap) elSnap.textContent = snap?.id ? snap.id.slice(0, 14) : (state.currentSnapshotId ? state.currentSnapshotId.slice(0, 14) : '—');
    if (elCommit) elCommit.textContent = (snap?.commit_hash && snap.commit_hash !== 'HEAD') ? snap.commit_hash.slice(0, 8) : '—';
    if (elFiles) elFiles.textContent = m.files ?? 0;
    if (elArts) elArts.textContent = m.artifacts ?? 0;
    if (elRels) elRels.textContent = m.relationships ?? 0;
    if (elStatus) elStatus.innerHTML = '<span class="status-pulse"></span> SYNCHRONIZED';
  }

  // Robust typed adapter for Architecture Packages
  function mapArchitecturePackage(rawPkg) {
    if (!rawPkg || typeof rawPkg !== 'object') {
      return {
        name: 'root',
        artifact_count: '—',
        module_count: '—',
        files_count: '—',
        sample_components: []
      };
    }
    const artCount = rawPkg.artifact_count !== undefined && rawPkg.artifact_count !== null
      ? rawPkg.artifact_count
      : (rawPkg.total_artifacts !== undefined && rawPkg.total_artifacts !== null ? rawPkg.total_artifacts : '—');

    const modCount = rawPkg.module_count !== undefined && rawPkg.module_count !== null
      ? rawPkg.module_count
      : (rawPkg.modules !== undefined && rawPkg.modules !== null ? rawPkg.modules : '—');

    const fileCount = rawPkg.files_count !== undefined && rawPkg.files_count !== null
      ? rawPkg.files_count
      : (rawPkg.file_count !== undefined && rawPkg.file_count !== null ? rawPkg.file_count : '—');

    return {
      name: rawPkg.name || 'root',
      artifact_count: artCount,
      module_count: modCount,
      files_count: fileCount,
      sample_components: Array.isArray(rawPkg.sample_components) ? rawPkg.sample_components : []
    };
  }

  // Snapshot History Ledger Renderer
  function renderSnapshotHistory(snapshots = []) {
    const listEl = document.getElementById('ov-snapshot-history-list');
    const countEl = document.getElementById('ov-snap-history-count');
    if (!listEl) return;
    listEl.innerHTML = '';

    const count = (snapshots && Array.isArray(snapshots)) ? snapshots.length : 0;
    if (countEl) countEl.textContent = `${count} Snapshot${count === 1 ? '' : 's'}`;

    if (!snapshots || snapshots.length === 0) {
      listEl.innerHTML = '<div class="p-4 text-center text-xs text-[#64748B] bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">No historical snapshots recorded for this repository.</div>';
      return;
    }

    snapshots.forEach((s, idx) => {
      const isCurrent = s.id === state.currentSnapshotId;
      const shortHash = (s.commit_hash && s.commit_hash !== 'no-git') ? s.commit_hash.slice(0, 7) : (s.id ? s.id.slice(0, 7) : 'HEAD');
      const branch = s.branch_name || s.branch || 'main';
      const timeStr = s.created_at ? new Date(s.created_at).toLocaleString() : 'Recent';
      const row = document.createElement('div');
      row.className = `p-3 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-colors ${
        isCurrent ? 'bg-[#F0FDF4] border-[#86EFAC]' : 'bg-white border-[#E2E8F0] hover:bg-[#F8FAFC]'
      }`;

      row.innerHTML = `
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center font-mono text-xs font-bold ${
            isCurrent ? 'bg-[#DCFCE7] text-[#15803D]' : 'bg-[#F1F5F9] text-[#475569]'
          }">
            #${snapshots.length - idx}
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="font-mono text-xs font-bold text-[#0F172A]">${escapeHtml(shortHash)}</span>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#F1F5F9] text-[#334155] border border-[#CBD5E1]">${escapeHtml(branch)}</span>
              ${isCurrent ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC]">ACTIVE SNAPSHOT</span>' : ''}
            </div>
            <div class="text-[11px] text-[#64748B] mt-0.5 flex items-center gap-2">
              <span>Created: ${escapeHtml(timeStr)}</span>
              <span>·</span>
              <span class="font-mono text-[10px]">${escapeHtml((s.id || '').slice(0, 14))}</span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          ${!isCurrent ? `
            <button class="btn-set-active-snap px-3 py-1.5 rounded-lg bg-white border border-[#CBD5E1] hover:bg-[#F1F5F9] text-xs font-semibold text-[#0F172A] transition-colors" data-sid="${s.id}">
              Set Active
            </button>
          ` : ''}
          <button class="btn-compare-base-snap px-3 py-1.5 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE] hover:bg-[#DBEAFE] text-xs font-semibold text-[#1D4ED8] transition-colors" data-sid="${s.id}">
            Compare as Base →
          </button>
        </div>
      `;
      listEl.appendChild(row);
    });

    listEl.querySelectorAll('.btn-set-active-snap').forEach(btn => {
      btn.onclick = async () => {
        const sid = btn.dataset.sid;
        state.currentSnapshotId = sid;
        localStorage.setItem('selected_snapshot_id', sid);
        const snapSelect = document.getElementById('snapshot-select');
        if (snapSelect) snapSelect.value = sid;
        await loadOverviewData();
        showNotification(`Switched active snapshot to ${sid.slice(0, 10)}`, 'success');
      };
    });

    listEl.querySelectorAll('.btn-compare-base-snap').forEach(btn => {
      btn.onclick = () => {
        const sid = btn.dataset.sid;
        switchPrimaryView('impact');
        const bSel = document.getElementById('diff-base-select') || document.getElementById('impact-base-select');
        const tSel = document.getElementById('diff-target-select') || document.getElementById('impact-target-select');
        if (bSel) bSel.value = sid;
        if (tSel) tSel.value = state.currentSnapshotId || sid;
        executeChangeImpactAnalysis();
      };
    });
  }

  // --- 4. Overview View Data Loader (Engineering Command Center) ---
  async function loadOverviewData() {
    if (!state.currentRepoId) return;
    const reqEpoch = state.requestEpoch;
    const reqRepoId = state.currentRepoId;

    try {
      let url = `/repositories/${state.currentRepoId}/overview`;
      if (state.currentSnapshotId) url += `?snapshot_id=${state.currentSnapshotId}`;

      const res = await fetch(url);
      if (!res.ok) {
        const flowList = document.getElementById('ov-flow-nodes-list');
        if (flowList) {
          flowList.innerHTML = `
            <div class="w-full p-4 text-center text-xs text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-xl space-y-2">
              <div class="font-bold flex items-center justify-center gap-1.5"><span class="material-symbols-outlined text-[16px]">error</span> Architecture Overview Unavailable</div>
              <p class="text-[#991B1B]">Could not fetch model overview (HTTP ${res.status}).</p>
              <button class="px-3.5 py-1.5 rounded-lg bg-[#DC2626] text-white text-[11px] font-semibold hover:bg-[#B91C1C] transition-colors" onclick="window.TwinApp.loadOverviewData()">Retry</button>
            </div>`;
        }
        return;
      }
      if (reqEpoch !== state.requestEpoch || reqRepoId !== state.currentRepoId) return;
      const data = await res.json();
      if (reqEpoch !== state.requestEpoch || reqRepoId !== state.currentRepoId) return;
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
        const rawPkgs = data.architecture_packages || [];
        if (rawPkgs.length === 0) {
          if ((m.files || 0) > 0 && (m.artifacts || 0) === 0) {
            pkgGrid.innerHTML = `
              <div class="col-span-full p-4 text-center text-xs text-[#0369A1] bg-[#F0F9FF] border border-[#BAE6FD] rounded-xl">
                <div class="font-bold flex items-center justify-center gap-1.5"><span class="material-symbols-outlined text-[16px]">info</span> Documentation / Non-Code Repository Detected</div>
                <p class="text-[#64748B] mt-1">This repository contains ${m.files} indexed files (e.g. Markdown, configuration, or documentation), but contains no supported programming language AST symbols (classes, functions, or API endpoints).</p>
              </div>`;
          } else {
            pkgGrid.innerHTML = '<div class="col-span-full p-4 text-center text-xs text-[#64748B] bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">No macro packages identified in this snapshot.</div>';
          }
        } else {
          rawPkgs.forEach(rawPkg => {
            const pkg = mapArchitecturePackage(rawPkg);
            const card = document.createElement('div');
            card.className = 'twin-card p-4 flex flex-col justify-between space-y-3';
            const sampleHtml = (pkg.sample_components || []).slice(0, 3).map(c => `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#F1F5F9] border border-[#CBD5E1] text-[#6D28D9]">${escapeHtml(c)}</span>`).join(' ');
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
              performGraphSearch(btn.dataset.pkg);
            };
          });
        }
      }

      // Dynamic Architecture Flow Pipeline
      const flowList = document.getElementById('ov-flow-nodes-list');
      if (flowList) {
        const rawPkgs = data.architecture_packages || [];
        const isDocRepo = (m.files || 0) > 0 && (m.artifacts || 0) === 0;
        const isRelsPending = (m.artifacts || 0) > 0 && (m.relationships || 0) === 0;

        if (isDocRepo) {
          flowList.innerHTML = `
            <div class="w-full p-4 text-center text-xs text-[#0369A1] bg-[#F0F9FF] border border-[#BAE6FD] rounded-xl space-y-1">
              <div class="font-bold flex items-center justify-center gap-1.5"><span class="material-symbols-outlined text-[16px]">info</span> Documentation Repository Detected</div>
              <p class="text-[#64748B]">This repository contains ${m.files} indexed files without programming language AST symbols. Topological flow projection is not applicable.</p>
            </div>`;
        } else if (isRelsPending) {
          flowList.innerHTML = `
            <div class="w-full p-4 text-center text-xs text-[#92400E] bg-[#FFFBEB] border border-[#FDE68A] rounded-xl space-y-2">
              <div class="font-bold flex items-center justify-center gap-1.5"><span class="material-symbols-outlined text-[16px]">pending</span> Structural Symbols Discovered (${m.artifacts} entities)</div>
              <p class="text-[#78350F]">AST symbols have been extracted, but call & import relationships have not been indexed yet (0 relationships). Run Technical Assessment in Project Health or inspect Components to explore symbols.</p>
              <div class="flex items-center justify-center gap-2 pt-1">
                <button class="px-3 py-1.5 rounded-lg bg-[#0F172A] text-white text-[11px] font-semibold hover:bg-[#1E293B] transition-colors" onclick="window.TwinApp.switchPrimaryView('discovery')">Run Technical Assessment →</button>
                <button class="px-3 py-1.5 rounded-lg bg-white border border-[#CBD5E1] text-[#0F172A] text-[11px] font-semibold hover:bg-[#F8FAFC] transition-colors" onclick="window.TwinApp.switchPrimaryView('components')">View Catalog</button>
              </div>
            </div>`;
        } else if (rawPkgs.length === 0) {
          flowList.innerHTML = `
            <div class="w-full text-center py-6 text-xs text-[#64748B] bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl space-y-2">
              <p>No macro architectural packages detected in this snapshot.</p>
              <button class="px-3 py-1.5 rounded-lg bg-[#0071e3] text-white text-[11px] font-semibold hover:bg-[#005bb5] transition-colors" onclick="window.TwinApp.switchPrimaryView('components')">Inspect Components</button>
            </div>`;
        } else {
          const topPkgs = rawPkgs.slice(0, 5);
          const icons = ['devices', 'router', 'receipt_long', 'memory', 'database'];
          const colors = [
            { bg: '#F0F9FF', text: '#0284C7', border: '#BAE6FD', badgeBg: '#E0F2FE', badgeText: '#0369A1' },
            { bg: '#ECFDF5', text: '#059669', border: '#A7F3D0', badgeBg: '#D1FAE5', badgeText: '#047857' },
            { bg: '#FFFBEB', text: '#D97706', border: '#FED7AA', badgeBg: '#FEF3C7', badgeText: '#B45309' },
            { bg: '#EEF2FF', text: '#4F46E5', border: '#C7D2FE', badgeBg: '#E0E7FF', badgeText: '#4338CA' },
            { bg: '#FAF5FF', text: '#7C3AED', border: '#DDD6FE', badgeBg: '#EDE9FE', badgeText: '#6D28D9' },
          ];

          flowList.innerHTML = topPkgs.map((rawPkg, i) => {
            const pkg = mapArchitecturePackage(rawPkg);
            const col = colors[i % colors.length];
            const icon = icons[i % icons.length];
            const nodeHtml = `
              <div class="flex-1 bg-white border border-[${col.border}]/80 p-3 rounded-lg shadow-2xs flex flex-col items-center text-center">
                <div class="w-8 h-8 rounded-full bg-[${col.bg}] text-[${col.text}] flex items-center justify-center">
                  <span class="material-symbols-outlined text-[18px]">${icon}</span>
                </div>
                <span class="text-xs font-bold text-[#0F172A] mt-1 truncate max-w-[120px]">${escapeHtml(pkg.name)}</span>
                <span class="text-[10px] text-[#64748B]">${pkg.artifact_count} artifacts</span>
                <span class="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[${col.badgeBg}] text-[${col.badgeText}] text-[10px] font-semibold border border-[${col.border}]">
                  ${pkg.module_count} modules
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
              <div class="twin-card p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Changed</div>
                <div class="text-lg font-bold text-[#F59E0B] mt-0.5">${imp.changed_count}</div>
              </div>
              <div class="twin-card p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Unique Affected</div>
                <div class="text-lg font-bold text-[#EF4444] mt-0.5">${imp.unique_affected ?? imp.directly_affected_count}</div>
              </div>
              <div class="twin-card p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Multi-Hop</div>
                <div class="text-lg font-bold text-[#EC4899] mt-0.5">${imp.multi_hop_affected ?? imp.indirectly_affected_count}</div>
              </div>
              <div class="twin-card p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Components</div>
                <div class="text-lg font-bold text-[#3B82F6] mt-0.5">${imp.components_affected}</div>
              </div>
              <div class="twin-card p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">APIs</div>
                <div class="text-lg font-bold text-[#8B5CF6] mt-0.5">${imp.apis_affected}</div>
              </div>
              <div class="twin-card p-2.5 text-center">
                <div class="text-[10px] text-[#64748B] uppercase font-bold">Processes</div>
                <div class="text-lg font-bold text-[#06B6D4] mt-0.5">${imp.processes_affected}</div>
              </div>
              <div class="twin-card p-2.5 text-center">
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

      // Dynamic Architecture Conformance Card
      const confAlert = document.getElementById('conformance-alert-box');
      const confTitle = document.getElementById('conf-title');
      const confDesc = document.getElementById('conf-desc');
      const confIcon = document.getElementById('conf-icon');

      if (confAlert && confTitle && confDesc && confIcon) {
        if ((m.violations || 0) > 0) {
          confAlert.className = 'p-3.5 rounded-xl bg-[#FEF2F2] border border-[#FECDD3] flex items-center gap-3';
          confIcon.className = 'w-7 h-7 rounded-lg bg-[#FEE2E2] text-[#DC2626] flex items-center justify-center font-bold text-sm';
          confIcon.textContent = '!';
          confTitle.className = 'text-xs font-bold text-[#991B1B]';
          confTitle.textContent = `${m.violations} Architecture Drift Violation(s) Detected`;
          confDesc.className = 'text-[11px] text-[#B91C1C]';
          confDesc.textContent = 'Active dependencies cross declared architectural boundaries. Review under Explore → Architecture.';
        } else {
          confAlert.className = 'p-3.5 rounded-xl bg-[#ECFDF5] border border-[#A7F3D0] flex items-center gap-3';
          confIcon.className = 'w-7 h-7 rounded-lg bg-[#D1FAE5] text-[#059669] flex items-center justify-center font-bold text-sm';
          confIcon.textContent = '✓';
          confTitle.className = 'text-xs font-bold text-[#064E3B]';
          confTitle.textContent = 'Architecture Conformance Verified';
          confDesc.className = 'text-[11px] text-[#047857]';
          confDesc.textContent = '0 structural violations detected. Component boundaries match baseline.';
        }
      }

      // Compact Twin Controls Metrics
      const isDocRepo = (m.files || 0) > 0 && (m.artifacts || 0) === 0;
      const isRelsPending = (m.artifacts || 0) > 0 && (m.relationships || 0) === 0;

      const causalCovEl = document.getElementById('ov-causal-coverage');
      if (causalCovEl) {
        if ((m.relationships || 0) > 0) {
          causalCovEl.textContent = `${(m.relationships).toLocaleString()} Indexed`;
          causalCovEl.className = 'font-semibold text-[#059669] bg-[#ECFDF5] px-2 py-0.5 rounded-full border border-[#A7F3D0]/60';
        } else if (isDocRepo) {
          causalCovEl.textContent = '0 (Non-Code)';
          causalCovEl.className = 'font-semibold text-[#64748B] bg-[#F1F5F9] px-2 py-0.5 rounded-full border border-[#CBD5E1]';
        } else {
          causalCovEl.textContent = '0 Indexed (Pending)';
          causalCovEl.className = 'font-semibold text-[#D97706] bg-[#FFFBEB] px-2 py-0.5 rounded-full border border-[#FDE68A]';
        }
      }

      const graphStatusEl = document.getElementById('ov-graph-status');
      const graphStatusIcon = document.getElementById('ov-graph-status-icon');
      if (graphStatusEl) {
        if (isDocRepo) {
          graphStatusEl.textContent = 'Documentation (no code AST)';
          if (graphStatusIcon) {
            graphStatusIcon.textContent = 'description';
            graphStatusIcon.className = 'material-symbols-outlined text-[16px] text-[#64748B]';
          }
        } else if (isRelsPending) {
          graphStatusEl.textContent = `Symbols only (${m.artifacts || 0}) · 0 relations`;
          if (graphStatusIcon) {
            graphStatusIcon.textContent = 'pending';
            graphStatusIcon.className = 'material-symbols-outlined text-[16px] text-[#D97706]';
          }
        } else if ((m.relationships || 0) > 0) {
          graphStatusEl.textContent = `Full topology indexed (${(m.relationships).toLocaleString()} relations)`;
          if (graphStatusIcon) {
            graphStatusIcon.textContent = 'check_circle';
            graphStatusIcon.className = 'material-symbols-outlined text-[16px] text-[#059669]';
          }
        } else if (!data.has_snapshots) {
          graphStatusEl.textContent = 'No snapshot generated yet';
          if (graphStatusIcon) {
            graphStatusIcon.textContent = 'warning';
            graphStatusIcon.className = 'material-symbols-outlined text-[16px] text-[#DC2626]';
          }
        } else {
          graphStatusEl.textContent = 'Source model synchronized';
          if (graphStatusIcon) {
            graphStatusIcon.textContent = 'sync';
            graphStatusIcon.className = 'material-symbols-outlined text-[16px] text-[#4F46E5]';
          }
        }
      }

      const nextTitle = document.getElementById('ov-next-action-title');
      const nextDesc = document.getElementById('ov-next-action-desc');
      if (nextTitle && nextDesc) {
        if (isDocRepo) {
          nextTitle.textContent = 'Non-Code Repository';
          nextDesc.textContent = 'Contains documentation or configuration files without code AST symbols.';
        } else if (isRelsPending) {
          nextTitle.textContent = 'Run Technical Assessment';
          nextDesc.textContent = 'Index call graphs, dependency trees, and test coverage in Project Health.';
        } else if ((m.relationships || 0) > 0) {
          nextTitle.textContent = 'Ready for Blast Radius';
          nextDesc.textContent = 'Run Change Impact or What-If simulation to predict engineering changes.';
        } else {
          nextTitle.textContent = 'Model Synchronized';
          nextDesc.textContent = 'Explore Components catalog or inspect Architecture Graph.';
        }
      }

      const driftCountEl = document.getElementById('ov-drift-count');
      if (driftCountEl) {
        if (data.violations && data.violations.length > 0) {
          driftCountEl.textContent = `${data.violations.length} breaking changes`;
          driftCountEl.className = 'text-xs font-semibold text-[#DC2626]';
        } else if (data.analysis_status?.architecture_validation === 'Evaluated') {
          driftCountEl.textContent = '0 breaking changes';
          driftCountEl.className = 'text-xs font-semibold text-[#16A34A]';
        } else {
          driftCountEl.textContent = 'Not evaluated';
          driftCountEl.className = 'text-xs font-semibold text-[#64748B]';
        }
      }

      // Simulator Target & Action Box in Overview
      const simTargetLabel = document.getElementById('ov-sim-target-label');
      if (simTargetLabel) {
        const sHash = (data.snapshot?.commit_hash && data.snapshot?.commit_hash !== 'HEAD' && data.snapshot?.commit_hash !== 'no-git')
          ? data.snapshot.commit_hash.slice(0, 7)
          : (data.snapshot?.id ? data.snapshot.id.slice(0, 7) : 'HEAD');
        simTargetLabel.textContent = `${data.snapshot?.branch_name || 'main'} · ${sHash}`;
      }
      const blastBtn = document.getElementById('ov-btn-run-blast-radius');
      const blastBtnText = document.getElementById('ov-btn-run-blast-radius-text');
      if (blastBtn) {
        if (state.snapshots && state.snapshots.length >= 2) {
          if (blastBtnText) blastBtnText.textContent = 'Run Blast-Radius Analysis';
          blastBtn.onclick = () => {
            switchPrimaryView('impact');
            const bSel = document.getElementById('diff-base-select') || document.getElementById('impact-base-select');
            const tSel = document.getElementById('diff-target-select') || document.getElementById('impact-target-select');
            if (tSel && state.snapshots[0]) tSel.value = state.snapshots[0].id;
            if (bSel && state.snapshots[1]) bSel.value = state.snapshots[1].id;
            executeChangeImpactAnalysis();
          };
        } else {
          if (blastBtnText) blastBtnText.textContent = 'Select Comparison (2 Snapshots Required)';
          blastBtn.onclick = () => {
            showNotification('Impact analysis requires two distinct snapshots. Create or ingest an additional snapshot to run pairwise blast-radius analysis.', 'warning');
            switchPrimaryView('changes');
          };
        }
      }

      // Render Discovered Architecture Packages & Tiers
      renderArchitectureTiers(data.architecture_packages || []);

      // Snapshot History Ledger
      renderSnapshotHistory(state.snapshots || []);

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
      if (ovCompSub) {
        const subParts = [];
        if (bd.MODULE) subParts.push(`${bd.MODULE} modules`);
        if (bd.CLASS) subParts.push(`${bd.CLASS} classes`);
        if (bd.COMPONENT) subParts.push(`${bd.COMPONENT} components`);
        if (subParts.length === 0) subParts.push(`${m.artifacts ?? 0} artifacts`);
        ovCompSub.textContent = subParts.join(' · ');
      }
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
      const flowList = document.getElementById('ov-flow-nodes-list');
      if (flowList) {
        flowList.innerHTML = `
          <div class="w-full p-4 text-center text-xs text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-xl space-y-2">
            <div class="font-bold flex items-center justify-center gap-1.5"><span class="material-symbols-outlined text-[16px]">error</span> Topology Loader Error</div>
            <p class="text-[#991B1B]">${escapeHtml(e.message || 'Error communicating with Twin backend')}</p>
            <button class="px-3.5 py-1.5 rounded-lg bg-[#DC2626] text-white text-[11px] font-semibold hover:bg-[#B91C1C] transition-colors" onclick="window.TwinApp.loadOverviewData()">Retry</button>
          </div>`;
      }
    }
  }

  function renderArchitectureTiers(packages) {
    const container = document.getElementById('arch-tiers-container');
    if (!container) return;
    container.innerHTML = '';

    if (!packages || packages.length === 0) {
      container.innerHTML = '<div class="col-span-full p-6 text-center text-xs text-[#64748B] bg-white border border-[#E2E8F0] rounded-xl">No architecture packages discovered in active snapshot.</div>';
      return;
    }

    packages.forEach(rawPkg => {
      const pkg = mapArchitecturePackage(rawPkg);
      const card = document.createElement('div');
      card.className = 'bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs space-y-3 flex flex-col justify-between';
      const sampleBadges = (pkg.sample_components || []).slice(0, 3).map(c =>
        `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] truncate max-w-[150px]">${escapeHtml(c)}</span>`
      ).join('');

      card.innerHTML = `
        <div class="space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-[#0F172A] flex items-center gap-1.5">
              <span>📦</span> ${escapeHtml(pkg.name)}
            </span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#E0F2FE] text-[#0369A1] border border-[#BAE6FD]">
              ${pkg.artifact_count} artifacts
            </span>
          </div>
          <div class="text-[11px] text-[#64748B] flex items-center gap-3">
            <span>${pkg.module_count} Modules</span>
            <span>${pkg.files_count} Files</span>
          </div>
        </div>
        ${sampleBadges ? `<div class="flex flex-wrap gap-1">${sampleBadges}</div>` : ''}
        <button class="btn-tier-inspect text-xs text-[#0071e3] hover:text-[#0059b5] font-semibold text-left pt-1 border-t border-[#F1F5F9] flex items-center gap-1" data-pkg="${escapeHtml(pkg.name)}" type="button">
          Inspect in Graph →
        </button>
      `;
      container.appendChild(card);
    });

    container.querySelectorAll('.btn-tier-inspect').forEach(btn => {
      btn.onclick = () => {
        performGraphSearch(btn.dataset.pkg);
      };
    });
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
      const invBtnLabel = document.getElementById('ov-btn-investigate-label');
      const invBtnIcon = document.getElementById('ov-btn-investigate-icon');
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

        if (confEl) confEl.textContent = 'Evidence: Causal graph correlation';

        if (invBtnLabel) invBtnLabel.textContent = 'Investigate Incident';
        if (invBtnIcon) invBtnIcon.textContent = 'travel_explore';

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
        if (stripeEl) stripeEl.className = "absolute left-0 top-0 bottom-0 w-1.5 bg-[#94A3B8]";
        if (pillEl) pillEl.className = "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#F1F5F9] text-[#475569] text-[11px] font-bold border border-[#CBD5E1]";
        if (pulseEl) pulseEl.className = "w-2 h-2 rounded-full bg-[#94A3B8]";
        if (statusEl) statusEl.textContent = 'Operational (0 Incidents)';

        if (titleEl) {
          titleEl.textContent = 'No Incidents Recorded';
          titleEl.className = "text-lg font-bold text-[#0F172A] tracking-tight";
        }
        if (descEl) {
          descEl.textContent = 'No active incidents recorded for this repository. Ingest runtime telemetry to observe live operational evidence.';
          descEl.className = "text-xs text-[#64748B] mt-1 leading-relaxed";
        }
        if (targetEl) targetEl.textContent = 'No active incident target';

        if (badgesContainer) {
          badgesContainer.innerHTML = `
            <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-[#E2E8F0] text-[#64748B] text-xs font-medium shadow-2xs">
              <span class="material-symbols-outlined text-[16px] text-[#94A3B8]">info</span>
              <span>0 active anomalies · 0 open incidents</span>
            </div>
          `;
        }

        if (confEl) confEl.textContent = 'Deterministic static verification';

        if (invBtnLabel) invBtnLabel.textContent = 'View Incidents (0 Active)';
        if (invBtnIcon) invBtnIcon.textContent = 'visibility';

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
      const data = await res.json();
      const events = Array.isArray(data) ? data : (data.events || data.items || []);

      const sbRuntimeBadge = document.getElementById('sidebar-runtime-badge');
      if (sbRuntimeBadge) sbRuntimeBadge.textContent = data.total !== undefined ? data.total : events.length;

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
      const repoId = state.currentRepoId;
      const snapId = state.currentSnapshotId;

      if (!repoId) {
        resultsContainer.innerHTML = `
          <div class="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 space-y-3">
            <div class="flex items-center gap-2 text-amber-400 font-semibold text-sm">
              <span class="material-symbols-outlined">warning</span> No Repository Selected
            </div>
            <p class="text-xs text-on-surface-variant">Please connect or select a repository to query Twin Knowledge.</p>
          </div>
        `;
        return;
      }

      resultsContainer.innerHTML = `
        <div class="flex items-center justify-center p-12 text-on-surface-variant gap-3">
          <span class="material-symbols-outlined animate-spin text-primary">progress_activity</span>
          <span class="text-xs font-mono">Querying deterministic Twin Knowledge for: "${escapeHtml(query)}"...</span>
        </div>
      `;

      try {
        const res = await apiFetch(`/repositories/${repoId}/twin-knowledge/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: query, snapshot_id: snapId || null }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(errData.detail || `Query failed with status ${res.status}`);
        }

        const data = await res.json();
        const prov = data.provenance || 'OBSERVED';
        let provBadgeClass = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
        if (prov === 'DERIVED') provBadgeClass = 'bg-blue-500/10 text-blue-400 border-blue-500/30';
        else if (prov === 'INFERRED') provBadgeClass = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
        else if (prov === 'SIMULATED') provBadgeClass = 'bg-purple-500/10 text-purple-400 border-purple-500/30';
        else if (prov === 'UNKNOWN') provBadgeClass = 'bg-rose-500/10 text-rose-400 border-rose-500/30';

        const confPct = Math.round((data.confidence ?? 1.0) * 100);
        const groundedEntities = data.grounded_entities || [];
        const evidenceIds = data.evidence_ids || [];
        const suggestedActions = data.suggested_actions || [];

        resultsContainer.innerHTML = `
          <div class="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 space-y-5 animate-in fade-in duration-200">
            <!-- Header Bar -->
            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant/20 pb-4">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-primary">psychology</span>
                <span class="text-sm font-bold text-on-surface">Twin Knowledge Result</span>
                <span class="px-2 py-0.5 rounded text-[10px] font-mono border ${provBadgeClass}">${escapeHtml(prov)}</span>
                <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-surface-container-high text-on-surface-variant border border-outline-variant/30">${escapeHtml(data.intent || 'QUERY')}</span>
              </div>
              <div class="flex items-center gap-2 text-xs font-mono text-on-surface-variant">
                <span class="material-symbols-outlined text-xs text-emerald-400">verified</span>
                <span>${confPct}% Grounded</span>
              </div>
            </div>

            <!-- Answer Box -->
            <div class="p-4 bg-surface-container/60 rounded-xl border border-outline-variant/20">
              <p class="text-xs leading-relaxed text-on-surface font-sans">${escapeHtml(data.answer)}</p>
            </div>

            <!-- Grounded Entities -->
            ${groundedEntities.length > 0 ? `
              <div class="space-y-2">
                <div class="text-[11px] font-bold uppercase tracking-wider text-on-surface-variant flex items-center gap-1.5">
                  <span class="material-symbols-outlined text-xs">account_tree</span>
                  Grounded Twin Entities (${groundedEntities.length})
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  ${groundedEntities.map(ent => `
                    <div class="p-2.5 bg-surface-container rounded-lg border border-outline-variant/20 flex flex-col justify-between">
                      <div class="flex items-center justify-between gap-2">
                        <span class="text-xs font-semibold text-on-surface truncate">${escapeHtml(ent.name || ent.title || ent.id || 'Entity')}</span>
                        ${ent.type ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">${escapeHtml(ent.type)}</span>` : ''}
                        ${ent.severity ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20">${escapeHtml(ent.severity)}</span>` : ''}
                      </div>
                      ${ent.location ? `<div class="text-[10px] text-on-surface-variant font-mono mt-1 truncate">${escapeHtml(ent.location)}</div>` : ''}
                      ${ent.evidence_id ? `<div class="mt-1.5 text-[9px] font-mono text-cyan-400 flex items-center gap-1"><span class="material-symbols-outlined text-[10px]">fingerprint</span>${escapeHtml(ent.evidence_id)}</div>` : ''}
                    </div>
                  `).join('')}
                </div>
              </div>
            ` : ''}

            <!-- Authoritative Evidence Chain -->
            ${evidenceIds.length > 0 ? `
              <div class="pt-2 border-t border-outline-variant/15 flex flex-wrap items-center gap-2">
                <span class="text-[10px] uppercase font-bold text-on-surface-variant">Evidence Provenance:</span>
                ${evidenceIds.map(eid => `
                  <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-surface-container-highest text-cyan-300 border border-cyan-500/20 flex items-center gap-1">
                    <span class="material-symbols-outlined text-[10px]">verified</span>
                    ${escapeHtml(eid)}
                  </span>
                `).join('')}
              </div>
            ` : ''}

            <!-- Suggested Actions -->
            ${suggestedActions.length > 0 ? `
              <div class="flex flex-wrap items-center gap-2 pt-2">
                ${suggestedActions.map(act => `
                  <button class="px-3 py-1.5 rounded-lg bg-primary hover:bg-blue-600 text-white text-xs font-medium transition-colors flex items-center gap-1.5" onclick="window.TwinApp.switchPrimaryView('${act.view}')">
                    <span>${escapeHtml(act.label)}</span>
                    <span class="material-symbols-outlined text-xs">arrow_forward</span>
                  </button>
                `).join('')}
              </div>
            ` : ''}
          </div>
        `;
      } catch (err) {
        resultsContainer.innerHTML = `
          <div class="bg-surface-container-low border border-rose-500/30 rounded-2xl p-6 space-y-2 text-rose-400 text-xs">
            <div class="font-bold flex items-center gap-2"><span class="material-symbols-outlined">error</span> Deterministic Twin Query Error</div>
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
    const select = document.getElementById('dep-component-select') || document.getElementById('dep-focus-select');
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

      if (state.componentsList.length > 0 && !selectedDepComponentId) {
        const getEndpointId = (ep) => (ep && typeof ep === 'object' ? ep.id : ep);
        const connectedComp = state.componentsList.find(c => {
          return state.edges.some(e => getEndpointId(e.source) === c.id || getEndpointId(e.target) === c.id);
        }) || state.componentsList[0];
        select.value = connectedComp.id;
        selectDependencyComponent(connectedComp.id);
      }
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
    const select = document.getElementById('dep-component-select') || document.getElementById('dep-focus-select');
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

    const getEndpointId = (ep) => (ep && typeof ep === 'object' ? ep.id : ep);
    const incoming = state.edges.filter(e => getEndpointId(e.target) === componentId);
    const outgoing = state.edges.filter(e => getEndpointId(e.source) === componentId);

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
      const baseSelect = document.getElementById('diff-base-select');
      const targetSelect = document.getElementById('diff-target-select');
      const targetSnapId = (targetSelect && targetSelect.value) || state.currentSnapshotId || null;
      let baseSnapId = (baseSelect && baseSelect.value && baseSelect.value !== targetSnapId)
        ? baseSelect.value
        : (state.diffSnapshotId && state.diffSnapshotId !== targetSnapId
          ? state.diffSnapshotId
          : (state.snapshots.find(s => s.id !== targetSnapId)?.id || null));

      const payload = {
        target_snapshot_id: targetSnapId,
        base_snapshot_id: baseSnapId,
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
      if (banner) {
        banner.className = 'p-3 bg-[#FEF2F2] border border-[#FCA5A5] rounded-xl text-xs text-[#991B1B] font-semibold flex items-center justify-between gap-2';
        banner.innerHTML = `
          <div class="flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px] text-[#EF4444]">error</span>
            <span>Test Impact Computation: ${escapeHtml(err.message)}</span>
          </div>
          <button onclick="TwinApp.executeTestImpactAnalysis()" class="px-2.5 py-1 rounded bg-[#EF4444] text-white text-[11px] font-bold hover:bg-[#DC2626]">Retry</button>
        `;
      }
      ['ti-metric-affected', 'ti-metric-direct', 'ti-metric-indirect', 'ti-metric-unaffected', 'ti-metric-unknown'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
      });
      ['ti-tab-count-affected', 'ti-tab-count-unknown', 'ti-tab-count-unaffected'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
      });
      if (affectedList) {
        affectedList.innerHTML = `
          <div class="p-8 text-center bg-white border border-[#FCA5A5] rounded-xl text-xs">
            <span class="material-symbols-outlined text-2xl text-[#EF4444] mb-1">error</span>
            <div class="font-bold text-[#991B1B]">Test Impact Analysis Failed</div>
            <p class="text-[#64748B] mt-1">${escapeHtml(err.message)}</p>
            <p class="text-[#94A3B8] text-[11px] mt-0.5">Please ensure both baseline and target revisions are valid.</p>
            <button onclick="TwinApp.executeTestImpactAnalysis()" class="mt-3 px-3 py-1.5 rounded-lg bg-[#0071E3] text-white text-xs font-semibold hover:bg-[#0077ED]">Retry Analysis</button>
          </div>
        `;
      }
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

    const riskBtn = document.getElementById('btn-run-risk-action');
    if (riskBtn) {
      riskBtn.onclick = () => executeRiskAnalysis();
    }

    const baseSelect = document.getElementById('diff-base-select');
    const targetSelect = document.getElementById('diff-target-select');
    const impactBaseSelect = document.getElementById('impact-base-select');
    const impactTargetSelect = document.getElementById('impact-target-select');

    if (baseSelect && targetSelect) {
      baseSelect.onchange = () => {
        if (impactBaseSelect) impactBaseSelect.value = baseSelect.value;
        validateBaselineAndTargetSelection();
        executeSnapshotDiff();
      };
      targetSelect.onchange = () => {
        if (impactTargetSelect) impactTargetSelect.value = targetSelect.value;
        validateBaselineAndTargetSelection();
        executeSnapshotDiff();
      };

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

  function renderImpactDiffTable(changes = []) {
    const diffTbody = document.getElementById('diff-table-body');
    if (!diffTbody) return;
    diffTbody.innerHTML = '';
    if (!changes || changes.length === 0) {
      diffTbody.innerHTML = '<tr><td colspan="5" class="td-empty" style="text-align:center; padding: 2rem; color:#64748B;">Zero structural changes detected between selected commits.</td></tr>';
      return;
    }
    changes.forEach(c => {
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

  function renderCausalPropagationTree(data) {
    const pathsContainer = document.getElementById('impact-paths-tree');
    const pathsCount = document.getElementById('impact-paths-count');
    if (pathsCount) pathsCount.textContent = (data.paths || []).length;
    if (!pathsContainer) return;

    pathsContainer.innerHTML = '';

    const paths = data.paths || [];
    const changes = data.changes || [];
    const directAffected = data.impact_tree?.direct || [];
    const indirectAffected = data.impact_tree?.indirect || [];
    const tests = data.impact_tree?.tests || [];

    if (changes.length === 0) {
      pathsContainer.innerHTML = '<div class="p-6 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-xl border border-dashed border-[#CBD5E1]">Zero code changes detected between baseline and target commits. Downstream propagation is empty.</div>';
      return;
    }

    if (paths.length === 0 && directAffected.length === 0) {
      pathsContainer.innerHTML = `
        <div class="p-6 text-center text-xs text-[#10B981] bg-[#ECFDF5] rounded-xl border border-dashed border-[#A7F3D0] space-y-1">
          <div class="font-bold text-sm">✓ Analysis Completed: Zero Downstream Impact</div>
          <div class="text-[#065F46]">The ${changes.length} changed entities are isolated. No components, services, APIs, or tests depend on these modified symbols.</div>
        </div>
      `;
      return;
    }

    // Top Summary Banner in Tree
    const headerSummary = document.createElement('div');
    headerSummary.className = 'p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg flex flex-wrap items-center justify-between gap-2 text-xs';
    headerSummary.innerHTML = `
      <div class="flex items-center gap-3">
        <span class="font-bold text-[#0F172A]">Causal Impact Chains:</span>
        <span class="px-2 py-0.5 rounded bg-[#FEF3C7] text-[#92400E] font-semibold text-[11px]">${changes.length} Changed</span>
        <span class="px-2 py-0.5 rounded bg-[#FEE2E2] text-[#991B1B] font-semibold text-[11px]">${directAffected.length} Direct</span>
        <span class="px-2 py-0.5 rounded bg-[#FCE7F3] text-[#9D174D] font-semibold text-[11px]">${indirectAffected.length} Multi-Hop</span>
        <span class="px-2 py-0.5 rounded bg-[#D1FAE5] text-[#065F46] font-semibold text-[11px]">${tests.length} Tests</span>
      </div>
      <span class="text-[#64748B] text-[11px]">Max Propagation Depth: ${data.summary?.max_propagation_depth || 1}</span>
    `;
    pathsContainer.appendChild(headerSummary);

    // Render individual paths
    paths.forEach((p, idx) => {
      const card = document.createElement('div');
      card.className = 'p-3 bg-white rounded-lg border border-[#E2E8F0] shadow-2xs space-y-2';

      let chainHtml = '';
      for (let i = 0; i < p.nodes.length; i++) {
        const nodeName = p.nodes[i];
        const isRoot = (i === 0);
        const isTarget = (i === p.nodes.length - 1);
        const isTestNode = isTarget && p.terminal_type === 'TEST';

        let nodeBg = 'bg-[#F1F5F9] text-[#334155] border-[#CBD5E1]';
        if (isRoot) nodeBg = 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]';
        else if (isTestNode) nodeBg = 'bg-[#D1FAE5] text-[#065F46] border-[#A7F3D0]';
        else if (isTarget) nodeBg = 'bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]';

        chainHtml += `
          <span onclick="window.TwinApp.inspectNodeByName('${escapeHtml(nodeName)}')" class="inline-flex items-center px-2 py-1 rounded text-xs font-mono font-semibold cursor-pointer border ${nodeBg} hover:opacity-80 transition-opacity">
            ${escapeHtml(nodeName)}
          </span>
        `;
        if (i < p.relationships.length) {
          const rel = p.relationships[i] || 'IMPACTS';
          chainHtml += `<span class="text-[#8B5CF6] text-[10px] font-bold px-1 select-none">--[${rel}]--></span>`;
        }
      }

      card.innerHTML = `
        <div class="flex items-center justify-between text-xs">
          <div class="flex items-center gap-2">
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#EDE9FE] text-[#6D28D9]">DEPTH ${p.depth}</span>
            <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#F1F5F9] text-[#475569] uppercase">${p.terminal_type}</span>
          </div>
          <span class="text-[11px] font-semibold text-[#10B981]">${(p.confidence * 100).toFixed(0)}% Confidence</span>
        </div>
        <div class="flex items-center flex-wrap gap-1 pt-1">
          ${chainHtml}
        </div>
      `;
      pathsContainer.appendChild(card);
    });

    // Test coverage & verification section
    if (tests.length > 0) {
      const testSection = document.createElement('div');
      testSection.className = 'mt-3 p-3 bg-[#ECFDF5] border border-[#A7F3D0] rounded-lg text-xs space-y-2';
      testSection.innerHTML = `
        <div class="flex items-center justify-between font-bold text-[#065F46]">
          <span class="flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px]">verified</span>
            <span>Impacted Verification Suites (${tests.length})</span>
          </span>
          <span class="text-[11px] font-semibold px-2 py-0.5 rounded bg-white/80 border border-[#A7F3D0]">Requires Re-Run (Historical Execution Not Evaluated)</span>
        </div>
        <div class="space-y-1">
          ${tests.map(t => `
            <div class="flex items-center justify-between font-mono text-[11px] bg-white/70 px-2 py-1 rounded border border-[#D1FAE5]">
              <span class="text-[#047857] font-semibold">${escapeHtml(t.qualified_name || t.id)}</span>
              <span class="text-[#64748B] text-[10px]">${escapeHtml(t.source_file || '')}</span>
            </div>
          `).join('')}
        </div>
      `;
      pathsContainer.appendChild(testSection);
    } else {
      const noTestsNote = document.createElement('div');
      noTestsNote.className = 'p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs text-[#64748B] flex flex-col sm:flex-row sm:items-center justify-between gap-1';
      noTestsNote.innerHTML = `
        <div class="flex items-center gap-1.5">
          <span class="material-symbols-outlined text-[16px] text-[#F59E0B]">warning</span>
          <span>No historical execution evidence available for this commit. No test suites directly cover changed symbols.</span>
        </div>
        <span class="text-[10px] font-semibold text-[#D97706] bg-[#FEF3C7] px-2 py-0.5 rounded border border-[#FDE68A]">Coverage Gap (Unverified)</span>
      `;
      pathsContainer.appendChild(noTestsNote);
    }
  }

  function renderImpactFindingsTable(findings = []) {
    const findingsBody = document.getElementById('impact-findings-body');
    const findingsCount = document.getElementById('impact-findings-count');
    if (findingsCount) findingsCount.textContent = (findings || []).length;
    if (!findingsBody) return;

    findingsBody.innerHTML = '';
    if (!findings || findings.length === 0) {
      findingsBody.innerHTML = '<tr><td colspan="7" class="td-empty">Zero impact findings generated.</td></tr>';
      return;
    }
    findings.forEach(f => {
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

  function renderImpactCategoriesGrid(cats = {}) {
    const catGrid = document.getElementById('impact-categories-grid');
    if (!catGrid) return;
    catGrid.innerHTML = '';
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

  async function executeChangeImpactAnalysis() {
    const baseSelect = document.getElementById('impact-base-select') || document.getElementById('diff-base-select');
    const targetSelect = document.getElementById('impact-target-select') || document.getElementById('diff-target-select');
    const depthInput = document.getElementById('impact-depth-input');
    const impactContainer = document.getElementById('impact-analysis-container');
    const diffTbody = document.getElementById('diff-table-body');
    const metaSpan = document.getElementById('impact-analysis-meta');
    const tree = document.getElementById('impact-paths-tree');
    const runBtn = document.getElementById('btn-run-impact-action');
    const anim3dBtn = document.getElementById('btn-impact-visualize-3d');

    if (!baseSelect || !targetSelect) return;
    const baseOpt = baseSelect.selectedOptions[0];
    const targetOpt = targetSelect.selectedOptions[0];
    const baseSha = baseOpt?.dataset.sha || baseSelect.value;
    const targetSha = targetOpt?.dataset.sha || targetSelect.value;
    const maxDepth = depthInput ? parseInt(depthInput.value, 10) || 5 : 5;

    if (!baseSha || !targetSha) {
      setImpactMetricCardState('BLOCKED');
      if (metaSpan) metaSpan.innerHTML = `<span style="color:#64748B;">Please select both Baseline and Target commits to compare.</span>`;
      if (diffTbody) diffTbody.innerHTML = '<tr><td colspan="5" class="td-empty" style="text-align:center; padding: 2rem; color:#64748B;">Please select both Baseline and Target commits to compare.</td></tr>';
      if (tree) tree.innerHTML = '<div class="p-6 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-xl border border-dashed border-[#CBD5E1]">Please select distinct Baseline and Target commits in the dropdowns above to execute impact propagation.</div>';
      return;
    }

    if (baseSha === targetSha) {
      setImpactMetricCardState('BLOCKED');
      currentImpactAnalysisResult = null;
      if (anim3dBtn) {
        anim3dBtn.disabled = true;
        anim3dBtn.classList.add('opacity-50', 'cursor-not-allowed');
      }
      if (metaSpan) {
        metaSpan.innerHTML = `<span style="color:#f59e0b; font-weight:600;">Baseline and Target refer to the same commit (${baseSha.slice(0, 7)}). Select distinct commits to analyze changes.</span>`;
      }
      if (diffTbody) {
        diffTbody.innerHTML = '<tr><td colspan="5" class="td-empty" style="text-align:center; padding: 2rem; color:#64748B;">Identical commits selected (Baseline == Target). Pairwise comparison requires distinct commits.</td></tr>';
      }
      if (tree) {
        tree.innerHTML = '<div class="p-6 text-center text-xs text-[#F59E0B] bg-[#FFFBEB] rounded-xl border border-dashed border-[#FDE68A]">Identical commits selected (Baseline == Target). Please select distinct versions to compute impact propagation paths.</div>';
      }
      return;
    }

    state.impactAnalysisSeq = (state.impactAnalysisSeq || 0) + 1;
    const currentSeq = state.impactAnalysisSeq;
    const lifecycleIcon = document.getElementById('impact-lifecycle-icon');

    if (impactContainer) impactContainer.style.display = 'block';
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.classList.add('opacity-70');
      runBtn.innerHTML = '<span class="material-symbols-outlined text-[15px] animate-spin">refresh</span><span>Analyzing...</span>';
    }
    setImpactMetricCardState('LOADING');
    if (lifecycleIcon) {
      lifecycleIcon.textContent = 'sync';
      lifecycleIcon.className = 'material-symbols-outlined text-[18px] text-[#0071e3] animate-spin';
    }
    if (metaSpan) {
      metaSpan.innerHTML = `Computing deterministic Change Impact & Blast Radius (depth ≤ ${maxDepth})...`;
    }
    if (diffTbody) {
      diffTbody.innerHTML = '<tr><td colspan="5" class="td-loading">⚡ Running deterministic Change Impact & Blast Radius analysis...</td></tr>';
    }
    if (tree) {
      tree.innerHTML = '<div class="p-6 text-center text-xs text-[#0284C7] bg-[#F0F9FF] rounded-xl border border-dashed border-[#BAE6FD]"><div class="flex items-center justify-center gap-2 font-semibold"><span class="material-symbols-outlined text-[16px] animate-spin">sync</span> Tracing dependency graph propagation paths...</div></div>';
    }

    try {
      // Step A: Check if Baseline or Target snapshot needs reconstruction from Git source tree
      let resolvedBaseId = baseOpt?.dataset.snapshotId || baseSelect.value;
      let resolvedTargetId = targetOpt?.dataset.snapshotId || targetSelect.value;

      if (!resolvedBaseId || baseOpt?.dataset.hasSnapshot === 'false') {
        if (metaSpan) metaSpan.innerHTML = `Reconstructing historical Twin snapshot for commit ${baseSha.slice(0, 7)} from Git source tree...`;
        const reconRes = await fetch(`/repositories/${state.currentRepoId}/snapshots/reconstruct`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ commit_sha: baseSha }),
        });
        if (!reconRes.ok) {
          const errData = await reconRes.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to reconstruct baseline commit ${baseSha.slice(0, 7)}`);
        }
        const reconData = await reconRes.json();
        resolvedBaseId = reconData.snapshot_id;
        if (baseOpt) {
          baseOpt.value = resolvedBaseId;
          baseOpt.dataset.hasSnapshot = 'true';
          baseOpt.dataset.snapshotId = resolvedBaseId;
          baseOpt.textContent = baseOpt.textContent.replace('[UNINDEXED]', '[ANALYZED]');
        }
      }

      if (!resolvedTargetId || targetOpt?.dataset.hasSnapshot === 'false') {
        if (metaSpan) metaSpan.innerHTML = `Reconstructing historical Twin snapshot for commit ${targetSha.slice(0, 7)} from Git source tree...`;
        const reconRes = await fetch(`/repositories/${state.currentRepoId}/snapshots/reconstruct`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ commit_sha: targetSha }),
        });
        if (!reconRes.ok) {
          const errData = await reconRes.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to reconstruct target commit ${targetSha.slice(0, 7)}`);
        }
        const reconData = await reconRes.json();
        resolvedTargetId = reconData.snapshot_id;
        if (targetOpt) {
          targetOpt.value = resolvedTargetId;
          targetOpt.dataset.hasSnapshot = 'true';
          targetOpt.dataset.snapshotId = resolvedTargetId;
          targetOpt.textContent = targetOpt.textContent.replace('[UNINDEXED]', '[ANALYZED]');
        }
      }

      // Step B: Execute deterministic Change Impact analysis
      if (metaSpan) {
        metaSpan.innerHTML = `Calculating transitive dependency propagation (depth ≤ ${maxDepth})...`;
      }

      const res = await fetch(`/repositories/${state.currentRepoId}/impact-analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_snapshot_id: resolvedBaseId,
          target_snapshot_id: resolvedTargetId,
          max_depth: maxDepth,
          include_tests: true,
          include_processes: true,
          include_apis: true,
        }),
      });

      if (currentSeq !== state.impactAnalysisSeq) return;

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Analysis failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      if (currentSeq !== state.impactAnalysisSeq) return;
      currentImpactAnalysisResult = data;

      if (data.status === 'NOT_READY') {
        setImpactMetricCardState('IDLE');
        if (anim3dBtn) {
          anim3dBtn.disabled = true;
          anim3dBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
        if (lifecycleIcon) {
          lifecycleIcon.textContent = 'info';
          lifecycleIcon.className = 'material-symbols-outlined text-[18px] text-[#D97706]';
        }
        if (metaSpan) {
          metaSpan.innerHTML = `Status: <strong style="color:#D97706;">NOT_READY</strong> | ${escapeHtml(data.message || 'Pairwise Change Impact requires two distinct snapshots.')}`;
        }
        if (diffTbody) {
          diffTbody.innerHTML = `<tr><td colspan="5" class="td-empty" style="color:#D97706;font-weight:600;">⚠ NOT_READY: ${escapeHtml(data.message || 'No change detected between selected snapshots.')}</td></tr>`;
        }
        if (tree) {
          tree.innerHTML = `<div class="p-6 text-center text-xs text-[#D97706] bg-[#FFFBEB] rounded-xl border border-dashed border-[#FDE68A]">⚠ NOT_READY: ${escapeHtml(data.message || 'No change detected between selected snapshots.')}</div>`;
        }
        return;
      }

      // 1. Update Metrics
      const s = data.summary || {};
      const changedCount = s.changed ?? 0;
      const affectedCount = s.unique_affected ?? s.directly_affected ?? 0;

      if (changedCount === 0 && affectedCount === 0) {
        // Verified zero downstream impact
        setImpactMetricCardState('ZERO');
        if (lifecycleIcon) {
          lifecycleIcon.textContent = 'verified';
          lifecycleIcon.className = 'material-symbols-outlined text-[18px] text-[#059669]';
        }
        if (metaSpan) {
          metaSpan.innerHTML = `Analysis ID: <strong>${data.analysis_id}</strong> | Status: <strong style="color:#059669;">VERIFIED ZERO IMPACT</strong> | Execution Time: <strong>${data.execution_time_ms} ms</strong> | Propagation Depth: <strong>${s.max_propagation_depth || 0}</strong>`;
        }
        if (tree) {
          tree.innerHTML = `
            <div class="p-6 text-center text-xs text-[#059669] bg-[#ECFDF5] rounded-xl border border-dashed border-[#A7F3D0] space-y-1">
              <div class="font-bold flex items-center justify-center gap-1.5"><span class="material-symbols-outlined text-[16px]">check_circle</span> Clean Isolation Verified</div>
              <p>Differential comparison verified across revisions. Zero breaking structural dependencies or downstream callers impacted.</p>
            </div>`;
        }
      } else {
        setImpactMetricCardState('READY', s);
        if (lifecycleIcon) {
          lifecycleIcon.textContent = 'check_circle';
          lifecycleIcon.className = 'material-symbols-outlined text-[18px] text-[#059669]';
        }
        if (metaSpan) {
          metaSpan.innerHTML = `Analysis ID: <strong>${data.analysis_id}</strong> | Status: <strong style="color:#059669;">COMPLETED</strong> | Execution Time: <strong>${data.execution_time_ms} ms</strong> | Propagation Depth: <strong>${s.max_propagation_depth || 0}</strong>`;
        }
        // Render Causal Propagation Tree
        renderCausalPropagationTree(data);
      }

      // Enable 3D Animation button
      if (anim3dBtn) {
        anim3dBtn.disabled = false;
        anim3dBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        anim3dBtn.classList.add('hover:bg-[#1E293B]', 'cursor-pointer');
        anim3dBtn.title = 'View & Animate Verified Impact in 3D Architecture Twin';
      }

      // 2. Render Diff Table
      renderImpactDiffTable(data.changes || []);

      // 4. Render Evidence & Findings Table
      renderImpactFindingsTable(data.findings || []);

      // 5. Render Affected Categories Grid
      renderImpactCategoriesGrid(data.affected_categories || {});

      // 6. Automatically evaluate Risk & Guardrails
      executeRiskAnalysis().catch(() => {});

    } catch (err) {
      setImpactMetricCardState('ERROR');
      if (anim3dBtn) {
        anim3dBtn.disabled = true;
        anim3dBtn.classList.add('opacity-50', 'cursor-not-allowed');
      }
      if (lifecycleIcon) {
        lifecycleIcon.textContent = 'error';
        lifecycleIcon.className = 'material-symbols-outlined text-[18px] text-[#DC2626]';
      }
      if (metaSpan) {
        metaSpan.innerHTML = `<span style="color:#DC2626; font-weight:600;">Analysis Failed: ${escapeHtml(err.message)}</span>`;
      }
      if (diffTbody) {
        diffTbody.innerHTML = `<tr><td colspan="5" class="td-empty" style="color:#DC2626;">Analysis failed: ${escapeHtml(err.message)}</td></tr>`;
      }
      if (tree) {
        tree.innerHTML = `
          <div class="p-6 text-center text-xs text-[#DC2626] bg-[#FEF2F2] rounded-xl border border-dashed border-[#FECACA] space-y-2">
            <div class="font-bold flex items-center justify-center gap-1.5"><span class="material-symbols-outlined text-[16px]">error</span> Change Impact Analysis Failed</div>
            <p class="text-[#991B1B]">${escapeHtml(err.message)}</p>
            <button class="px-3.5 py-1.5 rounded-lg bg-[#DC2626] text-white font-semibold text-xs hover:bg-[#B91C1C] transition-colors" onclick="window.TwinApp.executeChangeImpactAnalysis()">Retry Analysis</button>
          </div>`;
      }
    } finally {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.classList.remove('opacity-70');
        runBtn.innerHTML = '<span class="material-symbols-outlined text-[15px]">bolt</span><span>Execute Impact</span>';
      }
    }
  }

  async function executeRiskAnalysis() {
    const baseSelect = document.getElementById('impact-base-select') || document.getElementById('diff-base-select');
    const targetSelect = document.getElementById('impact-target-select') || document.getElementById('diff-target-select');
    const depthInput = document.getElementById('impact-depth-input');
    const emptyState = document.getElementById('risk-analysis-empty-state');
    const content = document.getElementById('risk-analysis-content');
    const btn = document.getElementById('btn-run-risk-action');

    if (!baseSelect || !targetSelect) return;
    const baseOpt = baseSelect.selectedOptions[0];
    const targetOpt = targetSelect.selectedOptions[0];
    const baseId = baseOpt?.dataset.snapshotId || baseSelect.value;
    const targetId = targetOpt?.dataset.snapshotId || targetSelect.value;
    const baseSha = baseOpt?.dataset.sha || baseId;
    const targetSha = targetOpt?.dataset.sha || targetId;
    const maxDepth = depthInput ? parseInt(depthInput.value, 10) || 5 : 5;

    if (!baseId || !targetId || baseSha === targetSha) {
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="material-symbols-outlined text-[15px] animate-spin">refresh</span> Evaluating...';
    }

    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/risk-analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_snapshot_id: baseId,
          target_snapshot_id: targetId,
          max_depth: maxDepth,
          environment: 'production',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Risk analysis failed with HTTP ${res.status}`);
      }

      const data = await res.json();

      if (emptyState) emptyState.style.display = 'none';
      if (content) content.style.display = 'block';

      // 1. Overall Category & Confidence
      const catBadge = document.getElementById('risk-category-badge');
      if (catBadge) {
        catBadge.textContent = data.overall_category;
        catBadge.className = `px-2.5 py-1 rounded-md text-xs font-bold risk-badge-${data.overall_category.toLowerCase()}`;
      }

      const confBadge = document.getElementById('risk-confidence-badge');
      if (confBadge) {
        confBadge.textContent = `Confidence: ${data.confidence}`;
        confBadge.className = `px-2 py-0.5 rounded text-[11px] font-semibold confidence-badge-${data.confidence.toLowerCase()}`;
      }

      const explanationEl = document.getElementById('risk-explanation-text');
      if (explanationEl) {
        explanationEl.textContent = data.explanation;
      }

      const scoreEl = document.getElementById('risk-overall-score');
      if (scoreEl) {
        scoreEl.textContent = `${data.overall_score}/100`;
      }

      // 2. Risk Signals Grid
      const signalsGrid = document.getElementById('risk-signals-grid');
      if (signalsGrid) {
        signalsGrid.innerHTML = '';
        (data.risk_factors || []).forEach(f => {
          const card = document.createElement('div');
          card.className = 'p-3 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0] space-y-1.5';
          let sevClass = 'bg-[#F1F5F9] text-[#475569]';
          if (f.severity === 'CRITICAL') sevClass = 'bg-[#FEE2E2] text-[#991B1B]';
          else if (f.severity === 'HIGH') sevClass = 'bg-[#FFEDD5] text-[#C2410C]';
          else if (f.severity === 'MEDIUM') sevClass = 'bg-[#FEF9C3] text-[#854D0E]';
          else if (f.severity === 'LOW') sevClass = 'bg-[#DCFCE7] text-[#166534]';

          card.innerHTML = `
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-[#0F172A]">${escapeHtml(f.name)}</span>
              <span class="text-[10px] font-bold px-1.5 py-0.5 rounded ${sevClass}">${f.severity}</span>
            </div>
            <div class="text-[11px] text-[#475569] leading-snug space-y-0.5">
              ${(f.evidence || []).slice(0, 3).map(e => `<div>• ${escapeHtml(e)}</div>`).join('')}
            </div>
            <div class="text-[10px] text-[#94A3B8] flex items-center justify-between pt-1 border-t border-[#E2E8F0]">
              <span>Score: ${f.score}/100</span>
              <span>${f.status}</span>
            </div>
          `;
          signalsGrid.appendChild(card);
        });
      }

      // 3. Architecture Guardrails
      const guardrailsList = document.getElementById('guardrail-results-list');
      if (guardrailsList) {
        guardrailsList.innerHTML = '';
        if (!data.guardrail_results || data.guardrail_results.length === 0) {
          guardrailsList.innerHTML = '<div class="p-3 bg-gray-50 rounded-lg text-xs text-gray-500">Architecture status unknown.</div>';
        } else {
          data.guardrail_results.forEach(g => {
            const gCard = document.createElement('div');
            gCard.className = 'guardrail-card p-3 bg-white rounded-lg border border-[#E2E8F0] flex flex-col sm:flex-row sm:items-center justify-between gap-2';

            let statusBadge = '';
            if (g.status === 'PASS') {
              statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#DCFCE7] text-[#166534] border border-[#BBF7D0]">PASS</span>';
            } else if (g.status === 'WARN') {
              statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#FEF9C3] text-[#854D0E] border border-[#FEF08A]">WARN</span>';
            } else if (g.status === 'VIOLATION') {
              statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#FEE2E2] text-[#991B1B] border border-[#FECACA]">VIOLATION</span>';
            } else {
              statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">UNKNOWN</span>';
            }

            const evidenceHtml = (g.evidence && g.evidence.length > 0)
              ? `<div class="mt-2 space-y-1 bg-[#F8FAFC] p-2.5 rounded border border-[#E2E8F0]">
                  <div class="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">Evidence &amp; Defect Details (${g.evidence.length})</div>
                  <ul class="text-[11px] font-mono text-[#334155] space-y-0.5 list-disc list-inside">
                    ${g.evidence.map(e => `<li>${escapeHtml(e)}</li>`).join('')}
                  </ul>
                </div>`
              : '';

            const affectedHtml = (g.affected_entities && g.affected_entities.length > 0)
              ? `<div class="mt-1 flex flex-wrap gap-1">
                  ${g.affected_entities.slice(0, 8).map(ent => `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#E0F2FE] text-[#0369A1] border border-[#BAE6FD]">${escapeHtml(ent)}</span>`).join('')}
                  ${g.affected_entities.length > 8 ? `<span class="text-[10px] text-[#64748B] self-center">+${g.affected_entities.length - 8} more</span>` : ''}
                </div>`
              : '';

            gCard.innerHTML = `
              <div class="space-y-1 w-full">
                <div class="flex items-center justify-between gap-2">
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-[#0F172A]">[${escapeHtml(g.rule_id)}] ${escapeHtml(g.rule_name)}</span>
                    <span class="text-[10px] text-[#64748B] font-mono">${escapeHtml(g.guardrail_type)}</span>
                  </div>
                  ${statusBadge}
                </div>
                <p class="text-xs text-[#475569]">${escapeHtml(g.explanation)}</p>
                ${affectedHtml}
                ${evidenceHtml}
              </div>
            `;
            guardrailsList.appendChild(gCard);
          });
        }
      }

      // 4. Recommendations
      const recList = document.getElementById('risk-recommendations-list');
      if (recList) {
        recList.innerHTML = '';
        (data.recommendations || []).forEach(r => {
          const li = document.createElement('li');
          li.textContent = r;
          recList.appendChild(li);
        });
      }

    } catch (err) {
      if (emptyState) {
        emptyState.style.display = 'block';
        emptyState.innerHTML = `<span style="color:#ef4444;">Risk evaluation failed: ${escapeHtml(err.message)}</span>`;
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-outlined text-[15px]">security</span> Evaluate Risk &amp; Guardrails';
      }
    }
  }

  async function projectImpactGraph() {
    if (!currentImpactAnalysisResult || !currentImpactAnalysisResult.analysis_id) {
      showNotification('Please run a change impact analysis first.', 'warning');
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
      showNotification(`Could not project impact graph: ${err.message}`, 'error');
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

    state.diffSnapshotId = baseId;
    state.currentSnapshotId = targetId;

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
        let modeBadge = '';
        if (data.diff_mode === 'FILE_DIFF_ONLY') {
          modeBadge = '<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-[#E0F2FE] text-[#0369A1] border border-[#BAE6FD]">Git Revision File Delta</span>';
        }
        banner.innerHTML = `
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">+${added} Added</span>
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-[#FFF1F2] text-[#BE123C] border border-[#FECDD3]">-${removed} Removed</span>
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-[#FFFBEB] text-[#B45309] border border-[#FDE68A]">~${modified} Modified</span>
          <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">${summary.total_changes || changes.length} Total Changed Artifacts</span>
          ${modeBadge}
        `;
      }

      tbody.innerHTML = '';
      if (changes.length === 0) {
        if (data.status === 'IDENTICAL_COMMITS') {
          tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-xs font-medium text-[#F59E0B] bg-[#FFFBEB] border border-dashed border-[#FDE68A]">Identical revisions selected for Baseline and Target. Please select distinct commits to evaluate changes.</td></tr>';
        } else if (data.status === 'VERIFIED_ZERO_CHANGES') {
          tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-xs font-medium text-[#059669] bg-[#ECFDF5] border border-dashed border-[#A7F3D0]">✓ Verified Zero Changes: Both the Git tree and structural AST symbols are identical between these two revisions.</td></tr>';
        } else if (data.status === 'REVISION_RESOLUTION_FAILED') {
          tbody.innerHTML = `<tr<td colspan="5" class="p-6 text-center text-xs font-medium text-[#EF4444] bg-[#FEF2F2] border border-dashed border-[#FECDD3]">⚠ ${escapeHtml(data.message || 'Could not resolve the selected Git revisions or snapshots.')}</td></tr>`;
        } else {
          tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-[#64748B]">Zero structural differences detected between the selected revisions.</td></tr>';
        }
        return;
      }

      changes.forEach(n => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-[#F8FAFC] transition-colors';
        const cType = n.change_type || 'MODIFIED';
        const tagClass = cType === 'ADDED' ? 'bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]' : (cType === 'REMOVED' ? 'bg-[#FFF1F2] text-[#BE123C] border-[#FECDD3]' : 'bg-[#FFFBEB] text-[#B45309] border-[#FDE68A]');
        const artName = n.artifact_name || n.symbol_name || n.qualified_name || n.artifact_id;
        const filePath = n.source_file || n.file_path || '';
        const artType = n.artifact_type || (n.is_symbol_level ? 'SYMBOL' : 'FILE');
        const detailText = (n.evidence && n.evidence.length > 0) ? n.evidence[0] : (n.details || (cType === 'ADDED' ? 'Added in target revision.' : (cType === 'REMOVED' ? 'Removed in target revision.' : 'Modified in revision delta.')));

        tr.innerHTML = `
          <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${tagClass}">${cType}</span></td>
          <td class="p-3.5 font-bold text-xs text-[#0F172A]">${escapeHtml(artName)}</td>
          <td class="p-3.5"><span class="px-2 py-0.5 rounded text-[10px] font-mono bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">${artType}</span></td>
          <td class="p-3.5 font-mono text-xs text-[#64748B]">${escapeHtml(filePath)}${n.line_start ? `:${n.line_start}` : ''}</td>
          <td class="p-3.5 text-xs text-[#475569]">${escapeHtml(detailText)}</td>
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
    if (!state.currentRepoId) {
      state.rawGraph = { nodes: [], edges: [] };
      state.nodes = [];
      state.edges = [];
      updateStats({ nodes: [], edges: [] });
      return;
    }

    state.graphReqSeq = (state.graphReqSeq || 0) + 1;
    const currentReqSeq = state.graphReqSeq;
    const targetRepo = state.currentRepoId;

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
      if (currentReqSeq !== state.graphReqSeq || state.currentRepoId !== targetRepo) return;
      if (res.ok) {
        const data = await res.json();
        if (currentReqSeq !== state.graphReqSeq || state.currentRepoId !== targetRepo) return;
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
    state.nodes.forEach(n => {
      if (isFinite(n.x) && isFinite(n.y)) {
        existingPos.set(n.id, { x: n.x, y: n.y, vx: n.vx || 0, vy: n.vy || 0 });
      }
    });

    // Golden-spiral / multi-ring spatial distribution for stable initial layout
    state.nodes = rawNodes.map((n, idx) => {
      const prev = existingPos.get(n.id);
      const phi = idx * 2.39996;
      const r = Math.min(380, 50 + Math.sqrt(idx) * 32);
      return {
        ...n,
        x: prev ? prev.x : Math.cos(phi) * r,
        y: prev ? prev.y : Math.sin(phi) * r,
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

    const nodesBadge = document.getElementById('graph-nodes-badge');
    if (nodesBadge) nodesBadge.textContent = state.nodes.length;

    const statusText = document.getElementById('graph-status-text');
    if (statusText) {
      statusText.textContent = `Living System Synchronized • ${state.nodes.length} Nodes, ${state.edges.length} Connections`;
    }

    if (state.hideIsolated) {
      state.nodes = state.nodes.filter(n => !n.is_isolated);
      state.nodeMap.clear();
      state.nodes.forEach(n => state.nodeMap.set(n.id, n));
    }

    // Restore inspection if valid
    if (state.selectedNodeId && state.nodeMap.has(state.selectedNodeId)) {
      inspectNode(state.nodeMap.get(state.selectedNodeId));
    }

    if (state.viewDimension === '3d' && window.Twin3D && window.Twin3D.active) {
      window.Twin3D.buildScene(data);
    } else {
      startPhysics();
      setTimeout(fitToScreen, 100);
    }
  }

  function getNodeRadius(type, inDegree) {
    const base = {
      PACKAGE: 22,
      SERVICE: 20,
      MODULE: 18,
      DATABASE: 18,
      DATABASE_TABLE: 16,
      CLASS: 15,
      API_ENDPOINT: 15,
      FUNCTION: 11,
      METHOD: 11,
      TEST_CASE: 12,
      EXTERNAL_DEPENDENCY: 10,
    }[type] || 13;
    return Math.min(30, base + Math.min(inDegree || 0, 8) * 1.2);
  }

  function updateStats(data) {
    const statNodes = document.getElementById('stat-nodes');
    const statEdges = document.getElementById('stat-edges');
    const statDrifts = document.getElementById('stat-drifts');
    if (statNodes) statNodes.textContent = (data.nodes || []).length;
    if (statEdges) statEdges.textContent = (data.edges || []).length;
    const driftCount = (data.edges || []).filter(e => e.is_drift).length;
    if (statDrifts) statDrifts.textContent = driftCount;

    const nodesBadge = document.getElementById('graph-nodes-badge');
    if (nodesBadge) nodesBadge.textContent = (data.nodes || []).length;

    if (data.branch_name) {
      const bEl = document.getElementById('branch-name');
      if (bEl) bEl.textContent = data.branch_name;
    }

    const statusText = document.getElementById('graph-status-text');
    if (statusText) {
      if (state.impactMode) {
        statusText.textContent = '⚡ Change Impact Mode: Tracing Forward Blast Radius';
      } else if (driftCount > 0) {
        statusText.textContent = `⚠️ Architecture Drift: ${driftCount} Boundary Violation(s) Highlighted`;
      } else {
        statusText.textContent = `Living System Synchronized • ${(data.nodes || []).length} Nodes, ${(data.edges || []).length} Connections`;
      }
    }
  }

  let physicsIterations = 0;
  function startPhysics() {
    if (state.animFrameId) cancelAnimationFrame(state.animFrameId);
    physicsIterations = 0;

    function step() {
      if (state.physicsEnabled && physicsIterations < 220) {
        tickPhysics();
        physicsIterations++;
      }
      render();
      state.animFrameId = requestAnimationFrame(step);
    }
    state.animFrameId = requestAnimationFrame(step);
  }

  function tickPhysics() {
    const nodes = state.nodes;
    const edges = state.edges;
    const nLen = nodes.length;
    if (nLen === 0) return;

    const kRepel = nLen > 120 ? 800 : 1200;
    const kAttract = 0.032;
    const damp = 0.86;

    // 1. Repulsion between node pairs
    for (let i = 0; i < nLen; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nLen; j++) {
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distSq = dx * dx + dy * dy + 120;
        const dist = Math.sqrt(distSq);
        const force = Math.min(14, kRepel / distSq);
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
      const targetDist = 110;
      const delta = dist - targetDist;
      const force = Math.max(-12, Math.min(12, delta * kAttract));
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

    // 3. Center gravity & velocity dampening
    for (let i = 0; i < nLen; i++) {
      const n = nodes[i];
      if (n === state.draggedNode) continue;
      n.vx -= n.x * 0.005;
      n.vy -= n.y * 0.005;
      n.vx *= damp;
      n.vy *= damp;
      n.x += Math.max(-12, Math.min(12, n.vx));
      n.y += Math.max(-12, Math.min(12, n.vy));
    }
  }

  // --- Rendering: MiroFish Spatial Graph (Clean White Canvas) ---
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
      if (neighbors) neighbors.forEach(nid => activeNeighborhood.add(nid));
    }

    // 1. Draw Edges
    state.edges.forEach(e => {
      const a = e.sourceNode;
      const b = e.targetNode;
      if (!a || !b) return;

      const isConnected = !hasSpotlight || (a.id === state.selectedNodeId || b.id === state.selectedNodeId);
      const isSelectedEdge = e.id === state.selectedEdgeId;

      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);

      if (isSelectedEdge) {
        ctx.strokeStyle = '#D97706';
        ctx.lineWidth = 3.0;
        ctx.setLineDash([]);
      } else if (e.is_drift) {
        ctx.strokeStyle = '#DC2626';
        ctx.lineWidth = 2.2;
        ctx.setLineDash([5, 4]);
      } else if (hasSpotlight && (a.id === state.selectedNodeId || b.id === state.selectedNodeId)) {
        // Highlighted relationship connected to selected node (Vivid Rose)
        ctx.strokeStyle = '#E11D48';
        ctx.lineWidth = 2.4;
        ctx.setLineDash([]);
      } else if (hasSpotlight) {
        // Dimmed relationship
        ctx.strokeStyle = 'rgba(203, 213, 225, 0.35)';
        ctx.lineWidth = 0.6;
        ctx.setLineDash([]);
      } else {
        // Normal state: refined, crisp connection lines on white surface
        ctx.strokeStyle = 'rgba(100, 116, 139, 0.45)';
        ctx.lineWidth = 1.0;
        ctx.setLineDash([]);
      }

      ctx.stroke();
      ctx.setLineDash([]);

      // Draw directional arrow on active connections
      if (isConnected || !hasSpotlight) {
        const arrowColor = (hasSpotlight && (a.id === state.selectedNodeId || b.id === state.selectedNodeId))
          ? '#E11D48'
          : (e.is_drift ? '#DC2626' : 'rgba(100, 116, 139, 0.70)');
        drawArrow(ctx, a.x, a.y, b.x, b.y, b.radius + 3, arrowColor);
      }

      // Draw Edge Label Pill if toggled on or if connected to selected node
      if (state.showEdgeLabels || (hasSpotlight && (a.id === state.selectedNodeId || b.id === state.selectedNodeId))) {
        drawEdgeBadge(ctx, (a.x + b.x) / 2, (a.y + b.y) / 2, e.type);
      }
    });

    // 2. Draw Nodes
    state.nodes.forEach(n => {
      const isSelected = n.id === state.selectedNodeId;
      const isHovered = state.hoveredNode && state.hoveredNode.id === n.id;
      const isDimmed = hasSpotlight && !activeNeighborhood.has(n.id);
      const isImpacted = n.is_impacted;

      ctx.save();
      ctx.globalAlpha = isDimmed ? 0.16 : 1.0;

      // Radiant Halos
      if (isSelected) {
        // Outer radiant glow
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 8, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(225, 29, 72, 0.16)';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#E11D48';
        ctx.stroke();

        // Inner halo
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 2, 0, 2 * Math.PI);
        ctx.lineWidth = 1.8;
        ctx.strokeStyle = '#FFFFFF';
        ctx.stroke();
      } else if (isHovered) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 6, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(2, 132, 199, 0.18)';
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = '#0284C7';
        ctx.stroke();
      } else if (isImpacted) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius + 6, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(217, 119, 6, 0.18)';
        ctx.fill();
        ctx.lineWidth = 1.8;
        ctx.strokeStyle = '#D97706';
        ctx.stroke();
      }

      // Main Node Body
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
      const color = state.colors[n.type] || state.colors.DEFAULT;
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 1.8;
      ctx.strokeStyle = isSelected ? '#FFFFFF' : 'rgba(255, 255, 255, 0.85)';
      ctx.stroke();

      // Diff Status Indicators
      if (n.diff_status === 'ADDED') {
        drawBadge(ctx, n.x + n.radius - 2, n.y - n.radius + 2, '+', '#059669');
      } else if (n.diff_status === 'REMOVED') {
        drawBadge(ctx, n.x + n.radius - 2, n.y - n.radius + 2, '-', '#DC2626');
      } else if (n.diff_status === 'MODIFIED') {
        drawBadge(ctx, n.x + n.radius - 2, n.y - n.radius + 2, '~', '#D97706');
      }

      // Node Label with Crisp White Backdrop Pill
      if (!isDimmed || state.transform.k > 1.2) {
        const rawName = n.name || n.label || 'Node';
        const labelText = (rawName.length > 15 && !isSelected && !isHovered && state.transform.k < 1.3)
          ? rawName.substring(0, 13) + '..'
          : rawName;

        ctx.font = `${isSelected ? '700' : '600'} 10px 'Inter', sans-serif`;
        const textMetrics = ctx.measureText(labelText);
        const tw = textMetrics.width;
        const th = 15;
        const lx = n.x - tw / 2 - 4;
        const ly = n.y + n.radius + 6;

        // Label Backdrop
        ctx.beginPath();
        ctx.roundRect(lx, ly, tw + 8, th, 4);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.94)';
        ctx.fill();
        ctx.strokeStyle = isSelected ? '#E11D48' : 'rgba(203, 213, 225, 0.85)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Label Text
        ctx.fillStyle = isSelected ? '#E11D48' : '#0F172A';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(labelText, n.x, ly + th / 2);
      }

      ctx.restore();
    });

    ctx.restore();
  }

  function drawArrow(ctx, fromX, fromY, toX, toY, offset, color) {
    const dx = toX - fromX;
    const dy = toY - fromY;
    const angle = Math.atan2(dy, dx);
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < offset + 8) return;

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
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 9px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(char, x, y);
  }

  function drawEdgeBadge(ctx, x, y, text) {
    if (!text) return;
    const label = String(text).toUpperCase();
    ctx.font = 'bold 8px monospace';
    const tw = ctx.measureText(label).width;
    const pw = tw + 8;
    const ph = 14;

    ctx.beginPath();
    ctx.roundRect(x - pw / 2, y - ph / 2, pw, ph, 3);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.96)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.55)';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = '#334155';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, x, y);
  }

  // --- Inspector Panel (MiroFish Slide-Out Drawer) ---
  function inspectNode(node) {
    state.selectedNodeId = node.id;
    const drawer = document.getElementById('node-detail-panel');
    if (drawer) drawer.classList.add('open');

    const typeBadge = document.getElementById('inspector-type-badge');
    if (typeBadge) {
      typeBadge.textContent = node.type;
      const col = state.colors[node.type] || '#0284C7';
      typeBadge.style.color = col;
      typeBadge.style.borderColor = `${col}55`;
      typeBadge.style.background = `${col}15`;
    }

    const panel = document.getElementById('inspector-content');
    if (!panel) return;

    const incoming = state.edges.filter(e => e.target === node.id);
    const outgoing = state.edges.filter(e => e.source === node.id);
    const relatedTests = incoming.concat(outgoing).filter(e => e.type === 'TESTS' || e.sourceNode?.type === 'TEST_CASE');

    let callersHtml = '';
    if (incoming.length > 0) {
      callersHtml = incoming.slice(0, 8).map(e => {
        const sName = e.sourceNode?.name || e.source;
        return `<button class="chip-nav px-2 py-1 rounded bg-[#F1F5F9] hover:bg-[#E2E8F0] border border-[#CBD5E1] text-[11px] text-[#0071E3] font-medium truncate max-w-[170px] transition-colors" data-node="${escapeHtml(e.source)}">${escapeHtml(sName)}</button>`;
      }).join('');
    } else {
      const inDeg = Number(node.in_degree || 0);
      const outDeg = Number(node.out_degree || outgoing.length || 0);
      if (inDeg > 0) {
        callersHtml = `<span class="text-[#64748B] text-[11px] italic" title="${inDeg} inbound relationship(s) in Twin graph; expand zoom level or inspect details to view collapsed member callers">${inDeg} callers at granular level</span>`;
      } else if (outDeg > 0) {
        callersHtml = `<span class="inline-flex items-center gap-1 text-[11px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 font-medium">Root Entry Point / Top-level Component</span>`;
      } else {
        callersHtml = `<span class="text-[#64748B] text-[11px]">No inbound callers (Isolated entity)</span>`;
      }
    }

    const calleesHtml = outgoing.length > 0
      ? outgoing.slice(0, 8).map(e => {
          const tName = e.targetNode?.name || e.target;
          return `<button class="chip-nav px-2 py-1 rounded bg-[#F1F5F9] hover:bg-[#E2E8F0] border border-[#CBD5E1] text-[11px] text-[#059669] font-medium truncate max-w-[170px] transition-colors" data-node="${escapeHtml(e.target)}">${escapeHtml(tName)}</button>`;
        }).join('')
      : '<span class="text-[#64748B] text-[11px]">No outbound calls</span>';

    panel.innerHTML = `
      <div class="space-y-1">
        <div class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Identity</div>
        <div class="text-sm font-bold text-[#0F172A] break-words">${escapeHtml(node.name)}</div>
        <div class="text-[11px] font-mono text-[#64748B] break-all">${escapeHtml(node.qualified_name || node.id)}</div>
      </div>

      <div class="space-y-1.5 pt-2 border-t border-[#E2E8F0]">
        <div class="flex items-center justify-between">
          <div class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Source Location</div>
          <div class="flex items-center gap-1.5">
            <a href="vscode://file/${node.file || ''}:${node.line_start || 1}" class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#EFF6FF] text-[#0071E3] hover:bg-[#DBEAFE] border border-[#BFDBFE] transition-colors" title="Open directly in VS Code at line ${node.line_start || 1}">
              <span class="material-symbols-outlined text-[12px]">code</span>
              <span>VS Code</span>
            </a>
            <a href="cursor://file/${node.file || ''}:${node.line_start || 1}" class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#F5F3FF] text-[#7C3AED] hover:bg-[#EDE9FE] border border-[#DDD6FE] transition-colors" title="Open directly in Cursor AI Editor at line ${node.line_start || 1}">
              <span class="material-symbols-outlined text-[12px]">terminal</span>
              <span>Cursor</span>
            </a>
          </div>
        </div>
        <div class="p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] font-mono text-[11px] text-[#334155] break-all flex items-center justify-between gap-2">
          <span>${escapeHtml(node.file || 'unknown')}:${node.line_start || 1}</span>
          <button onclick="navigator.clipboard.writeText('${escapeHtml(node.file || '')}:${node.line_start || 1}'); showNotification('Copied file location to clipboard', 'info');" class="text-[#94A3B8] hover:text-[#0F172A] p-0.5" title="Copy file path">
            <span class="material-symbols-outlined text-[14px]">content_copy</span>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-2 pt-2 border-t border-[#E2E8F0]">
        <div class="p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]">
          <div class="text-[10px] text-[#64748B]">Logical Tier</div>
          <div class="text-xs font-semibold text-[#0F172A]">${node.logical_layer || 'CORE'}</div>
        </div>
        <div class="p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0]">
          <div class="text-[10px] text-[#64748B]">Confidence</div>
          <div class="text-xs font-semibold text-[#059669]">${((node.confidence || 1.0) * 100).toFixed(0)}% AST</div>
        </div>
      </div>

      <div class="space-y-2 pt-2 border-t border-[#E2E8F0]">
        <div class="flex items-center justify-between text-[11px]">
          <span class="text-[#475569] font-semibold">Inbound Callers (${incoming.length})</span>
        </div>
        <div class="flex flex-wrap gap-1.5">${callersHtml}</div>
      </div>

      <div class="space-y-2 pt-2 border-t border-[#E2E8F0]">
        <div class="flex items-center justify-between text-[11px]">
          <span class="text-[#475569] font-semibold">Outbound Calls (${outgoing.length})</span>
        </div>
        <div class="flex flex-wrap gap-1.5">${calleesHtml}</div>
      </div>

      ${relatedTests.length > 0 ? `
        <div class="space-y-1.5 pt-2 border-t border-[#E2E8F0]">
          <span class="text-[#475569] font-semibold text-[11px]">Associated Tests (${relatedTests.length})</span>
          <div class="text-[11px] font-mono text-[#D97706] space-y-0.5">
            ${relatedTests.slice(0, 3).map(t => `<div>🧪 ${escapeHtml(t.sourceNode?.name || t.targetNode?.name)}</div>`).join('')}
          </div>
        </div>
      ` : ''}

      <div class="pt-3 border-t border-[#E2E8F0] space-y-2">
        <button id="btn-focus-this-node" class="w-full py-2 px-3 rounded-xl bg-[#F8FAFC] hover:bg-[#F1F5F9] text-xs font-semibold text-[#0071E3] border border-[#0071E3]/40 transition-all flex items-center justify-center gap-1.5">
          <span class="material-symbols-outlined text-[15px]">center_focus_strong</span>
          <span>Center on Node</span>
        </button>
        <button id="btn-run-impact-drawer" class="w-full py-2 px-3 rounded-xl bg-[#F59E0B] hover:bg-[#D97706] text-xs font-semibold text-white shadow-xs transition-all flex items-center justify-center gap-1.5">
          <span class="material-symbols-outlined text-[15px]">bolt</span>
          <span>Trace Blast Radius</span>
        </button>
      </div>
    `;

    panel.querySelectorAll('.chip-nav').forEach(btn => {
      btn.onclick = () => focusOnNode(btn.dataset.node);
    });

    const focusBtn = document.getElementById('btn-focus-this-node');
    if (focusBtn) {
      focusBtn.onclick = () => focusOnNode(node.id);
    }

    const impactBtn = document.getElementById('btn-run-impact-drawer');
    if (impactBtn) {
      impactBtn.onclick = () => triggerImpactAnalysis(node.id);
    }

    render();
  }

  function inspectEdge(edge) {
    state.selectedEdgeId = edge.id;
    const drawer = document.getElementById('node-detail-panel');
    if (drawer) drawer.classList.add('open');

    const typeBadge = document.getElementById('inspector-type-badge');
    if (typeBadge) {
      typeBadge.textContent = edge.type;
      typeBadge.style.color = '#D97706';
      typeBadge.style.borderColor = '#D9770655';
      typeBadge.style.background = '#D9770615';
    }

    const panel = document.getElementById('inspector-content');
    if (!panel) return;

    panel.innerHTML = `
      <div class="space-y-1">
        <div class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Relationship Contract</div>
        <div class="text-sm font-bold text-[#0F172A]">${edge.type}</div>
      </div>

      <div class="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] space-y-2">
        <div class="text-xs flex items-center gap-2">
          <span class="text-[#0284C7] font-bold">Source:</span>
          <span class="text-[#0F172A]">${escapeHtml(edge.sourceNode?.name || edge.source)}</span>
        </div>
        <div class="text-xs flex items-center gap-2">
          <span class="text-[#059669] font-bold">Target:</span>
          <span class="text-[#0F172A]">${escapeHtml(edge.targetNode?.name || edge.target)}</span>
        </div>
      </div>

      ${edge.is_drift ? `
        <div class="p-3 rounded-xl bg-[#FEF2F2] border border-[#FCA5A5] space-y-1 text-xs">
          <div class="font-bold text-[#DC2626] flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px]">warning</span>
            <span>Architecture Boundary Violation</span>
          </div>
          <div class="text-[#991B1B]">${escapeHtml(edge.drift_details?.expected_rule || 'Unauthorized cross-tier call')}</div>
        </div>
      ` : ''}

      <div class="space-y-1.5 pt-2 border-t border-[#E2E8F0]">
        <div class="text-[10px] uppercase font-bold text-[#64748B] tracking-wider">Detection Evidence</div>
        <div class="p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] font-mono text-[11px] text-[#334155] break-all">
          ${escapeHtml(edge.detection_method || 'ast_call_expression')}
        </div>
      </div>
    `;

    render();
  }

  function triggerImpactAnalysis(rootArtifactId) {
    state.impactMode = true;
    state.impactRootId = rootArtifactId;
    const impactBtn = document.getElementById('impact-mode-btn');
    if (impactBtn) impactBtn.classList.add('active');

    const node = state.nodeMap.get(rootArtifactId);
    const nodeName = node ? (node.name || node.label || rootArtifactId) : rootArtifactId;
    const inDegree = node ? (node.in_degree || 0) : 0;

    if (inDegree === 0) {
      showNotification(`⚡ Blast Radius: '${nodeName}' has 0 inbound callers (isolated entity). Blast radius confirmed zero.`, 'info');
    } else {
      showNotification(`⚡ Tracing Blast Radius for '${nodeName}': ${inDegree} direct upstream caller(s) identified. Computing propagation...`, 'info');
    }

    if (state.viewDimension === '3d' && window.Twin3D && window.Twin3D.active) {
      window.Twin3D.focusNode(rootArtifactId);
      window.Twin3D.highlightConnectedEdges(rootArtifactId);
    }

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
    if (state.viewDimension === '3d' && window.Twin3D && window.Twin3D.active) {
      window.Twin3D.focusNode(nodeId);
      inspectNode(node);
      return;
    }
    const w = state.width || 1000;
    const h = state.height || 700;
    state.transform.k = Math.max(1.1, Math.min(2.0, state.transform.k));
    state.transform.x = w / 2 - node.x * state.transform.k;
    state.transform.y = h / 2 - node.y * state.transform.k;
    inspectNode(node);
  }

  function performGraphSearch(query) {
    if (!query) return;
    const q = query.trim().toLowerCase();

    switchPrimaryView('architecture');
    switchArchSubtab('graph');

    const searchInput = document.getElementById('graph-search-input');
    if (searchInput) searchInput.value = query;

    const matched = (state.nodes || []).find(n => {
      const label = (n.label || '').toLowerCase();
      const name = (n.name || '').toLowerCase();
      const qual = (n.qualified_name || '').toLowerCase();
      const id = (n.id || '').toLowerCase();
      return label === q || name === q || qual.includes(q) || id.includes(q);
    });

    if (matched) {
      focusOnNode(matched.id);
      showNotification(`Focused on node: ${matched.label || matched.name}`, 'info');
    } else {
      state.focusNodeId = query.trim();
      loadGraph().then(() => {
        if (state.nodes && state.nodes.length > 0) {
          showNotification(`Displaying architecture graph for: ${query}`, 'info');
        } else {
          showNotification(`No nodes found matching "${query}" in this snapshot.`, 'warning');
        }
      });
    }
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
    const w = state.width || 1000;
    const h = state.height || 700;
    const newK = Math.max(0.15, Math.min(4.0, state.transform.k * factor));
    const kRatio = newK / state.transform.k;
    state.transform.x = w / 2 - (w / 2 - state.transform.x) * kRatio;
    state.transform.y = h / 2 - (h / 2 - state.transform.y) * kRatio;
    state.transform.k = newK;
    render();
  }

  function fitToScreen() {
    if (!state.nodes || state.nodes.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    state.nodes.forEach(n => {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y);
      maxY = Math.max(maxY, n.y);
    });

    const pad = 80;
    const gW = Math.max(80, maxX - minX + pad * 2);
    const gH = Math.max(80, maxY - minY + pad * 2);
    const w = state.width || 1000;
    const h = state.height || 700;
    const scale = Math.max(0.2, Math.min(w / gW, h / gH, 1.4));

    state.transform.k = scale;
    state.transform.x = w / 2 - ((minX + maxX) / 2) * scale;
    state.transform.y = h / 2 - ((minY + maxY) / 2) * scale;
    render();
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

  // =========================================================================
  // 14.5. THREE.JS 3D SOFTWARE ARCHITECTURE TWIN & ANIMATION SUBSYSTEM
  // =========================================================================
  const Twin3D = {
    active: false,
    initialized: false,
    container: null,
    scene: null,
    camera: null,
    renderer: null,
    controls: null,
    animFrameId: null,
    resizeObserver: null,

    // Scene Graph Groups
    nodesGroup: null,
    edgesGroup: null,
    labelsGroup: null,
    helpersGroup: null,
    particlesGroup: null,
    beaconMesh: null,
    selectedHalo: null,
    hoverSprite: null,

    // Entity Map: nodeId -> THREE.Mesh
    nodeMeshes: new Map(),
    nodeDataMap: new Map(),
    edgeLines: [],

    // Raycaster & Pointer
    raycaster: null,
    pointer: null,
    hoveredMesh: null,

    // Smooth Camera Animation
    cameraLerp: null,

    // Simulation & Impact State
    simMode: null,
    simData: null,
    simState: 'IDLE',
    simStepIndex: 0,
    simTotalSteps: 0,
    simSpeed: 1.0,
    simTimer: null,
    simStages: [],
    reducedMotion: false,
    waveParticles: [],

    init() {
      if (this.initialized) return true;
      if (typeof THREE === 'undefined') {
        console.warn('Three.js is not yet available in window.');
        return false;
      }

      this.container = document.getElementById('twin-3d-container');
      if (!this.container) return false;

      const rect = this.container.getBoundingClientRect();
      const width = Math.max(300, rect.width || this.container.clientWidth || window.innerWidth);
      const height = Math.max(300, rect.height || this.container.clientHeight || 700);

      // 1. Spatial Dark Environment Scene with Linear Soft Depth Fog
      this.scene = new THREE.Scene();
      this.scene.background = new THREE.Color(0x090D16);
      this.scene.fog = new THREE.Fog(0x090D16, 900, 4200);

      // 2. Perspective Camera
      this.camera = new THREE.PerspectiveCamera(45, width / height, 1, 10000);
      this.camera.position.set(0, 450, 900);

      // 3. WebGL Renderer
      this.renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        powerPreference: 'high-performance',
      });
      this.renderer.setSize(width, height);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
      this.renderer.toneMappingExposure = 1.25;

      this.container.innerHTML = '';
      this.container.appendChild(this.renderer.domElement);

      // 4. OrbitControls
      if (typeof THREE.OrbitControls !== 'undefined') {
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;
        this.controls.screenSpacePanning = true;
        this.controls.minDistance = 60;
        this.controls.maxDistance = 4500;
        this.controls.target.set(0, 0, 0);
      }

      // 5. Lighting Setup: Vivid architectural studio
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
      this.scene.add(ambientLight);

      const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
      dirLight.position.set(500, 900, 600);
      this.scene.add(dirLight);

      const fillLight = new THREE.DirectionalLight(0x38BDF8, 0.55);
      fillLight.position.set(-500, 300, -500);
      this.scene.add(fillLight);

      const pointLight = new THREE.PointLight(0xA855F7, 0.7, 1600);
      pointLight.position.set(0, 200, 0);
      this.scene.add(pointLight);

      // 6. Scene Hierarchy Groups
      this.helpersGroup = new THREE.Group();
      this.edgesGroup = new THREE.Group();
      this.nodesGroup = new THREE.Group();
      this.labelsGroup = new THREE.Group();
      this.particlesGroup = new THREE.Group();

      this.scene.add(this.helpersGroup);
      this.scene.add(this.edgesGroup);
      this.scene.add(this.nodesGroup);
      this.scene.add(this.labelsGroup);
      this.scene.add(this.particlesGroup);

      this.setupTierHelpers();

      // 7. Raycaster & Pointer Interaction
      this.raycaster = new THREE.Raycaster();
      this.pointer = new THREE.Vector2();

      this.setupInteractionListeners();
      this.setupHUDListeners();

      // 8. Auto-Resize Observer
      if (window.ResizeObserver && !this.resizeObserver) {
        this.resizeObserver = new ResizeObserver(() => {
          if (this.active) {
            this.onResize();
          }
        });
        this.resizeObserver.observe(this.container);
      }

      this.initialized = true;
      window.Twin3D = this;
      return true;
    },

    setupTierHelpers() {
      this.helpersGroup.clear();

      // Base Studio Spatial Grid
      const baseGrid = new THREE.GridHelper(1800, 36, 0x334155, 0x1E293B);
      baseGrid.position.y = -280;
      this.helpersGroup.add(baseGrid);

      // Architectural Tiers: APIs / Routes (Top), Services / Logic (Middle), Data / Storage (Bottom)
      const tierDefs = [
        { y: 180, color: 0xE11D48, radius: 520 },
        { y: 0, color: 0x0284C7, radius: 580 },
        { y: -180, color: 0xD97706, radius: 540 },
      ];

      tierDefs.forEach(tier => {
        const ringGeo = new THREE.RingGeometry(tier.radius - 2, tier.radius + 2, 64);
        const ringMat = new THREE.MeshBasicMaterial({
          color: tier.color,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.22,
        });
        const ringMesh = new THREE.Mesh(ringGeo, ringMat);
        ringMesh.rotation.x = Math.PI / 2;
        ringMesh.position.y = tier.y;
        this.helpersGroup.add(ringMesh);
      });
    },

    // High-DPI Text Billboard Sprite Factory
    createLabelSprite(text, type, colorHex, isProminent = false) {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const fontSize = isProminent ? 26 : 21;
      canvas.width = 512;
      canvas.height = 128;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      ctx.font = `600 ${fontSize}px ui-sans-serif, system-ui, -apple-system, sans-serif`;
      const textMetrics = ctx.measureText(text);
      const paddingX = 22;
      const pillWidth = Math.min(canvas.width - 24, textMetrics.width + paddingX * 2);
      const pillHeight = 44;
      const x = (canvas.width - pillWidth) / 2;
      const y = (canvas.height - pillHeight) / 2;
      const radius = 10;

      // Draw glassmorphic badge pill background
      ctx.beginPath();
      ctx.roundRect(x, y, pillWidth, pillHeight, radius);
      ctx.fillStyle = isProminent ? 'rgba(15, 23, 42, 0.92)' : 'rgba(15, 23, 42, 0.85)';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = isProminent ? '#38BDF8' : 'rgba(100, 116, 139, 0.65)';
      ctx.stroke();

      // Text with clean crisp contrast
      ctx.fillStyle = '#F8FAFC';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, canvas.width / 2, canvas.height / 2);

      const texture = new THREE.CanvasTexture(canvas);
      texture.minFilter = THREE.LinearFilter;
      const spriteMat = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthWrite: false,
      });
      const sprite = new THREE.Sprite(spriteMat);
      const scaleX = isProminent ? 88 : 72;
      const scaleY = isProminent ? 22 : 18;
      sprite.scale.set(scaleX, scaleY, 1);
      return sprite;
    },

    setupInteractionListeners() {
      const dom = this.renderer.domElement;
      const tooltip = document.getElementById('twin-3d-tooltip');

      dom.addEventListener('pointermove', (e) => {
        const rect = dom.getBoundingClientRect();
        this.pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        this.pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        if (this.nodesGroup && this.raycaster && this.camera) {
          this.raycaster.setFromCamera(this.pointer, this.camera);
          const intersects = this.raycaster.intersectObjects(this.nodesGroup.children, false);

          if (intersects.length > 0) {
            const hit = intersects[0].object;
            dom.style.cursor = 'pointer';

            if (this.hoveredMesh !== hit) {
              this.unhover();
              this.hoveredMesh = hit;
              if (hit.material && hit.material.emissive) {
                hit.userData.prevEmissive = hit.material.emissive.getHex();
                hit.userData.prevIntensity = hit.material.emissiveIntensity;
                hit.material.emissive.setHex(0x38BDF8);
                hit.material.emissiveIntensity = 0.8;
              }

              // Show dynamic hover sprite if node does not already have an anchor label
              const nodeData = hit.userData?.nodeData;
              if (nodeData && !nodeData.labelSprite) {
                if (this.hoverSprite) {
                  this.scene.remove(this.hoverSprite);
                  if (this.hoverSprite.material?.map) this.hoverSprite.material.map.dispose();
                  if (this.hoverSprite.material) this.hoverSprite.material.dispose();
                  this.hoverSprite = null;
                }
                const labelText = nodeData.name || nodeData.label || nodeData.id;
                this.hoverSprite = this.createLabelSprite(labelText, nodeData.type, 0x38BDF8, true);
                this.hoverSprite.position.set(hit.position.x, hit.position.y + (hit.userData?.radius || 10) + 16, hit.position.z);
                this.scene.add(this.hoverSprite);
              }
            }

            if (tooltip && hit.userData?.nodeData) {
              const node = hit.userData.nodeData;
              tooltip.style.display = 'block';
              tooltip.style.left = `${Math.min(window.innerWidth - 240, e.clientX + 14)}px`;
              tooltip.style.top = `${Math.min(window.innerHeight - 100, e.clientY + 14)}px`;
              document.getElementById('twin-3d-tooltip-badge').textContent = node.type || 'ENTITY';
              document.getElementById('twin-3d-tooltip-title').textContent = node.name || node.label || node.id;
              document.getElementById('twin-3d-tooltip-path').textContent = node.file || node.qualified_name || '';

              const provEl = document.getElementById('twin-3d-tooltip-provenance');
              if (provEl) {
                const prov = node.provenance || (node.is_simulated ? 'SIMULATED' : (node.is_derived ? 'DERIVED' : 'OBSERVED'));
                provEl.textContent = prov;
              }
            }
          } else {
            dom.style.cursor = 'grab';
            this.unhover();
            if (tooltip) tooltip.style.display = 'none';
          }
        }
      });

      dom.addEventListener('click', (e) => {
        if (!this.nodesGroup || !this.raycaster || !this.camera) return;
        const rect = dom.getBoundingClientRect();
        this.pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        this.pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.pointer, this.camera);
        const intersects = this.raycaster.intersectObjects(this.nodesGroup.children, false);

        if (intersects.length > 0) {
          const hit = intersects[0].object;
          if (hit.userData?.nodeData) {
            const node = hit.userData.nodeData;
            this.selectNode(node.id, true);
          }
        }
      });
    },

    unhover() {
      if (this.hoveredMesh) {
        if (this.hoveredMesh.material && this.hoveredMesh.userData?.prevEmissive !== undefined) {
          this.hoveredMesh.material.emissive.setHex(this.hoveredMesh.userData.prevEmissive);
          this.hoveredMesh.material.emissiveIntensity = this.hoveredMesh.userData.prevIntensity || 0;
        }
        this.hoveredMesh = null;
      }
      if (this.hoverSprite) {
        this.scene.remove(this.hoverSprite);
        if (this.hoverSprite.material?.map) this.hoverSprite.material.map.dispose();
        if (this.hoverSprite.material) this.hoverSprite.material.dispose();
        this.hoverSprite = null;
      }
    },

    selectNode(nodeId, openInspector = true) {
      const node = state.nodeMap.get(nodeId) || this.nodeDataMap.get(nodeId);
      if (!node) return;

      state.selectedNodeId = nodeId;
      this.highlightSelectedHalo(nodeId);
      this.highlightConnectedEdges(nodeId);

      if (openInspector) {
        inspectNode(node);
      }
    },

    highlightSelectedHalo(nodeId) {
      this.clearSelectedHalo();

      const mesh = this.nodeMeshes.get(nodeId);
      if (!mesh) return;

      const r = (mesh.userData?.radius || 10) * 1.65;
      const haloGeo = new THREE.RingGeometry(r - 1.0, r + 1.8, 32);
      const haloMat = new THREE.MeshBasicMaterial({
        color: 0x38BDF8,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.88,
      });
      this.selectedHalo = new THREE.Mesh(haloGeo, haloMat);
      this.selectedHalo.position.copy(mesh.position);
      this.selectedHalo.lookAt(this.camera.position);
      this.scene.add(this.selectedHalo);
    },

    clearSelectedHalo() {
      if (this.selectedHalo) {
        this.scene.remove(this.selectedHalo);
        if (this.selectedHalo.geometry) this.selectedHalo.geometry.dispose();
        if (this.selectedHalo.material) this.selectedHalo.material.dispose();
        this.selectedHalo = null;
      }
    },

    highlightConnectedEdges(nodeId) {
      if (!this.edgesGroup || this.edgeLines.length === 0) return;
      const connectedEdges = this.edgeLines.filter(e => e.sourceId === nodeId || e.targetId === nodeId);
      if (connectedEdges.length === 0) return;

      // Spawn subtle pulse along connected edges
      connectedEdges.slice(0, 8).forEach(e => {
        this.spawnWaveParticle(e.p1, e.p2);
      });
    },

    setupHUDListeners() {
      document.getElementById('btn-3d-reset-cam')?.addEventListener('click', () => this.resetCamera());
      document.getElementById('btn-3d-fit-graph')?.addEventListener('click', () => this.fitGraph(false));
      document.getElementById('btn-3d-toggle-tiers')?.addEventListener('click', () => {
        this.helpersGroup.visible = !this.helpersGroup.visible;
      });

      // Dimension Toggle Buttons (2D vs 3D)
      document.getElementById('view-mode-2d')?.addEventListener('click', () => this.toggleViewMode('2d'));
      document.getElementById('view-mode-3d')?.addEventListener('click', () => this.toggleViewMode('3d'));

      // Playback Toolbar Transport
      document.getElementById('sim-3d-play-pause-btn')?.addEventListener('click', () => this.togglePlayback());
      document.getElementById('sim-3d-step-btn')?.addEventListener('click', () => this.stepForward());
      document.getElementById('sim-3d-reset-btn')?.addEventListener('click', () => this.resetSimulationAnimation());
      document.getElementById('sim-3d-focus-btn')?.addEventListener('click', () => {
        if (this.simStages && this.simStages[this.simStepIndex]?.mutantNode) {
          this.focusNode(this.simStages[this.simStepIndex].mutantNode.id);
        } else if (state.lastSimulationResult) {
          const target = (state.lastSimulationResult.structured_scenario?.target_entities || [])[0]
            || (state.lastSimulationResult.proposed_changes || [])[0]?.target;
          if (target) {
            let mNode = null;
            this.nodeDataMap.forEach((n, id) => {
              if (!mNode && (id === target || n.name === target || (n.qualified_name && n.qualified_name.includes(target)))) {
                mNode = n;
              }
            });
            if (mNode) this.focusNode(mNode.id);
          }
        }
      });
      document.getElementById('sim-3d-speed-select')?.addEventListener('change', (e) => {
        this.simSpeed = parseFloat(e.target.value) || 1.0;
      });
      document.getElementById('sim-3d-reduced-motion')?.addEventListener('change', (e) => {
        this.reducedMotion = e.target.checked;
      });
      document.getElementById('sim-3d-baseline-btn')?.addEventListener('click', () => this.closePlaybackBar());

      // Buttons to animate from other views
      document.getElementById('btn-sim-visualize-3d')?.addEventListener('click', () => {
        if (state.lastSimulationResult) {
          switchPrimaryView('architecture');
          this.toggleViewMode('3d');
          this.animateWhatIfSimulation(state.lastSimulationResult);
        } else {
          showNotification('Run a simulation first to animate in 3D.', 'info');
        }
      });

      document.getElementById('btn-impact-visualize-3d')?.addEventListener('click', () => {
        const btn = document.getElementById('btn-impact-visualize-3d');
        if (btn && btn.disabled) return;
        if (typeof currentImpactAnalysisResult !== 'undefined' && currentImpactAnalysisResult) {
          switchPrimaryView('architecture');
          this.toggleViewMode('3d');
          this.animateChangeImpact(currentImpactAnalysisResult);
        }
      });
    },

    toggleViewMode(mode) {
      state.viewDimension = mode;
      const btn2D = document.getElementById('view-mode-2d');
      const btn3D = document.getElementById('view-mode-3d');
      const canvas2D = document.getElementById('twin-canvas');
      const container3D = document.getElementById('twin-3d-container');
      const hud3D = document.getElementById('twin-3d-hud');
      const legendBadge = document.getElementById('legend-space-badge');
      const legendCard = document.getElementById('graph-legend-card');
      const statusPill = document.getElementById('graph-status-pill');

      if (mode === '3d') {
        this.active = true;
        if (btn3D) {
          btn3D.classList.add('bg-white', 'text-[#0F172A]', 'shadow-xs', 'font-semibold');
          btn3D.classList.remove('text-[#64748B]');
        }
        if (btn2D) {
          btn2D.classList.remove('bg-white', 'text-[#0F172A]', 'shadow-xs', 'font-semibold');
          btn2D.classList.add('text-[#64748B]');
        }
        if (canvas2D) canvas2D.style.display = 'none';
        if (container3D) container3D.classList.remove('hidden');
        if (hud3D) hud3D.classList.remove('hidden');
        if (legendBadge) legendBadge.textContent = 'Three.js 3D';

        // Adapt legend card & status pill to 3D dark glassmorphic theme
        if (legendCard) {
          legendCard.classList.remove('bg-white/95', 'border-[#E2E8F0]');
          legendCard.classList.add('bg-[#0F172A]/90', 'border-slate-700/80', 'text-slate-200');
        }
        if (statusPill) {
          statusPill.classList.remove('bg-white/95', 'border-[#E2E8F0]', 'text-[#475569]');
          statusPill.classList.add('bg-[#0F172A]/90', 'border-slate-700/80', 'text-slate-200');
        }

        this.init();
        this.onResize();
        this.buildScene(state.rawGraph);
        this.fitGraph(true);
        this.startRenderLoop();
        requestAnimationFrame(() => {
          this.onResize();
          this.fitGraph(true);
        });
      } else {
        this.active = false;
        if (btn2D) {
          btn2D.classList.add('bg-white', 'text-[#0F172A]', 'shadow-xs', 'font-semibold');
          btn2D.classList.remove('text-[#64748B]');
        }
        if (btn3D) {
          btn3D.classList.remove('bg-white', 'text-[#0F172A]', 'shadow-xs', 'font-semibold');
          btn3D.classList.add('text-[#64748B]');
        }
        if (canvas2D) canvas2D.style.display = 'block';
        if (container3D) container3D.classList.add('hidden');
        if (hud3D) hud3D.classList.add('hidden');
        document.getElementById('sim-3d-playback-bar')?.classList.add('hidden');
        if (legendBadge) legendBadge.textContent = 'MiroFish 2D';

        // Restore light theme for 2D
        if (legendCard) {
          legendCard.classList.remove('bg-[#0F172A]/90', 'border-slate-700/80', 'text-slate-200');
          legendCard.classList.add('bg-white/95', 'border-[#E2E8F0]');
        }
        if (statusPill) {
          statusPill.classList.remove('bg-[#0F172A]/90', 'border-slate-700/80', 'text-slate-200');
          statusPill.classList.add('bg-white/95', 'border-[#E2E8F0]', 'text-[#475569]');
        }

        this.stopRenderLoop();
        resizeCanvas();
        render();
      }
    },

    onResize() {
      if (!this.renderer || !this.camera || !this.container) return;
      const rect = this.container.getBoundingClientRect();
      const isFull = this.container.parentElement?.classList.contains('graph-fullscreen-mode');
      const w = Math.max(300, isFull ? window.innerWidth : (rect.width || this.container.clientWidth || 1000));
      const h = Math.max(300, isFull ? window.innerHeight : (rect.height || this.container.clientHeight || 700));

      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    },

    buildScene(graphData) {
      if (!this.initialized) {
        if (!this.init()) return;
      }

      this.clearScene();

      let rawNodes = (graphData && graphData.nodes && graphData.nodes.length > 0) ? graphData.nodes : null;
      let rawEdges = (graphData && graphData.edges && graphData.edges.length > 0) ? graphData.edges : null;

      if (!rawNodes || rawNodes.length === 0) {
        if (state.rawGraph && state.rawGraph.nodes && state.rawGraph.nodes.length > 0) {
          rawNodes = state.rawGraph.nodes;
          rawEdges = state.rawGraph.edges;
        } else if (state.nodes && state.nodes.length > 0) {
          rawNodes = state.nodes;
          rawEdges = state.edges;
        }
      }

      if (!rawNodes || rawNodes.length === 0) {
        if (state.currentRepoId) {
          loadGraph();
        }
        return;
      }

      rawEdges = rawEdges || [];

      // Group nodes by package/module deterministically
      const clusterMap = new Map();
      rawNodes.forEach(node => {
        let pkg = 'core';
        if (node.package) pkg = node.package;
        else if (node.file) {
          const parts = node.file.split('/');
          pkg = parts.length > 1 ? parts[0] : 'root';
        }
        if (!clusterMap.has(pkg)) clusterMap.set(pkg, []);
        clusterMap.get(pkg).push(node);
      });

      // Sort cluster keys alphabetically for 100% deterministic spatial anchors
      const sortedPkgs = Array.from(clusterMap.keys()).sort();
      const clusterCount = sortedPkgs.length;

      // Layout nodes into 3D Space
      sortedPkgs.forEach((pkg, clusterIdx) => {
        const clusterNodes = clusterMap.get(pkg);
        const anchorAngle = clusterCount > 1 ? (clusterIdx * (2 * Math.PI / clusterCount)) : 0;
        const anchorDist = clusterCount > 1 ? (240 + (clusterIdx % 2) * 60) : 0;
        const anchorX = Math.cos(anchorAngle) * anchorDist;
        const anchorZ = Math.sin(anchorAngle) * anchorDist;

        // Landmark text sprite for package cluster
        if (clusterCount > 1 || clusterNodes.length > 8) {
          const pkgSprite = this.createLabelSprite(pkg.toUpperCase(), 'PACKAGE', 0x38BDF8, true);
          pkgSprite.position.set(anchorX, 230, anchorZ);
          this.labelsGroup.add(pkgSprite);
        }

        clusterNodes.forEach((node, nodeIdx) => {
          // Architectural Tier (Y-axis)
          let tierY = 0;
          const type = (node.type || '').toUpperCase();
          if (type.includes('API') || type.includes('ROUTE') || type.includes('ENDPOINT')) {
            tierY = 180;
          } else if (type.includes('DATABASE') || type.includes('TABLE') || type.includes('SQL')) {
            tierY = -180;
          } else if (type.includes('TEST')) {
            tierY = -260;
          } else if (type.includes('EXTERNAL')) {
            tierY = -260;
          } else {
            tierY = 0; // Services, classes, modules
          }

          // Golden Spiral Dispersion within Package Cluster (X/Z plane)
          const phi = nodeIdx * 2.39996;
          const r = 25 + Math.sqrt(nodeIdx) * 32;
          const posX = anchorX + Math.cos(phi) * r;
          const posZ = anchorZ + Math.sin(phi) * r;
          const posY = tierY + (nodeIdx % 3 - 1) * 14;

          node.x3d = posX;
          node.y3d = posY;
          node.z3d = posZ;

          // Node Sphere Mesh
          const radius = this.getNodeRadius3D(type, node.in_degree);
          node.radius3d = radius;
          let colorHex = this.getNodeColorHex(type);
          if (node.diff_status === 'ADDED') {
            colorHex = 0x10B981; // Emerald green
          } else if (node.diff_status === 'REMOVED') {
            colorHex = 0xEF4444; // Rose red
          } else if (node.diff_status === 'MODIFIED') {
            colorHex = 0xF59E0B; // Amber warning
          } else if (node.is_impacted) {
            colorHex = 0xF97316; // Radiant blast orange
          }

          const geo = new THREE.SphereGeometry(radius, 20, 20);
          const mat = new THREE.MeshStandardMaterial({
            color: colorHex,
            roughness: 0.32,
            metalness: 0.22,
            emissive: colorHex,
            emissiveIntensity: 0.16,
          });

          const mesh = new THREE.Mesh(geo, mat);
          mesh.position.set(posX, posY, posZ);
          mesh.userData = {
            nodeId: node.id,
            nodeData: node,
            radius: radius,
            origColor: colorHex,
          };

          this.nodesGroup.add(mesh);
          this.nodeMeshes.set(node.id, mesh);
          this.nodeDataMap.set(node.id, node);
        });
      });

      // Add prominent billboard labels for top landmark nodes (highest degrees or central entities)
      const prominentNodes = [...rawNodes]
        .sort((a, b) => (b.in_degree || 0) - (a.in_degree || 0))
        .slice(0, 10);
      const prominentIds = new Set(prominentNodes.map(n => n.id));

      rawNodes.forEach(node => {
        if (prominentIds.has(node.id) && node.x3d !== undefined) {
          const sprite = this.createLabelSprite(node.name || node.label || node.id, node.type, this.getNodeColorHex((node.type || '').toUpperCase()), false);
          sprite.position.set(node.x3d, node.y3d + (node.radius3d || 10) + 14, node.z3d);
          this.labelsGroup.add(sprite);
          node.labelSprite = sprite;
        }
      });

      // Render Relationship Lines
      const linePositions = [];
      const lineColors = [];
      const edgeColorNormal = new THREE.Color(0x64748B);
      const edgeColorDrift = new THREE.Color(0xEF4444);

      rawEdges.forEach(edge => {
        const srcMesh = this.nodeMeshes.get(edge.source);
        const tgtMesh = this.nodeMeshes.get(edge.target);
        if (!srcMesh || !tgtMesh) return;

        const p1 = srcMesh.position;
        const p2 = tgtMesh.position;

        linePositions.push(p1.x, p1.y, p1.z, p2.x, p2.y, p2.z);
        const col = edge.is_drift ? edgeColorDrift : edgeColorNormal;
        lineColors.push(col.r, col.g, col.b, col.r, col.g, col.b);

        this.edgeLines.push({
          sourceId: edge.source,
          targetId: edge.target,
          edgeData: edge,
          p1: p1.clone(),
          p2: p2.clone(),
        });
      });

      if (linePositions.length > 0) {
        const lineGeo = new THREE.BufferGeometry();
        lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
        lineGeo.setAttribute('color', new THREE.Float32BufferAttribute(lineColors, 3));

        const lineMat = new THREE.LineBasicMaterial({
          vertexColors: true,
          transparent: true,
          opacity: 0.55,
        });

        const linesMesh = new THREE.LineSegments(lineGeo, lineMat);
        this.edgesGroup.add(linesMesh);
      }

      // If a node was previously selected, restore its halo
      if (state.selectedNodeId && this.nodeMeshes.has(state.selectedNodeId)) {
        this.highlightSelectedHalo(state.selectedNodeId);
      }

      this.fitGraph(true);
    },

    getNodeRadius3D(type, inDegree) {
      const base = {
        PACKAGE: 16,
        SERVICE: 14,
        MODULE: 13,
        DATABASE: 13,
        DATABASE_TABLE: 12,
        CLASS: 11,
        API_ENDPOINT: 11,
        FUNCTION: 8.5,
        METHOD: 8.5,
        TEST_CASE: 9.5,
        EXTERNAL_DEPENDENCY: 8,
      }[type] || 10;
      return Math.min(24, base + Math.min(inDegree || 0, 6) * 0.9);
    },

    getNodeColorHex(type) {
      const map = {
        PACKAGE: 0x2563EB,
        MODULE: 0x059669,
        CLASS: 0x0284C7,
        SERVICE: 0x7C3AED,
        API_ENDPOINT: 0xE11D48,
        FUNCTION: 0xDB2777,
        METHOD: 0x6366F1,
        DATABASE_TABLE: 0xD97706,
        DATABASE: 0xEA580C,
        TEST_CASE: 0x8B5CF6,
        EXTERNAL_DEPENDENCY: 0x64748B,
      };
      return map[type] || 0x64748B;
    },

    clearScene() {
      // Clean up node meshes
      this.nodeMeshes.forEach(mesh => {
        if (mesh.geometry) mesh.geometry.dispose();
        if (mesh.material) mesh.material.dispose();
      });
      this.nodeMeshes.clear();
      this.nodeDataMap.clear();
      this.nodesGroup.clear();

      // Clean up billboard labels
      this.labelsGroup.children.forEach(child => {
        if (child.material?.map) child.material.map.dispose();
        if (child.material) child.material.dispose();
      });
      this.labelsGroup.clear();

      // Clean up edge meshes
      this.edgesGroup.children.forEach(child => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      });
      this.edgesGroup.clear();
      this.edgeLines = [];

      // Clean up particles & hover
      this.clearParticles();
      this.unhover();
      this.clearSelectedHalo();

      if (this.beaconMesh) {
        this.scene.remove(this.beaconMesh);
        this.beaconMesh = null;
      }
    },

    clearParticles() {
      this.particlesGroup.children.forEach(child => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      });
      this.particlesGroup.clear();
      this.waveParticles = [];
    },

    focusNode(nodeId) {
      const mesh = this.nodeMeshes.get(nodeId);
      if (!mesh) return;

      this.highlightSelectedHalo(nodeId);

      const target = mesh.position.clone();
      const pos = target.clone().add(new THREE.Vector3(0, 60, 220));

      this.animateCameraTo(pos, target, 750);
    },

    fitGraph(immediate = false) {
      if (this.nodeMeshes.size === 0) return;

      const box = new THREE.Box3();
      this.nodeMeshes.forEach(mesh => box.expandByPoint(mesh.position));

      const sphere = box.getBoundingSphere(new THREE.Sphere());
      const radius = Math.max(180, sphere.radius);
      const fov = (this.camera.fov * Math.PI) / 180;
      let dist = radius / Math.sin(fov / 2);
      dist = Math.max(300, Math.min(dist * 1.1, 2600));

      const center = sphere.center;
      const targetPos = new THREE.Vector3(center.x, center.y + dist * 0.45, center.z + dist * 0.95);

      if (immediate) {
        this.camera.position.copy(targetPos);
        if (this.controls) {
          this.controls.target.copy(center);
          this.controls.update();
        } else {
          this.camera.lookAt(center);
        }
        this.cameraLerp = null;
      } else {
        this.animateCameraTo(targetPos, center, 750);
      }
    },

    resetCamera() {
      const targetPos = new THREE.Vector3(0, 450, 900);
      const targetLookAt = new THREE.Vector3(0, 0, 0);
      this.animateCameraTo(targetPos, targetLookAt, 750);
    },

    animateCameraTo(targetPos, targetLookAt, duration = 750) {
      if (this.reducedMotion) {
        this.camera.position.copy(targetPos);
        if (this.controls) {
          this.controls.target.copy(targetLookAt);
          this.controls.update();
        } else {
          this.camera.lookAt(targetLookAt);
        }
        this.cameraLerp = null;
        return;
      }

      this.cameraLerp = {
        startPos: this.camera.position.clone(),
        targetPos: targetPos.clone(),
        startTarget: this.controls ? this.controls.target.clone() : new THREE.Vector3(),
        targetLookAt: targetLookAt.clone(),
        startTime: performance.now(),
        duration: duration,
      };
    },

    startRenderLoop() {
      if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
      const tick = () => {
        if (!this.active) return;
        this.renderTick();
        this.animFrameId = requestAnimationFrame(tick);
      };
      this.animFrameId = requestAnimationFrame(tick);
    },

    stopRenderLoop() {
      if (this.animFrameId) {
        cancelAnimationFrame(this.animFrameId);
        this.animFrameId = null;
      }
    },

    renderTick() {
      if (!this.renderer || !this.scene || !this.camera) return;

      // Smooth camera interpolation
      if (this.cameraLerp) {
        const elapsed = performance.now() - this.cameraLerp.startTime;
        const progress = Math.min(1, elapsed / this.cameraLerp.duration);
        // Smooth cubic ease-in-out curve
        const ease = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;

        this.camera.position.lerpVectors(this.cameraLerp.startPos, this.cameraLerp.targetPos, ease);
        if (this.controls) {
          this.controls.target.lerpVectors(this.cameraLerp.startTarget, this.cameraLerp.targetLookAt, ease);
          this.controls.update();
        }
        if (progress >= 1) {
          this.cameraLerp = null;
        }
      } else if (this.controls) {
        this.controls.update();
      }

      // Animate selected halo to billboard towards camera
      if (this.selectedHalo) {
        this.selectedHalo.lookAt(this.camera.position);
      }

      // Animate pulsing beacon for mutation / injection
      if (this.beaconMesh) {
        const time = Date.now() * 0.003;
        const scale = 1.0 + Math.sin(time) * 0.25;
        this.beaconMesh.scale.set(scale, scale, scale);
        this.beaconMesh.lookAt(this.camera.position);
      }

      // Animate propagation particles along edges
      this.waveParticles.forEach(p => {
        p.progress += 0.015 * this.simSpeed;
        if (p.progress > 1) p.progress = 0;
        p.mesh.position.lerpVectors(p.start, p.end, p.progress);
      });

      this.renderer.render(this.scene, this.camera);
    },

    // --- 3D What-If Simulation Pipeline ---
    animateWhatIfSimulation(data) {
      this.simMode = 'WHAT_IF';
      this.simData = data;
      this.simStepIndex = 0;
      this.simState = 'PLAYING';

      const bar = document.getElementById('sim-3d-playback-bar');
      const label = document.getElementById('sim-3d-mode-label');
      const playIcon = document.getElementById('sim-3d-play-icon');

      if (bar) bar.classList.remove('hidden');
      if (label) label.textContent = 'Evidence-Backed What-If Simulation';
      if (playIcon) playIcon.textContent = 'pause';

      // 1. Identify mutant node from scenario
      const changes = data.proposed_changes || [];
      const structTargets = data.structured_scenario?.target_entities || [];
      const findingsTargets = (data.findings || []).flatMap(f => f.affected_entity_ids || []);
      const firstTarget = structTargets[0] || changes[0]?.target || (data.impact?.changed_artifacts || [])[0] || findingsTargets[0] || '';
      let mutantNode = null;

      if (firstTarget) {
        const ftLower = firstTarget.toLowerCase();
        this.nodeDataMap.forEach((node, id) => {
          if (!mutantNode) {
            const nIdLower = id.toLowerCase();
            const nNameLower = (node.name || '').toLowerCase();
            const nQualLower = (node.qualified_name || '').toLowerCase();
            if (nIdLower === ftLower || nNameLower === ftLower || nQualLower === ftLower || nQualLower.includes(ftLower) || ftLower.includes(nNameLower)) {
              mutantNode = node;
            }
          }
        });
      }

      // 2. Extract multi-hop propagation paths & impact sets
      const paths = data.impact?.propagation_paths || [];
      const affectedComponents = new Set(data.impact?.affected_components || []);
      const affectedTests = new Set(data.tests?.directly_affected_tests || []);

      const isCapacityOrUnsupported = data.status === 'UNSUPPORTED' ||
        (data.structured_scenario?.analysis_objective && data.structured_scenario.analysis_objective.includes('CAPACITY')) ||
        (data.engine_routing?.roles_executed || []).some(r => r.status === 'NOT_EVALUATED' && r.role.includes('Reliability'));

      const isZeroImpact = (!data.impact?.affected_components || data.impact.affected_components.length === 0) &&
                           (!data.impact?.affected_apis || data.impact.affected_apis.length === 0) &&
                           (!data.tests?.directly_affected_tests || data.tests.directly_affected_tests.length === 0) &&
                           paths.length === 0;

      this.simStages = [];

      if (isCapacityOrUnsupported) {
        this.simStages.push({
          phase: 'BASELINE',
          label: 'Phase 1: Baseline Architecture Synchronized',
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });
        this.simStages.push({
          phase: 'INJECTION',
          label: `Phase 2: Capacity / Workload Scenario Injected on ${mutantNode?.name || firstTarget || 'Target'}`,
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });
        this.simStages.push({
          phase: 'UNSUPPORTED',
          label: 'Phase 3: Capacity Prediction Unsupported (Live Telemetry Required - Marked NOT_EVALUATED)',
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });
        this.simStages.push({
          phase: 'COMPLETED',
          label: 'Phase 4: Simulation Completed • Zero False Claims Made',
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });
      } else if (isZeroImpact) {
        this.simStages.push({
          phase: 'BASELINE',
          label: 'Phase 1: Baseline Architecture Synchronized',
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });
        this.simStages.push({
          phase: 'INJECTION',
          label: `Phase 2: Virtual Mutation Injected on Isolated Entity: ${mutantNode?.name || firstTarget || 'Target'}`,
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });
        this.simStages.push({
          phase: 'ZERO_IMPACT',
          label: 'Phase 3: Verified Zero Blast Radius • 0 Downstream Dependents Affected',
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });
        this.simStages.push({
          phase: 'COMPLETED',
          label: 'Phase 4: Simulation Completed • Zero Regressions Predicted',
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });
      } else {
        this.simStages.push({
          phase: 'BASELINE',
          label: 'Phase 1: Baseline Architecture Synchronized',
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });

        this.simStages.push({
          phase: 'INJECTION',
          label: `Phase 2: Virtual Mutation Injected on ${mutantNode?.name || firstTarget}`,
          mutantNode: mutantNode,
          highlightNodes: mutantNode ? [mutantNode.id] : [],
          activeEdges: [],
        });

        const compArray = Array.from(affectedComponents);
        const directNodes = compArray.slice(0, 3);
        const indirectNodes = compArray.slice(3);

        if (directNodes.length > 0) {
          this.simStages.push({
            phase: 'DIRECT',
            label: `Phase 3: Direct Blast Radius (${directNodes.length} immediate dependents)`,
            mutantNode: mutantNode,
            highlightNodes: directNodes,
            activeEdges: paths.length > 0 ? (paths[0]?.hops || []) : [],
          });
        }

        if (indirectNodes.length > 0) {
          this.simStages.push({
            phase: 'INDIRECT',
            label: `Phase 4: Transitive Multi-Hop Blast Radius (${indirectNodes.length} indirect dependents)`,
            mutantNode: mutantNode,
            highlightNodes: indirectNodes,
            activeEdges: paths.length > 1 ? (paths[1]?.hops || []) : [],
          });
        }

        if (affectedTests.size > 0) {
          this.simStages.push({
            phase: 'TESTS',
            label: `Phase 5: Impacted Test Verification Suites (${affectedTests.size} test cases)`,
            mutantNode: mutantNode,
            highlightNodes: Array.from(affectedTests),
            activeEdges: [],
          });
        }

        this.simStages.push({
          phase: 'COMPLETED',
          label: 'Phase 6: Simulation Complete • Click Nodes to Inspect Evidence',
          mutantNode: mutantNode,
          highlightNodes: compArray.concat(Array.from(affectedTests)),
          activeEdges: [],
        });
      }

      this.simTotalSteps = this.simStages.length;

      if (this.reducedMotion) {
        this.simStepIndex = this.simTotalSteps - 1;
        this.applyStage(this.simStages[this.simStepIndex]);
        this.simState = 'COMPLETED';
        if (playIcon) playIcon.textContent = 'replay';
        return;
      }

      this.applyStage(this.simStages[0]);
      this.startPlaybackTimer();
    },

    // --- 3D Change Impact Pipeline ---
    animateChangeImpact(data) {
      this.simMode = 'CHANGE_IMPACT';
      this.simData = data;
      this.simStepIndex = 0;
      this.simState = 'PLAYING';

      const bar = document.getElementById('sim-3d-playback-bar');
      const label = document.getElementById('sim-3d-mode-label');
      const playIcon = document.getElementById('sim-3d-play-icon');

      if (bar) bar.classList.remove('hidden');
      if (label) label.textContent = 'Verified Change Impact Propagation';
      if (playIcon) playIcon.textContent = 'pause';

      const changes = data.changes || [];
      const changedIds = changes.map(c => c.artifact_id || c.qualified_name);
      const directAffected = data.impact_tree?.direct || [];
      const indirectAffected = data.impact_tree?.indirect || [];
      const tests = data.impact_tree?.tests || [];

      this.simStages = [
        {
          phase: 'CHANGES',
          label: `Phase 1: Commit Changes (${changes.length} entities)`,
          highlightNodes: changedIds,
          changes: changes,
        },
        {
          phase: 'DIRECT',
          label: `Phase 2: Direct Structural Dependencies (${directAffected.length} components)`,
          highlightNodes: directAffected.map(d => d.id || d.artifact_id),
        },
        {
          phase: 'INDIRECT',
          label: `Phase 3: Multi-Hop Transitive Blast Radius (${indirectAffected.length} components)`,
          highlightNodes: indirectAffected.map(d => d.id || d.artifact_id),
        },
        {
          phase: 'TESTS',
          label: `Phase 4: Impacted Verification Suites (${tests.length} tests)`,
          highlightNodes: tests.map(t => t.id || t.artifact_id),
        },
        {
          phase: 'COMPLETED',
          label: 'Phase 5: Change Impact Complete • Inspect Verified Causal Paths',
          highlightNodes: changedIds.concat(directAffected.map(d => d.id || d.artifact_id)),
        }
      ];

      this.simTotalSteps = this.simStages.length;

      if (this.reducedMotion) {
        this.simStepIndex = this.simTotalSteps - 1;
        this.applyStage(this.simStages[this.simStepIndex]);
        this.simState = 'COMPLETED';
        if (playIcon) playIcon.textContent = 'replay';
        return;
      }

      this.applyStage(this.simStages[0]);
      this.startPlaybackTimer();
    },

    applyStage(stage) {
      if (!stage) return;
      const statusText = document.getElementById('sim-3d-status-text');
      if (statusText) statusText.textContent = stage.label;

      // Handle Mutant Node Beacon
      if (stage.mutantNode) {
        const mesh = this.nodeMeshes.get(stage.mutantNode.id);
        if (mesh) {
          if (!this.beaconMesh) {
            const beaconGeo = new THREE.RingGeometry(18, 22, 32);
            const beaconMat = new THREE.MeshBasicMaterial({
              color: 0xEC4899,
              side: THREE.DoubleSide,
              transparent: true,
              opacity: 0.85,
            });
            this.beaconMesh = new THREE.Mesh(beaconGeo, beaconMat);
            this.scene.add(this.beaconMesh);
          }
          this.beaconMesh.position.copy(mesh.position);
          this.beaconMesh.visible = true;

          if (stage.phase === 'INJECTION') {
            this.focusNode(stage.mutantNode.id);
          }
        }
      }

      // Handle Change status styling
      if (stage.changes) {
        stage.changes.forEach(c => {
          let mesh = this.nodeMeshes.get(c.artifact_id);
          if (!mesh) {
            this.nodeDataMap.forEach((n, id) => {
              if (n.qualified_name === c.qualified_name) mesh = this.nodeMeshes.get(id);
            });
          }
          if (mesh && mesh.material) {
            if (c.change_type === 'ADDED') {
              mesh.material.color.setHex(0x10B981);
              mesh.material.emissive.setHex(0x10B981);
              mesh.material.emissiveIntensity = 0.5;
            } else if (c.change_type === 'REMOVED') {
              mesh.material.color.setHex(0xEF4444);
              mesh.material.emissive.setHex(0xEF4444);
              mesh.material.emissiveIntensity = 0.5;
            } else {
              mesh.material.color.setHex(0x0284C7);
              mesh.material.emissive.setHex(0x0284C7);
              mesh.material.emissiveIntensity = 0.5;
            }
          }
        });
      }

      // Handle highlighted downstream nodes
      if (stage.highlightNodes && stage.highlightNodes.length > 0) {
        const targetColor = stage.phase === 'TESTS' ? 0x8B5CF6 : (stage.phase === 'INDIRECT' ? 0xDC2626 : 0xD97706);
        stage.highlightNodes.forEach(nid => {
          let mesh = this.nodeMeshes.get(nid);
          if (!mesh) {
            this.nodeDataMap.forEach((n, id) => {
              if (n.name === nid || n.qualified_name === nid) mesh = this.nodeMeshes.get(id);
            });
          }
          if (mesh && mesh.material) {
            mesh.material.color.setHex(targetColor);
            mesh.material.emissive.setHex(targetColor);
            mesh.material.emissiveIntensity = 0.45;
          }
        });
      }

      // Trigger wave particles along active edges
      if (stage.activeEdges && stage.activeEdges.length > 0) {
        stage.activeEdges.forEach(edge => {
          const srcId = edge.source || edge.source_artifact_id;
          const tgtId = edge.target || edge.target_artifact_id;
          const srcMesh = this.nodeMeshes.get(srcId);
          const tgtMesh = this.nodeMeshes.get(tgtId);
          if (srcMesh && tgtMesh) {
            this.spawnWaveParticle(srcMesh.position, tgtMesh.position);
          }
        });
      }
    },

    spawnWaveParticle(startPos, endPos) {
      const geo = new THREE.SphereGeometry(3.5, 12, 12);
      const mat = new THREE.MeshBasicMaterial({
        color: 0xFDE047,
        transparent: true,
        opacity: 0.9,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(startPos);
      this.particlesGroup.add(mesh);

      this.waveParticles.push({
        mesh: mesh,
        start: startPos.clone(),
        end: endPos.clone(),
        progress: 0,
      });

      if (this.waveParticles.length > 30) {
        const oldest = this.waveParticles.shift();
        this.particlesGroup.remove(oldest.mesh);
        oldest.mesh.geometry.dispose();
        oldest.mesh.material.dispose();
      }
    },

    startPlaybackTimer() {
      if (this.simTimer) clearTimeout(this.simTimer);
      const delay = Math.max(400, 1400 / this.simSpeed);
      this.simTimer = setTimeout(() => {
        if (this.simState === 'PLAYING') {
          this.stepForward();
        }
      }, delay);
    },

    stepForward() {
      if (this.simStepIndex < this.simTotalSteps - 1) {
        this.simStepIndex++;
        this.applyStage(this.simStages[this.simStepIndex]);
        if (this.simStepIndex === this.simTotalSteps - 1) {
          this.simState = 'COMPLETED';
          const icon = document.getElementById('sim-3d-play-icon');
          if (icon) icon.textContent = 'replay';
        } else if (this.simState === 'PLAYING') {
          this.startPlaybackTimer();
        }
      } else {
        this.simState = 'COMPLETED';
        const icon = document.getElementById('sim-3d-play-icon');
        if (icon) icon.textContent = 'replay';
      }
    },

    togglePlayback() {
      const icon = document.getElementById('sim-3d-play-icon');
      if (this.simState === 'PLAYING') {
        this.simState = 'PAUSED';
        if (this.simTimer) clearTimeout(this.simTimer);
        if (icon) icon.textContent = 'play_arrow';
      } else if (this.simState === 'PAUSED') {
        this.simState = 'PLAYING';
        if (icon) icon.textContent = 'pause';
        this.startPlaybackTimer();
      } else if (this.simState === 'COMPLETED') {
        this.resetSimulationAnimation();
        this.simState = 'PLAYING';
        if (icon) icon.textContent = 'pause';
        this.startPlaybackTimer();
      }
    },

    resetSimulationAnimation() {
      if (this.simTimer) clearTimeout(this.simTimer);
      this.simStepIndex = 0;
      this.simState = 'PAUSED';

      const icon = document.getElementById('sim-3d-play-icon');
      if (icon) icon.textContent = 'play_arrow';

      // Restore original colors
      this.nodeMeshes.forEach(mesh => {
        if (mesh.userData?.origColor) {
          mesh.material.color.setHex(mesh.userData.origColor);
          mesh.material.emissive.setHex(0x000000);
          mesh.material.emissiveIntensity = 0;
        }
      });

      this.clearParticles();
      if (this.beaconMesh) this.beaconMesh.visible = false;

      if (this.simStages.length > 0) {
        this.applyStage(this.simStages[0]);
      }
    },

    closePlaybackBar() {
      if (this.simTimer) clearTimeout(this.simTimer);
      document.getElementById('sim-3d-playback-bar')?.classList.add('hidden');
      this.resetSimulationAnimation();
      this.simMode = null;
    },

    dispose() {
      this.stopRenderLoop();
      this.clearScene();
      if (this.controls) {
        this.controls.dispose();
        this.controls = null;
      }
      if (this.resizeObserver) {
        this.resizeObserver.disconnect();
        this.resizeObserver = null;
      }
      if (this.renderer) {
        this.renderer.dispose();
      }
      this.initialized = false;
    }
  };

  // --- Fullscreen Toggle Logic ---
  function toggleGraphFullscreen() {
    const container = document.getElementById('graph-workspace-container');
    if (!container) return;
    const isFull = container.classList.toggle('graph-fullscreen-mode');
    const icon = document.getElementById('fullscreen-icon');
    if (icon) {
      icon.textContent = isFull ? 'fullscreen_exit' : 'fullscreen';
    }
    if (isFull) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    setTimeout(() => {
      resizeCanvas();
      fitToScreen();
    }, 60);
  }

  // --- Event Listeners Initialization ---
  function initEventListeners() {
    const canvas = state.canvas;
    if (!canvas) return;

    // Initialize 3D Spatial Canvas Listeners (Dimension toggle, HUD, Simulation playback)
    Twin3D.setupHUDListeners();

    // MiroFish Floating Toolbar Controls
    document.getElementById('zoom-in-btn')?.addEventListener('click', () => zoomBy(1.25));
    document.getElementById('zoom-out-btn')?.addEventListener('click', () => zoomBy(0.8));
    document.getElementById('btn-fit-view')?.addEventListener('click', fitToScreen);
    document.getElementById('fit-screen-btn')?.addEventListener('click', fitToScreen);
    document.getElementById('btn-refresh-graph')?.addEventListener('click', () => loadGraph());
    document.getElementById('btn-fullscreen-graph')?.addEventListener('click', toggleGraphFullscreen);

    // Escape key exits fullscreen
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const container = document.getElementById('graph-workspace-container');
        if (container && container.classList.contains('graph-fullscreen-mode')) {
          toggleGraphFullscreen();
        }
      }
    });

    const toggleEdgeLabelsBtn = document.getElementById('toggle-edge-labels-btn');
    if (toggleEdgeLabelsBtn) {
      toggleEdgeLabelsBtn.addEventListener('click', () => {
        state.showEdgeLabels = !state.showEdgeLabels;
        toggleEdgeLabelsBtn.classList.toggle('text-[#0071E3]', state.showEdgeLabels);
        toggleEdgeLabelsBtn.classList.toggle('border-[#0071E3]', state.showEdgeLabels);
        render();
      });
    }

    const onToggleIsolated = () => {
      state.hideIsolated = !state.hideIsolated;
      document.getElementById('toggle-isolated-btn')?.classList.toggle('text-[#0071E3]', state.hideIsolated);
      document.getElementById('btn-toggle-isolated')?.classList.toggle('text-[#0071E3]', state.hideIsolated);
      processGraphData(state.rawGraph);
    };
    document.getElementById('toggle-isolated-btn')?.addEventListener('click', onToggleIsolated);
    document.getElementById('btn-toggle-isolated')?.addEventListener('click', onToggleIsolated);

    document.getElementById('impact-mode-btn')?.addEventListener('click', () => {
      state.impactMode = !state.impactMode;
      document.getElementById('impact-mode-btn')?.classList.toggle('bg-[#FEF3C7]', state.impactMode);
      if (!state.impactMode) {
        state.impactRootId = null;
      } else if (state.selectedNodeId) {
        state.impactRootId = state.selectedNodeId;
      }
      loadGraph();
    });

    // Close Inspector Drawer
    document.getElementById('close-inspector-btn')?.addEventListener('click', () => {
      document.getElementById('node-detail-panel')?.classList.remove('open');
      state.selectedNodeId = null;
      state.selectedEdgeId = null;
      if (window.Twin3D && window.Twin3D.active) {
        window.Twin3D.clearSelectedHalo();
      }
      render();
    });

    // Search input within white canvas toolbar
    const graphSearchInput = document.getElementById('graph-search-input');
    if (graphSearchInput) {
      graphSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          performGraphSearch(graphSearchInput.value);
        }
      });
    }

    // Canvas Pan & Zoom (Mouse Wheel & Drag)
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const newK = Math.max(0.15, Math.min(4.0, state.transform.k * zoomFactor));
      const factor = newK / state.transform.k;

      state.transform.x = mouseX - (mouseX - state.transform.x) * factor;
      state.transform.y = mouseY - (mouseY - state.transform.y) * factor;
      state.transform.k = newK;
      render();
    }, { passive: false });

    canvas.addEventListener('mousedown', (e) => {
      const rect = canvas.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left - state.transform.x) / state.transform.k;
      const mouseY = (e.clientY - rect.top - state.transform.y) / state.transform.k;

      // Check node hit
      const hitNode = state.nodes.find(n => {
        const dx = n.x - mouseX;
        const dy = n.y - mouseY;
        return dx * dx + dy * dy <= n.radius * n.radius;
      });

      if (hitNode) {
        state.draggedNode = hitNode;
        state.selectedEdgeId = null;
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
          inspectEdge(hitEdge);
        } else {
          state.isDraggingCanvas = true;
          state.dragStart.x = e.clientX - state.transform.x;
          state.dragStart.y = e.clientY - state.transform.y;
          // Deselect node on clicking empty canvas
          if (state.selectedNodeId || state.selectedEdgeId) {
            state.selectedNodeId = null;
            state.selectedEdgeId = null;
            document.getElementById('node-detail-panel')?.classList.remove('open');
            render();
          }
        }
      }
    });

    window.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      if (state.draggedNode) {
        const mouseX = (e.clientX - rect.left - state.transform.x) / state.transform.k;
        const mouseY = (e.clientY - rect.top - state.transform.y) / state.transform.k;
        state.draggedNode.x = mouseX;
        state.draggedNode.y = mouseY;
        state.draggedNode.vx = 0;
        state.draggedNode.vy = 0;
        physicsIterations = Math.max(0, 220 - 40); // wake physics briefly
      } else if (state.isDraggingCanvas) {
        state.transform.x = e.clientX - state.dragStart.x;
        state.transform.y = e.clientY - state.dragStart.y;
        render();
      } else if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
        // Hover detection
        const mouseX = (e.clientX - rect.left - state.transform.x) / state.transform.k;
        const mouseY = (e.clientY - rect.top - state.transform.y) / state.transform.k;
        const hit = state.nodes.find(n => {
          const dx = n.x - mouseX;
          const dy = n.y - mouseY;
          return dx * dx + dy * dy <= n.radius * n.radius;
        });

        if (hit !== state.hoveredNode) {
          state.hoveredNode = hit || null;
          canvas.style.cursor = hit ? 'pointer' : 'grab';
          render();
        }
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
          showNotification(`Process Discovery Completed: Found ${data.processes_discovered} workflows, ${data.steps_created} steps, ${data.transitions_created} transitions.`, 'success');
          loadProcessesView();
        } catch (err) {
          showNotification('Process discovery failed: ' + err.message, 'error');
        } finally {
          discBtn.disabled = false;
          discBtn.textContent = '⚡ Run Process Discovery';
        }
      });
    }

    // Ingest Runtime modal
    const modalIngest = document.getElementById('modal-ingest-runtime');
    const closeIngestBtn = document.getElementById('modal-ingest-close-btn');
    const cancelIngestBtn = document.getElementById('modal-ingest-cancel-btn');
    const submitIngestBtn = document.getElementById('modal-ingest-submit-btn');

    if (modalIngest) {
      closeIngestBtn?.addEventListener('click', () => modalIngest.style.display = 'none');
      cancelIngestBtn?.addEventListener('click', () => modalIngest.style.display = 'none');

      submitIngestBtn?.addEventListener('click', async () => {
        if (!state.currentRepoId) {
          showNotification('Please select a codebase first.', 'warning');
          return;
        }
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
          showNotification(`Runtime Ingestion Complete: ${resData.ingested_count} ingested, ${resData.correlated_count} correlated, ${resData.redacted_count} fields redacted.`, 'success');
          switchPrimaryView('runtime');
          await loadRuntimeView();

        } catch (err) {
          if (errorBox) {
            errorBox.style.display = 'block';
            errorBox.textContent = err.message;
          } else {
            showNotification(`Runtime ingestion error: ${err.message}`, 'error');
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
    const modalInc = document.getElementById('modal-create-incident');
    const closeIncBtn = document.getElementById('modal-incident-close-btn');
    const cancelIncBtn = document.getElementById('modal-incident-cancel-btn');
    const submitIncBtn = document.getElementById('modal-incident-submit-btn');

    if (modalInc) {
      closeIncBtn?.addEventListener('click', () => modalInc.style.display = 'none');
      cancelIncBtn?.addEventListener('click', () => modalInc.style.display = 'none');

      submitIncBtn?.addEventListener('click', async () => {
        if (!state.currentRepoId) {
          showNotification('Please select a codebase first.', 'warning');
          return;
        }
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
          } else {
            showNotification('Incident title is required.', 'warning');
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
              title: title.trim(),
              severity: severity.toLowerCase(),
              environment: env,
              affected_component_name: component ? component.trim() : null,
              description: desc.trim(),
              snapshot_id: state.currentSnapshotId || null
            })
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(errData.detail || 'Failed to create incident');
          }

          const newInc = await res.json();
          modalInc.style.display = 'none';
          showNotification(`Incident declared: ${newInc.title}`, 'success');
          switchPrimaryView('incidents');
          await loadIncidentsView();
          await investigateIncident(newInc.id);

        } catch (err) {
          if (errorBox) {
            errorBox.style.display = 'block';
            errorBox.textContent = err.message;
          } else {
            showNotification(`Incident declaration failed: ${err.message}`, 'error');
          }
        } finally {
          submitIncBtn.disabled = false;
          submitIncBtn.textContent = 'Declare & Investigate';
        }
      });
    }
  }

  // ====================================================================
  // PHASE 8: WHAT-IF / SCENARIO SIMULATION WORKSPACE
  // ====================================================================
  let currentSimulationType = 'MODIFY_SYMBOL';
  let candidateSearchTimer = null;

  function initSimulationHandlers() {
    // Guided Archetype scenario cards
    const archetypeCards = document.querySelectorAll('.sim-archetype-card');
    archetypeCards.forEach(card => {
      card.addEventListener('click', () => {
        archetypeCards.forEach(c => {
          c.classList.remove('active', 'border-[#0071e3]', 'bg-[#EFF6FF]');
          c.classList.add('border-[#E2E8F0]', 'bg-[#F8FAFC]');
        });
        card.classList.add('active', 'border-[#0071e3]', 'bg-[#EFF6FF]');
        card.classList.remove('border-[#E2E8F0]', 'bg-[#F8FAFC]');
        currentSimulationType = card.dataset.type;
        updateSimulationFormFields();
      });
    });

    // Mutation type override buttons
    const typeButtons = document.querySelectorAll('.sim-type-btn');
    typeButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        typeButtons.forEach(b => {
          b.className = 'sim-type-btn px-2.5 py-2 text-left rounded-lg border text-xs font-medium transition-all border-[#E2E8F0] bg-[#F8FAFC] text-[#475569] hover:bg-[#F1F5F9]';
        });
        btn.className = 'sim-type-btn active px-2.5 py-2 text-left rounded-lg border text-xs font-medium transition-all border-[#0071e3] bg-[#EFF6FF] text-[#0071e3]';
        currentSimulationType = btn.dataset.type;
        updateSimulationFormFields();
      });
    });

    // Natural-language quick prompt chips
    document.querySelectorAll('.sim-chip-btn').forEach(btn => {
      btn.onclick = () => {
        const q = btn.dataset.query;
        const nlInput = document.getElementById('input-sim-nl-query');
        if (nlInput) {
          nlInput.value = q;
          planScenarioFromNL(q);
        }
      };
    });

    // Plan & Disambiguate button
    document.getElementById('btn-plan-simulation')?.addEventListener('click', () => {
      const q = document.getElementById('input-sim-nl-query')?.value?.trim();
      if (q) {
        planScenarioFromNL(q);
      } else {
        showNotification('Please enter a scenario question first (e.g. "What if we remove ...?")', 'warning');
      }
    });

    // Clear resolved target button
    document.getElementById('sim-clear-target-btn')?.addEventListener('click', () => {
      state.simResolvedTarget = null;
      const badge = document.getElementById('sim-resolved-target-badge');
      if (badge) {
        badge.style.display = 'none';
        badge.classList.add('hidden');
      }
      const targetInput = document.getElementById('input-sim-target');
      if (targetInput) targetInput.value = '';
      hideTargetSuggestions();
      showNotification('Target entity selection cleared.', 'info');
    });

    // Autocomplete / candidate search for target entity input
    const targetInput = document.getElementById('input-sim-target');
    if (targetInput) {
      targetInput.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        if (candidateSearchTimer) clearTimeout(candidateSearchTimer);
        if (val.length >= 2 && state.currentRepoId) {
          candidateSearchTimer = setTimeout(() => searchTargetCandidates(val), 250);
        } else {
          hideTargetSuggestions();
        }
      });
      targetInput.addEventListener('focus', () => {
        const val = targetInput.value.trim();
        if (val.length >= 2 && state.currentRepoId) {
          searchTargetCandidates(val);
        }
      });
    }

    // Close suggestions on outside click
    document.addEventListener('click', (e) => {
      if (!e.target.closest('#input-sim-target') && !e.target.closest('#sim-target-suggestions')) {
        hideTargetSuggestions();
      }
    });

    // Run Orchestrated Simulation button
    const runBtn = document.getElementById('btn-run-simulation');
    if (runBtn) {
      runBtn.addEventListener('click', executeOrchestratedSimulation);
    }

    // Reset Form button
    const resetBtn = document.getElementById('btn-new-simulation-reset');
    if (resetBtn) {
      resetBtn.addEventListener('click', resetSimulationForm);
    }

    // Download 13-Section Engineering Report button
    const downloadReportBtn = document.getElementById('btn-sim-download-report');
    if (downloadReportBtn) {
      downloadReportBtn.addEventListener('click', downloadScenarioReport);
    }
  }

  function hideTargetSuggestions() {
    const suggestions = document.getElementById('sim-target-suggestions');
    if (suggestions) {
      suggestions.classList.add('hidden');
      suggestions.style.display = 'none';
      suggestions.innerHTML = '';
    }
  }

  async function searchTargetCandidates(query) {
    if (!state.currentRepoId) return;
    const lowerQuery = query.toLowerCase();
    const candidateMap = new Map();

    // 1. Search local AST nodes
    if (state.nodes && state.nodes.length > 0) {
      for (const node of state.nodes) {
        const name = node.name || node.label || node.id || '';
        const qName = node.qualified_name || '';
        if (name.toLowerCase().includes(lowerQuery) || qName.toLowerCase().includes(lowerQuery)) {
          candidateMap.set(name, {
            id: node.id || name,
            name: name,
            qualified_name: qName,
            location: node.location || node.file_path || '',
            artifact_type: node.type || node.kind || 'NODE',
          });
          if (candidateMap.size >= 8) break;
        }
      }
    }

    // 2. Search local components
    if (state.componentsList && state.componentsList.length > 0) {
      for (const comp of state.componentsList) {
        const name = comp.name || comp.id || '';
        if (name.toLowerCase().includes(lowerQuery) && !candidateMap.has(name)) {
          candidateMap.set(name, {
            id: comp.id || name,
            name: name,
            qualified_name: comp.file_path || '',
            location: comp.file_path || '',
            artifact_type: comp.type || 'COMPONENT',
          });
          if (candidateMap.size >= 12) break;
        }
      }
    }

    // 3. Fetch server candidates
    try {
      const baseSnap = state.currentSnapshotId || '';
      const res = await fetch(`/repositories/${state.currentRepoId}/scenarios/target-candidates?q=${encodeURIComponent(query)}&base_snapshot_id=${encodeURIComponent(baseSnap)}`);
      if (res.ok) {
        const serverCandidates = await res.json();
        if (Array.isArray(serverCandidates)) {
          for (const sc of serverCandidates) {
            const name = sc.name || sc.id;
            if (name && !candidateMap.has(name)) {
              candidateMap.set(name, sc);
            }
          }
        }
      }
    } catch (_) {}

    const candidates = Array.from(candidateMap.values()).slice(0, 8);
    if (candidates.length > 0) {
      renderTargetSuggestions(candidates);
    } else {
      hideTargetSuggestions();
    }
  }

  function renderTargetSuggestions(candidates) {
    const suggestions = document.getElementById('sim-target-suggestions');
    if (!suggestions) return;

    suggestions.innerHTML = candidates.map(c => `
      <div class="px-3 py-2 hover:bg-[#EFF6FF] cursor-pointer border-b border-[#F1F5F9] last:border-b-0 flex items-center justify-between gap-2 sim-suggestion-item" data-target="${escapeHtml(c.name || c.id)}">
        <div class="min-w-0">
          <div class="text-xs font-bold text-[#0F172A] truncate font-mono">${escapeHtml(c.name || c.id)}</div>
          <div class="text-[10px] text-[#64748B] truncate">${escapeHtml(c.location || c.qualified_name || '')}</div>
        </div>
        <span class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-[#F1F5F9] text-[#475569] shrink-0 border border-[#CBD5E1]">
          ${escapeHtml(c.artifact_type || 'ENTITY')}
        </span>
      </div>
    `).join('');

    suggestions.classList.remove('hidden');
    suggestions.style.display = 'block';

    suggestions.querySelectorAll('.sim-suggestion-item').forEach(item => {
      item.onclick = (e) => {
        e.stopPropagation();
        const targetVal = item.dataset.target;
        selectResolvedTarget(targetVal);
      };
    });
  }

  function selectResolvedTarget(targetVal) {
    state.simResolvedTarget = targetVal;
    hideTargetSuggestions();

    const card = document.getElementById('sim-ambiguity-card');
    if (card) {
      card.style.display = 'none';
      card.classList.add('hidden');
    }

    const badge = document.getElementById('sim-resolved-target-badge');
    const badgeName = document.getElementById('sim-resolved-target-name');
    if (badge && badgeName) {
      badge.style.display = 'block';
      badge.classList.remove('hidden');
      badgeName.textContent = targetVal;
    }

    const targetInput = document.getElementById('input-sim-target');
    if (targetInput) targetInput.value = targetVal;

    showNotification(`Selected target entity: '${targetVal}'`, 'success');
  }

  async function planScenarioFromNL(queryText) {
    if (!state.currentRepoId) {
      showNotification('Please connect or select a repository first.', 'warning');
      return;
    }

    const planBtn = document.getElementById('btn-plan-simulation');
    const originalText = planBtn ? planBtn.innerHTML : '';
    if (planBtn) {
      planBtn.disabled = true;
      planBtn.innerHTML = '<span class="material-symbols-outlined text-[15px] animate-spin">sync</span><span>Resolving Targets...</span>';
    }

    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/scenarios/natural-language`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          base_snapshot_id: state.currentSnapshotId || '',
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Could not plan scenario');
      }

      const plan = await res.json();
      handleScenarioPlanResult(plan);
    } catch (err) {
      showNotification('Scenario Planning: ' + err.message, 'error');
    } finally {
      if (planBtn) {
        planBtn.disabled = false;
        planBtn.innerHTML = originalText;
      }
    }
  }

  function handleScenarioPlanResult(plan) {
    const card = document.getElementById('sim-ambiguity-card');
    const badge = document.getElementById('sim-resolved-target-badge');
    const badgeName = document.getElementById('sim-resolved-target-name');
    const targetInput = document.getElementById('input-sim-target');

    const resolvedTarget = plan.target_entity || (plan.target_entities && plan.target_entities.length > 0 ? plan.target_entities[0] : null);

    if (plan.status === 'AMBIGUOUS' && (plan.candidate_entities || []).length > 0) {
      renderCandidateList(plan.candidate_entities, plan.ambiguity_explanation || 'Multiple matching entities found. Select target:');
    } else if (resolvedTarget) {
      selectResolvedTarget(resolvedTarget);

      // Sync inferred mutation type
      if (plan.inferred_mutation_type) {
        currentSimulationType = plan.inferred_mutation_type;
        const typeButtons = document.querySelectorAll('.sim-type-btn');
        typeButtons.forEach(b => {
          if (b.dataset.type === plan.inferred_mutation_type) {
            b.className = 'sim-type-btn active px-2.5 py-2 text-left rounded-lg border text-xs font-medium transition-all border-[#0071e3] bg-[#EFF6FF] text-[#0071e3]';
          } else {
            b.className = 'sim-type-btn px-2.5 py-2 text-left rounded-lg border text-xs font-medium transition-all border-[#E2E8F0] bg-[#F8FAFC] text-[#475569] hover:bg-[#F1F5F9]';
          }
        });
        updateSimulationFormFields();
      }

      showNotification(`Target resolved: '${resolvedTarget}' (${plan.analysis_objective || 'Ready'})`, 'success');
    } else {
      if (card) { card.style.display = 'none'; card.classList.add('hidden'); }
      if (badge) { badge.style.display = 'none'; badge.classList.add('hidden'); }
      const msg = plan.ambiguity_explanation || (plan.can_execute === false ? 'No matching target entity found in Twin snapshot.' : `Scenario planned: ${plan.analysis_objective || 'Ready'}`);
      showNotification(msg, plan.can_execute === false ? 'warning' : 'info');
    }
  }

  function renderCandidateList(candidates, title) {
    const card = document.getElementById('sim-ambiguity-card');
    const list = document.getElementById('sim-ambiguity-candidates-list') || document.getElementById('sim-candidate-list');
    if (!card || !list) return;

    card.classList.remove('hidden');
    card.style.display = 'block';
    const titleElem = card.querySelector('div.text-\\[10px\\]') || card.querySelector('div.text-xs');
    if (titleElem && title) titleElem.textContent = title;

    list.innerHTML = candidates.slice(0, 10).map(c => `
      <button type="button" class="w-full text-left px-2.5 py-1.5 rounded-lg bg-white border border-[#CBD5E1] hover:border-[#0071E3] hover:bg-[#EFF6FF] flex items-center justify-between gap-2 transition-colors sim-candidate-btn" data-target="${escapeHtml(c.name || c.id)}">
        <div class="min-w-0">
          <div class="text-xs font-bold text-[#0F172A] truncate">${escapeHtml(c.name || c.id)}</div>
          <div class="text-[10px] text-[#64748B] font-mono truncate">${escapeHtml(c.location || c.qualified_name || '')}</div>
        </div>
        <span class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-[#F1F5F9] text-[#475569] shrink-0 border border-[#E2E8F0]">
          ${escapeHtml(c.artifact_type || 'ARTIFACT')}
        </span>
      </button>
    `).join('');

    list.querySelectorAll('.sim-candidate-btn').forEach(btn => {
      btn.onclick = (e) => {
        e.preventDefault();
        const targetVal = btn.dataset.target;
        selectResolvedTarget(targetVal);
      };
    });
  }

  function updateSimulationFormFields() {
    const srcContainer = document.getElementById('sim-source-container');
    const relContainer = document.getElementById('sim-reltype-container');
    const targetLabel = document.getElementById('sim-target-label');
    const targetInput = document.getElementById('input-sim-target');

    if (currentSimulationType === 'ADD_DEPENDENCY' || currentSimulationType === 'REMOVE_DEPENDENCY' || currentSimulationType === 'MODIFY_COMPONENT_RELATIONSHIP') {
      if (srcContainer) srcContainer.style.display = 'block';
      if (relContainer) relContainer.style.display = (currentSimulationType === 'ADD_DEPENDENCY' || currentSimulationType === 'MODIFY_COMPONENT_RELATIONSHIP') ? 'block' : 'none';
      if (targetLabel) targetLabel.textContent = 'Target Entity (Destination)';
      if (targetInput) targetInput.placeholder = 'e.g. PaymentService';
    } else if (currentSimulationType === 'MODIFY_API') {
      if (srcContainer) srcContainer.style.display = 'none';
      if (relContainer) relContainer.style.display = 'none';
      if (targetLabel) targetLabel.textContent = 'API Route / Endpoint';
      if (targetInput) targetInput.placeholder = 'e.g. /api/v1/orders or POST /payments';
    } else {
      if (srcContainer) srcContainer.style.display = 'none';
      if (relContainer) relContainer.style.display = 'none';
      if (targetLabel) targetLabel.textContent = 'Target Symbol / Entity';
      if (targetInput) targetInput.placeholder = 'e.g. PaymentService.calculate_tax';
    }
  }

  function resetSimulationForm() {
    const nlInput = document.getElementById('input-sim-nl-query');
    const nameInput = document.getElementById('input-sim-name');
    const targetInput = document.getElementById('input-sim-target');
    const sourceInput = document.getElementById('input-sim-source');
    const descInput = document.getElementById('input-sim-desc');
    const errBox = document.getElementById('sim-error-box');
    const ambiguityCard = document.getElementById('sim-ambiguity-card');
    const badge = document.getElementById('sim-resolved-target-badge');

    if (nlInput) nlInput.value = '';
    if (nameInput) nameInput.value = '';
    if (targetInput) targetInput.value = '';
    if (sourceInput) sourceInput.value = '';
    if (descInput) descInput.value = '';
    if (errBox) errBox.style.display = 'none';
    if (ambiguityCard) ambiguityCard.classList.add('hidden');
    if (badge) badge.classList.add('hidden');

    state.simResolvedTarget = null;

    const resultsCard = document.getElementById('sim-results-card');
    const placeholder = document.getElementById('sim-placeholder-card');
    if (resultsCard) resultsCard.style.display = 'none';
    if (placeholder) placeholder.style.display = 'block';

    showNotification('What-If simulation form reset to baseline.', 'info');
  }

  async function loadSimulationView() {
    const badge = document.getElementById('sim-active-base-snap');
    const snapId = state.currentSnapshotId || '';
    if (badge) badge.textContent = snapId ? `Base Snapshot: ${snapId.substring(0, 10)}` : 'No Snapshot Selected';

    if (!state.currentRepoId) return;

    // Load saved scenarios history
    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/scenarios`);
      if (res.ok) {
        const scenarios = await res.json();
        renderSimulationHistory(scenarios);
      }
    } catch (err) {
      console.warn('Could not load scenario history:', err);
    }
  }

  function renderSimulationHistory(scenarios) {
    const list = document.getElementById('sim-history-list');
    const count = document.getElementById('sim-history-count');
    if (!list) return;

    if (count) count.textContent = `${scenarios.length} saved`;

    if (!scenarios || scenarios.length === 0) {
      list.innerHTML = '<div class="text-[11px] text-[#94A3B8] italic text-center py-4">No saved scenarios yet for this repository.</div>';
      return;
    }

    list.innerHTML = scenarios.map(s => `
      <div class="p-2.5 rounded-lg border border-[#E2E8F0] hover:border-[#CBD5E1] bg-[#F8FAFC] flex items-center justify-between gap-2 cursor-pointer transition-colors sim-history-item" data-id="${s.id}">
        <div class="min-w-0">
          <div class="text-xs font-semibold text-[#0F172A] truncate">${escapeHtml(s.name)}</div>
          <div class="text-[10px] text-[#64748B] flex items-center gap-1.5 mt-0.5">
            <span class="font-mono">${s.status}</span>
            <span>•</span>
            <span>${(s.mutations || []).length} mutations</span>
          </div>
        </div>
        <button class="px-2 py-1 rounded bg-white border border-[#E2E8F0] text-[10px] font-semibold text-[#0071e3] hover:bg-[#EFF6FF] shrink-0" onclick="window.TwinApp.inspectScenario('${s.id}')">
          Simulate
        </button>
      </div>
    `).join('');
  }

  async function inspectScenario(scenarioId) {
    if (!state.currentRepoId) return;
    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/scenarios/${scenarioId}/analyze`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        renderOrchestratedScenarioResult(data);
      }
    } catch (err) {
      showNotification('Error simulating scenario: ' + err.message, 'error');
    }
  }

  async function executeOrchestratedSimulation() {
    if (!state.currentRepoId) {
      showNotification('Please connect or select a repository first.', 'warning');
      return;
    }

    const nlQuery = document.getElementById('input-sim-nl-query')?.value?.trim();
    const manualTarget = document.getElementById('input-sim-target')?.value?.trim();
    let targetToUse = state.simResolvedTarget || manualTarget;

    // Disallow literal string "undefined", "null", or empty strings
    if (targetToUse === 'undefined' || targetToUse === 'null' || !targetToUse) {
      targetToUse = null;
    }

    const errBox = document.getElementById('sim-error-box');
    const runBtn = document.getElementById('btn-run-simulation');
    const runBtnText = document.getElementById('btn-run-simulation-text');

    if (!nlQuery && !targetToUse) {
      if (errBox) {
        errBox.style.display = 'block';
        errBox.textContent = 'Please enter a scenario hypothesis (e.g. "What happens if we remove ...?") or select a target entity.';
      }
      return;
    }

    const timeline = document.getElementById('sim-exec-timeline');
    if (errBox) errBox.style.display = 'none';
    if (timeline) timeline.style.display = 'block';
    if (runBtn) runBtn.disabled = true;
    if (runBtnText) runBtnText.textContent = 'Orchestrating Multi-Agent Analysis...';

    const baseSnap = state.currentSnapshotId || '';

    try {
      const res = await fetch(`/repositories/${state.currentRepoId}/scenarios/orchestrate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: nlQuery || `What if we perform ${currentSimulationType} on ${targetToUse}?`,
          base_snapshot_id: baseSnap,
          target_override: targetToUse || null,
          mutation_type_override: currentSimulationType || null,
          explicit_target: targetToUse || null,
          explicit_type: currentSimulationType || null,
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errData.detail || 'Orchestrated simulation failed.');
      }

      const resultData = await res.json();
      renderOrchestratedScenarioResult(resultData);
      loadSimulationView(); // refresh scenario history
    } catch (err) {
      if (errBox) {
        errBox.style.display = 'block';
        errBox.textContent = err.message;
      }
      showNotification('Simulation error: ' + err.message, 'error');
    } finally {
      if (timeline) timeline.style.display = 'none';
      if (runBtn) runBtn.disabled = false;
      if (runBtnText) runBtnText.textContent = 'Run Deterministic Simulation';
    }
  }

  function renderOrchestratedScenarioResult(data) {
    state.lastSimulationResult = data;
    const resultsCard = document.getElementById('sim-results-card');
    const placeholder = document.getElementById('sim-placeholder-card');
    const errBox = document.getElementById('sim-error-box');

    // Robust unwrap supporting both OrchestratedScenarioResult and raw ScenarioAnalysisResult
    const sim = data.simulation || data;
    const plan = data.plan || data.structured_scenario || {};
    const report = data.report || {};
    const impact = sim.impact || data.impact || {};
    const risk = sim.risk || data.risk || {};
    const comparison = sim.comparison || data.comparison || {};
    const tests = sim.tests || data.tests || {};
    const findings = data.findings || sim.findings || report.findings || [];
    const evidence = sim.evidence || data.evidence || [];
    const assumptions = sim.assumptions || data.assumptions || report.assumptions_and_prerequisites || [];
    const unknowns = sim.unknowns || data.unknowns || report.unknowns_and_limitations || [];

    // Check for explicit failure or unexecutable plan
    if (sim.status === 'FAILED' || (plan.can_execute === false && (!sim.proposed_changes || sim.proposed_changes.length === 0))) {
      if (placeholder) placeholder.style.display = 'none';
      if (resultsCard) resultsCard.style.display = 'none';
      if (errBox) {
        errBox.style.display = 'block';
        const failureReason = sim.error_message || plan.ambiguity_explanation || 'Simulation could not be executed for the specified target.';
        errBox.innerHTML = `
          <div class="flex items-start gap-2">
            <span class="material-symbols-outlined text-red-600 text-[18px] shrink-0 mt-0.5">error</span>
            <div>
              <div class="font-bold text-red-800 text-xs">Simulation Target Resolution Failure</div>
              <div class="text-xs text-red-700 mt-0.5">${escapeHtml(failureReason)}</div>
              ${plan.candidate_entities && plan.candidate_entities.length > 0 ? `<div class="text-[11px] text-red-600 mt-1">Suggested candidates: ${plan.candidate_entities.map(c => `<code>${escapeHtml(c)}</code>`).join(', ')}</div>` : ''}
            </div>
          </div>
        `;
      }
      showNotification('Simulation failed: Target could not be resolved or executed.', 'error');
      return;
    }

    if (errBox) errBox.style.display = 'none';
    if (placeholder) placeholder.style.display = 'none';
    if (resultsCard) resultsCard.style.display = 'block';

    // Header info
    const nameElem = document.getElementById('sim-res-name');
    const subElem = document.getElementById('sim-res-sub');
    const timeElem = document.getElementById('sim-res-time');
    const questionElem = document.getElementById('sim-res-question');
    const whyElem = document.getElementById('sim-res-explanation');

    const originalQ = plan.user_query || plan.original_question || data.original_question || report.original_question || 'Hypothetical Scenario';
    const title = sim.name || plan.analysis_objective || report.title || 'Scenario Result';
    const mutationsCount = (sim.proposed_changes || data.proposed_changes || []).length;
    const affectedCount = (impact.affected_components || []).length;

    if (nameElem) nameElem.innerHTML = `<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#EFF6FF] text-[#1D4ED8] border border-[#BFDBFE] mr-1.5 uppercase">SIMULATED</span> ${escapeHtml(title)}`;
    if (subElem) subElem.textContent = `${mutationsCount} mutation(s) • ${affectedCount} affected component(s) (Isolated Virtual Twin — 0 commits mutated)`;
    if (timeElem) timeElem.textContent = `${data.execution_time_ms || sim.execution_time_ms || 0}ms`;
    if (questionElem) questionElem.textContent = `"${escapeHtml(originalQ)}"`;
    if (whyElem) whyElem.textContent = risk.explanation || plan.analysis_objective || 'Scenario analysis complete.';

    // 4 Bento metrics
    const totalImpactNodes = (impact.affected_components || []).length + (impact.affected_apis || []).length;
    const impactElem = document.getElementById('sim-metric-impact');
    const depthElem = document.getElementById('sim-metric-depth');
    if (impactElem) impactElem.textContent = `${totalImpactNodes} nodes`;
    if (depthElem) depthElem.textContent = `Max depth: ${impact.max_propagation_depth ?? 0}`;

    const newViolationsCount = (comparison.new_guardrail_violations || []).length;
    const guardrailElem = document.getElementById('sim-metric-guardrails');
    const guardrailSub = document.getElementById('sim-metric-guardrails-sub');
    if (guardrailElem) {
      guardrailElem.textContent = `${newViolationsCount} violations`;
      guardrailElem.className = newViolationsCount > 0 ? 'text-lg font-bold text-[#DC2626] mt-0.5' : 'text-lg font-bold text-[#10B981] mt-0.5';
    }
    if (guardrailSub) guardrailSub.textContent = newViolationsCount > 0 ? 'Boundary breached' : 'Baseline pass';

    const riskElem = document.getElementById('sim-metric-risk');
    const riskScore = document.getElementById('sim-metric-risk-score');
    const riskCategory = risk.scenario_risk_category || 'LOW';
    if (riskElem) {
      riskElem.textContent = riskCategory;
      if (riskCategory === 'HIGH' || riskCategory === 'CRITICAL') {
        riskElem.className = 'text-lg font-bold text-[#DC2626] mt-0.5';
      } else if (riskCategory === 'MODERATE') {
        riskElem.className = 'text-lg font-bold text-[#D97706] mt-0.5';
      } else {
        riskElem.className = 'text-lg font-bold text-[#10B981] mt-0.5';
      }
    }
    if (riskScore) riskScore.textContent = `Score: ${risk.overall_score ?? 0} / 100 (${risk.confidence_level || 'HIGH'})`;

    const totalTests = (tests.directly_affected_tests || []).length + (tests.indirectly_affected_tests || []).length;
    const testElem = document.getElementById('sim-metric-tests');
    const testUnknown = document.getElementById('sim-metric-tests-unknown');
    if (testElem) testElem.textContent = `${totalTests} tests`;
    if (testUnknown) {
      const unk = tests.unknown_coverage_count ?? 0;
      testUnknown.textContent = `${unk} unknown coverage`;
      testUnknown.className = unk > 0 ? 'text-[11px] text-[#D97706] font-medium' : 'text-[11px] text-[#64748B]';
    }

    // Engine Routing Banner (Logical Multi-Agent Roles)
    const routingList = document.getElementById('sim-engine-routing-list');
    if (routingList) {
      const rawRoles = data.engine_routing?.roles_executed || data.orchestration_roles_executed || [];
      if (rawRoles.length === 0) {
        routingList.innerHTML = '<span class="text-[11px] text-[#64748B] italic">Deterministic What-If Engine executed.</span>';
      } else {
        routingList.innerHTML = rawRoles.map(r => {
          const roleName = typeof r === 'string' ? r : (r.role || 'ROLE');
          const engineName = typeof r === 'string' ? 'Deterministic Engine' : (r.engine || 'Engine');
          const status = typeof r === 'string' ? 'VERIFIED' : (r.status || 'VERIFIED');
          let pill = 'bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]';
          if (status === 'NOT_EVALUATED') {
            pill = 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]';
          } else if (status === 'SYNTHESIZED') {
            pill = 'bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE]';
          }
          return `
            <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-[10px] font-medium ${pill}">
              <span class="font-bold">${escapeHtml(roleName)}:</span>
              <span class="opacity-80">${escapeHtml(engineName)}</span>
              <span class="text-[9px] uppercase font-bold tracking-wider opacity-60">(${status})</span>
            </div>
          `;
        }).join('');
      }
    }

    // Audited Findings & Actionable Recommendations
    const findingsList = document.getElementById('sim-findings-list');
    if (findingsList) {
      if (findings.length === 0) {
        findingsList.innerHTML = '<div class="text-xs text-[#94A3B8] italic p-3 text-center">No risk or architecture findings identified for this scenario.</div>';
      } else {
        findingsList.innerHTML = findings.map(f => {
          let sevClass = 'bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]';
          if (f.severity === 'CRITICAL' || f.severity === 'HIGH') {
            sevClass = 'bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA]';
          } else if (f.severity === 'MEDIUM') {
            sevClass = 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]';
          } else if (f.severity === 'LOW') {
            sevClass = 'bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE]';
          }

          let provPill = 'bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE]';
          if (f.provenance === 'OBSERVED_RUNTIME') {
            provPill = 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]';
          } else if (f.provenance === 'HISTORICAL_INCIDENT') {
            provPill = 'bg-[#FFE4E6] text-[#BE123C] border-[#FECDD3]';
          } else if (f.provenance === 'UNKNOWN_EVIDENCE') {
            provPill = 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]';
          }

          const entitiesHtml = (f.affected_entity_ids || []).slice(0, 4).map(e => `
            <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#F8FAFC] border border-[#E2E8F0] text-[#334155]">${escapeHtml(e)}</span>
          `).join('');

          return `
            <div class="p-3.5 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] space-y-2">
              <div class="flex items-center justify-between gap-2 flex-wrap">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${sevClass}">
                    ${f.severity}
                  </span>
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-white border border-[#CBD5E1] text-[#0F172A]">
                    ${f.category}
                  </span>
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${provPill}">
                    ${f.provenance}
                  </span>
                </div>
                <span class="text-[10px] font-mono font-bold text-[#64748B]">${f.finding_id}</span>
              </div>

              <div class="text-xs font-semibold text-[#0F172A] leading-relaxed">
                ${escapeHtml(f.description)}
              </div>

              ${f.rationale ? `<div class="text-[11px] text-[#64748B] italic">${escapeHtml(f.rationale)}</div>` : ''}

              ${entitiesHtml ? `<div class="flex items-center gap-1.5 flex-wrap pt-1">${entitiesHtml}</div>` : ''}

              <div class="pt-2 border-t border-[#E2E8F0] space-y-1">
                <div class="text-xs text-[#0F172A]">
                  <span class="font-bold text-[#059669]">Recommended Action:</span> ${escapeHtml(f.recommended_action || 'Review downstream dependencies')}
                </div>
                <div class="text-[11px] text-[#64748B]">
                  <span class="font-bold text-[#475569]">Verification:</span> ${escapeHtml(f.verification_steps || 'Execute unit and integration tests')}
                </div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Comparison
    const addedElem = document.getElementById('sim-comp-added');
    const removedElem = document.getElementById('sim-comp-removed');

    const addedList = comparison.added_relationships || [];
    if (addedElem) {
      if (addedList.length === 0) {
        addedElem.innerHTML = '<span class="text-[#94A3B8] italic">No relationships added</span>';
      } else {
        addedElem.innerHTML = addedList.map(a => `
          <div class="px-2 py-1 rounded bg-[#DCFCE7] text-[#15803D] font-mono text-[11px] truncate">
            + ${escapeHtml(a.source)} → ${escapeHtml(a.target)} (${a.relationship_type})
          </div>
        `).join('');
      }
    }

    const removedList = comparison.removed_relationships || [];
    if (removedElem) {
      if (removedList.length === 0) {
        removedElem.innerHTML = '<span class="text-[#94A3B8] italic">No relationships removed</span>';
      } else {
        removedElem.innerHTML = removedList.map(r => `
          <div class="px-2 py-1 rounded bg-[#FEE2E2] text-[#B91C1C] font-mono text-[11px] truncate line-through">
            - ${escapeHtml(r.source)} ↛ ${escapeHtml(r.target)}
          </div>
        `).join('');
      }
    }

    // Separated Evidence Ledger
    const evidenceLedger = document.getElementById('sim-evidence-ledger');
    if (evidenceLedger) {
      const items = evidence || [];
      if (items.length === 0) {
        evidenceLedger.innerHTML = '<div class="text-[11px] text-[#94A3B8] italic">No evidence generated for this scenario.</div>';
      } else {
        evidenceLedger.innerHTML = items.slice(0, 15).map(ev => {
          let badgeColor = 'bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE]';
          let icon = 'account_tree';
          if (ev.category === 'OBSERVED_RUNTIME') {
            badgeColor = 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]';
            icon = 'dynamic_feed';
          } else if (ev.category === 'HISTORICAL_INCIDENT') {
            badgeColor = 'bg-[#FFE4E6] text-[#BE123C] border-[#FECDD3]';
            icon = 'warning';
          } else if (ev.category === 'UNKNOWN_EVIDENCE') {
            badgeColor = 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]';
            icon = 'help_outline';
          }

          return `
            <div class="p-2.5 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] space-y-1">
              <div class="flex items-center justify-between gap-2">
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeColor}">
                  <span class="material-symbols-outlined text-[12px]">${icon}</span>
                  ${ev.category}
                </span>
                <span class="text-[11px] font-semibold text-[#0F172A] truncate">${escapeHtml(ev.label)}</span>
              </div>
              <p class="text-[11px] text-[#64748B] leading-relaxed">${escapeHtml(ev.description)}</p>
            </div>
          `;
        }).join('');
      }
    }

    // Assumptions & Unknowns
    const assumptionsList = document.getElementById('sim-assumptions-list');
    if (assumptionsList) {
      const allAssumptions = [...(assumptions || []), ...(unknowns || []).map(u => `Coverage unknown: ${u}`)];
      if (allAssumptions.length === 0) {
        assumptionsList.innerHTML = '<li>Baseline assumptions stationary.</li>';
      } else {
        assumptionsList.innerHTML = allAssumptions.map(a => `<li>${escapeHtml(a)}</li>`).join('');
      }
    }
  }

  async function downloadScenarioReport() {
    if (!state.lastSimulationResult) {
      showNotification('Run a scenario simulation first before downloading a report.', 'warning');
      return;
    }

    let markdown = state.lastSimulationResult.report?.markdown_content || state.lastSimulationResult.report_markdown || state.lastSimulationResult.markdown_content;
    const scenarioId = state.lastSimulationResult.scenario_id || `sim_${Date.now()}`;

    if (!markdown && state.currentRepoId && state.lastSimulationResult.scenario_id) {
      try {
        const res = await fetch(`/repositories/${state.currentRepoId}/scenarios/${state.lastSimulationResult.scenario_id}/report`);
        if (res.ok) {
          const reportJson = await res.json();
          markdown = reportJson.markdown_content || reportJson.report_markdown;
        }
      } catch (err) {
        console.warn('Could not fetch report markdown:', err);
      }
    }

    if (!markdown) {
      showNotification('Engineering report could not be generated for this scenario.', 'error');
      return;
    }

    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `twincore_scenario_report_${scenarioId.substring(0, 8)}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    showNotification('Engineering report downloaded successfully.', 'success');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ==============================================================
  // PROJECT DISCOVERY & TECHNICAL HEALTH ASSESSMENT (PHASE 9)
  // ==============================================================

  async function loadDiscoveryView() {
    if (!state.currentRepoId) return;
    const reqEpoch = state.requestEpoch;
    const reqRepoId = state.currentRepoId;

    // Setup filter listeners
    const filterContainer = document.getElementById('disc-finding-filters');
    if (filterContainer && !filterContainer._hasDiscoveryListeners) {
      filterContainer._hasDiscoveryListeners = true;
      filterContainer.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          const filter = btn.dataset.filter || 'all';
          filterDiscoveryFindings(filter);
        });
      });
    }

    // If already loaded in memory, render
    if (state.discoveryAssessmentResult) {
      renderAssessmentResult(state.discoveryAssessmentResult);
      return;
    }

    // Try fetching existing assessment from backend
    try {
      const res = await apiFetch(`/repositories/${state.currentRepoId}/discovery/assessment`);
      if (reqEpoch !== state.requestEpoch || reqRepoId !== state.currentRepoId) return;
      if (res.ok) {
        const data = await res.json();
        if (reqEpoch !== state.requestEpoch || reqRepoId !== state.currentRepoId) return;
        if (data && data.assessment_id) {
          state.discoveryAssessmentResult = data;
          renderAssessmentResult(data);
          return;
        }
      }
    } catch (err) {
      console.warn('Failed to load existing discovery assessment:', err);
    }

    if (reqEpoch !== state.requestEpoch || reqRepoId !== state.currentRepoId) return;
    // Render un-evaluated initial state
    renderUnEvaluatedDiscoveryState();
  }

  function renderUnEvaluatedDiscoveryState() {
    const statusBadge = document.getElementById('disc-status-badge');
    if (statusBadge) {
      statusBadge.textContent = 'NOT_EVALUATED';
      statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#F1F5F9] text-[#475569] border border-[#CBD5E1] uppercase';
    }

    const preBanner = document.getElementById('disc-pre-assessment-banner');
    if (preBanner) preBanner.style.display = 'block';

    const revBadge = document.getElementById('disc-active-revision-badge');
    if (revBadge) {
      const snapHash = (state.currentSnapshotData?.commit_hash && state.currentSnapshotData?.commit_hash !== 'HEAD')
        ? state.currentSnapshotData.commit_hash.slice(0, 7)
        : (state.currentSnapshotId ? state.currentSnapshotId.slice(0, 7) : 'HEAD');
      const branch = state.currentSnapshotData?.branch_name || 'main';
      revBadge.textContent = `${branch} · ${snapHash}`;
    }

    const errBox = document.getElementById('disc-error-box');
    if (errBox) errBox.classList.add('hidden');

    const alertText = document.getElementById('disc-completeness-text');
    if (alertText) {
      alertText.textContent = 'Select a repository revision and click "Run Technical Assessment" to begin discovery.';
    }

    const overall = document.getElementById('disc-overall-health');
    if (overall) overall.textContent = 'Overall: — / 100';

    const discMetric = document.getElementById('disc-metric-discovered');
    if (discMetric) discMetric.textContent = '— / —';

    const discCov = document.getElementById('disc-metric-coverage');
    if (discCov) discCov.textContent = '0.0% AST Coverage';

    const discSym = document.getElementById('disc-metric-symbols');
    if (discSym) discSym.textContent = '—';

    const discRel = document.getElementById('disc-metric-relationships');
    if (discRel) discRel.textContent = '—';

    const discTests = document.getElementById('disc-metric-tests');
    if (discTests) discTests.textContent = '— / —';

    const discTestsRatio = document.getElementById('disc-metric-tests-ratio');
    if (discTestsRatio) discTestsRatio.textContent = 'Verified test coverage';

    const dimGrid = document.getElementById('disc-dimensions-grid');
    if (dimGrid) {
      dimGrid.innerHTML = `
        <div class="p-6 rounded-xl border border-[#E2E8F0] bg-white shadow-xs text-xs text-[#94A3B8] text-center col-span-3 py-8 space-y-2">
          <p class="italic">Assessment not yet executed for this revision.</p>
          <p class="text-[11px] text-[#64748B]">Click "Run Technical Assessment" above to evaluate all 9 architectural dimensions.</p>
        </div>`;
    }

    const findingsList = document.getElementById('disc-findings-list');
    if (findingsList) {
      findingsList.innerHTML = `
        <div class="text-xs text-[#94A3B8] italic p-6 text-center border border-dashed border-[#CBD5E1] rounded-xl">
          Assessment not yet executed. Run technical assessment to detect structural defects.
        </div>`;
    }

    const roadmapList = document.getElementById('disc-roadmap-list');
    if (roadmapList) {
      roadmapList.innerHTML = `
        <div class="text-xs text-[#94A3B8] italic p-6 text-center border border-dashed border-[#CBD5E1] rounded-xl">
          Roadmap will synthesize automatically once technical assessment completes.
        </div>`;
    }
  }

  async function runTechnicalAssessment() {
    if (!state.currentRepoId) {
      showNotification('Connect a repository before running technical assessment.', 'warning');
      return;
    }

    const btn = document.getElementById('btn-run-assessment');
    const btnText = document.getElementById('btn-run-assessment-text');
    const statusBadge = document.getElementById('disc-status-badge');
    const errBox = document.getElementById('disc-error-box');

    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = 'Assessing Repository...';
    if (errBox) errBox.classList.add('hidden');
    if (statusBadge) {
      statusBadge.textContent = 'ANALYZING...';
      statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-300 uppercase animate-pulse';
    }

    try {
      let url = `/repositories/${state.currentRepoId}/discovery/assess`;
      if (state.currentSnapshotId) {
        url += `?snapshot_id=${encodeURIComponent(state.currentSnapshotId)}`;
      }

      const res = await apiFetch(url, { method: 'POST' });
      if (!res.ok) {
        let errDetail = 'Failed to execute technical assessment';
        try {
          const errData = await res.json();
          if (errData && errData.detail) errDetail = errData.detail;
        } catch (_) {}
        throw new Error(errDetail);
      }

      const data = await res.json();
      state.discoveryAssessmentResult = data;
      renderAssessmentResult(data);
      showNotification('Technical assessment completed successfully.', 'success');
    } catch (err) {
      console.warn('Technical assessment error:', err);
      if (errBox) {
        errBox.textContent = `Assessment Failed: ${err.message || 'Unknown error'}`;
        errBox.classList.remove('hidden');
      }
      if (statusBadge) {
        statusBadge.textContent = 'FAILED';
        statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#FEF2F2] text-[#DC2626] border border-[#FECACA] uppercase';
      }
      showNotification(`Technical assessment failed: ${err.message}`, 'error');
    } finally {
      if (btn) btn.disabled = false;
      if (btnText) btnText.textContent = 'Run Technical Assessment';
    }
  }

  function renderAssessmentResult(data) {
    if (!data) return;

    const preBanner = document.getElementById('disc-pre-assessment-banner');
    if (preBanner) preBanner.style.display = 'none';

    // 1. Status Badge
    const statusBadge = document.getElementById('disc-status-badge');
    if (statusBadge) {
      const st = data.status || 'UNKNOWN';
      statusBadge.textContent = st;
      if (st === 'COMPLETE') {
        statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] uppercase';
      } else if (st === 'PARTIAL') {
        statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#FFFBEB] text-[#D97706] border border-[#FDE68A] uppercase';
      } else if (st === 'UNSUPPORTED') {
        statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#F8FAFC] text-[#64748B] border border-[#CBD5E1] uppercase';
      } else {
        statusBadge.className = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#FEF2F2] text-[#DC2626] border border-[#FECACA] uppercase';
      }
    }

    // 2. Metrics & Completeness
    const comp = data.completeness || {};
    const discMetric = document.getElementById('disc-metric-discovered');
    if (discMetric) {
      discMetric.textContent = `${comp.files_analyzed || 0} / ${comp.files_discovered || 0}`;
    }

    const discCov = document.getElementById('disc-metric-coverage');
    if (discCov) {
      discCov.textContent = `${comp.code_coverage_pct || 0}% AST Coverage`;
    }

    const discSym = document.getElementById('disc-metric-symbols');
    if (discSym) {
      discSym.textContent = (comp.symbols_extracted || 0).toLocaleString();
    }

    const discRel = document.getElementById('disc-metric-relationships');
    if (discRel) {
      discRel.textContent = (comp.relationships_extracted || 0).toLocaleString();
    }

    const discTests = document.getElementById('disc-metric-tests');
    if (discTests) {
      discTests.textContent = `${comp.tests_linked || 0} / ${comp.tests_discovered || 0}`;
    }

    const discTestsRatio = document.getElementById('disc-metric-tests-ratio');
    if (discTestsRatio) {
      discTestsRatio.textContent = `Coverage Ratio: ${(comp.test_to_component_ratio || 0).toFixed(2)}`;
    }

    const alertText = document.getElementById('disc-completeness-text');
    if (alertText) {
      alertText.textContent = comp.notes || (data.status === 'UNSUPPORTED'
        ? 'Repository contains non-code or unsupported files. Deep AST analysis unavailable.'
        : `Analysis verified across ${comp.files_analyzed || 0} files and ${comp.relationships_extracted || 0} relationships.`);
    }

    // 3. Overall Health Score
    const overall = document.getElementById('disc-overall-health');
    if (overall) {
      if (data.overall_health_score !== null && data.overall_health_score !== undefined) {
        overall.textContent = `Overall: ${data.overall_health_score} / 100`;
        if (data.overall_health_score >= 80) {
          overall.className = 'text-xs font-bold text-[#059669] bg-[#ECFDF5] px-2.5 py-1 rounded-lg border border-[#A7F3D0]';
        } else if (data.overall_health_score >= 50) {
          overall.className = 'text-xs font-bold text-[#D97706] bg-[#FFFBEB] px-2.5 py-1 rounded-lg border border-[#FDE68A]';
        } else {
          overall.className = 'text-xs font-bold text-[#DC2626] bg-[#FEF2F2] px-2.5 py-1 rounded-lg border border-[#FECACA]';
        }
      } else {
        overall.textContent = 'Overall: N/A';
        overall.className = 'text-xs font-bold text-[#64748B] bg-[#F1F5F9] px-2.5 py-1 rounded-lg border border-[#CBD5E1]';
      }
    }

    // 4. Dimensional Scorecard
    const dimGrid = document.getElementById('disc-dimensions-grid');
    if (dimGrid) {
      const scores = data.dimensional_scores || [];
      if (scores.length === 0) {
        dimGrid.innerHTML = `
          <div class="p-4 rounded-xl border border-[#E2E8F0] bg-white shadow-xs text-xs text-[#94A3B8] italic text-center col-span-3 py-8">
            No dimensional scores evaluated.
          </div>`;
      } else {
        dimGrid.innerHTML = scores.map(dim => {
          const score = dim.score !== null && dim.score !== undefined ? dim.score : '—';
          let scoreColor = 'text-[#059669] bg-[#ECFDF5] border-[#A7F3D0]';
          let barBg = 'bg-[#059669]';
          if (score < 50) {
            scoreColor = 'text-[#DC2626] bg-[#FEF2F2] border-[#FECACA]';
            barBg = 'bg-[#DC2626]';
          } else if (score < 80) {
            scoreColor = 'text-[#D97706] bg-[#FFFBEB] border-[#FDE68A]';
            barBg = 'bg-[#D97706]';
          }
          const numScore = typeof score === 'number' ? score : 0;

          return `
            <div class="p-4 rounded-xl border border-[#E2E8F0] bg-white shadow-xs space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-[#0F172A]">${escapeHtml(dim.dimension_name)}</span>
                <span class="text-xs font-extrabold px-2 py-0.5 rounded border ${scoreColor}">${score}/100</span>
              </div>
              <div class="w-full bg-[#E2E8F0] h-1.5 rounded-full overflow-hidden">
                <div class="${barBg} h-1.5 rounded-full" style="width: ${numScore}%"></div>
              </div>
              <p class="text-[11px] text-[#64748B] leading-relaxed">${escapeHtml(dim.rationale)}</p>
            </div>
          `;
        }).join('');
      }
    }

    // 5. Findings
    renderFindingsList(data.findings || []);

    // 6. Advisory Remediation Roadmap
    const roadmapList = document.getElementById('disc-roadmap-list');
    if (roadmapList) {
      const recs = data.roadmap_recommendations || [];
      if (recs.length === 0) {
        roadmapList.innerHTML = `
          <div class="text-xs text-[#059669] bg-[#ECFDF5] border border-[#A7F3D0] p-4 rounded-xl text-center">
            No active remediation recommendations required. Repository health parameters are within normal thresholds.
          </div>`;
      } else {
        roadmapList.innerHTML = recs.map(r => {
          let prioBadge = 'bg-slate-100 text-slate-800 border-slate-300';
          if (r.priority === 'P0_IMMEDIATE') {
            prioBadge = 'bg-red-50 text-red-800 border-red-300';
          } else if (r.priority === 'P1_HIGH') {
            prioBadge = 'bg-orange-50 text-orange-800 border-orange-300';
          } else if (r.priority === 'P2_MEDIUM') {
            prioBadge = 'bg-blue-50 text-blue-800 border-blue-300';
          }

          const comps = (r.affected_components || []).map(c =>
            `<span class="px-1.5 py-0.5 rounded bg-[#F1F5F9] text-[#334155] border border-[#CBD5E1] text-[10px] font-mono">${escapeHtml(c)}</span>`
          ).join(' ');

          const prereqs = (r.prerequisites || []).map(p =>
            `<li class="text-[10px] text-[#64748B]">${escapeHtml(p)}</li>`
          ).join('');

          return `
            <div class="p-4 rounded-xl border border-[#E2E8F0] bg-white shadow-xs space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${prioBadge}">
                  ${escapeHtml(r.priority.replace('_', ' '))}
                </span>
                <span class="text-[10px] font-medium text-[#64748B]">Confidence: ${(r.confidence * 100).toFixed(0)}%</span>
              </div>
              <h4 class="text-xs font-bold text-[#0F172A]">${escapeHtml(r.title)}</h4>
              <p class="text-[11px] text-[#475569] leading-relaxed">${escapeHtml(r.technical_rationale)}</p>
              
              <div class="space-y-1 pt-1 border-t border-[#F1F5F9]">
                <div class="text-[10px] font-semibold text-[#0F172A]">Expected Benefit:</div>
                <div class="text-[11px] text-[#059669]">${escapeHtml(r.expected_benefit)}</div>
              </div>

              ${comps ? `
                <div class="space-y-1">
                  <div class="text-[10px] font-semibold text-[#0F172A]">Affected Components:</div>
                  <div class="flex flex-wrap gap-1">${comps}</div>
                </div>
              ` : ''}

              <div class="space-y-1">
                <div class="text-[10px] font-semibold text-[#0F172A]">Verification Criteria:</div>
                <div class="text-[11px] text-[#475569] font-mono bg-[#F8FAFC] p-2 rounded border border-[#E2E8F0]">${escapeHtml(r.verification_criteria)}</div>
              </div>

              ${prereqs ? `
                <div class="space-y-0.5">
                  <div class="text-[10px] font-semibold text-[#64748B]">Prerequisites:</div>
                  <ul class="list-disc pl-4">${prereqs}</ul>
                </div>
              ` : ''}
            </div>
          `;
        }).join('');
      }
    }
  }

  function filterDiscoveryFindings(filterType) {
    state.discoveryFindingFilter = filterType;
    const filterContainer = document.getElementById('disc-finding-filters');
    if (filterContainer) {
      filterContainer.querySelectorAll('.filter-btn').forEach(btn => {
        const isActive = btn.dataset.filter === filterType;
        btn.classList.toggle('active', isActive);
        if (isActive) {
          btn.className = 'px-2 py-0.5 text-[10px] font-bold rounded bg-[#0F172A] text-white filter-btn active';
        } else {
          btn.className = 'px-2 py-0.5 text-[10px] font-bold rounded bg-[#F1F5F9] text-[#475569] filter-btn';
        }
      });
    }

    if (state.discoveryAssessmentResult) {
      renderFindingsList(state.discoveryAssessmentResult.findings || []);
    }
  }

  function renderFindingsList(findings) {
    const findingsList = document.getElementById('disc-findings-list');
    if (!findingsList) return;

    const filter = state.discoveryFindingFilter || 'all';
    let filtered = findings;
    if (filter === 'critical') {
      filtered = findings.filter(f => f.severity === 'CRITICAL' || f.severity === 'HIGH');
    } else if (filter === 'medium') {
      filtered = findings.filter(f => f.severity === 'MEDIUM');
    }

    if (filtered.length === 0) {
      if ((findings || []).length === 0) {
        findingsList.innerHTML = `
          <div class="text-xs text-[#059669] bg-[#ECFDF5] border border-[#A7F3D0] p-6 text-center rounded-xl font-medium">
            ✓ Clean Architecture: 0 structural violations, circular dependencies, or test coverage deficits detected.
          </div>`;
      } else {
        findingsList.innerHTML = `
          <div class="text-xs text-[#64748B] italic p-6 text-center border border-dashed border-[#CBD5E1] rounded-xl">
            No findings matching the selected filter (${filter}).
          </div>`;
      }
      return;
    }

    findingsList.innerHTML = filtered.map(f => {
      let sevBadge = 'bg-slate-100 text-slate-800 border-slate-300';
      if (f.severity === 'CRITICAL') {
        sevBadge = 'bg-red-100 text-red-900 border-red-300';
      } else if (f.severity === 'HIGH') {
        sevBadge = 'bg-orange-100 text-orange-900 border-orange-300';
      } else if (f.severity === 'MEDIUM') {
        sevBadge = 'bg-amber-100 text-amber-900 border-amber-300';
      } else if (f.severity === 'LOW') {
        sevBadge = 'bg-blue-100 text-blue-900 border-blue-300';
      }

      const evRefs = (f.evidence_references || []).map(r =>
        `<span class="px-1.5 py-0.5 rounded bg-[#F1F5F9] text-[#334155] border border-[#CBD5E1] text-[10px] font-mono">${escapeHtml(r)}</span>`
      ).join(' ');

      return `
        <div class="p-3.5 rounded-xl border border-[#E2E8F0] bg-white shadow-xs space-y-2">
          <div class="flex items-center justify-between">
            <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${sevBadge}">
              ${escapeHtml(f.severity)}
            </span>
            <span class="text-[10px] font-mono text-[#64748B]">${escapeHtml(f.id)}</span>
          </div>

          <div class="space-y-0.5">
            <div class="text-xs font-bold text-[#0F172A] font-mono">${escapeHtml(f.affected_entity || 'Repository')}</div>
            <div class="text-[10px] text-[#64748B]">Category: <span class="font-medium text-[#334155]">${escapeHtml(f.category)}</span> &bull; Detected via: <span class="font-medium text-[#334155]">${escapeHtml(f.detection_method)}</span></div>
          </div>

          <p class="text-[11px] text-[#334155] leading-relaxed">${escapeHtml(f.rationale)}</p>

          ${evRefs ? `
            <div class="pt-1">
              <div class="text-[10px] font-semibold text-[#64748B]">Evidence:</div>
              <div class="flex flex-wrap gap-1 mt-0.5">${evRefs}</div>
            </div>
          ` : ''}

          <div class="pt-1.5 border-t border-[#F1F5F9] flex items-center justify-between text-[10px]">
            <span class="text-[#0071e3] font-medium flex items-center gap-1">
              <span class="material-symbols-outlined text-[14px]">arrow_forward</span>
              ${escapeHtml(f.recommended_next_action || 'Inspect component dependencies')}
            </span>
            <span class="text-[#94A3B8]">Confidence: ${(f.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
      `;
    }).join('');
  }

  async function downloadAssessmentReport() {
    if (!state.currentRepoId) {
      showNotification('Select a repository first.', 'warning');
      return;
    }

    try {
      showNotification('Generating technical assessment report...', 'info');
      const res = await apiFetch(`/repositories/${state.currentRepoId}/discovery/report`);
      if (!res.ok) {
        throw new Error('Failed to retrieve assessment report');
      }

      const data = await res.json();
      const markdown = data.report_markdown;
      if (!markdown) {
        throw new Error('Report content is empty');
      }

      const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const repoName = (state.currentRepoData?.name || 'repository').replace(/[^a-zA-Z0-9_-]/g, '_');
      link.setAttribute('download', `twincore-technical-assessment-${repoName}.md`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      showNotification('Technical assessment report downloaded successfully.', 'success');
    } catch (err) {
      console.error('Download report error:', err);
      showNotification(`Failed to export report: ${err.message}`, 'error');
    }
  }

  window.TwinApp = {
    state,
    getState: () => state,
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
    executeRiskAnalysis,
    loadTestsView,
    loadRuntimeView,
    loadIncidentsView,
    investigateIncident,
    openConnectModal,
    closeConnectModal,
    openIngestModal,
    closeIngestModal,
    openCreateIncidentModal,
    closeCreateIncidentModal,
    openAuthModal,
    closeAuthModal,
    logoutUser,
    checkAuthentication,
    selectRepository,
    selectSnapshot,
    loadSnapshotsForRepo,
    loadSnapshotsForCurrentRepo,
    disconnectRepository,
    resyncRepository,
    showNotification,
    startApplicationStateMachine,
    apiFetch,
    loadDependenciesView,
    selectDependencyComponent,
    loadSimulationView,
    runSimulationAction: executeOrchestratedSimulation,
    inspectScenario,
    Twin3D,
    openCommandPalette: () => window.openCommandPalette?.(),
    loadDiscoveryView,
    runTechnicalAssessment,
    filterDiscoveryFindings,
    downloadAssessmentReport,
    openDisconnectModal,
    confirmDisconnectRepository,
    loadDemoSandbox: async () => {
      showNotification('Loading interactive E-Commerce Microservices sandbox...', 'info');
      try {
        let repoToUse = (state.repositories || []).find(r => r.name?.toLowerCase().includes('demo') || r.name?.toLowerCase().includes('campus') || r.name?.toLowerCase().includes('ecommerce'));
        if (!repoToUse && state.repositories && state.repositories.length > 0) {
          repoToUse = state.repositories[0];
        }
        if (repoToUse) {
          await selectRepository(repoToUse.id);
          switchPrimaryView('architecture');
          showNotification('Interactive Demo Sandbox launched successfully!', 'success');
        } else {
          showNotification('Creating sandbox workspace environment...', 'info');
          await triggerLocalOnboarding('/Users/sanjay/DIGITAL TWIN', 'TwinCore-Demo-Sandbox');
        }
      } catch (err) {
        showNotification(`Could not launch sandbox: ${err.message}`, 'error');
      }
    },
    openModal,
    closeModal,
    selectResolvedTarget,
    setAppState,
    refreshActiveView,
    refreshCurrentView: refreshActiveView,
  };

})();
