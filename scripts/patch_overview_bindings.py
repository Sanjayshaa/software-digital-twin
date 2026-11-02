with open("backend/app/static/twin.js", "r", encoding="utf-8") as f:
    js = f.read()

target = """      // Populate Discovered APIs
      const apiList = document.getElementById('ov-apis-list');
      const apiCount = document.getElementById('ov-api-count');
      if (apiList) {
        apiList.innerHTML = '';
        const apis = data.services_and_apis || [];
        if (apiCount) apiCount.textContent = apis.length;
        if (apis.length === 0) {
          apiList.innerHTML = '<span class="text-[#94A3B8]">0 declared HTTP API endpoints</span>';
        } else {
          apis.slice(0, 5).forEach(api => {
            const div = document.createElement('div');
            div.className = 'flex items-center justify-between gap-1 py-0.5 border-b border-[#F8FAFC] truncate';
            div.innerHTML = `
              <span class="font-mono text-[#059669] truncate" title="${escapeHtml(api.path)}">${escapeHtml(api.http_method)} ${escapeHtml(api.path)}</span>
              <span class="text-[9px] text-[#64748B] shrink-0">${escapeHtml(api.location.split(':')[0].split('/').pop())}</span>
            `;
            apiList.appendChild(div);
          });
        }
      }"""

replacement = """      // Populate Discovered APIs
      const apiList = document.getElementById('ov-apis-list');
      const apiCount = document.getElementById('ov-api-count');
      if (apiList) {
        apiList.innerHTML = '';
        const apis = data.services_and_apis || [];
        if (apiCount) apiCount.textContent = apis.length;
        if (apis.length === 0) {
          apiList.innerHTML = '<span class="text-[#94A3B8]">0 declared HTTP API endpoints</span>';
        } else {
          apis.slice(0, 5).forEach(api => {
            const div = document.createElement('div');
            div.className = 'flex items-center justify-between gap-1 py-0.5 border-b border-[#F8FAFC] truncate';
            div.innerHTML = `
              <span class="font-mono text-[#059669] truncate" title="${escapeHtml(api.path)}">${escapeHtml(api.http_method)} ${escapeHtml(api.path)}</span>
              <span class="text-[9px] text-[#64748B] shrink-0">${escapeHtml(api.location.split(':')[0].split('/').pop())}</span>
            `;
            apiList.appendChild(div);
          });
        }
      }

      // Populate Discovered Database Entities
      const dbList = document.getElementById('ov-database-list');
      const dbCount = document.getElementById('ov-db-count');
      if (dbList) {
        dbList.innerHTML = '';
        const dbs = data.database_entities || [];
        if (dbCount) dbCount.textContent = dbs.length;
        if (dbs.length === 0) {
          dbList.innerHTML = '<span class="text-[#94A3B8]">0 declared ORM or database tables detected</span>';
        } else {
          dbs.slice(0, 5).forEach(db => {
            const div = document.createElement('div');
            div.className = 'flex items-center justify-between gap-1 py-0.5 border-b border-[#F8FAFC] truncate';
            div.innerHTML = `
              <span class="font-mono text-[#7C3AED] truncate" title="${escapeHtml(db.name)}">${escapeHtml(db.name)}</span>
              <span class="text-[9px] text-[#64748B] shrink-0">${escapeHtml((db.file_path || '').split('/').pop())}</span>
            `;
            dbList.appendChild(div);
          });
        }
      }

      // Sync 4 Overview KPI counters
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

if target in js:
    js = js.replace(target, replacement, 1)
    with open("backend/app/static/twin.js", "w", encoding="utf-8") as f:
        f.write(js)
    print("Successfully patched overview bindings in twin.js.")
else:
    print("ERROR: Target in twin.js not found!")
