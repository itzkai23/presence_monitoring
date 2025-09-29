# import cv2
# import face_recognition
# import os
# import pickle
# import requests
# from datetime import datetime
# import numpy as np
# import time

# # ---------------------------
# # Config
# # ---------------------------
# ENCODINGS_FILE = "media/encodings.pkl"
# SNAPSHOT_DIR = "media/guest_snapshots"
# STUDENT_INFO_API = "http://127.0.0.1:8000/api/student_info/"
# LOG_API = "http://127.0.0.1:8000/api/log_presence/"

# # 🔹 MODIFIED: stricter thresholds
# TOLERANCE = 0.45          # Student recognition
# GUEST_TOLERANCE = 0.55    # Guest duplicate detection
# GUEST_COOLDOWN_SECONDS = 3

# # ---------------------------
# # Load encodings
# # ---------------------------
# if not os.path.exists(ENCODINGS_FILE):
#     raise RuntimeError("You must run generate_encodings.py first!")

# with open(ENCODINGS_FILE, 'rb') as f:
#     data = pickle.load(f)
#     known_face_encodings = data['encodings']
#     known_face_metadata = data['metadata']

# print(f"Loaded {len(known_face_encodings)} known encodings")

# # ---------------------------
# # Tracking
# # ---------------------------
# logged_students = set()
# logged_guest_encodings = []
# guest_last_detected = {}

# os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# # ---------------------------
# # Start camera
# # ---------------------------
# video_capture = cv2.VideoCapture(0)

# while True:
#     ret, frame = video_capture.read()
#     if not ret:
#         print(" Failed to capture frame")
#         break

#     rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#     face_locations = face_recognition.face_locations(rgb)
#     face_encodings = face_recognition.face_encodings(rgb, face_locations)

#     for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
#         label = "Guest Detected"
#         box_color = (0, 255, 255)
#         student_id = None
#         student_name = "Unknown"
#         is_duplicate_guest = False

#         # ---------------------------
#         # Student matching
#         # ---------------------------
#         if known_face_encodings:
#             distances = face_recognition.face_distance(known_face_encodings, face_encoding)
#             best_idx = np.argmin(distances)

#             # 🔹 MODIFIED: only accept if under strict tolerance
#             if distances[best_idx] < TOLERANCE:
#                 student_meta = known_face_metadata[best_idx]
#                 pk = student_meta.get("pk")
#                 try:
#                     res = requests.get(f"{STUDENT_INFO_API}{pk}/")
#                     if res.status_code == 200:
#                         info = res.json()
#                         student_id = info["student_id"]
#                         student_name = info.get("name", "Unknown")
#                 except Exception as e:
#                     print(" API error:", e)

#         # ---------------------------
#         # Student logging
#         # ---------------------------
#         if student_id:
#             label = "Student"
#             box_color = (0, 255, 0)
#             if student_id not in logged_students:
#                 try:
#                     res = requests.post(LOG_API, json={
#                         "student_id": student_id,
#                         "role": "Student"
#                     })
#                     if res.status_code == 200:
#                         print(f"Logged student: {student_id}")
#                     else:
#                         print(f" Student log failed: {res.status_code} → {res.text}")
#                 except Exception as e:
#                     print(" Logging error:", str(e))
#                 logged_students.add(student_id)

#         # ---------------------------
#         # Guest logging (fallback if not student)
#         # ---------------------------
#         else:  # 🔹 MODIFIED: ALWAYS treat as guest if not matched
#             guest_hash = tuple(np.round(face_encoding, 4))
#             now_time = time.time()

#             if guest_hash in guest_last_detected and now_time - guest_last_detected[guest_hash] < GUEST_COOLDOWN_SECONDS:
#                 is_duplicate_guest = True
#             else:
#                 for prev_enc in logged_guest_encodings:
#                     if face_recognition.face_distance([prev_enc], face_encoding)[0] < GUEST_TOLERANCE:
#                         is_duplicate_guest = True
#                         break

