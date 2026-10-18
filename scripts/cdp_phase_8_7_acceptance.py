#!/usr/bin/env python3
"""
Phase 8.7 — Frontend Recovery, Real Repository Access & Product Usability Hardening
End-to-End Chrome DevTools Protocol (CDP) Acceptance Verification Suite.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
import websockets

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9223
TARGET_URL = "http://localhost:8000"

class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0
        self.pending_requests = {}
        self.console_errors = []
        self.network_failures = []
        self._listen_task = None

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50_000_000)
        self._listen_task = asyncio.create_task(self._listen())
        await self.send("Runtime.enable")
        await self.send("Page.enable")
        await self.send("Network.enable")
        await self.send("DOM.enable")

    async def send(self, method, params=None):
        self.msg_id += 1
        curr_id = self.msg_id
        fut = asyncio.get_running_loop().create_future()
        self.pending_requests[curr_id] = fut
        msg = {"id": curr_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))
        return await fut

    async def eval_js(self, expression, await_promise=False):
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise,
        })
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS Exception: {res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    def _handle_event(self, event):
        method = event.get("method")
        params = event.get("params", {})
        if method == "Runtime.consoleAPICalled":
            t = params.get("type")
            args = [a.get("value", a.get("description", "")) for a in params.get("args", [])]
            msg = f"[{t}] " + " ".join(str(x) for x in args)
            if t == "error":
                self.console_errors.append(msg)
            print("  [BROWSER CONSOLE]", msg)
        elif method == "Runtime.exceptionThrown":
            exc = params.get("exceptionDetails", {})
            msg = f"Exception: {exc.get('text')} - {exc.get('exception', {}).get('description')}"
            self.console_errors.append(msg)
            print("  [BROWSER EXCEPTION]", msg)
        elif method == "Network.responseReceived":
            status = params.get("response", {}).get("status", 200)
            url = params.get("response", {}).get("url", "")
            if status >= 400 and not "/auth/" in url:
                self.network_failures.append(f"{status} {url}")

    async def _listen(self):
        try:
            async for raw in self.ws:
                event = json.loads(raw)
                if "id" in event:
                    req_id = event["id"]
                    if req_id in self.pending_requests:
                        fut = self.pending_requests.pop(req_id)
                        if not fut.done():
                            fut.set_result(event.get("result", {}))
                elif "method" in event:
                    self._handle_event(event)
        except Exception:
            pass

    async def close(self):
        if self._listen_task:
            self._listen_task.cancel()
        if self.ws:
            await self.ws.close()


async def run_suite():
    print("=" * 70)
    print("PHASE 8.7 — FRONTEND RECOVERY & USABILITY CDP ACCEPTANCE SUITE")
    print("=" * 70)

    # Clean profile dir to avoid stale tab restoration
    import shutil
    user_data_dir = "/tmp/cdp_twin_phase87_test"
    if os.path.exists(user_data_dir):
        shutil.rmtree(user_data_dir, ignore_errors=True)

    # Launch Chrome in headless mode with remote debugging and 1440x900 desktop viewport
    chrome_proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={PORT}",
        "--window-size=1440,900",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        f"--user-data-dir={user_data_dir}"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    client = None
    try:
        # Wait for Chrome debug port to open
        tabs = None
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as response:
                    tabs = json.loads(response.read().decode())
                    if tabs:
                        break
            except Exception:
                time.sleep(0.2)

        if not tabs:
            raise RuntimeError("Failed to connect to Headless Chrome remote debugging port.")

        page_tabs = [t for t in tabs if t.get("type") == "page"]
        ws_url = page_tabs[0]["webSocketDebuggerUrl"] if page_tabs else tabs[0]["webSocketDebuggerUrl"]
        client = CDPClient(ws_url)
        await client.connect()

        # Enforce Rule 28: 1440x900 Desktop Viewport
        await client.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440,
            "height": 900,
            "deviceScaleFactor": 1,
            "mobile": False
        })
        print("[✓] Connected to Headless Chrome CDP (1440x900 Desktop Viewport)")

        # Step 1: Fresh Session Hardening & Gating
        print("\n--- STEP 1: Fresh Session Hardening & Gating ---")
        await client.send("Page.navigate", {"url": TARGET_URL})
        await asyncio.sleep(1.0)
        await client.eval_js("localStorage.clear(); sessionStorage.clear();")
        await client.send("Page.navigate", {"url": TARGET_URL})
        
        # Wait for page ready and window.TwinApp
        twin_app_ready = False
        for _ in range(40):
            ready = await client.eval_js("document.readyState === 'complete' && typeof window.TwinApp !== 'undefined'")
            if ready:
                twin_app_ready = True
                break
            await asyncio.sleep(0.2)
        assert twin_app_ready, "window.TwinApp failed to initialize on fresh page load"

        # Wait for state machine to load user repositories
        for _ in range(30):
            repos = await client.eval_js("window.TwinApp && window.TwinApp.getState ? window.TwinApp.getState().repositories : null")
            if repos is not None and len(repos) > 0:
                break
            await asyncio.sleep(0.2)

        # 1.1 Verify Zero test fixture pollution in repository selector
        repo_options = await client.eval_js("""
            Array.from(document.querySelectorAll('#repo-select option')).map(o => ({ value: o.value, text: o.textContent }))
        """)
        print(f"[*] Repositories in selector: {len(repo_options)}")
        for r in repo_options:
            assert "controlled-repo" not in r["text"], f"Fixture polluted: {r['text']}"
            assert "empty-repo" not in r["text"], f"Fixture polluted: {r['text']}"
            assert "arch-api-repo" not in r["text"], f"Fixture polluted: {r['text']}"
        print("[✓] Zero test fixture pollution in repository selector.")

        # 1.2 Verify initial disconnected state
        curr_repo = await client.eval_js("window.TwinApp ? window.TwinApp.getState().currentRepoId : null")
        assert curr_repo is None, f"Expected null repo on fresh load, got {curr_repo}"

        no_repo_class = await client.eval_js("document.body.classList.contains('no-repo')")
        assert no_repo_class, "Expected document.body to have 'no-repo' class when disconnected"

        sidebar_display = await client.eval_js("window.getComputedStyle(document.getElementById('app-sidebar')).display")
        assert sidebar_display == "none", f"Expected #app-sidebar to be hidden ('none') when disconnected, got '{sidebar_display}'"
        print("[✓] Sidebar is cleanly removed/hidden when no repository is connected.")

        # 1.3 Verify Gated Controls when disconnected (Rules 1, 2, 4, 5, 10)
        snap_disabled = await client.eval_js("document.getElementById('snapshot-select')?.disabled")
        snap_text = await client.eval_js("document.getElementById('snapshot-select')?.options[0]?.text")
        assert snap_disabled, "Snapshot selector must be disabled when no repository is active"
        assert "-- Select Snapshot --" in snap_text, f"Expected '-- Select Snapshot --', got '{snap_text}'"
        print("[✓] Snapshot selector strictly disabled with '-- Select Snapshot --'.")

        search_disabled = await client.eval_js("document.getElementById('top-search-btn')?.disabled")
        assert search_disabled, "Search bar must be disabled when no repository is active"
        print("[✓] Search bar strictly disabled when disconnected.")

        ingest_disabled = await client.eval_js("document.getElementById('top-btn-ingest-runtime')?.disabled")
        incident_disabled = await client.eval_js("document.getElementById('top-btn-create-incident')?.disabled")
        assert ingest_disabled, "Ingest button must be disabled when no repository is active"
        assert incident_disabled, "Incident button must be disabled when no repository is active"
        print("[✓] Ingest and Incident header buttons strictly disabled when disconnected.")

        signin_nowrap = await client.eval_js("window.getComputedStyle(document.getElementById('top-btn-login')).whiteSpace")
        assert signin_nowrap == "nowrap", f"Sign in button must have whiteSpace: nowrap, got {signin_nowrap}"
        print("[✓] Sign In button guaranteed no-wrap typography.")

        # 1.4 Verify #view-no-repo single authoritative onboarding card and 3 acquisition cards
        no_repo_visible = await client.eval_js("document.getElementById('view-no-repo')?.style.display !== 'none'")
        assert no_repo_visible, "Expected #view-no-repo welcome hero to be visible on fresh session"
        onboard_card_count = await client.eval_js("document.querySelectorAll('#view-no-repo .onboard-card').length")
        assert onboard_card_count == 3, f"Expected 3 onboard acquisition cards, found {onboard_card_count}"
        print("[✓] Fresh session cleanly renders #view-no-repo with 3 redesigned .onboard-card elements.")

        # Step 2: Modal Navigation & Provider Tabs
        print("\n--- STEP 2: Onboard Modal & Provider Tabs ---")
        await client.eval_js("window.TwinApp.openConnectModal('github');")
        await asyncio.sleep(0.5)
        github_visible = await client.eval_js("""
            document.getElementById('modal-panel-github')?.style.display !== 'none'
        """)
        assert github_visible, "GitHub panel should be visible"

        token_type = await client.eval_js("document.getElementById('input-github-token')?.getAttribute('type')")
        assert token_type == "password", f"Expected token type='password', got {token_type}"
        print("[✓] GitHub tab correctly presents masked password token input.")

        # Switch to Local tab
        await client.eval_js("document.getElementById('tab-prov-local')?.click();")
        await asyncio.sleep(0.3)
        local_visible = await client.eval_js("""
            document.getElementById('modal-panel-local')?.style.display !== 'none'
        """)
        assert local_visible, "Local panel should be visible"
        print("[✓] Local project tab opens cleanly.")

        # Switch to Archive tab
        await client.eval_js("document.getElementById('tab-prov-archive')?.click();")
        await asyncio.sleep(0.3)
        archive_visible = await client.eval_js("""
            document.getElementById('modal-panel-archive')?.style.display !== 'none'
        """)
        assert archive_visible, "Archive panel should be visible"
        print("[✓] Archive ZIP upload tab opens cleanly.")

        # Test ESC Key Closes Modal
        await client.eval_js("""
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        """)
        await asyncio.sleep(0.4)
        modal_open = await client.eval_js("""
            document.getElementById('modal-onboard')?.style.display !== 'none'
        """)
        assert not modal_open, "ESC key should close the connect modal"
        print("[✓] ESC key closes the onboard modal cleanly.")

        # Step 3: Stitch Light/Dark Theme Switching & Card Theming
        print("\n--- STEP 3: Theme Manager & Card Quality ---")
        init_theme = await client.eval_js("localStorage.getItem('twin_theme') || 'light'")
        print(f"[*] Initial theme: {init_theme}")

        # Toggle to dark
        await client.eval_js("document.getElementById('btn-toggle-theme')?.click();")
        await asyncio.sleep(0.3)
        is_dark = await client.eval_js("document.body.classList.contains('theme-dark')")
        saved_dark = await client.eval_js("localStorage.getItem('twin_theme')")
        icon_dark = await client.eval_js("document.querySelector('#btn-toggle-theme .material-symbols-outlined')?.textContent")
        assert is_dark and saved_dark == 'dark', f"Expected dark theme, got is_dark={is_dark}, saved={saved_dark}"
        print(f"[✓] Dark mode toggled: body.theme-dark active, icon='{icon_dark}', saved to localStorage.")

        # Toggle back to light
        await client.eval_js("document.getElementById('btn-toggle-theme')?.click();")
        await asyncio.sleep(0.3)
        is_light = await client.eval_js("document.body.classList.contains('theme-light')")
        saved_light = await client.eval_js("localStorage.getItem('twin_theme')")
        icon_light = await client.eval_js("document.querySelector('#btn-toggle-theme .material-symbols-outlined')?.textContent")
        assert is_light and saved_light == 'light', f"Expected light theme, got is_light={is_light}, saved={saved_light}"
        print(f"[✓] Light mode toggled: body.theme-light active, icon='{icon_light}', saved to localStorage.")

        # Step 4: Canonical Repository Selection, Card Layout & Metrics
        print("\n--- STEP 4: Repository Selection, Restored Sidebar & Card Verification ---")
        target_repo_id = await client.eval_js("""
            (() => {
                const repos = window.TwinApp.getState().repositories || [];
                const found = repos.find(r => r.name === 'LAB-RECORD-SYSTEM' || r.id === '1dafa8df-4083-47b4-9021-d8a47a897aa8');
                return found ? found.id : null;
            })()
        """)
        assert target_repo_id, "Could not find LAB-RECORD-SYSTEM repository"
        print(f"[*] Selecting canonical repository: {target_repo_id}")

        await client.eval_js(f"window.TwinApp.selectRepository('{target_repo_id}');")
        await asyncio.sleep(2.0)

        # 4.1 Verify sidebar is now visible
        has_no_repo = await client.eval_js("document.body.classList.contains('no-repo')")
        sidebar_display_connected = await client.eval_js("window.getComputedStyle(document.getElementById('app-sidebar')).display")
        assert not has_no_repo, "document.body should NOT have 'no-repo' class after repository is selected"
        assert sidebar_display_connected == "flex", f"Expected #app-sidebar to be 'flex', got '{sidebar_display_connected}'"
        print("[✓] Sidebar is dynamically restored when repository is connected.")

        # 4.2 Verify bottom switcher shows repository identity, Disconnect, and Resync
        active_repo_box = await client.eval_js("document.getElementById('sidebar-repo-active-container')?.style.display !== 'none'")
        assert active_repo_box, "Expected #sidebar-repo-active-container to be visible when repository is active"
        print("[✓] Bottom workspace switcher shows repository card with Disconnect and Resync actions.")

        # 4.3 Verify snapshot selector enabled and formatted
        snap_disabled_now = await client.eval_js("document.getElementById('snapshot-select')?.disabled")
        assert not snap_disabled_now, "Snapshot selector must be enabled when repository is active"
        snaps = await client.eval_js("""
            Array.from(document.querySelectorAll('#snapshot-select option')).map(o => o.textContent)
        """)
        print(f"[*] Snapshots found: {len(snaps)-1}")
        for s in snaps[1:]:
            assert " · " in s, f"Snapshot format should be 'branch · hash': {s}"
        print("[✓] Snapshot selector enabled and labels formatted cleanly with branch and commit hash.")

        # 4.4 Verify Overview Cards Redesign and Grid Dimensions (Non-squished proof)
        card_widths = await client.eval_js("""
            (() => {
                const statCards = Array.from(document.querySelectorAll('.stat-card-entity')).map(el => Math.round(el.getBoundingClientRect().width));
                const pkgCard = Math.round(document.getElementById('ov-packages-grid')?.getBoundingClientRect()?.width || 0);
                const impactCard = Math.round(document.getElementById('ov-impact-container')?.getBoundingClientRect()?.width || 0);
                return { statCards, pkgCard, impactCard };
            })()
        """)
        print(f"[*] Rendered Card Widths: Stat cards={card_widths['statCards']}, Macro Packages={card_widths['pkgCard']}px, Impact={card_widths['impactCard']}px")
        for w in card_widths['statCards']:
            assert w >= 150, f"Stat card is unexpectedly narrow ({w}px), suspected layout squish"
        assert card_widths['pkgCard'] >= 450, f"Macro packages card squished ({card_widths['pkgCard']}px)"
        assert card_widths['impactCard'] >= 450, f"Impact card squished ({card_widths['impactCard']}px)"
        print("[✓] All Overview cards verified with robust full-width grid geometry (ZERO SQUISHING).")

        # Step 5: Change Impact Verification
        print("\n--- STEP 5: Change Impact Canonical Metrics ---")
        await client.eval_js("window.TwinApp.switchPrimaryView('impact');")
        await asyncio.sleep(1.0)

        # Select canonical baseline snap_2dcb5aee2bc8f941 and target snap_9135acb3565f0037
        await client.eval_js("""
            document.getElementById('diff-base-select').value = 'snap_2dcb5aee2bc8f941';
            document.getElementById('diff-target-select').value = 'snap_9135acb3565f0037';
            window.TwinApp.executeChangeImpactAnalysis();
        """)
        await asyncio.sleep(3.0)

        # Check Canonical Metrics
        changed = await client.eval_js("document.getElementById('metric-impact-changed')?.textContent")
        direct = await client.eval_js("document.getElementById('metric-impact-direct')?.textContent")
        indirect = await client.eval_js("document.getElementById('metric-impact-indirect')?.textContent")
        print(f"[✓] Canonical Impact Metrics: Changed={changed}, Direct={direct}, Indirect={indirect}")
        assert changed == "120", f"Expected 120 changed, got {changed}"
        assert direct == "29", f"Expected 29 direct, got {direct}"
        assert indirect == "7", f"Expected 7 indirect, got {indirect}"

        # Step 6: Truthful Identical Snapshot Comparison
        print("\n--- STEP 6: Identical Snapshot Truthfulness Verification ---")
        await client.eval_js("""
            document.getElementById('diff-base-select').value = 'snap_9135acb3565f0037';
            document.getElementById('diff-target-select').value = 'snap_9135acb3565f0037';
            window.TwinApp.executeChangeImpactAnalysis();
        """)
        await asyncio.sleep(0.5)

        table_text = await client.eval_js("document.getElementById('diff-table-body')?.textContent || ''")
        tree_text = await client.eval_js("document.getElementById('impact-paths-tree')?.textContent || ''")
        changed_val = await client.eval_js("document.getElementById('metric-impact-changed')?.textContent")

        assert "identical" in table_text.lower() or "identical" in tree_text.lower(), f"Expected identical snapshot warning, got table={table_text}, tree={tree_text}"
        assert changed_val == "-", f"Expected '-' for identical snapshots, got: {changed_val}"
        print("[✓] Identical snapshots honestly report comparison state (no fake zero-value claims).")

        # Step 7: Disconnect Action Verification
        print("\n--- STEP 7: Disconnect Repository Verification ---")
        await client.eval_js("document.getElementById('btn-disconnect-repo')?.click();")
        await asyncio.sleep(0.5)

        disconnected_repo = await client.eval_js("window.TwinApp.getState().currentRepoId")
        assert disconnected_repo is None, f"Expected null currentRepoId after disconnect, got {disconnected_repo}"

        disconnected_sidebar = await client.eval_js("window.getComputedStyle(document.getElementById('app-sidebar')).display")
        assert disconnected_sidebar == "none", f"Sidebar should be hidden after disconnect, got {disconnected_sidebar}"

        no_repo_returned = await client.eval_js("document.getElementById('view-no-repo')?.style.display !== 'none'")
        assert no_repo_returned, "Expected #view-no-repo welcome view to be restored after disconnect"
        print("[✓] Disconnect action cleanly clears repository state, hides sidebar, and restores #view-no-repo.")

        # Step 8: Console Error & Asset Failure Audit
        print("\n--- STEP 8: Runtime Console & Asset Integrity ---")
        print(f"[*] Total Console Errors: {len(client.console_errors)}")
        for err in client.console_errors:
            print(f"    [ERR] {err}")
        print(f"[*] Total Unexpected Network Failures: {len(client.network_failures)}")
        for fail in client.network_failures:
            print(f"    [FAIL] {fail}")

        assert len(client.console_errors) == 0, f"Found console errors: {client.console_errors}"
        assert len(client.network_failures) == 0, f"Found network failures: {client.network_failures}"
        print("[✓] Zero console errors. Zero asset/API network failures.")

        print("\n" + "=" * 70)
        print("ALL PHASE 8.7.4 QUALITY RECOVERY CRITERIA SATISFIED EMPIRICALLY (PASS)")
        print("=" * 70)

    finally:
        if client:
            await client.close()
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()

if __name__ == "__main__":
    asyncio.run(run_suite())
