import os
import face_recognition
import pickle

PHOTO_DIR = "media/student_photos"
ENCODINGS_FILE = "encodings.pkl"

def regenerate_encodings():
    known_face_encodings = []
    known_face_metadata = []

    for filename in os.listdir(PHOTO_DIR):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            path = os.path.join(PHOTO_DIR, filename)
            image = face_recognition.load_image_file(path)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                encoding = encodings[0]
                try:
                    pk = int(filename.split("_")[1].split(".")[0])  # expects student_5.jpg
                except:
                    pk = None
                known_face_encodings.append(encoding)
                known_face_metadata.append({ "pk": pk })

    with open(ENCODINGS_FILE, 'wb') as f:
        pickle.dump({
            "encodings": known_face_encodings,
            "metadata": known_face_metadata
        }, f)

    print(f"✅ Encodings regenerated: {len(known_face_encodings)} face(s)")