#             if is_duplicate_guest:
#                 label = "Guest (Already Logged)"
#                 box_color = (0, 140, 255)
#             else:
#                 guest_last_detected[guest_hash] = now_time
#                 logged_guest_encodings.append(face_encoding)

#                 ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#                 filename = f"guest_{ts}.jpg"
#                 filepath = os.path.join(SNAPSHOT_DIR, filename)

#                 padding = 40
#                 height, width = frame.shape[:2]
#                 top_pad = max(top - padding, 0)
#                 bottom_pad = min(bottom + padding, height)
#                 left_pad = max(left - padding, 0)
#                 right_pad = min(right + padding, width)
#                 guest_face = frame[top_pad:bottom_pad, left_pad:right_pad]

#                 if guest_face.size > 0:
#                     try:
#                         cv2.imwrite(filepath, guest_face)
#                         print(f"Snapshot saved: {filepath}")

#                         rel_path = os.path.relpath(filepath, "media").replace("\\", "/")

#                         res = requests.post(LOG_API, json={
#                             "student_id": None,
#                             "role": "Guest",
#                             "snapshot": rel_path
#                         })
#                         if res.status_code == 200:
#                             print("Guest log submitted")
#                         else:
#                             print(f"Guest log failed: {res.status_code} → {res.text}")
#                     except Exception as e:
#                         print(f"Error saving guest snapshot or logging: {e}")
#                 else:
#                     print("Guest face region is empty — snapshot not saved")

#         # ---------------------------
#         # Draw box + label
#         # ---------------------------
#         cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)
#         cv2.putText(frame, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, box_color, 2)

#     cv2.imshow("Live Face Recognition", frame)
#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break

# video_capture.release()
# cv2.destroyAllWindows()
# live_face_recognition.py
import cv2
import face_recognition
import os
import pickle
import requests
import numpy as np
import time
from datetime import datetime
from sklearn.svm import SVC
from collections import defaultdict

# -------------------------
# Config
# -------------------------
ENCODINGS_FILE = "media/encodings.pkl"
SVM_MODEL_FILE = "media/svm_classifier.pkl"
GUEST_SNAPSHOT_DIR = "media/guest_snapshots"
STUDENT_SNAPSHOT_DIR = "media/student_snapshots"

STUDENT_INFO_API = "http://127.0.0.1:8000/api/student_info/"
LOG_API = "http://127.0.0.1:8000/api/log_presence/"

# thresholds / caps
DISTANCE_THRESHOLD = 0.45            # base distance cutoff for matching
GUEST_TOLERANCE = 0.55
GUEST_COOLDOWN_SECONDS = 3
MAX_DAILY_SNAPSHOTS = 5             # per-student per-day snapshot limit (your requirement)
MAX_TOTAL_IMAGES = 10               # maximum total images (permanent + snapshots)
STUDENT_SNAPSHOT_COOLDOWN = 10      # seconds cooldown between student snapshots
DIVERSITY_THRESHOLD = 0.35          # minimum distance to consider a snapshot "diverse" (tuneable)

FRAME_SCALE = 0.4
FRAME_SKIP = 2
LABEL_INTERVAL = 1.0
LABEL_STABILITY_FRAMES = 5
PREDICTION_STABILITY_FRAMES = 3     # require N repeated predictions to confirm

# -------------------------
# Helper: dynamic thresholds
# fewer images -> lower prob threshold (lenient)
# also allow a relaxed distance fallback for low-count students
# -------------------------
def dynamic_prob_threshold(img_count: int) -> float:
    # Lower thresholds for smaller counts to allow capturing more snapshots for new students.
    if img_count <= 1:
        return 0.30
    if img_count == 2:
        return 0.40
    if img_count <= 4:
        return 0.50
    if img_count <= 6:
        return 0.60
    if img_count <= 8:
        return 0.65
    return 0.70  # more confident for well-represented students

