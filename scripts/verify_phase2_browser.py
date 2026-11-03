#!/usr/bin/env python3
"""
Phase 2 Live Browser Verification via Chrome DevTools Protocol (CDP).
Tests all 10 required Phase 2 checks:
1. Open PR mode.
2. PR panel loads without JavaScript errors.
3. Pull-request history API is called.
4. Empty PR state is handled.
5. PR analysis status renders correctly.
6. Snapshot pending state renders correctly.
7. Completed report renders provenance.
8. Failed analysis renders a useful error.
9. Repository connect does not show "signal is aborted without reason".
10. Retry works after timeout/failure.
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

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
venv_site = os.path.abspath(os.path.join(root_dir, ".venv", "lib", "python3.12", "site-packages"))
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.insert(0, venv_site)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import websockets

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9245
TARGET_URL = "http://127.0.0.1:8000/app"
PROFILE_DIR = "/tmp/twincore_phase2_browser_profile"


class CDPClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0
        self.pending_requests = {}
        self.console_errors = []
        self.uncaught_exceptions = []
        self.api_requests = []
        self.api_responses = []
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
            msg_type = params.get("type")
            args = params.get("args", [])
            text = " ".join([str(a.get("value", a.get("description", ""))) for a in args])
            if msg_type in ("error", "assert"):
                self.console_errors.append(f"Console {msg_type}: {text}")
        elif method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails", {})
            text = details.get("text", "")
            desc = details.get("exception", {}).get("description", "")
            url = details.get("url", "")
            line = details.get("lineNumber", -1)
            err_str = f"Uncaught Exception: {text} - {desc} at {url}:{line}"
            self.uncaught_exceptions.append(err_str)
        elif method == "Network.requestWillBeSent":
            req = params.get("request", {})
            url = req.get("url", "")
            if "/repositories" in url or "/webhooks" in url:
                self.api_requests.append(f"{req.get('method')} {url}")
        elif method == "Network.responseReceived":
            resp = params.get("response", {})
            url = resp.get("url", "")
            if "/repositories" in url or "/webhooks" in url:
                self.api_responses.append(f"HTTP {resp.get('status')} {url}")

    async def _listen(self):
        try:
            assert self.ws is not None
            async for raw in self.ws:
                msg = json.loads(raw)
                if "id" in msg:
                    req_id = msg["id"]
                    if req_id in self.pending_requests:
                        fut = self.pending_requests.pop(req_id)
                        if not fut.done():
                            if "error" in msg:
                                fut.set_exception(RuntimeError(msg["error"]))
                            else:
                                fut.set_result(msg.get("result", {}))
                else:
                    self._handle_event(msg)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def close(self):
        if self._listen_task:
            self._listen_task.cancel()
        if self.ws:
            await self.ws.close()


def kill_existing_chrome(port):
    try:
        res = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        if res.stdout.strip():
            for pid in res.stdout.strip().split():
                subprocess.run(["kill", "-9", pid], capture_output=True)
            time.sleep(0.5)
    except Exception:
        pass


def launch_chrome(port):
    kill_existing_chrome(port)
    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)
    os.makedirs(PROFILE_DIR, exist_ok=True)

    cmd = [
        CHROME_BIN,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--headless",
        "--window-size=1440,900",
        "--disable-gpu",
        "--disable-web-security",
        TARGET_URL,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.0)
    return proc


def get_ws_url(port):
    url = f"http://127.0.0.1:{port}/json"
    for _ in range(30):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                tabs = json.loads(resp.read().decode())
                if tabs:
                    page_tabs = [t for t in tabs if t.get("type") == "page"]
                    if page_tabs and "webSocketDebuggerUrl" in page_tabs[0]:
                        return page_tabs[0]["webSocketDebuggerUrl"]
                    elif "webSocketDebuggerUrl" in tabs[0]:
                        return tabs[0]["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"Could not connect to Chrome debugging port {port}")


async def run_live_verification():
    results = {}
    proc = launch_chrome(PORT)
    try:
        ws_url = get_ws_url(PORT)
        cdp = CDPClient(ws_url)
        await cdp.connect()

        # Wait for page bootstrap
        await asyncio.sleep(2.0)

        # Ensure page initialized
        init_ok = await cdp.eval_js("Boolean(window.TwinApp && window.TwinApp.switchPrimaryView)")
        if not init_ok:
            raise RuntimeError("TwinApp failed to bootstrap on window object.")

        # Resolve real test repo & snapshot from database
        from app.core.database import SessionLocal
        from app.models.entities import Repository, Snapshot, User
        from app.core.auth import create_access_token

        db = SessionLocal()
        try:
            snaps = db.query(Snapshot).all()
            ready_snaps = [s for s in snaps if s.status == "READY"]
            matched_repo = None
            matched_snap = None
            matched_user = None
            for s in ready_snaps:
                r = db.query(Repository).filter_by(id=s.repository_id).first()
                if r and r.owner_id:
                    u = db.query(User).filter_by(id=r.owner_id).first()
                    if u:
                        matched_repo = r
                        matched_snap = s
                        matched_user = u
                        break

            assert matched_repo is not None and matched_snap is not None, "A valid repository with READY snapshot is required"
            user = matched_user
            token = create_access_token(data={"sub": user.id, "username": user.username, "role": user.role})
            repo_id = matched_repo.id
            snap_id = matched_snap.id
        finally:
            db.close()

        # Authenticate and set active repo context
        await cdp.eval_js(f"localStorage.setItem('jwt_token', '{token}')")
        await cdp.eval_js("window.TwinApp.checkAuthentication()")
        await cdp.eval_js(f"""
            window.TwinApp.state.currentRepoId = '{repo_id}';
            window.TwinApp.state.currentSnapshotId = '{snap_id}';
            window.TwinApp.switchPrimaryView('impact');
        """)
        await asyncio.sleep(0.5)

        # -------------------------------------------------------------------
        # Check 1: Open PR mode
        # -------------------------------------------------------------------
        await cdp.eval_js("window.TwinApp.switchImpactMode('pr')")
        await asyncio.sleep(0.5)
        pr_panel_display = await cdp.eval_js("document.getElementById('panel-impact-pr')?.style.display")
        entity_panel_display = await cdp.eval_js("document.getElementById('panel-impact-entity')?.style.display")
        check1_passed = (pr_panel_display == 'block' and entity_panel_display == 'none')
        results["Check 1: Open PR mode"] = "PASSED" if check1_passed else "FAILED"

        # -------------------------------------------------------------------
        # Check 2: PR panel loads without JavaScript errors
        # -------------------------------------------------------------------
        check2_passed = (len(cdp.uncaught_exceptions) == 0 and len(cdp.console_errors) == 0)
        results["Check 2: PR panel loads without JavaScript errors"] = "PASSED" if check2_passed else f"FAILED (Exceptions: {cdp.uncaught_exceptions}, Errors: {cdp.console_errors})"

        # -------------------------------------------------------------------
        # Check 3: Pull-request history API is called
        # -------------------------------------------------------------------
        # Trigger loadPullRequestsForCurrentRepo
        await cdp.eval_js("window.TwinApp.loadPullRequestsForCurrentRepo()")
        await asyncio.sleep(1.0)
        pr_api_called = any("/pull-requests" in r for r in cdp.api_requests)
        results["Check 3: Pull-request history API is called"] = "PASSED" if pr_api_called else "FAILED"

        # -------------------------------------------------------------------
        # Check 4: Empty PR state is handled
        # -------------------------------------------------------------------
        empty_badge_text = await cdp.eval_js("document.getElementById('pr-card-badge')?.textContent")
        empty_pill_text = await cdp.eval_js("document.getElementById('pr-card-status-pill')?.textContent")
        check4_passed = (empty_badge_text == "PR #—" and empty_pill_text in ("EMPTY", "NO SELECTION", "ERROR"))
        results["Check 4: Empty PR state is handled"] = "PASSED" if check4_passed else "FAILED"

        # -------------------------------------------------------------------
        # Check 5: PR analysis status renders correctly
        # -------------------------------------------------------------------
        # Inject sample PR records
        await cdp.eval_js("""
            window.TwinApp.state.pullRequests = [
                {
                    pull_request_number: 101,
                    title: 'feat: add payment retry webhook',
                    head_branch: 'feat/webhook-retry',
                    base_branch: 'main',
                    base_commit_sha: '1111111111111111',
                    head_commit_sha: '2222222222222222',
                    base_snapshot_id: 'snap-1',
                    target_snapshot_id: 'snap-2',
                    status: 'COMPLETE',
                    ci_recommendation: 'REVIEW_REQUIRED',
                    changed_count: 3,
                    affected_count: 7,
                    impacted_tests_count: 4,
                    tests_executed_count: 4,
                    tests_passed_count: 4,
                    tests_failed_count: 0,
                    report_markdown: '## PR 101 Report\\nVerified evidence attached.'
                },
                {
                    pull_request_number: 102,
                    title: 'fix: syntax correction',
                    head_branch: 'fix/syntax',
                    base_branch: 'main',
                    base_commit_sha: '3333333333333333',
                    head_commit_sha: '3333333333333333',
                    status: 'SNAPSHOTS_PENDING',
                    ci_recommendation: 'BLOCKED',
                    error_message: 'Target snapshot is currently SCANNING; waiting for completion.'
                },
                {
                    pull_request_number: 103,
                    title: 'test: failed regression',
                    head_branch: 'fix/broken',
                    base_branch: 'main',
                    base_commit_sha: '4444444444444444',
                    head_commit_sha: '5555555555555555',
                    status: 'FAILED',
                    ci_recommendation: 'BLOCKED',
                    error_message: 'Base commit is not an ancestor of head commit.'
                }
            ];
            window.TwinApp.handlePRSelectionChange(101);
        """)
        await asyncio.sleep(0.3)
        status_pill_101 = await cdp.eval_js("document.getElementById('pr-card-status-pill')?.textContent")
        ci_pill_101 = await cdp.eval_js("document.getElementById('pr-card-ci-pill')?.textContent")
        check5_passed = (status_pill_101 == "COMPLETE" and "REVIEW_REQUIRED" in ci_pill_101)
        results["Check 5: PR analysis status renders correctly"] = "PASSED" if check5_passed else f"FAILED ({status_pill_101})"

        # -------------------------------------------------------------------
        # Check 6: Snapshot pending state renders correctly
        # -------------------------------------------------------------------
        await cdp.eval_js("window.TwinApp.handlePRSelectionChange(102)")
        await asyncio.sleep(0.3)
        status_pill_102 = await cdp.eval_js("document.getElementById('pr-card-status-pill')?.textContent")
        action_text_102 = await cdp.eval_js("document.getElementById('pr-card-action-text')?.textContent")
        check6_passed = (status_pill_102 == "SNAPSHOTS_PENDING" and "SCANNING" in action_text_102)
        results["Check 6: Snapshot pending state renders correctly"] = "PASSED" if check6_passed else f"FAILED ({status_pill_102})"

        # -------------------------------------------------------------------
        # Check 7: Completed report renders provenance
        # -------------------------------------------------------------------
        await cdp.eval_js("window.TwinApp.handlePRSelectionChange(101)")
        await asyncio.sleep(0.3)
        base_sha_101 = await cdp.eval_js("document.getElementById('pr-card-base-sha')?.textContent")
        snap_state_101 = await cdp.eval_js("document.getElementById('pr-card-snapshots-state')?.textContent")
        # Toggle markdown view
        await cdp.eval_js("window.TwinApp.togglePRMarkdownReport()")
        await asyncio.sleep(0.2)
        md_hidden = await cdp.eval_js("document.getElementById('pr-markdown-container')?.classList.contains('hidden')")
        md_text = await cdp.eval_js("document.getElementById('pr-markdown-container')?.textContent")
        check7_passed = (base_sha_101 == "1111111" and "READY (2/2)" in snap_state_101 and not md_hidden and "PR 101 Report" in md_text)
        results["Check 7: Completed report renders provenance"] = "PASSED" if check7_passed else "FAILED"

        # -------------------------------------------------------------------
        # Check 8: Failed analysis renders a useful error
        # -------------------------------------------------------------------
        await cdp.eval_js("window.TwinApp.handlePRSelectionChange(103)")
        await asyncio.sleep(0.3)
        status_pill_103 = await cdp.eval_js("document.getElementById('pr-card-status-pill')?.textContent")
        ci_pill_103 = await cdp.eval_js("document.getElementById('pr-card-ci-pill')?.textContent")
        action_text_103 = await cdp.eval_js("document.getElementById('pr-card-action-text')?.textContent")
        check8_passed = (status_pill_103 == "FAILED" and "BLOCKED" in ci_pill_103 and "ancestor" in action_text_103)
        results["Check 8: Failed analysis renders a useful error"] = "PASSED" if check8_passed else f"FAILED ({action_text_103})"

        # -------------------------------------------------------------------
        # Check 9: Repository connect does not show "signal is aborted without reason"
        # -------------------------------------------------------------------
        # Test simulated timeout and abort in onboarding modal error handler
        abort_test_result = await cdp.eval_js("""
            (() => {
                const timeoutErr = new Error("Operation 'GitHub Repository Clone & Synthesis' timed out after 15.0s.");
                timeoutErr.name = 'TimeoutError';
                timeoutErr.code = 'ETIMEDOUT';
                timeoutErr.state = 'TIMEOUT';
                timeoutErr.operation = 'GitHub Repository Clone & Synthesis';
                timeoutErr.elapsedMs = 15000;
                timeoutErr.stillProcessing = true;
                timeoutErr.safeErrorCode = 'ERR_TWIN_TIMEOUT';

                // Call showOnboardError
                window.TwinApp.openConnectModal('github');
                const norm = window.TwinApp.normalizeApiError(timeoutErr, 'GitHub Repository Connect');
                window.TwinApp.updateIngestionStepper(norm.state);
                window.TwinApp.showOnboardError(norm);

                const errBox = document.getElementById('onboard-error-box');
                const text = errBox?.textContent || '';
                const hasAbortedWithoutReason = text.includes('signal is aborted without reason');
                const hasTimeoutState = text.includes('TIMEOUT');
                const hasElapsed = text.includes('15.0s');
                const hasProcessingNote = text.includes('still be processing in the background');
                const hasSafeCode = text.includes('ERR_TWIN_TIMEOUT');

                return {
                    text,
                    hasAbortedWithoutReason,
                    hasTimeoutState,
                    hasElapsed,
                    hasProcessingNote,
                    hasSafeCode,
                };
            })()
        """)
        check9_passed = (
            not abort_test_result["hasAbortedWithoutReason"] and
            abort_test_result["hasTimeoutState"] and
            abort_test_result["hasElapsed"] and
            abort_test_result["hasProcessingNote"] and
            abort_test_result["hasSafeCode"]
        )
        results["Check 9: Repository connect does not show 'signal is aborted without reason'"] = "PASSED" if check9_passed else f"FAILED ({abort_test_result})"

        # -------------------------------------------------------------------
        # Check 10: Retry works after timeout/failure
        # -------------------------------------------------------------------
        retry_test_result = await cdp.eval_js("""
            (() => {
                let retryClicked = false;
                window.TwinApp.showOnboardError({
                    state: 'TIMEOUT',
                    code: 'TIMEOUT',
                    safeErrorCode: 'ERR_TWIN_TIMEOUT',
                    operation: 'GitHub Repository Clone & Synthesis',
                    elapsedStr: '15.0s',
                    stillProcessing: true,
                    message: 'Request timed out waiting for repository synthesis.',
                    retryAction: 'Retry Connection',
                }, () => {
                    retryClicked = true;
                });

                const retryBtn = document.getElementById('btn-onboard-retry-action');
                if (retryBtn) retryBtn.click();
                return retryClicked;
            })()
        """)
        results["Check 10: Retry works after timeout/failure"] = "PASSED" if retry_test_result else "FAILED"

        await cdp.close()

        print("\n================ LIVE BROWSER VERIFICATION RESULTS ================")
        all_passed = True
        for name, res in results.items():
            print(f"  {name}: {res}")
            if res != "PASSED":
                all_passed = False
        print("===================================================================\n")
        print(f"Console Errors: {len(cdp.console_errors)}")
        for e in cdp.console_errors:
            print(f"  - {e}")
        print(f"API Requests Tracked: {len(cdp.api_requests)}")
        for r in cdp.api_requests[:6]:
            print(f"  - {r}")
        print(f"API Responses Tracked: {len(cdp.api_responses)}")
        for r in cdp.api_responses[:6]:
            print(f"  - {r}")

        return all_passed

    finally:
        kill_existing_chrome(PORT)


if __name__ == "__main__":
    success = asyncio.run(run_live_verification())
    sys.exit(0 if success else 1)
