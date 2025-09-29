// presence_table.js (safe rewrite)
// Keep fetchPresenceLogs / escapeHTML / formatDateTime semantics, but ensure every <tr> has same number of <td> as <th>.

async function fetchPresenceLogs() {
  try {
    const response = await fetch('/get-presence-logs/', { credentials: 'same-origin' });

    if (!response.ok) {
      const text = await response.text();
      console.error("Fetch failed:", response.status, text.slice(0, 200));
      return [];
    }

    const ct = response.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
      const text = await response.text();
      console.error("Expected JSON but got:", ct, "Preview:", text.slice(0, 200));
      return [];
    }

    const logs = await response.json();
    console.log("📋 All logs:", logs);
    return Array.isArray(logs) ? logs : [];
  } catch (error) {
    console.error("Error fetching presence logs:", error);
    return [];
  }
}

function escapeHTML(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

function formatDateTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);

  if (isNaN(d)) {
    // fallback if ts is not ISO format
    return escapeHTML(ts);
  }

  const options = {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true
  };

  return d.toLocaleString("en-US", options);
}

// Helper to get CSRF token (tries DOM token then cookie)
function getCSRFToken() {
  // prefer hidden input token if present
  const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
  if (tokenInput && tokenInput.value) return tokenInput.value;

  // fallback to cookie (Django default name)
  const name = 'csrftoken';
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : '';
}

// Renders rows; ensures each <tr> has the first column (checkbox cell)
// - For Guest rows: first <td> contains checkbox (.log-checkbox value=log.id)
// - For Student rows: first <td> is empty (keeps alignment)
function renderPresenceTable(logs) {
  const searchEl = document.getElementById("searchPresence");
  const query = (searchEl ? searchEl.value : "").toLowerCase();
  const tbody = document.getElementById("presenceTableBody");
  if (!tbody) return;

  tbody.innerHTML = "";

  const filtered = logs.filter(log => {
    const ts = String(log.logs_timestamp || "");
    return (
      String(log.name || "").toLowerCase().includes(query) ||
      String(log.student_id || "").toLowerCase().includes(query) ||
      ts.toLowerCase().includes(query) ||
      String(log.role || "").toLowerCase().includes(query) ||
      String(log.department || "").toLowerCase().includes(query) ||
      String(log.purpose || "").toLowerCase().includes(query)
    );
  });

  if (filtered.length === 0) {
    // Ensure colspan matches number of columns in header (9)
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">No presence records found.</td></tr>`;
    return;
  }

  const today = new Date().toISOString().split("T")[0];

  filtered.forEach(log => {
    const ts = String(log.logs_timestamp || "");
    const badgeClass = (String(log.role || "").toLowerCase() === "student") ? 'bg-dark text-light' : 'bg-secondary text-light';
    const logDateOnly = ts.split(" ")[0];
    const isToday = logDateOnly === today;

    const wasEdited = Boolean(log.edited);
    const editable = isToday && (String(log.role || "").toLowerCase() === "guest" || (String(log.role || "").toLowerCase() === "student" && !wasEdited));

    let purposeCell = "";
    if (String(log.role || "").toLowerCase() === "guest" && editable) {
      purposeCell = `<input type="text" class="form-control form-control-sm guest-purpose-input" 
                        value="${escapeHTML(log.purpose)}" data-log-id="${escapeHTML(log.id)}" />`;
    } else if (String(log.role || "").toLowerCase() === "student" && editable) {
      purposeCell = `
        <select class="form-select form-select-sm purpose-select" data-log-id="${escapeHTML(log.id)}">
          <option value="class" ${log.purpose === 'class' ? 'selected' : ''}>class</option>
          <option value="study" ${log.purpose === 'study' ? 'selected' : ''}>study</option>
          <option value="appointment" ${log.purpose === 'appointment' ? 'selected' : ''}>appointment</option>
          <option value="event" ${log.purpose === 'event' ? 'selected' : ''}>event</option>
        </select>`;
    } else {
      purposeCell = escapeHTML(log.purpose || '—');
    }

    const snapshotCell = (String(log.role || "").toLowerCase() === "guest" && log.snapshot)
      ? `<a href="${escapeHTML(log.snapshot)}" target="_blank">
           <img src="${escapeHTML(log.snapshot)}" alt="Guest Snapshot" class="img-thumbnail" style="width: 60px; height: 60px;" />
         </a>`
      : '—';

    const actionCell = String(log.role || "").toLowerCase() === "guest"
      ? `<button class="btn btn-sm btn-danger delete-log-btn" data-log-id="${escapeHTML(log.id)}">Delete</button>`
      : ''; // students have no delete button

    // Build the row HTML with FIRST td reserved for checkbox or spacer
    const checkboxCell = (String(log.role || "").toLowerCase() === "guest")
      ? `<td class="align-middle text-center"><input type="checkbox" class="form-check-input log-checkbox" value="${escapeHTML(log.id)}" aria-label="Select guest log ${escapeHTML(log.id)}"></td>`
      : `<td class="align-middle text-center"></td>`;

    const rowHTML = `
      <tr>
        ${checkboxCell}
        <td>${escapeHTML(log.student_id)}</td>
        <td>${escapeHTML(log.name)}</td>
        <td>${formatDateTime(ts)}</td>
        <td><span class="badge ${badgeClass}">${escapeHTML(log.role)}</span></td>
        <td>${escapeHTML(log.department)}</td>
        <td>${purposeCell}</td>
        <td>${snapshotCell}</td>
        <td>${actionCell}</td>
      </tr>
    `;

    tbody.insertAdjacentHTML("beforeend", rowHTML);
  });

  // wire up dynamic controls after DOM insertion
  bindPurposeEditEvents();
  bindDeleteButtons();
  bindBulkDeleteCheckboxes(); // ensure checkboxes and bulk delete state are bound
}