def dynamic_distance_relaxation(img_count: int) -> float:
    # Return extra allowance to distance threshold for under-represented students
    # (smaller => more relaxed)
    if img_count <= 2:
        return 0.12
    if img_count <= 4:
        return 0.08
    if img_count <= 6:
        return 0.05
    return 0.0

# -------------------------
# Load models
# -------------------------
if not os.path.exists(ENCODINGS_FILE) or not os.path.exists(SVM_MODEL_FILE):
    raise RuntimeError("Run generate_encodings.py first (encodings + svm files required).")

with open(ENCODINGS_FILE, "rb") as f:
    data = pickle.load(f)
    known_face_encodings = data.get("encodings", [])
    known_face_metadata = data.get("metadata", [])

with open(SVM_MODEL_FILE, "rb") as f:
    svm_clf: SVC = pickle.load(f)

# -------------------------
# State / caches
# -------------------------
logged_students = set()
current_day = datetime.now().strftime("%Y%m%d")
logged_guest_encodings = []
guest_last_detected = {}
daily_student_snapshot_count = defaultdict(lambda: defaultdict(int))  # student_pk -> {YYYYMMDD: count}
last_student_snapshot_time = defaultdict(float)                      # student_pk -> timestamp
student_info_cache = {}
label_state = {}

# Build per-student maps from encodings.pkl (lightweight in-memory)
student_image_counts = defaultdict(int)           # pk -> total images (encodings.pkl)
student_encodings_map = defaultdict(list)         # pk -> [encoding1, encoding2, ...]

for enc, meta in zip(known_face_encodings, known_face_metadata):
    pk = meta.get("pk")
    if pk is not None:
        student_image_counts[pk] += 1
        student_encodings_map[pk].append(enc)

capped_students = {pk for pk, count in student_image_counts.items() if count >= MAX_TOTAL_IMAGES}

# small cache for prediction stability: face_id -> list[(pk, conf)]
prediction_history = defaultdict(list)

os.makedirs(GUEST_SNAPSHOT_DIR, exist_ok=True)
os.makedirs(STUDENT_SNAPSHOT_DIR, exist_ok=True)

# -------------------------
# Helpers
# -------------------------
def safe_post(url, json_payload, timeout=3):
    try:
        requests.post(url, json=json_payload, timeout=timeout)
    except Exception:
        pass

def fetch_student_info(pk):
    if pk in student_info_cache:
        return student_info_cache[pk]
    try:
        res = requests.get(f"{STUDENT_INFO_API}{pk}/", timeout=3)
        if res.status_code == 200:
            student_info_cache[pk] = res.json()
            return student_info_cache[pk]
    except Exception:
        pass
    return None

def save_guest_snapshot(frame, top, right, bottom, left):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"guest_{ts}.jpg"
    filepath = os.path.join(GUEST_SNAPSHOT_DIR, filename)
    padding = 40
    h, w = frame.shape[:2]
    crop = frame[max(top - padding, 0):min(bottom + padding, h),
                 max(left - padding, 0):min(right + padding, w)]
    if crop.size > 0:
        try:
            cv2.imwrite(filepath, crop)
            return os.path.relpath(filepath, "media").replace("\\", "/")
        except Exception:
            return None
    return None

