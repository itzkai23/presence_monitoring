let currentFilters = { department: '', course: '' };

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

// =============================
// Student Camera Capture Logic
// =============================
let captureStep = 0;
let capturedImages = [];

// Capture prompts for steps
const capturePrompts = [
  "📸 Capture LEFT side (3/4 angle).",
  "📸 Capture RIGHT side (3/4 angle).",
  "📸 Capture EXTRA POSE 1 (any angle).",
  "📸 Capture EXTRA POSE 2 (any angle).",
  "📸 Capture FRONT (straight ahead)."
];

// Inline face overlays
const faceOverlays = {
  0: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160">
        <ellipse cx="70" cy="80" rx="40" ry="55" stroke="cyan" stroke-width="3" fill="none"/>
        <circle cx="55" cy="65" r="6" fill="cyan"/>
      </svg>`,
  1: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160">
        <ellipse cx="50" cy="80" rx="40" ry="55" stroke="cyan" stroke-width="3" fill="none"/>
        <circle cx="65" cy="65" r="6" fill="cyan"/>
      </svg>`,
  2: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160">
        <ellipse cx="60" cy="80" rx="40" ry="55" stroke="cyan" stroke-width="3" fill="none"/>
      </svg>`,
  3: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160">
        <ellipse cx="60" cy="80" rx="40" ry="55" stroke="cyan" stroke-width="3" fill="none"/>
      </svg>`,
  4: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160">
        <ellipse cx="60" cy="80" rx="40" ry="55" stroke="cyan" stroke-width="3" fill="none"/>
        <circle cx="45" cy="65" r="6" fill="cyan"/>
        <circle cx="75" cy="65" r="6" fill="cyan"/>
      </svg>`
};

// Track per-student progress
const studentCaptureProgress = {};
let currentStudentId = null;
let videoStream = null;
let selectedDeviceId = null;

// ----------------------------
// Camera Device Selection
// ----------------------------
async function loadCameraDevices() {
  try {
    // Request permission once to unlock device labels
    await navigator.mediaDevices.getUserMedia({ video: true, audio: false });

    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = devices.filter(d => d.kind === "videoinput");

    if (!videoDevices.length) {
      throw new Error("No video devices found.");
    }

    // Prefer EMEET (case-insensitive), otherwise first available
    const emeet = videoDevices.find(d => /emeet/i.test(d.label));
    if (emeet) {
      selectedDeviceId = emeet.deviceId;
      console.log("🎯 EMEET camera selected:", emeet.label);
    } else {
      selectedDeviceId = videoDevices[0].deviceId;
      console.log("⚠️ EMEET not found. Using:", videoDevices[0].label);
    }

  } catch (err) {
    console.error("❌ Error loading camera devices:", err.name, err.message);
    alert("Camera device error: " + err.name + " - " + err.message);
  }
}

async function startCamera() {
  const video = document.getElementById("cameraStream");
  try {
    // Stop any existing stream before starting new
    if (videoStream) {
      videoStream.getTracks().forEach(track => track.stop());
      videoStream = null;
    }

    const constraints = {
      video: selectedDeviceId ? { deviceId: { exact: selectedDeviceId } } : { facingMode: "user" },
      audio: false
    };

    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    videoStream = stream;

    // Safer attributes for autoplay
    video.setAttribute("playsinline", true);
    video.setAttribute("autoplay", true);
    video.setAttribute("muted", true);

    video.srcObject = stream;
    await video.play();
    console.log("✅ Camera started:", stream);
  } catch (err) {
    console.error("❌ Camera error:", err.name, err.message);
    alert("Camera error: " + err.name + " - " + err.message);
    closeCameraModal();
  }
}

function restartCamera() {
  if (videoStream) {
    videoStream.getTracks().forEach(track => track.stop());
  }
  startCamera();
}

// ----------------------------
// Camera Modal Handlers
// ----------------------------
function openCameraModal(studentId) {
  currentStudentId = studentId;

  if (studentCaptureProgress[studentId]) {
    captureStep = studentCaptureProgress[studentId].step;
    capturedImages = studentCaptureProgress[studentId].images;
  } else {
    captureStep = 0;
    capturedImages = [];
  }

  const modal = document.getElementById("cameraModal");
  modal.style.display = "flex";
  document.getElementById("previewImage").style.display = "none";
  document.getElementById("cameraStream").style.display = "block";

  updateCapturePrompt();
  toggleConfirmButton(false);

  loadCameraDevices().then(() => startCamera());
}

function capturePhoto() {
  const video = document.getElementById("cameraStream");
  const canvas = document.getElementById("captureCanvas");
  const preview = document.getElementById("previewImage");

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);

  const dataURL = canvas.toDataURL("image/jpeg");
  capturedImages[captureStep] = dataURL;

  preview.src = dataURL;
  preview.style.display = "block";
  video.style.display = "none";

  setOverlayText(`✅ Captured (${captureStep + 1}/5)`);
  updateFaceGuide(true);
  toggleConfirmButton(true);
}

function confirmPhoto() {
  if (!capturedImages[captureStep]) {
    alert("Please capture a photo first.");
    return;
  }

  studentCaptureProgress[currentStudentId] = { step: captureStep, images: capturedImages };
  captureStep++;

  if (captureStep < 5) {
    document.getElementById("previewImage").style.display = "none";
    document.getElementById("cameraStream").style.display = "block";

    updateCapturePrompt();
    toggleConfirmButton(false);
    updateFaceGuide(false);

    studentCaptureProgress[currentStudentId].step = captureStep;
  } else {
    // All 5 steps captured → upload
    fetch(`/upload_student_photo/${currentStudentId}/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRFToken()
      },
      body: JSON.stringify({ images: capturedImages })
    })
      .then(res => res.json())
      .then(data => {
        alert(data.message || "Photos uploaded.");
        if (data.status === "success") {
          delete studentCaptureProgress[currentStudentId];
          location.reload();
        }
        closeCameraModal();
      })
      .catch(err => {
        console.error("❌ Upload failed:", err);
        alert("Failed to upload photos.");
      });
  }
}

