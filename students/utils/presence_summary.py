import csv
from datetime import datetime
from collections import Counter
from .guest_utils import classify_guest_purpose
from .phrasebank_utils import load_phrasebank, choose_phrase

PHRASEBANK = load_phrasebank()

def load_csv_logs(filepath):
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        return list(reader)

def generate_summary_from_csv(logs, start_date, end_date):
    student_ids = set()
    guest_purposes = Counter()

    for row in logs:
        log_date = datetime.strptime(row["timestamp"], "%Y-%m-%d").date()
        if start_date <= log_date <= end_date:
            if row["student_id"]:
                student_ids.add(row["student_id"])
            elif row["guest_name"]:
                purpose = classify_guest_purpose(row.get("purpose", ""))
                guest_purposes[purpose] += 1

    student_count = len(student_ids)

    if student_count > 10:
        student_phrase = choose_phrase("student_increase", {"count": student_count}, PHRASEBANK)
    elif student_count < 5:
        student_phrase = choose_phrase("student_decrease", {"count": student_count}, PHRASEBANK)
    else:
        student_phrase = choose_phrase("student_stable", {"count": student_count}, PHRASEBANK)

    guest_phrases = []
    for category, count in guest_purposes.items():
        guest_phrases.append(
            choose_phrase(f"guest_{category}", {"count": count}, PHRASEBANK)
        )

    return f"{student_phrase} " + " ".join(guest_phrases)
