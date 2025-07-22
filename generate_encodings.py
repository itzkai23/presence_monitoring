# generate_encodings.py
import face_recognition
import os
import pickle

# Paths
PHOTO_DIR = "media/student_photos"
ENCODINGS_FILE = os.path.join("media", "encodings.pkl")

# Initialize
known_face_encodings = []
known_face_metadata = []

# Process all student photos
print("🔄 Generating new encodings...")
for filename in os.listdir(PHOTO_DIR):
    if filename.lower().endswith((".jpg", ".jpeg", ".png")):
        path = os.path.join(PHOTO_DIR, filename)
        image = face_recognition.load_image_file(path)
        encodings = face_recognition.face_encodings(image)
        if encodings:
            encoding = encodings[0]
            try:
                pk = int(filename.split("_")[1].split(".")[0])  # expects student_<id>.jpg
            except (IndexError, ValueError):
                print(f"⚠️ Skipping invalid filename: {filename}")
                continue
            known_face_encodings.append(encoding)
            known_face_metadata.append({"pk": pk})
        else:
            print(f"⚠️ No face found in: {filename}")

# Save encodings to file
with open(ENCODINGS_FILE, 'wb') as f:
    pickle.dump({
        "encodings": known_face_encodings,
        "metadata": known_face_metadata
    }, f)

print(f"✅ Encodings saved to {ENCODINGS_FILE}: {len(known_face_encodings)} faces")