def save_student_snapshot(frame, top, right, bottom, left, student_pk, new_enc):
    """
    Save student snapshot if it passes checks:
    - not capped globally
    - daily limit not exceeded
    - per-student cooldown between snapshots
    - diversity check unless student has fewer than 5 total images (we allow growth)
    """
    if student_pk in capped_students:
        return None

    today = datetime.now().strftime("%Y%m%d")
    if daily_student_snapshot_count[student_pk][today] >= MAX_DAILY_SNAPSHOTS:
        return None

    now_ts = time.time()
    if now_ts - last_student_snapshot_time[student_pk] < STUDENT_SNAPSHOT_COOLDOWN:
        return None

    existing_encs = student_encodings_map.get(student_pk, [])
    # Allow growth for under-represented students (< 5 images) by bypassing diversity check:
    allow_growth = student_image_counts.get(student_pk, 0) < 5

    if existing_encs and (not allow_growth):
        try:
            dists = face_recognition.face_distance(existing_encs, new_enc)
            if np.min(dists) < DIVERSITY_THRESHOLD:
                # too similar to existing images -> skip (avoid duplicates)
                return None
        except Exception:
            # if distance check fails, fallback to skipping (safe)
            return None

    # save cropped image
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"student_{student_pk}_{ts}.jpg"
    filepath = os.path.join(STUDENT_SNAPSHOT_DIR, filename)

    padding = 40
    h, w = frame.shape[:2]
    crop = frame[max(top - padding, 0):min(bottom + padding, h),
                 max(left - padding, 0):min(right + padding, w)]
    if crop.size > 0:
        try:
            cv2.imwrite(filepath, crop)
            daily_student_snapshot_count[student_pk][today] += 1
            last_student_snapshot_time[student_pk] = now_ts
            # update in-memory counters so behavior changes immediately
            student_image_counts[student_pk] += 1
            student_encodings_map[student_pk].append(new_enc)
            if student_image_counts[student_pk] >= MAX_TOTAL_IMAGES:
                capped_students.add(student_pk)
            return os.path.relpath(filepath, "media").replace("\\", "/")
        except Exception:
            return None
    return None

def smooth_label(face_id, new_label, new_color, interval=LABEL_INTERVAL, stability_frames=LABEL_STABILITY_FRAMES):
    now_ts = time.time()
    s = label_state.get(face_id)
    if s is None:
        s = {"label": new_label, "color": new_color, "last_update": now_ts, "streak": 1}
        label_state[face_id] = s
        return new_label, new_color
    if new_label == s["label"]:
        s["streak"] += 1
    else:
        s["streak"] = 1
    if (now_ts - s["last_update"] >= interval) or (s["streak"] >= stability_frames):
        s["label"] = new_label
        s["color"] = new_color
        s["last_update"] = now_ts
        s["streak"] = 1
    label_state[face_id] = s
    return s["label"], s["color"]

def stable_prediction(face_id, candidate_pk, conf):
    """
    Keep last PREDICTION_STABILITY_FRAMES predictions for face_id.
    If they all agree on candidate_pk, return (pk, avg_conf), else (None, None).
    """
    hist = prediction_history[face_id]
    hist.append((candidate_pk, conf))
    if len(hist) > PREDICTION_STABILITY_FRAMES:
        hist.pop(0)
    labels = [h[0] for h in hist]
    if len(hist) == PREDICTION_STABILITY_FRAMES and len(set(labels)) == 1:
        return candidate_pk, float(np.mean([h[1] for h in hist]))
    return None, None

# -------------------------
# Main loop
# -------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Cannot open webcam.")

print("[INFO] Starting live recognition. Press 'q' to quit.")

