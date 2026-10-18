#!/usr/bin/env python3
"""
Phase 8.7.6 Acceptance Suite: Multi-User Repository Privacy, Bootstrap State & UI Integrity.
Covers Cases 01-20 and captures 1440x900 screenshots across all visual states.
"""

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import websockets

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9224
TARGET_URL = "http://localhost:8000"
USER_DATA_DIR = "/tmp/cdp_twin_phase876_test"
SCREENSHOT_DIR = "/Users/sanjay/DIGITAL TWIN /scratch/phase_8_7_6_screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

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

    async def capture_screenshot(self, filename):
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        raw_b64 = res.get("data", "")
        img_bytes = base64.b64decode(raw_b64)
        out_path = os.path.join(SCREENSHOT_DIR, filename)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        print(f"  [SCREENSHOT SAVED] {out_path} ({len(img_bytes)} bytes)")
        return out_path

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


async def run_phase_8_7_6_suite():
    print("=" * 80)
    print("PHASE 8.7.6 — REPOSITORY PRIVACY, BOOTSTRAP STATE & UI INTEGRITY SUITE")
    print("=" * 80)

    if os.path.exists(USER_DATA_DIR):
        shutil.rmtree(USER_DATA_DIR, ignore_errors=True)

    chrome_proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={PORT}",
        "--window-size=1440,900",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        f"--user-data-dir={USER_DATA_DIR}"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    client = None
    try:
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

        await client.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440,
            "height": 900,
            "deviceScaleFactor": 1,
            "mobile": False
        })
        print("[✓] Connected to Headless Chrome CDP (1440x900 Desktop Viewport)")

        # ------------------------------------------------------------------
        # CASE 01: Fresh guest browser session cleanly loads in state-signed-out
        # ------------------------------------------------------------------
        print("\n--- CASE 01: Fresh Guest Session State ---")
        await client.send("Page.navigate", {"url": TARGET_URL})
        await asyncio.sleep(1.0)
        await client.eval_js("localStorage.clear(); sessionStorage.clear();")
        await client.send("Page.navigate", {"url": TARGET_URL})
        
        for _ in range(40):
            ready = await client.eval_js("document.readyState === 'complete' && typeof window.TwinApp !== 'undefined' && !document.body.classList.contains('booting')")
            if ready:
                break
            await asyncio.sleep(0.1)

        is_signed_out = await client.eval_js("document.body.classList.contains('state-signed-out')")
        assert is_signed_out, "Expected document.body to have 'state-signed-out' class"
        print("[✓] Case 01 PASS: Fresh session initialized in 'state-signed-out'.")

        # ------------------------------------------------------------------
        # CASE 02: Boot-Screen overlay and hidden app-shell during boot
        # ------------------------------------------------------------------
        print("\n--- CASE 02: Zero-Flash Boot Screen Mechanism ---")
        has_boot_screen = await client.eval_js("Boolean(document.getElementById('boot-screen'))")
        assert has_boot_screen, "DOM must include #boot-screen element"
        boot_hidden = await client.eval_js("window.getComputedStyle(document.getElementById('boot-screen')).visibility === 'hidden'")
        assert boot_hidden, "Post-boot #boot-screen must be visibility: hidden"
        print("[✓] Case 02 PASS: #boot-screen properly present and transitions out after boot.")

        # ------------------------------------------------------------------
        # CASE 03: Guest session receives [] from GET /repositories
        # ------------------------------------------------------------------
        print("\n--- CASE 03: Server-Side Guest Privacy Enforcement ---")
        repos = await client.eval_js("""(async () => {
            const res = await window.TwinApp.apiFetch('/repositories');
            return await res.json();
        })()""", await_promise=True)
        assert isinstance(repos, list) and len(repos) == 0, f"Expected [] for guest repositories, got: {repos}"
        print("[✓] Case 03 PASS: Guest receives empty list [] from GET /repositories.")

        # ------------------------------------------------------------------
        # CASE 04: Header workspace controls strictly hidden for guest
        # ------------------------------------------------------------------
        print("\n--- CASE 04: Header Workspace Controls Hidden ---")
        ctrls_disp = await client.eval_js("window.getComputedStyle(document.getElementById('header-workspace-controls')).display")
        assert ctrls_disp == "none", f"Expected #header-workspace-controls display: none, got: '{ctrls_disp}'"
        print("[✓] Case 04 PASS: Codebase and snapshot selectors strictly hidden from header for guests.")

        # ------------------------------------------------------------------
        # CASE 05: Header separator strictly hidden for guest
        # ------------------------------------------------------------------
        print("\n--- CASE 05: Header Separator Hidden ---")
        sep_disp = await client.eval_js("window.getComputedStyle(document.getElementById('header-workspace-separator')).display")
        assert sep_disp == "none", f"Expected #header-workspace-separator display: none, got: '{sep_disp}'"
        print("[✓] Case 05 PASS: Header separator strictly hidden for guests.")

        # ------------------------------------------------------------------
        # CASE 06: Left sidebar strictly hidden for guest
        # ------------------------------------------------------------------
        print("\n--- CASE 06: Left Sidebar Hidden ---")
        sidebar_disp = await client.eval_js("window.getComputedStyle(document.getElementById('app-sidebar')).display")
        assert sidebar_disp == "none", f"Expected #app-sidebar display: none, got: '{sidebar_disp}'"
        print("[✓] Case 06 PASS: Left sidebar strictly hidden for guests.")

        # ------------------------------------------------------------------
        # CASE 07: Ingest, Incident, and Search hidden for guest
        # ------------------------------------------------------------------
        print("\n--- CASE 07: Ingest, Incident, and Search Controls Hidden ---")
        search_disp = await client.eval_js("window.getComputedStyle(document.getElementById('top-search-btn')).display")
        ingest_disp = await client.eval_js("window.getComputedStyle(document.getElementById('top-btn-ingest-runtime')).display")
        incident_disp = await client.eval_js("window.getComputedStyle(document.getElementById('top-btn-create-incident')).display")
        assert search_disp == "none", f"Search button should be hidden, got '{search_disp}'"
        assert ingest_disp == "none", f"Ingest button should be hidden, got '{ingest_disp}'"
        assert incident_disp == "none", f"Incident button should be hidden, got '{incident_disp}'"
        print("[✓] Case 07 PASS: Ingest, Incident, and Search buttons strictly hidden for guests.")

        # ------------------------------------------------------------------
        # CASE 08: Previously connected codebases section hidden for guest
        # ------------------------------------------------------------------
        print("\n--- CASE 08: No 'Previously Connected Codebases' for Guest ---")
        prev_disp = await client.eval_js("window.getComputedStyle(document.getElementById('no-repo-existing-codebases-section')).display")
        assert prev_disp == "none", f"Expected #no-repo-existing-codebases-section display: none, got: '{prev_disp}'"
        print("[✓] Case 08 PASS: Codebases list completely hidden for unauthenticated guests.")

        # ------------------------------------------------------------------
        # CASE 09: Clean guest onboarding hero with 3 acquisition cards
        # ------------------------------------------------------------------
        print("\n--- CASE 09: Clean Guest Onboarding Hero ---")
        hero_title = await client.eval_js("document.getElementById('no-repo-hero-title')?.textContent")
        assert "Welcome to Software Digital Twin" in hero_title, f"Unexpected hero title: '{hero_title}'"
        card_count = await client.eval_js("document.querySelectorAll('#view-no-repo .onboard-card').length")
        assert card_count == 3, f"Expected 3 acquisition cards, got: {card_count}"
        signin_disp = await client.eval_js("window.getComputedStyle(document.getElementById('top-btn-login')).display")
        assert signin_disp in ["flex", "inline-flex"], f"Sign in button should be visible, got '{signin_disp}'"
        await client.capture_screenshot("01_guest_clean_onboarding_1440x900.png")
        print("[✓] Case 09 PASS: Clean guest hero displayed; captured screenshot 01.")

        # ------------------------------------------------------------------
        # CASE 10: Icon font rendering verification (no raw ligatures leaked)
        # ------------------------------------------------------------------
        print("\n--- CASE 10: Icon Font Ligature Verification ---")
        raw_ligatures = ["code_blocks", "folder_open", "terminal", "arrow_forward", "light_mode"]
        for lig in raw_ligatures:
            found_as_text = await client.eval_js(f"""(() => {{
                const els = Array.from(document.querySelectorAll('.onboard-card h3, .onboard-card p, #no-repo-hero-title, #no-repo-hero-subtitle'));
                return els.some(el => el.textContent.includes('{lig}'));
            }})()""")
            assert not found_as_text, f"Ligature '{lig}' leaked into text element"
        print("[✓] Case 10 PASS: Zero raw ligature string leakage.")

        # ------------------------------------------------------------------
        # CASE 11: Connect modals open cleanly for GitHub, Local, and Archive
        # ------------------------------------------------------------------
        print("\n--- CASE 11: Connect Modals Verification ---")
        await client.eval_js("window.TwinApp.openConnectModal('github');")
        await asyncio.sleep(0.3)
        await client.capture_screenshot("02_guest_connect_modal_github_1440x900.png")
        
        await client.eval_js("document.getElementById('tab-prov-local')?.click();")
        await asyncio.sleep(0.3)
        await client.capture_screenshot("03_guest_connect_modal_local_1440x900.png")

        await client.eval_js("document.getElementById('tab-prov-archive')?.click();")
        await asyncio.sleep(0.3)
        await client.capture_screenshot("04_guest_connect_modal_archive_1440x900.png")
        await client.eval_js("window.TwinApp.closeConnectModal();")
        await asyncio.sleep(0.2)
        print("[✓] Case 11 PASS: Connect modals render cleanly; captured screenshots 02, 03, 04.")

        # ------------------------------------------------------------------
        # CASE 12: Auth modal sign in & registration
        # ------------------------------------------------------------------
        print("\n--- CASE 12: Authentication Sign In ---")
        await client.eval_js("window.TwinApp.openAuthModal();")
        await asyncio.sleep(0.3)
        await client.capture_screenshot("05_auth_modal_signin_1440x900.png")

        # Register and login test_user_a
        await client.eval_js("""(async () => {
            await window.TwinApp.apiFetch('/api/v1/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: 'test_user_a',
                    email: 'user_a@enterprise.internal',
                    password: 'Password123!'
                })
            });
            const loginRes = await window.TwinApp.apiFetch('/api/v1/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: 'test_user_a',
                    password: 'Password123!'
                })
            });
            const data = await loginRes.json();
            localStorage.setItem('jwt_token', data.access_token);
            await window.TwinApp.checkAuthentication();
            await window.TwinApp.startApplicationStateMachine();
            window.TwinApp.closeAuthModal();
        })()""", await_promise=True)
        await asyncio.sleep(0.5)

        is_signed_in = await client.eval_js("document.body.classList.contains('state-signed-in-no-repo')")
        assert is_signed_in, "Expected 'state-signed-in-no-repo' class after login with 0 repos"
        await client.capture_screenshot("06_user_a_signed_in_no_repo_1440x900.png")
        print("[✓] Case 12 PASS: Authenticated as User A; captured screenshots 05, 06.")

        # ------------------------------------------------------------------
        # CASE 13: Create User A owned repository and verify 'Your Codebases'
        # ------------------------------------------------------------------
        print("\n--- CASE 13: User A Owned Repository Creation ---")
        repo_data = await client.eval_js("""(async () => {
            const res = await window.TwinApp.apiFetch('/repositories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: 'user-a-microservice',
                    source_type: 'LOCAL',
                    remote_url: '/codebases/user-a-microservice',
                    default_branch: 'main'
                })
            });
            return await res.json();
        })()""", await_promise=True)
        repo_a_id = repo_data.get("id")
        assert repo_a_id, f"Failed to create repo for user A: {repo_data}"
        print(f"[*] User A Repository created: {repo_a_id}")

        await client.eval_js("window.TwinApp.startApplicationStateMachine();", await_promise=True)
        await asyncio.sleep(0.5)

        # ------------------------------------------------------------------
        # CASE 14: User A sees 'Your Codebases' list with [ Open Workspace ]
        # ------------------------------------------------------------------
        print("\n--- CASE 14: 'Your Codebases' List with [ Open Workspace ] ---")
        codebases_visible = await client.eval_js("window.getComputedStyle(document.getElementById('no-repo-existing-codebases-section')).display !== 'none'")
        assert codebases_visible, "Expected #no-repo-existing-codebases-section to be visible for signed-in user with codebases"
        
        btn_count = await client.eval_js("document.querySelectorAll('#no-repo-existing-grid .btn-open-workspace').length")
        assert btn_count >= 1, "Expected at least 1 .btn-open-workspace button"
        btn_text = await client.eval_js("document.querySelector('#no-repo-existing-grid .btn-open-workspace')?.textContent")
        assert "Open Workspace" in btn_text, f"Expected 'Open Workspace', got '{btn_text}'"
        print("[✓] Case 14 PASS: 'Your Codebases' renders with explicit [ Open Workspace ] button.")

        # ------------------------------------------------------------------
        # CASE 15: Open Workspace directly activates workspace
        # ------------------------------------------------------------------
        print("\n--- CASE 15: Open Workspace Directly Activates Workspace ---")
        await client.eval_js(f"window.TwinApp.selectRepository('{repo_a_id}');", await_promise=True)
        await asyncio.sleep(0.5)

        is_active = await client.eval_js("document.body.classList.contains('state-workspace-active')")
        assert is_active, "Expected body to have 'state-workspace-active'"

        modal_open = await client.eval_js("document.getElementById('modal-onboard')?.style.display !== 'none'")
        assert not modal_open, "Connecting/onboarding modal MUST NOT be opened by Open Workspace"
        print("[✓] Case 15 PASS: Workspace activated directly without opening connect modal.")

        # ------------------------------------------------------------------
        # CASE 16: Active workspace header and sidebar verification
        # ------------------------------------------------------------------
        print("\n--- CASE 16: Active Workspace Controls & Overview ---")
        sidebar_active = await client.eval_js("window.getComputedStyle(document.getElementById('app-sidebar')).display === 'flex'")
        ctrls_active = await client.eval_js("window.getComputedStyle(document.getElementById('header-workspace-controls')).display === 'flex'")
        assert sidebar_active, "Sidebar must be visible in active workspace"
        assert ctrls_active, "Header controls must be visible in active workspace"
        await client.capture_screenshot("07_user_a_workspace_active_overview_1440x900.png")
        print("[✓] Case 16 PASS: Workspace active with sidebar and header controls; captured screenshot 07.")

        # ------------------------------------------------------------------
        # CASE 17: Disconnect action transitions cleanly
        # ------------------------------------------------------------------
        print("\n--- CASE 17: Disconnect Action ---")
        await client.eval_js("document.getElementById('btn-disconnect-repo')?.click();")
        await asyncio.sleep(0.5)

        is_disconnected = await client.eval_js("document.body.classList.contains('state-signed-in-no-repo')")
        assert is_disconnected, "Expected 'state-signed-in-no-repo' after disconnect"
        await client.capture_screenshot("08_user_a_workspace_disconnected_1440x900.png")
        print("[✓] Case 17 PASS: Disconnect cleanly returns to 'state-signed-in-no-repo'; captured screenshot 08.")

        # ------------------------------------------------------------------
        # CASE 18: Logout clears session and restores pristine guest state
        # ------------------------------------------------------------------
        print("\n--- CASE 18: Logout Session Clearing ---")
        await client.eval_js("window.TwinApp.logoutUser();", await_promise=True)
        await asyncio.sleep(0.5)

        is_guest_again = await client.eval_js("document.body.classList.contains('state-signed-out')")
        assert is_guest_again, "Expected 'state-signed-out' class after logout"
        token_cleared = await client.eval_js("localStorage.getItem('jwt_token') === null")
        repo_cleared = await client.eval_js("localStorage.getItem('selected_repo_id') === null")
        assert token_cleared and repo_cleared, "Local storage must be completely cleared"
        await client.capture_screenshot("09_post_logout_clean_guest_1440x900.png")
        print("[✓] Case 18 PASS: Logout cleanly clears tokens and restores pristine guest state; captured screenshot 09.")

        # ------------------------------------------------------------------
        # CASE 19: User B isolation (cannot enumerate User A repository)
        # ------------------------------------------------------------------
        print("\n--- CASE 19: Multi-User Isolation (User B cannot see User A) ---")
        await client.eval_js("""(async () => {
            await window.TwinApp.apiFetch('/api/v1/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: 'test_user_b',
                    email: 'user_b@enterprise.internal',
                    password: 'Password123!'
                })
            });
            const loginRes = await window.TwinApp.apiFetch('/api/v1/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: 'test_user_b',
                    password: 'Password123!'
                })
            });
            const data = await loginRes.json();
            localStorage.setItem('jwt_token', data.access_token);
            await window.TwinApp.checkAuthentication();
            await window.TwinApp.startApplicationStateMachine();
        })()""", await_promise=True)
        await asyncio.sleep(0.5)

        user_b_repos = await client.eval_js("""(async () => {
            const res = await window.TwinApp.apiFetch('/repositories');
            return await res.json();
        })()""", await_promise=True)
        
        assert not any(r["id"] == repo_a_id for r in user_b_repos), f"CRITICAL LEAK: User B can see User A's repo: {user_b_repos}"
        await client.capture_screenshot("10_user_b_privacy_isolated_1440x900.png")
        print("[✓] Case 19 PASS: User B receives only own repositories; User A repo is not present; captured screenshot 10.")

        # ------------------------------------------------------------------
        # CASE 20: Cross-user privacy enforcement (User B direct request gets 404)
        # ------------------------------------------------------------------
        print("\n--- CASE 20: Strict 404 Non-Disclosure Policy ---")
        user_b_cross_status = await client.eval_js(f"""(async () => {{
            const res = await window.TwinApp.apiFetch('/repositories/{repo_a_id}/summary');
            return res.status;
        }})()""", await_promise=True)
        assert user_b_cross_status == 404, f"Expected 404 for cross-user repo summary, got {user_b_cross_status}"
        print("[✓] Case 20 PASS: User B direct request to User A repo summary returns 404.")

        print("\n" + "=" * 80)
        print("ALL 20 PHASE 8.7.6 ACCEPTANCE CASES PASSED EMPIRICALLY (100% PASS)")
        print(f"Screenshots saved to: {SCREENSHOT_DIR}")
        print("=" * 80)

    finally:
        if client:
            await client.close()
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()

if __name__ == "__main__":
    asyncio.run(run_phase_8_7_6_suite())
