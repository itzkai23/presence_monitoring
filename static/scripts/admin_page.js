let currentFilters = { department: '', course: '' };
let currentStudentId = null;
let videoStream = null;

function toggleList(id) {
  const element = document.getElementById(id);
  const arrowToggle = document.querySelector(`[onclick="toggleList('${id}')"]`);
  if (element) {
    element.classList.toggle('active');
    if (arrowToggle) arrowToggle.classList.toggle('active');
  }
}

function showDashboard() {
  const dashboard = document.getElementById("dashboardContainer");
  const studentTable = document.getElementById("studentTableContainer");
  if (dashboard) dashboard.style.display = "block";
  if (studentTable) studentTable.style.display = "none";

  document.querySelectorAll('#sidebar .nav-link').forEach(el => el.classList.remove('active'));
  const dashboardLink = Array.from(document.querySelectorAll('#sidebar .nav-link'))
    .find(link => link.textContent.trim() === "Dashboard");
  if (dashboardLink) dashboardLink.classList.add('active');

  document.querySelectorAll('.toggle-arrow.active').forEach(el => el.classList.remove('active'));
  const departmentsContainer = document.getElementById("departmentsContainer");
  if (departmentsContainer?.classList.contains("active")) {
    departmentsContainer.classList.remove("active");
  }
}

document.getElementById('toggleSidebar')?.addEventListener('click', () => {
  document.getElementById('sidebar')?.classList.toggle('active');
  document.getElementById('mainContent')?.classList.toggle('shifted');
});

function applyFilters(department = '', course = '') {
  currentFilters = { department, course};
  const params = new URLSearchParams();
  if (department) params.append('department', department);
  if (course) params.append('course', course);

  let url = `/filter_students`;
  if ([...params].length > 0) url += `?${params.toString()}`;

  fetch(url)
    .then(response => response.json())
    .then(students => {
      const activeStudents = students.filter(s => !s.is_archived); // safeguard
      renderStudentTable(activeStudents);
    })
    .catch(() => renderStudentTable([]));
}

function renderStudentTable(students) {
  const dashboard = document.getElementById("dashboardContainer");
  const studentTable = document.getElementById("studentTableContainer");
  if (dashboard) dashboard.style.display = 'none';
  if (studentTable) studentTable.style.display = 'block';

  if (!students.length) {
    studentTable.innerHTML = '<p>No students found.</p>';
    return;
  }

  let html = `
    <table class="table table-striped table-bordered">
      <thead>
        <tr>
          <th>Photo</th>
          <th>Student ID</th>
          <th>Name</th>
          <th>Email</th>
          <th>Course</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
  `;

  students.forEach(s => {
    const photo = s.photo_url || '/static/default-profile.png';
    html += `
      <tr data-id="${s.id}">
        <td>
          <img 
            src="${photo}" 
            alt="Photo" 
            width="50" height="50" 
            style="object-fit: cover; border-radius: 50%; cursor: pointer;" 
            onclick="openCameraModal('${s.id}')"
          >
        </td>
        <td>${s.student_id}</td>
        <td>${s.first_name} ${s.last_name}</td>
        <td>${s.email}</td>
        <td>${s.course}</td>
        <td>
          <button class="btn btn-sm btn-danger archive-btn" data-id="${s.id}">Delete</button>
        </td>
      </tr>
    `;
  });

  html += '</tbody></table>';
  studentTable.innerHTML = html;

  attachArchiveHandlers();
}

function attachArchiveHandlers() {
  document.querySelectorAll(".archive-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      if (confirm("Archive this student?")) {
        const res = await fetch(`/archive-student/${id}/`, {
          method: "POST",
          headers: { "X-CSRFToken": getCSRFToken() }
        });
        const result = await res.json();
        alert(result.message);
        if (result.status === "success") {
          document.querySelector(`tr[data-id="${id}"]`)?.remove();  // remove from DOM
        }
      }
    });
  });
}

function toggleNestedList(element) {
  const nextUl = element.nextElementSibling;
  const isActive = nextUl?.classList.contains('active');

  const parentUl = element.closest('ul');
  if (parentUl) {
    parentUl.querySelectorAll(':scope > li > .toggle-arrow.active').forEach(sibling => {
      if (sibling !== element) {
        sibling.classList.remove('active');
        sibling.nextElementSibling?.classList.remove('active');
      }
    });
  }

  if (nextUl?.classList.contains('nested-list')) {
    nextUl.classList.toggle('active', !isActive);
    element.classList.toggle('active', !isActive);
  }

  document.getElementById("dashboardContainer").style.display = "none";
  document.getElementById("studentTableContainer").style.display = "block";

  const filterText = element.textContent.trim();
  if (filterText === "DEPARTMENTS") {
    applyFilters();
    localStorage.setItem('currentContent', 'dashboard');
  } else if (nextUl?.classList.contains('nested-list')) {
    applyFilters(filterText, '');
    localStorage.setItem('currentContent', `department:${filterText}`);
  } else {
    applyFilters('', filterText);
    localStorage.setItem('currentContent', `course:${filterText}`);
  }
}

function openCameraModal(studentId) {
  currentStudentId = studentId;
  const modal = document.getElementById("cameraModal");
  modal.style.display = "flex";

  document.getElementById("previewImage").style.display = "none";
  document.getElementById("cameraStream").style.display = "block";

  startCamera();
}

function startCamera() {
  const video = document.getElementById("cameraStream");

  navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false })
    .then((stream) => {
      videoStream = stream;
      video.srcObject = stream;
      video.play();
    })
    .catch((err) => {
      console.error("Camera error:", err);
      alert("Unable to access camera. Please check your browser permissions.");
      closeCameraModal();
    });
}

function capturePhoto() {
  const video = document.getElementById("cameraStream");
  const canvas = document.getElementById("captureCanvas");
  const preview = document.getElementById("previewImage");

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);

  preview.src = canvas.toDataURL("image/jpeg");
  preview.style.display = "block";
  video.style.display = "none";
}

function confirmPhoto() {
  const canvas = document.getElementById("captureCanvas");
  const dataURL = canvas.toDataURL("image/jpeg");

  if (!dataURL) {
    alert("No photo captured.");
    return;
  }

  fetch(`/upload_student_photo/${currentStudentId}/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken()
    },
    body: JSON.stringify({ image_data: dataURL })
  })
    .then(res => res.json())
    .then(data => {
      alert(data.message || "Photo uploaded.");
      if (data.status === "success") location.reload();
      closeCameraModal();
    })
    .catch(() => alert("Failed to upload photo."));
}

function retakePhoto() {
  document.getElementById("previewImage").style.display = "none";
  document.getElementById("cameraStream").style.display = "block";
}

function closeCameraModal() {
  const modal = document.getElementById("cameraModal");
  modal.style.display = "none";
  if (videoStream) {
    videoStream.getTracks().forEach(track => track.stop());
    videoStream = null;
  }
}

function getCSRFToken() {
  const cookies = document.cookie.split(";").map(c => c.trim());
  const csrf = cookies.find(c => c.startsWith("csrftoken="));
  return csrf ? csrf.split("=")[1] : "";
}

document.addEventListener('DOMContentLoaded', () => {
  applyFilters(); // Initial load
  document.querySelectorAll('.toggle-arrow').forEach(el => {
    el.addEventListener('click', () => toggleNestedList(el));
  });
});