// Purpose edit events (unchanged logic, but uses fetch with CSRF)
function bindPurposeEditEvents() {
  document.querySelectorAll('.purpose-select').forEach(select => {
    select.addEventListener('change', async (e) => {
      const logId = e.target.getAttribute('data-log-id');
      const newPurpose = e.target.value;

      const response = await fetch(`/update-purpose/${logId}/`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ purpose: newPurpose })
      });

      const result = await response.json();
      alert(result.message);
      if (result.status === 'success') {
        const logs = await fetchPresenceLogs();
        renderPresenceTable(logs);
      }
    });
  });

  document.querySelectorAll('.guest-purpose-input').forEach(input => {
    input.addEventListener('blur', async (e) => {
      const logId = e.target.getAttribute('data-log-id');
      const newPurpose = e.target.value.trim();
      if (!newPurpose) return;

      const response = await fetch(`/update-purpose/${logId}/`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ purpose: newPurpose })
      });

      const result = await response.json();
      alert(result.message);
      if (result.status === 'success') {
        const logs = await fetchPresenceLogs();
        renderPresenceTable(logs);
      }
    });
  });
}

// Individual delete (keeps original behavior, adds CSRF)
async function bindDeleteButtons() {
  document.querySelectorAll('.delete-log-btn').forEach(button => {
    // remove existing listeners if any (defensive)
    button.replaceWith(button.cloneNode(true));
  });

  document.querySelectorAll('.delete-log-btn').forEach(button => {
    button.addEventListener('click', async () => {
      const logId = button.getAttribute('data-log-id');
      const confirmed = confirm("Are you sure you want to delete this guest log?");
      if (!confirmed) return;

      const response = await fetch(`/delete-guest-log/${logId}/`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken()
        },
      });

      const result = await response.json();
      alert(result.message);
      if (result.status === 'success') {
        const logs = await fetchPresenceLogs();
        renderPresenceTable(logs);
      }
    });
  });
}

// Bulk-delete wiring: selectAll checkbox + bulk delete button
function bindBulkDeleteCheckboxes() {
  // wire select all checkbox
  const selectAll = document.getElementById("selectAllLogs");
  if (selectAll) {
    selectAll.onchange = () => {
      const checkboxes = document.querySelectorAll(".log-checkbox");
      checkboxes.forEach(cb => cb.checked = selectAll.checked);
      toggleBulkDeleteBtn();
    };
  }

  // individual checkboxes toggle
  document.querySelectorAll(".log-checkbox").forEach(cb => {
    cb.onchange = () => {
      // if any unchecked, uncheck selectAll
      const all = document.querySelectorAll(".log-checkbox");
      const checked = document.querySelectorAll(".log-checkbox:checked");
      if (selectAll) selectAll.checked = (checked.length === all.length && all.length > 0);
      toggleBulkDeleteBtn();
    };
  });

  // bind bulk delete button
  const bulkDeleteBtn = document.getElementById("bulkDeleteBtn");
  if (bulkDeleteBtn) {
    bulkDeleteBtn.onclick = async () => {
      const selectedIds = Array.from(document.querySelectorAll(".log-checkbox:checked")).map(cb => cb.value);
      if (selectedIds.length === 0) {
        alert("Please select at least one guest log to delete.");
        return;
      }
      if (!confirm(`Delete ${selectedIds.length} selected guest log(s)?`)) return;

      const response = await fetch(`/delete-multiple-guest-logs/`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ ids: selectedIds }),
      });

      const result = await response.json();
      alert(result.message);
      if (result.status === 'success') {
        const logs = await fetchPresenceLogs();
        renderPresenceTable(logs);
      }
    };
  }

  // initial button state
  toggleBulkDeleteBtn();
}

