async function fetchPresenceLogs() {
  try {
    const response = await fetch('/get-presence-logs/');
    const logs = await response.json();
    console.log("📋 All logs:", logs);
    return logs;
  } catch (error) {
    console.error("Error fetching presence logs:", error);
    return [];
  }
}

function escapeHTML(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderPresenceTable(logs) {
  const query = document.getElementById("searchPresence").value.toLowerCase();
  const tbody = document.getElementById("presenceTableBody");
  tbody.innerHTML = "";  // 🔁 Always clear table first

  const filtered = logs.filter(log =>
    String(log.name).toLowerCase().includes(query) ||
    String(log.student_id).toLowerCase().includes(query) ||
    String(log.date).toLowerCase().includes(query) ||
    String(log.role).toLowerCase().includes(query) ||
    String(log.department).toLowerCase().includes(query) ||
    String(log.purpose || '').toLowerCase().includes(query)
  );

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No presence records found.</td></tr>`;
    return;
  }

  const today = new Date().toISOString().split("T")[0];

  filtered.forEach(log => {
    const badgeClass = log.role === "Student" ? 'bg-dark text-light' : 'bg-secondary text-light';
    const logDate = log.date.split(" ")[0];
    const isToday = logDate === today;
    const editable = isToday && (log.role === "Guest" || (log.role === "Student" && !log.edited));

    let purposeCell = "";

    if (log.role === "Guest" && editable) {
      purposeCell = `<input type="text" class="form-control form-control-sm guest-purpose-input" 
                        value="${escapeHTML(log.purpose)}" data-log-id="${log.id}" />`;
    } else if (log.role === "Student" && editable) {
      purposeCell = `
        <select class="form-select form-select-sm purpose-select" data-log-id="${log.id}">
          <option value="class" ${log.purpose === 'class' ? 'selected' : ''}>class</option>
          <option value="study" ${log.purpose === 'study' ? 'selected' : ''}>study</option>
          <option value="appointment" ${log.purpose === 'appointment' ? 'selected' : ''}>appointment</option>
          <option value="event" ${log.purpose === 'event' ? 'selected' : ''}>event</option>
        </select>`;
    } else {
      purposeCell = escapeHTML(log.purpose || '—');
    }

    const snapshotCell = (log.role === "Guest" && log.snapshot)
      ? `<a href="${log.snapshot}" target="_blank">
           <img src="${log.snapshot}" alt="Guest Snapshot" class="img-thumbnail" style="width: 60px; height: 60px;" />
         </a>`
      : '—';

    const actionCell = log.role === "Guest"
      ? `<button class="btn btn-sm btn-danger delete-log-btn" data-log-id="${log.id}">Delete</button>`
      : '';

    const rowHTML = `
      <tr>
        <td>${escapeHTML(log.student_id)}</td>
        <td>${escapeHTML(log.name)}</td>
        <td>${escapeHTML(log.date)}</td>
        <td><span class="badge ${badgeClass}">${escapeHTML(log.role)}</span></td>
        <td>${escapeHTML(log.department)}</td>
        <td>${purposeCell}</td>
        <td>${snapshotCell}</td>
        <td>${actionCell}</td>
      </tr>`;

    tbody.insertAdjacentHTML("beforeend", rowHTML);
  });

  bindPurposeEditEvents();
  bindDeleteButtons();
}

function bindPurposeEditEvents() {
  document.querySelectorAll('.purpose-select').forEach(select => {
    select.addEventListener('change', async (e) => {
      const logId = e.target.getAttribute('data-log-id');
      const newPurpose = e.target.value;

      const response = await fetch(`/update-purpose/${logId}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ purpose: newPurpose })
      });

      const result = await response.json();
      alert(result.message);
      if (result.status === 'success') location.reload();
    });
  });

  document.querySelectorAll('.guest-purpose-input').forEach(input => {
    input.addEventListener('blur', async (e) => {
      const logId = e.target.getAttribute('data-log-id');
      const newPurpose = e.target.value.trim();
      if (!newPurpose) return;

      const response = await fetch(`/update-purpose/${logId}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ purpose: newPurpose })
      });

      const result = await response.json();
      alert(result.message);
      if (result.status === 'success') location.reload();
    });
  });
}

function bindDeleteButtons() {
  document.querySelectorAll('.delete-log-btn').forEach(button => {
    button.addEventListener('click', async () => {
      const logId = button.getAttribute('data-log-id');
      const confirmed = confirm("Are you sure you want to delete this guest log?");
      if (!confirmed) return;

      const response = await fetch(`/delete-guest-log/${logId}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      const result = await response.json();
      alert(result.message);
      if (result.status === 'success') location.reload();
    });
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const logs = await fetchPresenceLogs();
  renderPresenceTable(logs);

  document.getElementById("searchPresence").addEventListener("input", () => {
    renderPresenceTable(logs);
  });
});

console.log("admin_page.js loaded");
