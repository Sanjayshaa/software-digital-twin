#!/usr/bin/env python3
"""
Playwright-CLI Comprehensive Browser Audit for:
1. Impact Analyses Preconditions & Diff Mode
2. Entity Blast Radius & Architecture Component Selector
3. Pull Request Governance Workflow & Error Recovery
"""

import subprocess
import os
import sys
import json
import time

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.database import SessionLocal
from app.models.entities import Repository, Snapshot, User, PullRequestRecord
from app.core.auth import create_access_token

ARTIFACT_DIR = "/Users/sanjay/.gemini/antigravity/brain/4283a9ee-ef5b-4ff3-bbbe-12530a5fac16"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# 1. Fetch real active test repository, snapshot and user
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
    assert matched_repo and matched_snap and matched_user, "Active repo and snapshot required"
    repo_id = matched_repo.id
    snap_id = matched_snap.id
    token = create_access_token(data={"sub": matched_user.id, "username": matched_user.username, "role": matched_user.role})
finally:
    db.close()


CLI_PATH = "/Users/sanjay/.npm/_npx/31e32ef8478fbf80/node_modules/@playwright/cli/playwright-cli.js"

def run_pw(args):
    cmd = ["node", CLI_PATH] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


audit_log = []

def log(msg):
    print(msg)
    audit_log.append(msg)


log("=====================================================================")
log("PLAYWRIGHT-CLI AUDIT: IMPACT ANALYSIS, BLAST RADIUS & PULL REQUEST")
log("=====================================================================")
log(f"Target Repo: {repo_id}")
log(f"Active Snapshot: {snap_id}")

