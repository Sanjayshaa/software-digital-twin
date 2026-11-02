with open("backend/app/static/twin.js", "r", encoding="utf-8") as f:
    js = f.read()

dup = """      // Sync 4 Overview KPI counters
      const ovCompCount = document.getElementById('ov-components-count');
      const ovApiCount = document.getElementById('ov-apis-count');
      const ovDepCount = document.getElementById('ov-deps-count');
      const ovTestCount = document.getElementById('ov-tests-count');
      const ovTestSub = document.getElementById('ov-tests-sub');

      if (ovCompCount) ovCompCount.textContent = (data.metrics?.files || data.metrics?.artifacts || 0);
      if (ovApiCount) ovApiCount.textContent = (data.metrics?.artifacts || 0);
      if (ovDepCount) ovDepCount.textContent = (data.metrics?.relationships || 0);
      if (ovTestCount) ovTestCount.textContent = (data.metrics?.tests || 0);
      if (ovTestSub) {
        if ((data.metrics?.tests || 0) === 0) {
          ovTestSub.textContent = '0 / 5 Linked · Unknown';
          ovTestSub.className = 'text-[11px] text-[#DC2626] font-semibold mt-1 truncate';
        } else {
          ovTestSub.textContent = `${data.metrics?.tests} Linked Tests`;
          ovTestSub.className = 'text-[11px] text-[#059669] font-semibold mt-1 truncate';
        }
      }"""

if dup in js:
    js = js.replace(dup, "")
    with open("backend/app/static/twin.js", "w", encoding="utf-8") as f:
        f.write(js)
    print("Removed duplicate declarations.")
else:
    print("ERROR: dup not found!")
