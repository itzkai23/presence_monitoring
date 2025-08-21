import os
import django
import random
from faker import Faker
from datetime import timedelta
from django.utils import timezone

# ----------------------------
# Setup Django environment
# ----------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "student_registration.settings")
django.setup()

from students.models import Student, PresenceLog

# ----------------------------
# Faker instance
# ----------------------------
fake = Faker()

# Departments & Purposes
DEPARTMENTS = [
    'CAS', 'CCJE', 'CBA', 'CCS', 'CTE'
]
PURPOSES = [
    'class', 'meeting', 'research', 'library', 'consultation', 'event'
]

# ----------------------------
# Create Fake Students (if none exist)
# ----------------------------
if Student.objects.count() == 0:
    print("No students found. Creating 10 fake students...")
    for _ in range(10):
        dept = random.choice(DEPARTMENTS)
        Student.objects.create(
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            student_id=str(fake.unique.random_number(digits=8)),
            email=fake.unique.email(),
            department=dept,
            course=fake.word().title() + " Course",
            password="password123",  # auto-hashed in save()
        )

# ----------------------------
# Create Fake Presence Logs
# ----------------------------
students = list(Student.objects.all())
created_logs = []

for _ in range(50):  # At least 50 records
    student = random.choice(students)
    log = PresenceLog.objects.create(
        student=student,
        date=fake.date_time_between(start_date="-2M", end_date="now", tzinfo=timezone.get_current_timezone()),
        role="Student",
        department=student.department,
        purpose=random.choice(PURPOSES),
        edited=random.choice([True, False])
    )
    created_logs.append(log)

print(f"✅ Created {len(created_logs)} fake PresenceLog records.")