function toggleBulkDeleteBtn() {
  const bulkDeleteBtn = document.getElementById("bulkDeleteBtn");
  if (!bulkDeleteBtn) return;
  const anyChecked = document.querySelectorAll(".log-checkbox:checked").length > 0;
  bulkDeleteBtn.disabled = !anyChecked;
}

// MAIN: load logs and render once
document.addEventListener('DOMContentLoaded', async () => {
  const logs = await fetchPresenceLogs();
  renderPresenceTable(logs);

  const searchEl = document.getElementById("searchPresence");
  if (searchEl) {
    searchEl.addEventListener("input", () => {
      renderPresenceTable(logs);
    });
  }

  // Backup button logic (kept from your original)
  const backupBtn = document.getElementById("backup-btn");
  if (backupBtn) {
    backupBtn.addEventListener("click", () => {
      if (!confirm("Are you sure you want to backup all guest snapshots to Google Drive?")) return;

      backupBtn.disabled = true;
      backupBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Backing up...';

      fetch("/backup-images/")
        .then(r => r.json())
        .then(data => {
          let msg = `✅ Backup complete!\n\nUploaded: ${data.uploaded.length}\nDeleted locally: ${data.deleted.length}`;
          if (data.errors && data.errors.length > 0) {
            msg += `\n\n⚠️ Errors:\n${data.errors.join("\n")}`;
          }
          alert(msg);
          backupBtn.disabled = false;
          backupBtn.innerHTML = 'Backup Guest Snapshots to Google Drive <span id="snapshot-count" class="badge bg-light text-dark ms-2">0</span>';
          updateSnapshotCount(); // refresh count after backup
        })
        .catch(() => {
          alert("❌ Unexpected error during backup.");
          backupBtn.disabled = false;
        });
    });
  }

  async function updateSnapshotCount() {
    try {
      const res = await fetch("/count-guest-snapshots/");
      const data = await res.json();
      const el = document.getElementById("snapshot-count");
      if (el) el.textContent = data.count;
    } catch(e) {
      console.error("Failed to fetch snapshot count:", e);
    }
  }

  updateSnapshotCount();

  // Facial Recognition Single Button Logic (kept intact)
  const facialBtn = document.getElementById("facialRecBtn");
  if (facialBtn) {
    const facialText = facialBtn.querySelector(".btn-text");
    const statusDot = facialBtn.querySelector(".status-dot");
    const statusEl = document.getElementById("status");
    let isRunning = false;

    facialBtn.addEventListener("click", () => {
      if (!isRunning) {
        facialText.textContent = "Starting Facial Recognition...";
        facialText.classList.add("processing-dots");
        statusDot.className = "status-dot dot-starting";
        facialBtn.disabled = true;
        statusEl.innerText = "⏳ Starting recognition...";

        fetch("/start_face_recognition/")
          .then(r => r.json())
          .then(data => {
            facialText.classList.remove("processing-dots");
            facialText.textContent = "Facial Recognition Running";
            facialBtn.classList.add("btn-running");
            statusDot.className = "status-dot dot-active";
            isRunning = true;
            facialBtn.disabled = false;
            statusEl.innerText = data.message;
          })
          .catch(() => {
            facialText.textContent = "Start Facial Recognition";
            statusDot.className = "status-dot d-none";
            facialBtn.disabled = false;
            statusEl.innerText = "❌ Failed to start.";
          });

      } else {
        facialText.textContent = "Stopping Facial Recognition...";
        facialText.classList.add("processing-dots");
        statusDot.className = "status-dot dot-stopping";
        facialBtn.classList.add("btn-stopping");
        facialBtn.disabled = true;
        statusEl.innerText = "⏳ Stopping recognition...";

        fetch("/stop_face_recognition/")
          .then(r => r.json())
          .then(data => {
            facialText.classList.remove("processing-dots");
            facialText.textContent = "Start Facial Recognition";
            facialBtn.classList.remove("btn-running", "btn-stopping");
            statusDot.className = "status-dot d-none";
            isRunning = false;
            facialBtn.disabled = false;
            statusEl.innerText = data.message;
          })
          .catch(() => {
            facialText.textContent = "Facial Recognition Running";
            statusDot.className = "status-dot dot-active";
            facialBtn.disabled = false;
            statusEl.innerText = "❌ Failed to stop.";
          });
      }
    });
  }
});