function retakePhoto() {
  document.getElementById("previewImage").style.display = "none";
  document.getElementById("cameraStream").style.display = "block";

  capturedImages[captureStep] = null;
  updateCapturePrompt();
  updateFaceGuide(false);
  toggleConfirmButton(false);
}

function closeCameraModal() {
  const modal = document.getElementById("cameraModal");
  modal.style.display = "none";

  if (videoStream) {
    videoStream.getTracks().forEach(track => track.stop());
    videoStream = null;
  }

  if (currentStudentId) {
    studentCaptureProgress[currentStudentId] = { step: captureStep, images: capturedImages };
  }
}

function toggleConfirmButton(enabled) {
  const btn = document.querySelector("#cameraModal button.btn-success");
  if (btn) btn.disabled = !enabled;
}

// ----------------------------
// Overlay Helpers
// ----------------------------
function updateCapturePrompt() {
  setOverlayText(capturePrompts[captureStep]);
  updateFaceDirection(captureStep);
}

function setOverlayText(text) {
  const overlay = document.getElementById("cameraOverlay");
  if (overlay) overlay.innerText = text;
}

function updateFaceGuide(success = false) {
  const guide = document.getElementById("faceGuide");
  if (guide) {
    guide.style.border = success ? "3px solid rgba(0,255,0,0.8)" : "3px dashed rgba(0,255,255,0.7)";
  }
}

function updateFaceDirection(step) {
  const direction = document.getElementById("faceDirection");
  if (direction) direction.innerHTML = faceOverlays[step] || "";
}

function getCSRFToken() {
  const cookies = document.cookie.split(";").map(c => c.trim());
  const csrf = cookies.find(c => c.startsWith("csrftoken="));
  return csrf ? csrf.split("=")[1] : "";
}

// =============================
// Existing Page Functions
// =============================
document.addEventListener("DOMContentLoaded", () => {
  applyFilters?.();

  document.querySelectorAll(".toggle-arrow").forEach(el => {
    el.addEventListener("click", () => toggleNestedList(el));
  });
});
