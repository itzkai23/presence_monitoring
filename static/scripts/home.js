document.addEventListener("DOMContentLoaded", () => {
  const monthSelect = document.getElementById("monthSelect");
  const yearSelect = document.getElementById("yearSelect");
  const calendarGrid = document.getElementById("calendarGrid");
  const calendarTitle = document.getElementById("calendarTitle");
  const calendarLoading = document.getElementById("calendarLoading");

  const currentDate = new Date();
  const todayDateStr = currentDate.toISOString().split("T")[0];
  let studentLogs = [];

  async function fetchLogs() {
    try {
      calendarLoading.style.display = "block";
      const response = await fetch("/api/student_logs/");
      studentLogs = await response.json();
      renderCalendar();
    } catch (error) {
      console.error("Error fetching logs:", error);
    } finally {
      calendarLoading.style.display = "none";
    }
  }

  function renderCalendar() {
    const month = parseInt(monthSelect.value);
    const year = parseInt(yearSelect.value);

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startOffset = (firstDay.getDay() + 6) % 7;

    calendarGrid.innerHTML = `
      <div class="calendar-header">Mon</div>
      <div class="calendar-header">Tue</div>
      <div class="calendar-header">Wed</div>
      <div class="calendar-header">Thu</div>
      <div class="calendar-header">Fri</div>
      <div class="calendar-header">Sat</div>
      <div class="calendar-header">Sun</div>
    `;

    for (let i = 0; i < startOffset; i++) {
      const empty = document.createElement("div");
      empty.className = "calendar-day empty";
      calendarGrid.appendChild(empty);
    }

    for (let day = 1; day <= lastDay.getDate(); day++) {
      const cell = document.createElement("div");
      cell.className = "calendar-day";
      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

      const log = studentLogs.find(l => l.date.startsWith(dateStr));

      if (log) {
        cell.classList.add("logged");
        cell.title = `Purpose: ${log.purpose || "None"}`;
        cell.addEventListener("click", () => {
          showLogModal(log);
        });
      }

      if (
        year === currentDate.getFullYear() &&
        month === currentDate.getMonth() &&
        day === currentDate.getDate()
      ) {
        cell.classList.add("today");
      }

      cell.textContent = day;
      calendarGrid.appendChild(cell);
    }

    const monthName = new Date(year, month).toLocaleString("default", { month: "long" });
    calendarTitle.textContent = `Calendar - ${monthName} ${year}`;
  }

function showLogModal(log) {
  const canEdit = log.date.startsWith(todayDateStr) && !log.edited && log.role === "Student";

  document.getElementById("logDate").textContent = log.date;
  document.getElementById("logPurpose").textContent = log.purpose || "None";

  const section = document.getElementById("editPurposeSection");
  const input = document.getElementById("editPurposeInput");
  const saveBtn = document.getElementById("savePurposeBtn");
  const feedback = document.getElementById("purposeFeedback");

  if (canEdit) {
    section.style.display = "block";
    input.value = log.purpose;

    saveBtn.onclick = async () => {
      const newPurpose = input.value;
      const res = await fetch(`/update_purpose/${log.id}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({ purpose: newPurpose })
      });

      const result = await res.json();
      if (result.status === "success") {
        log.purpose = newPurpose;
        log.edited = true;
        feedback.style.display = "block";
        renderCalendar();
      } else {
        alert(result.message || "Error saving purpose.");
      }
    };
  } else {
    section.style.display = "none";
  }

  const modal = new bootstrap.Modal(document.getElementById("logDetailsModal"));
  modal.show();
}

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith(name + "=")) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // Initialize dropdowns and fetch
  monthSelect.value = currentDate.getMonth();
  yearSelect.value = currentDate.getFullYear();

  fetchLogs();
  monthSelect.addEventListener("change", renderCalendar);
  yearSelect.addEventListener("change", renderCalendar);
});
