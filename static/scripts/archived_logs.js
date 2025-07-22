async function fetchArchivedLogs() {
  try {
    const response = await fetch('/get-archived-logs/');
    return await response.json();
  } catch (error) {
    console.error("❌ Error fetching archived logs:", error);
    return [];
  }
}

function renderArchiveTable(logs) {
  const query = document.getElementById("searchArchive").value.toLowerCase();
  const tbody = document.getElementById("archiveTableBody");

  const filtered = logs.filter(log =>
    log.name.toLowerCase().includes(query) ||
    log.student_id.toLowerCase().includes(query) ||
    log.date.toLowerCase().includes(query) ||
    (log.archived_at || '').toLowerCase().includes(query) ||
    log.role.toLowerCase().includes(query) ||
    log.department.toLowerCase().includes(query) ||
    log.purpose.toLowerCase().includes(query)
  );

  tbody.innerHTML = filtered.length
    ? ""
    : `<tr><td colspan="8" class="text-center text-muted">No archived records found.</td></tr>`;

  filtered.forEach((log, index) => {
    tbody.innerHTML += `
      <tr>
        <td class="text-center">${index + 1}</td>
        <td class="text-center">${log.archived_at || '—'}</td>
        <td class="text-center">${log.date}</td>
        <td class="text-center">${log.student_id}</td>
        <td>${log.name}</td>
        <td class="text-center">${log.role}</td>
        <td class="text-center">${log.department}</td>
        <td>${log.purpose}</td>
      </tr>`;
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  const logs = await fetchArchivedLogs();
  renderArchiveTable(logs);

  document.getElementById("searchArchive").addEventListener("input", () => {
    renderArchiveTable(logs);
  });
});