frame_idx = 0
try:
    while True:
        # Reset daily logged students at day boundary
        today = datetime.now().strftime("%Y%m%d")
        if today != current_day:
            logged_students.clear()
            current_day = today
            print("[INFO] New day detected; cleared logged_students.")

        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        frame_idx += 1
        if frame_idx % FRAME_SKIP != 0:
            # show frame (no heavy processing)
            cv2.imshow("Live Face Recognition", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            continue

        small = cv2.resize(frame, (0, 0), fx=FRAME_SCALE, fy=FRAME_SCALE)
        rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        locations = face_recognition.face_locations(rgb_small, model="hog")
        encodings = face_recognition.face_encodings(rgb_small, locations)

        for (t, r, b, l), enc in zip(locations, encodings):
            # convert coordinates back to original frame scale
            top, right, bottom, left = [int(x / FRAME_SCALE) for x in (t, r, b, l)]
            label, color = "Guest", (0, 165, 255)
            student_id, pk, used_conf = None, None, 0.0

            if known_face_encodings:
                try:
                    # distance to all known encodings (fast numpy op)
                    dists = face_recognition.face_distance(known_face_encodings, enc)
                    best_idx = int(np.argmin(dists))
                    min_dist = float(dists[best_idx])

                    # quick pre-check: require some closeness (with dynamic relaxation)
                    candidate_pk = known_face_metadata[best_idx].get("pk")
                    img_count = student_image_counts.get(candidate_pk, 0)
                    relax = dynamic_distance_relaxation(img_count)
                    effective_distance_cutoff = DISTANCE_THRESHOLD + relax

                    if min_dist < effective_distance_cutoff:
                        # SVM prediction + probabilities
                        pred = svm_clf.predict([enc])[0]
                        try:
                            probs = svm_clf.predict_proba([enc])[0]
                            conf = float(np.max(probs))
                        except Exception:
                            # if SVC without probability, fallback to decision_function approx
                            conf = 0.0

                        # dynamic probability threshold (lenient for small img_count)
                        prob_thr = dynamic_prob_threshold(img_count)

                        # acceptance criteria:
                        # accept if prediction equals candidate_pk AND (conf >= prob_thr OR min_dist is very small)
                        strong_distance_cutoff = DISTANCE_THRESHOLD - 0.08  # very confident distance
                        if pred == candidate_pk and (conf >= prob_thr or min_dist <= strong_distance_cutoff):
                            # require stability across frames
                            face_key = tuple(np.round(enc[:5], 2))
                            stable_pk, stable_conf = stable_prediction(face_key, candidate_pk, conf)
                            if stable_pk is not None:
                                pk = stable_pk
                                used_conf = stable_conf
                                info = fetch_student_info(pk)
                                if info:
                                    student_id = info.get("student_id")
                                    label = f"Student {student_id} ({used_conf:.2f})"
                                    color = (0, 255, 0)
                except Exception:
                    # swallow errors to avoid crashing live loop
                    pass

            # If we recognized a student and haven't logged them yet today -> log and optionally snapshot
            if student_id:
                if student_id not in logged_students:
                    payload = {"student_id": student_id, "role": "Student"}
                    # save snapshot (only if snapshot passes checks inside the function)
                    snapshot_rel = save_student_snapshot(frame, top, right, bottom, left, pk, enc)
                    if snapshot_rel:
                        payload["snapshot"] = snapshot_rel
                    safe_post(LOG_API, payload)
                    logged_students.add(student_id)

                label = f"Student {student_id} ({used_conf:.2f})"
                color = (0, 255, 0)

            else:
                # treat as guest (deduplicate quick repeats)
                now_ts = time.time()
                guest_hash = tuple(np.round(enc, 4))
                is_dup = False

                if guest_hash in guest_last_detected and (now_ts - guest_last_detected[guest_hash] < GUEST_COOLDOWN_SECONDS):
                    is_dup = True
                else:
                    for prev in logged_guest_encodings:
                        try:
                            if face_recognition.face_distance([prev], enc)[0] < GUEST_TOLERANCE:
                                is_dup = True
                                break
                        except Exception:
                            continue

                if not is_dup:
                    guest_last_detected[guest_hash] = now_ts
                    logged_guest_encodings.append(enc)
                    snap_rel = save_guest_snapshot(frame, top, right, bottom, left)
                    payload = {"student_id": None, "role": "Guest"}
                    if snap_rel:
                        payload["snapshot"] = snap_rel
                    safe_post(LOG_API, payload)

            # draw box + smoothed label
            face_id = tuple(np.round(enc[:5], 2))
            sm_label, sm_color = smooth_label(face_id, label, color)
            cv2.rectangle(frame, (left, top), (right, bottom), sm_color, 2)
            cv2.putText(frame, sm_label, (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, sm_color, 2)

        # show frame
        cv2.imshow("Live Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
