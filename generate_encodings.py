# scripts/generate_encodings.py
import os
import django
from collections import defaultdict, Counter
from django.conf import settings

# ----------------------------
# Setup Django environment
# ----------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "student_registration.settings")
django.setup()
from students.utils.cloud_backup import backup_student_images_to_drive
from students.utils import svm_trainer

# ----------------------------
# Paths
# ----------------------------
PHOTO_DIR = os.path.join(settings.MEDIA_ROOT, "student_photos")       # permanent photos
SNAPSHOT_DIR = os.path.join(settings.MEDIA_ROOT, "student_snapshots") # daily snapshots

# ----------------------------
# Settings
# ----------------------------
MAX_DAILY_SNAPSHOTS = 5
MAX_TOTAL_IMAGES = 10  # per student global cap

# ----------------------------
# Helpers
# ----------------------------
def is_snapshot_file(filename):
    """Check if filename looks like a student snapshot: student_<pk>_<YYYYMMDD>_*.jpg"""
    parts = filename.split("_")
    return len(parts) >= 3 and parts[0] == "student" and parts[1].isdigit()


# ----------------------------
# Main
# ----------------------------
def generate_encodings():
    """
    Process new student photos and snapshots incrementally.
    Enforces daily and global limits.
    Returns: (added_count, total_students_tracked)
    """
    # Load existing encodings
    encodings, metadata = svm_trainer.load_existing_encodings()
    existing_files = {m["filename"] for m in metadata}

    snapshots_to_delete = []

    # --- Reconstruct counts from metadata ---
    daily_count = defaultdict(lambda: defaultdict(int))  # {pk: {YYYYMMDD: count}}
    for m in metadata:
        fname = m.get("filename", "")
        if is_snapshot_file(fname):
            parts = fname.split("_")
            try:
                pk = int(parts[1])
                date_str = parts[2]  # YYYYMMDD
                daily_count[pk][date_str] += 1
            except (IndexError, ValueError):
                continue

    total_count = Counter([m["pk"] for m in metadata if m.get("pk") is not None])
    added_count = 0

    print(f"Incremental update. Tracking {len(total_count)} students, {len(encodings)} encodings.")

    # --- Scan permanent student photos ---
    if os.path.exists(PHOTO_DIR):
        for filename in os.listdir(PHOTO_DIR):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            if filename in existing_files:
                continue  # already processed

            path = os.path.join(PHOTO_DIR, filename)
            parts = filename.split("_")
            try:
                pk = int(parts[1])
            except (IndexError, ValueError):
                continue

            if total_count[pk] >= MAX_TOTAL_IMAGES:
                continue  # global cap reached

            if svm_trainer.add_encoding_from_file(path, pk, encodings, metadata):
                total_count[pk] += 1
                added_count += 1
                print(f"Added encoding from permanent photo: {filename}")

    # --- Scan daily snapshots ---
    if os.path.exists(SNAPSHOT_DIR):
        for filename in os.listdir(SNAPSHOT_DIR):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            if not is_snapshot_file(filename):
                continue

            path = os.path.join(SNAPSHOT_DIR, filename)
            parts = filename.split("_")
            try:
                pk = int(parts[1])
                date_str = parts[2]  # YYYYMMDD
            except (IndexError, ValueError):
                continue

            # Enforce per-day limit
            if daily_count[pk][date_str] >= MAX_DAILY_SNAPSHOTS:
                snapshots_to_delete.append(path)
                continue

            # Enforce global 10-image limit
            if total_count[pk] >= MAX_TOTAL_IMAGES:
                snapshots_to_delete.append(path)
                continue

            if svm_trainer.add_encoding_from_file(path, pk, encodings, metadata):
                daily_count[pk][date_str] += 1
                total_count[pk] += 1
                added_count += 1
                snapshots_to_delete.append(path)
                print(f"Added encoding from snapshot: {filename}")

    # --- Save encodings & retrain SVM ---
    svm_trainer.save_encodings(encodings, metadata)
    svm_trainer.train_svm_classifier(encodings, metadata)

    print(f"Finished. Total encodings: {len(encodings)}, Students: {len(set(m['pk'] for m in metadata))}")

    # --- Cleanup used snapshots ---
    for snap in snapshots_to_delete:
        try:
            os.remove(snap)
            print(f"Deleted snapshot: {os.path.basename(snap)}")
        except Exception as e:
            print(f"Failed to delete snapshot {snap}: {e}")

    # --- Cloud backup (permanent photos only) ---
    try:
        response = backup_student_images_to_drive()
        import json
        result = json.loads(response.content.decode())
        if any(result.get(k) for k in ("uploaded", "deleted", "errors")):
            print("Cloud backup summary:")
            for k in ("uploaded", "deleted", "errors"):
                if result.get(k):
                    print(f"   {k.capitalize()}: {result[k]}")
    except Exception as e:
        print(f"Cloud backup failed: {e}")

    return added_count, len(set(m['pk'] for m in metadata))


if __name__ == "__main__":
    added, total = generate_encodings()
    print(f"Encodings updated. Added {added}, total {total} students.")
