import asyncio
import json
import os
import shutil
import subprocess
import time
import urllib.request
import websockets

PORT = 9238
CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DIR = "/tmp/cdp_test_declare_inc"

if os.path.exists(USER_DIR):
    shutil.rmtree(USER_DIR, ignore_errors=True)

proc = subprocess.Popen([
    CHROME_BIN,
    "--headless=new",
    f"--remote-debugging-port={PORT}",
    "--window-size=1440,900",
    "--no-first-run",
    "--disable-extensions",
    f"--user-data-dir={USER_DIR}"
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.2)

async def test():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as res:
        tabs = json.loads(res.read().decode())
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    ws_url = page_tabs[0]["webSocketDebuggerUrl"]
    ws = await websockets.connect(ws_url)
    
    msg_id = 0
    async def send(method, params=None):
        nonlocal msg_id
        msg_id += 1
        await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                return data

    await send("Page.enable")
    await send("Runtime.enable")
    await send("Emulation.setDeviceMetricsOverride", {
        "width": 1440,
        "height": 900,
        "deviceScaleFactor": 1,
        "mobile": False
    })
    
    await send("Page.navigate", {"url": "http://localhost:8000"})
    await asyncio.sleep(2.0)
    
    # 1. Select LAB-RECORD-SYSTEM
    await send("Runtime.evaluate", {
        "expression": "window.TwinApp.selectRepository('1dafa8df-4083-47b4-9021-d8a47a897aa8');",
        "returnByValue": True
    })
    await asyncio.sleep(2.0)
    
    # 2. Open incident modal
    await send("Runtime.evaluate", {
        "expression": "window.openCreateIncidentModal();",
        "returnByValue": True
    })
    await asyncio.sleep(0.5)
    
    # 3. Fill in fields exactly as user did and click Declare & Investigate
    await send("Runtime.evaluate", {
        "expression": """(() => {
            document.getElementById('input-incident-title').value = 'High Latency & 500 Errors on Record Synchronization';
            document.getElementById('input-incident-severity').value = 'critical';
            document.getElementById('input-incident-component').value = 'api/v1/records/export';
            document.getElementById('input-incident-desc').value = 'Database connection exhaustion and timeouts during batch export';
            document.getElementById('modal-incident-submit-btn').click();
        })()""",
        "returnByValue": True
    })
    print("[*] Clicked Declare & Investigate")
    await asyncio.sleep(3.0)
    
    # 4. Check if modal is closed and incident view is active with investigation
    status = await send("Runtime.evaluate", {
        "expression": """(() => {
            const modal = document.getElementById('modal-create-incident');
            const modalDisplay = modal ? modal.style.display : null;
            const incView = document.getElementById('view-incidents');
            const incDisplay = incView ? incView.style.display : null;
            const incList = document.getElementById('incidents-list-container')?.textContent || '';
            const ws = document.getElementById('incident-investigation-workspace');
            const wsDisplay = ws ? ws.style.display : null;
            const report = document.getElementById('investigation-report-container')?.textContent || '';
            return {
                modalClosed: modalDisplay === 'none',
                incViewActive: incDisplay === 'block',
                hasNewInc: incList.includes('High Latency'),
                workspaceVisible: wsDisplay === 'block',
                hasReport: report.length > 50
            };
        })()""",
        "returnByValue": True
    })
    res_val = status.get("result", {}).get("result", {}).get("value")
    print("Verification Result:", json.dumps(res_val, indent=2))
    assert res_val.get("modalClosed") is True, "Modal should be closed after declaring"
    assert res_val.get("incViewActive") is True, "Incidents view should be active"
    assert res_val.get("hasNewInc") is True, "New incident should appear in incidents list"
    assert res_val.get("workspaceVisible") is True, "Investigation workspace should be visible"
    print("[✓] Incident declared, investigated, and rendered successfully!")
    await ws.close()

try:
    asyncio.run(test())
finally:
    proc.terminate()
