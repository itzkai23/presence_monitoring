import csv
from collections import Counter
from datetime import datetime

def load_csv_logs(file_path):
    """
    Loads log data from a CSV file.
    Each row is expected to include: timestamp, type (student/guest), student_id (optional), reason (optional).
    """
    logs = []
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            logs.append(row)
    return logs

def generate_summary_from_csv(logs, start_date, end_date):
    """
    Generates a summary of presence logs between start_date and end_date.
    It counts unique student IDs and guest visit reasons.
    """
    student_ids = set()
    guest_reasons = Counter()

    for row in logs:
        timestamp = row.get('timestamp')
        if not timestamp:
            continue  # skip malformed rows

        # Try to parse the timestamp
        try:
            log_date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            try:
                log_date = datetime.strptime(timestamp, "%Y-%m-%d").date()
            except ValueError:
                continue  # skip rows with unparseable dates

        # Only include logs within the date range
        if start_date <= log_date <= end_date:
            log_type = row.get('type')
            if log_type == 'student':
                student_ids.add(row.get('student_id'))
            elif log_type == 'guest':
                guest_reasons[row.get('reason', 'Unspecified')] += 1

    student_count = len(student_ids)
    guest_count = sum(guest_reasons.values())

    reason_summary = ", ".join(
        f"{count} for {reason}" for reason, count in guest_reasons.items()
    )

    return (
        f"During the period from {start_date.strftime('%B %d')} to {end_date.strftime('%B %d, %Y')}, "
        f"{student_count} unique students were recorded, and approximately {guest_count} guest entries were logged. "
        f"Most guest visits were for {reason_summary if reason_summary else 'unspecified reasons'}."
    )