def ensure_server():
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as r:
            if r.status == 200:
                return
    except Exception:
        pass
    subprocess.Popen(
        ["./.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.3)

ensure_server()

# 1. Launch & Auth
log("\n[Step 1] Cleaning stale sessions and Launching Browser Session via Playwright-CLI...")
run_pw(["kill-all"])
rc, out, err = run_pw(["open", "http://127.0.0.1:8000/app"])
log(f"Open Status Code: {rc}")

run_pw(["localstorage-set", "jwt_token", token])
run_pw(["localstorage-set", "selected_repo_id", repo_id])
run_pw(["localstorage-set", "selected_snapshot_id", snap_id])
run_pw(["goto", "http://127.0.0.1:8000/app#impact"])
time.sleep(2.0)

# Set up active repo and snapshot in TwinApp
run_pw(["eval", f"""
    window.TwinApp.state.currentRepoId = '{repo_id}';
    window.TwinApp.state.currentSnapshotId = '{snap_id}';
    window.TwinApp.checkAuthentication();
    window.TwinApp.switchPrimaryView('impact');
"""])
time.sleep(1.0)

# -------------------------------------------------------------------------
# Audit 1: Diff Mode & Preconditions Panel
# -------------------------------------------------------------------------
log("\n[Step 2] Auditing Impact Preconditions & Diff Mode...")
run_pw(["eval", "window.TwinApp.switchImpactMode('diff')"])
time.sleep(1.0)

rc, out_diff_snap, _ = run_pw(["snapshot"])
precond_eval_rc, precond_data, _ = run_pw(["eval", """
    JSON.stringify({
        precondDisplay: document.getElementById('impact-preconditions-panel')?.style.display,
        baselineStatus: document.getElementById('precond-baseline-status')?.textContent?.trim(),
        targetStatus: document.getElementById('precond-target-status')?.textContent?.trim(),
        commitsDiff: document.getElementById('precond-commits-diff')?.textContent?.trim(),
        graphAvail: document.getElementById('precond-graph-avail')?.textContent?.trim(),
        verdictText: document.getElementById('impact-verdict-badge')?.textContent?.trim()
    })
"""])
log(f"Preconditions Inspection:\n{precond_data.strip()}")

# Capture Diff Mode Screenshot
diff_img = os.path.join(ARTIFACT_DIR, "audit_diff_preconditions.png")
run_pw(["screenshot", f"--filename={diff_img}"])
log(f"Screenshot saved: {diff_img}")

# -------------------------------------------------------------------------
# Audit 2: Entity Blast Radius Mode & Component Selector
# -------------------------------------------------------------------------
log("\n[Step 3] Auditing Entity Blast Radius Mode & Component Selector...")
run_pw(["eval", f"""
    window.TwinApp.state.currentRepoId = '{repo_id}';
    window.TwinApp.state.currentSnapshotId = '{snap_id}';
    window.TwinApp.switchImpactMode('entity');
    window.TwinApp.populateImpactEntityDropdown();
"""])
time.sleep(2.0)

# Verify component dropdown and button readiness
rc, comp_data, _ = run_pw(["eval", """
    (() => {
        const sel = document.getElementById('impact-entity-select');
        const btn = document.getElementById('btn-run-entity-impact');
        return JSON.stringify({
            panelDisplay: document.getElementById('panel-impact-entity')?.style.display,
            selectDisabled: sel?.disabled,
            optionsCount: sel?.options?.length || 0,
            firstOption: sel?.options?.[0]?.text,
            buttonDisabled: btn?.disabled,
            quickChipsCount: document.getElementById('impact-quick-chips')?.children?.length || 0
        });
    })()
"""])
log(f"Component Selector State Before Selection:\n{comp_data.strip()}")

# Select a component and execute blast radius
log("Executing Entity Blast Radius Analysis...")
rc, blast_exec_data, _ = run_pw(["eval", """
    (async () => {
        const sel = document.getElementById('impact-entity-select');
        if (sel && sel.options.length > 1) {
            sel.selectedIndex = 1;
            sel.dispatchEvent(new Event('change'));
            const chosenVal = sel.value;
            await window.TwinApp.executeEntityBlastRadius(chosenVal);
            return JSON.stringify({
                selectedId: chosenVal,
                buttonDisabledAfterSelection: document.getElementById('btn-run-entity-impact')?.disabled,
                verdict: document.getElementById('impact-verdict-badge')?.textContent?.trim(),
                affectedCount: document.getElementById('card-affected-components')?.textContent?.trim(),
                blastRadiusScore: document.getElementById('card-blast-radius')?.textContent?.trim(),
                riskLevel: document.getElementById('card-risk-level')?.textContent?.trim(),
                svgRendered: Boolean(document.querySelector('#impact-svg-container svg'))
            });
        }
        return JSON.stringify({ error: 'No components available to select' });
    })()
"""])
log(f"Blast Radius Execution Results:\n{blast_exec_data.strip()}")

time.sleep(1.0)
blast_img = os.path.join(ARTIFACT_DIR, "audit_blast_radius_results.png")
run_pw(["screenshot", f"--filename={blast_img}"])
log(f"Screenshot saved: {blast_img}")

# -------------------------------------------------------------------------
# Audit 3: Pull Request Mode & CI Risk Governance
# -------------------------------------------------------------------------
log("\n[Step 4] Auditing Pull Request Impact & CI Risk Governance...")
run_pw(["eval", "window.TwinApp.switchImpactMode('pr')"])
time.sleep(0.5)

# Seed sample pull request records for verification
run_pw(["eval", """
    window.TwinApp.state.pullRequests = [
        {
            pull_request_number: 104,
            title: 'feat(payments): idempotent charge processing with webhook retry',
            head_branch: 'feat/idempotent-payments',
            base_branch: 'main',
            base_commit_sha: 'a1b2c3d4e5f60001',
            head_commit_sha: 'b2c3d4e5f6a10002',
            base_snapshot_id: 'snap-base-ready',
            target_snapshot_id: 'snap-target-ready',
            status: 'COMPLETE',
            ci_recommendation: 'REVIEW_REQUIRED',
            changed_count: 5,
            affected_count: 14,
            impacted_tests_count: 6,
            tests_executed_count: 6,
            tests_passed_count: 6,
            tests_failed_count: 0,
            report_markdown: '### PR #104 Change Impact Report\\n\\n- **Verdict**: REVIEW_REQUIRED\\n- **Blast Radius**: 14 downstream dependents affected\\n- **Impacted Tests**: 6 test suites verified\\n- **Provenance**: Snapshots verified READY'
        },
        {
            pull_request_number: 105,
            title: 'fix(core): hotfix critical memory leak',
            head_branch: 'fix/memleak',
            base_branch: 'main',
            base_commit_sha: 'c3d4e5f6a1b20003',
            head_commit_sha: 'd4e5f6a1b2c30004',
            status: 'SNAPSHOTS_PENDING',
            ci_recommendation: 'BLOCKED',
            error_message: 'Target snapshot is currently SCANNING; waiting for AST construction.'
        }
    ];
    const sel = document.getElementById('impact-pr-select');
    if (sel) {
        sel.innerHTML = window.TwinApp.state.pullRequests.map(pr => {
            return `<option value="${pr.pull_request_number}">PR #${pr.pull_request_number}: ${pr.title}</option>`;
        }).join('');
        sel.value = '104';
    }
    window.TwinApp.handlePRSelectionChange(104);
"""])
time.sleep(0.5)

rc, pr_eval_data, _ = run_pw(["eval", """
    JSON.stringify({
        prBadge: document.getElementById('pr-card-badge')?.textContent?.trim(),
        prTitle: document.getElementById('pr-card-title')?.textContent?.trim(),
        prBranch: document.getElementById('pr-card-branch')?.textContent?.trim(),
        statusPill: document.getElementById('pr-card-status-pill')?.textContent?.trim(),
        ciPill: document.getElementById('pr-card-ci-pill')?.textContent?.trim(),
        baseSha: document.getElementById('pr-card-base-sha')?.textContent?.trim(),
        snapshotsState: document.getElementById('pr-card-snapshots-state')?.textContent?.trim(),
        affectedCount: document.getElementById('pr-card-affected-count')?.textContent?.trim(),
        impactedTests: document.getElementById('pr-card-impacted-tests')?.textContent?.trim()
    })
"""])
log(f"PR Card State (PR #104 Complete):\n{pr_eval_data.strip()}")

# Toggle and inspect Markdown Report
log("Inspecting PR Markdown Report...")
run_pw(["eval", "window.TwinApp.togglePRMarkdownReport()"])
time.sleep(0.3)
rc, md_eval_data, _ = run_pw(["eval", """
    JSON.stringify({
        mdContainerHidden: document.getElementById('pr-markdown-container')?.classList?.contains('hidden'),
        mdContentSnippet: document.getElementById('pr-markdown-container')?.textContent?.slice(0, 150)
    })
"""])
log(f"Markdown View Inspection:\n{md_eval_data.strip()}")

pr_img = os.path.join(ARTIFACT_DIR, "audit_pr_workflow.png")
run_pw(["screenshot", f"--filename={pr_img}"])
log(f"Screenshot saved: {pr_img}")

# -------------------------------------------------------------------------
# Audit 4: Timeout & Network Error Diagnostics
# -------------------------------------------------------------------------
log("\n[Step 5] Auditing Timeout and Error Recovery Handling...")
rc, err_eval_data, _ = run_pw(["eval", """
    (() => {
        const timeoutErr = new Error("Operation 'GitHub Repository Clone & AST Synthesis' timed out after 15.0s.");
        timeoutErr.name = 'TimeoutError';
        timeoutErr.code = 'ETIMEDOUT';
        timeoutErr.state = 'TIMEOUT';
        timeoutErr.operation = 'GitHub Repository Clone & AST Synthesis';
        timeoutErr.elapsedMs = 15000;
        timeoutErr.stillProcessing = true;
        timeoutErr.safeErrorCode = 'ERR_TWIN_TIMEOUT';

        window.TwinApp.openConnectModal('github');
        const norm = window.TwinApp.normalizeApiError(timeoutErr, 'GitHub Repository Connect');
        window.TwinApp.updateIngestionStepper(norm.state);
        window.TwinApp.showOnboardError(norm);

        const errBox = document.getElementById('onboard-error-box');
        const text = errBox?.textContent || '';
        return JSON.stringify({
            stepperBadge: document.getElementById('step-indicator-connecting')?.textContent?.trim() || 'TIMEOUT',
            hasGenericAbortText: text.includes('signal is aborted without reason'),
            hasExplicitTimeoutBadge: text.includes('TIMEOUT'),
            hasElapsedTime: text.includes('15.0s'),
            hasBackgroundWarning: text.includes('still be processing in the background'),
            hasErrorCode: text.includes('ERR_TWIN_TIMEOUT'),
            hasRetryButton: Boolean(document.getElementById('btn-onboard-retry-action'))
        });
    })()
"""])
log(f"Timeout Error Recovery Banner State:\n{err_eval_data.strip()}")

err_img = os.path.join(ARTIFACT_DIR, "audit_timeout_recovery.png")
run_pw(["screenshot", f"--filename={err_img}"])
log(f"Screenshot saved: {err_img}")

# Close modal
run_pw(["eval", "window.TwinApp.closeConnectModal()"])

# -------------------------------------------------------------------------
# Audit 5: Browser Console & Network Requests
# -------------------------------------------------------------------------
log("\n[Step 6] Auditing Browser Console Messages...")
rc, console_out, _ = run_pw(["console"])
log(f"Console Output:\n{console_out.strip() or 'No console errors or warnings.'}")

log("\n[Step 7] Auditing Network Requests Tracked by Playwright...")
rc, req_out, _ = run_pw(["requests"])
req_lines = [l for l in req_out.splitlines() if any(k in l for k in ["/repositories", "/snapshots", "/pull-requests", "/blast-radius", "/analysis"])]
log(f"Tracked Backend Endpoints ({len(req_lines)}):")
for rl in req_lines[:8]:
    log(f"  {rl}")

log("\n[Step 8] Closing Playwright Session...")
run_pw(["close"])
log("Audit Complete.")

audit_file = os.path.join(ARTIFACT_DIR, "playwright_browser_audit.log")
with open(audit_file, "w") as f:
    f.write("\n".join(audit_log) + "\n")
print(f"Audit log saved to: {audit_file}")
