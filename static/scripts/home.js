document.addEventListener("DOMContentLoaded", () => {
  const monthSelect = document.getElementById("monthSelect");
  const yearSelect = document.getElementById("yearSelect");
  const calendarGrid = document.getElementById("calendarGrid");
  const calendarTitle = document.getElementById("calendarTitle");
  const calendarLoading = document.getElementById("calendarLoading");

  const currentDate = new Date();
  const todayDateStr = currentDate.toISOString().split("T")[0]; // YYYY-MM-DD
  let studentLogs = [];

  // 📌 Philippine holidays (fixed dates)
  const philippineHolidays = {
    "01-01": "New Year's Day",
    "02-25": "EDSA People Power Revolution",
    "04-09": "Araw ng Kagitingan",
    "05-01": "Labor Day",
    "06-12": "Independence Day",
    "08-21": "Ninoy Aquino Day",
    "08-26": "National Heroes Day",
    "11-01": "All Saints' Day",
    "11-02": "All Souls' Day",
    "11-30": "Bonifacio Day",
    "12-25": "Christmas Day",
    "12-30": "Rizal Day"
  };

  // 🔹 Use hardcoded API path
  const STUDENT_LOGS_API = "/api/student_logs/";

  // 🔹 Fetch logs
  async function fetchLogs() {
    try {
      calendarLoading.style.display = "block";
      const response = await fetch(STUDENT_LOGS_API);
      if (!response.ok) throw new Error("Network response not ok");
      studentLogs = await response.json();
      renderCalendar();
    } catch (error) {
      console.error("Error fetching logs:", error);
      calendarGrid.innerHTML = "<p class='text-danger text-center mt-3'>Failed to load logs.</p>";
    } finally {
      calendarLoading.style.display = "none";
    }
  }

  // 🔹 Render calendar
  function renderCalendar() {
    const month = parseInt(monthSelect.value);
    const year = parseInt(yearSelect.value);

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startOffset = (firstDay.getDay() + 6) % 7; // Monday first

    // Reset grid with headers
    calendarGrid.innerHTML = `
      <div class="calendar-header">Mon</div>
      <div class="calendar-header">Tue</div>
      <div class="calendar-header">Wed</div>
      <div class="calendar-header">Thu</div>
      <div class="calendar-header">Fri</div>
      <div class="calendar-header">Sat</div>
      <div class="calendar-header">Sun</div>
    `;

    // Empty cells before first day
    for (let i = 0; i < startOffset; i++) {
      const empty = document.createElement("div");
      empty.className = "calendar-day empty";
      calendarGrid.appendChild(empty);
    }

    // Days of the month
    for (let day = 1; day <= lastDay.getDate(); day++) {
      const cell = document.createElement("div");
      cell.className = "calendar-day";
      const dateStr = `${year}-${String(month + 1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;

      // ✅ Check logs
      const log = studentLogs.find(l => l.logs_timestamp && l.logs_timestamp.split("T")[0] === dateStr);

      const dateNum = document.createElement("div");
      dateNum.className = "date-number";
      dateNum.textContent = day;
      cell.appendChild(dateNum);

      if (log) {
        cell.classList.add("logged");
        const logText = `Purpose: ${log.purpose || "None"}`;
        cell.title = logText;

        const logLabel = document.createElement("div");
        logLabel.className = "log-label";
        logLabel.textContent = logText;
        cell.appendChild(logLabel);

        cell.addEventListener("click", () => showLogModal(log));
      }

      // ✅ Today highlight
      if (year === currentDate.getFullYear() && month === currentDate.getMonth() && day === currentDate.getDate()) {
        cell.classList.add("today");
      }

      // ✅ Holiday highlight
      const dateKey = `${String(month + 1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
      if (philippineHolidays[dateKey]) {
        const holidayText = philippineHolidays[dateKey];
        cell.classList.add("holiday");
        cell.title = holidayText;

        const holidayLabel = document.createElement("div");
        holidayLabel.className = "holiday-label";
        holidayLabel.textContent = holidayText;
        cell.appendChild(holidayLabel);
      }

      calendarGrid.appendChild(cell);
    }

    // Update month title
    const monthName = new Date(year, month).toLocaleString("default", { month: "long" });
    calendarTitle.textContent = `${monthName} ${year}`;
  }

  // 🔹 Show log modal
  function showLogModal(log) {
    const logDate = log.logs_timestamp ? log.logs_timestamp.split("T")[0] : "Unknown";
    const canEdit = logDate === todayDateStr && log.role === "Student";

    document.getElementById("logDate").textContent = logDate;
    document.getElementById("logPurpose").textContent = log.purpose || "None";

    const section = document.getElementById("editPurposeSection");
    const input = document.getElementById("editPurposeInput");
    const saveBtn = document.getElementById("savePurposeBtn");
    const feedback = document.getElementById("purposeFeedback");

    if (canEdit) {
      section.style.display = "block";
      input.value = log.purpose;

      saveBtn.onclick = async () => {
        try {
          const res = await fetch(`/update-purpose/${log.id}/`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken")
            },
            body: JSON.stringify({ purpose: input.value })
          });
          const result = await res.json();
          if (result.status === "success") {
            log.purpose = input.value;
            feedback.style.display = "block";
            renderCalendar();
          } else {
            alert(result.message || "Error saving purpose.");
          }
        } catch (err) {
          console.error(err);
          alert("Failed to save purpose.");
        }
      };
    } else {
      section.style.display = "none";
    }

    new bootstrap.Modal(document.getElementById("logDetailsModal")).show();
  }

  // 🔹 CSRF helper
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      document.cookie.split(";").forEach(cookie => {
        cookie = cookie.trim();
        if (cookie.startsWith(name + "=")) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        }
      });
    }
    return cookieValue;
  }

  // Initialize dropdowns & fetch logs
  monthSelect.value = currentDate.getMonth();
  yearSelect.value = currentDate.getFullYear();

  fetchLogs();
  monthSelect.addEventListener("change", renderCalendar);
  yearSelect.addEventListener("change", renderCalendar);
});
