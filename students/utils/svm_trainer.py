# students/utils/svm_trainer.py
import os
import pickle
import face_recognition
from sklearn.svm import SVC, LinearSVC
from sklearn.linear_model import SGDClassifier
from django.conf import settings

# Paths
ENCODINGS_FILE = os.path.join(settings.MEDIA_ROOT, "encodings.pkl")
CLASSIFIER_FILE = os.path.join(settings.MEDIA_ROOT, "svm_classifier.pkl")

# Thresholds
LINEAR_THRESHOLD = 10_000  # switch to LinearSVC if >= 10k samples
INCREMENTAL_THRESHOLD = 50_000  # use SGDClassifier for incremental training

def load_existing_encodings():
    """Load saved encodings and metadata."""
    if os.path.exists(ENCODINGS_FILE):
        try:
            with open(ENCODINGS_FILE, "rb") as f:
                data = pickle.load(f)
                return data.get("encodings", []), data.get("metadata", [])
        except Exception as e:
            print(f"⚠️ Failed to load existing encodings: {e}")
    return [], []

def save_encodings(encodings, metadata):
    """Save encodings + metadata."""
    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump({"encodings": encodings, "metadata": metadata}, f)

def save_classifier(clf):
    """Save classifier to file."""
    with open(CLASSIFIER_FILE, "wb") as f:
        pickle.dump(clf, f)

def load_classifier():
    """Load classifier if available."""
    if os.path.exists(CLASSIFIER_FILE):
        try:
            with open(CLASSIFIER_FILE, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load classifier: {e}")
    return None

def train_svm_classifier(encodings, metadata):
    """
    Train and save the SVM/LinearSVC/SGD model.
    - SVC(kernel="linear") for small datasets (<10k samples).
    - LinearSVC for larger datasets (10k–50k).
    - SGDClassifier for very large datasets (≥50k) with incremental support.
    """
    if not encodings:
        print("⚠️ No encodings to train.")
        return

    labels = [m["pk"] for m in metadata]
    n_samples = len(encodings)

    if n_samples < LINEAR_THRESHOLD:
        # Small dataset → standard SVC
        clf = SVC(C=1.0, kernel="linear", probability=True)
        clf.fit(encodings, labels)
        model_type = "SVC (linear)"
    elif n_samples < INCREMENTAL_THRESHOLD:
        # Medium dataset → faster LinearSVC
        clf = LinearSVC(C=1.0, max_iter=10000)
        clf.fit(encodings, labels)
        model_type = "LinearSVC"
    else:
        # Very large dataset → incremental training
        clf = SGDClassifier(loss="hinge", max_iter=1000, tol=1e-3)
        unique_labels = list(set(labels))
        clf.partial_fit(encodings, labels, classes=unique_labels)
        model_type = "SGDClassifier (incremental)"

    save_classifier(clf)
    print(f"🤖 Trained {model_type} with {len(set(labels))} students ({n_samples} samples).")

def add_encoding_from_file(filepath, pk, encodings, metadata):
    """Add encoding for a single image file."""
    try:
        img = face_recognition.load_image_file(filepath)
        encs = face_recognition.face_encodings(img)
        if encs:
            encodings.append(encs[0])
            metadata.append({"pk": pk, "filename": os.path.basename(filepath)})
            return True
    except Exception as e:
        print(f"⚠️ Could not process {filepath}: {e}")
    return False

def incremental_update(filepath, pk):
    """
    Incrementally add a new encoding and update the classifier.
    Falls back to full retraining if incremental is not available.
    """
    encodings, metadata = load_existing_encodings()
    if add_encoding_from_file(filepath, pk, encodings, metadata):
        save_encodings(encodings, metadata)

        clf = load_classifier()
        new_enc = [encodings[-1]]
        new_label = [metadata[-1]["pk"]]

        if isinstance(clf, SGDClassifier):
            clf.partial_fit(new_enc, new_label)
            save_classifier(clf)
            print(f"✅ Incrementally updated SGDClassifier for student {pk}.")
        else:
            # retrain from scratch for non-incremental models
            train_svm_classifier(encodings, metadata)
    else:
        print(f"⚠️ Failed to add encoding for student {pk}.")
