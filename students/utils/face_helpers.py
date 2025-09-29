# students/utils/face_helpers.py
import os
import requests
import cv2
from datetime import datetime
from collections import defaultdict

# -----------------------------
# CONFIG (can be overridden)
# -----------------------------
STUDENT_INFO_API = "http://127.0.0.1:8000/api/student_info/"
LOG_API = "http://127.0.0.1:8000/api/log_presence/"
SNAPSHOT_DIR = "media/guest_snapshots"
MAX_DAILY_SNAPSHOTS = 2

# Ensure snapshot directory exists
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# State tracking
daily_snapshot_count = defaultdict(lambda: defaultdict(int))  # {student_pk: {YYYYMMDD: count}}

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def fetch_student_info(pk, timeout=3):
    """Fetch student info from API. Returns dict or None."""
    try:
        res = requests.get(f"{STUDENT_INFO_API}{pk}/", timeout=timeout)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def log_presence(student_id=None, role="Guest", snapshot=None, timeout=3):
    """Log presence via API. Non-blocking errors."""
    payload = {"student_id": student_id, "role": role}
    if snapshot:
        payload["snapshot"] = snapshot
    try:
        requests.post(LOG_API, json=payload, timeout=timeout)
    except:
        pass

def save_guest_snapshot(frame, top, right, bottom, left, padding=40):
    """Crop and save a guest face snapshot. Returns relative media path or None."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"guest_{ts}.jpg"
    filepath = os.path.join(SNAPSHOT_DIR, filename)

    h, w = frame.shape[:2]
    top_pad = max(top - padding, 0)
    bottom_pad = min(bottom + padding, h)
    left_pad = max(left - padding, 0)
    right_pad = min(right + padding, w)

    face_crop = frame[top_pad:bottom_pad, left_pad:right_pad]
    if face_crop.size > 0:
        cv2.imwrite(filepath, face_crop)
        return os.path.relpath(filepath, "media").replace("\\", "/")
    return None

def can_log_student(pk, max_daily_snapshots=None):
    """Check if a student can log today (max daily snapshots)."""
    today = datetime.now().strftime("%Y%m%d")
    limit = max_daily_snapshots or MAX_DAILY_SNAPSHOTS
    if daily_snapshot_count[pk][today] < limit:
        daily_snapshot_count[pk][today] += 1
        return True
    return False
