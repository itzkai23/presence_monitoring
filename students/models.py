from django.db import models
from django.contrib.auth.hashers import make_password
from django.utils import timezone

# ----------------------------
# ✅ Student Model 
# ----------------------------

class Student(models.Model):
    YEAR_CHOICES = [
        ('1st Year', '1st Year'),
        ('2nd Year', '2nd Year'),
        ('3rd Year', '3rd Year'),
        ('4th Year', '4th Year'),
    ]

    DEPARTMENT_CHOICES = [
        ('CAS', 'College of Arts and Science (CAS)'),
        ('CCJE', 'College of Criminal Justice Education (CCJE)'),
        ('CBA', 'College of Business and Accountancy (CBA)'),
        ('CCS', 'College of Computer Studies (CCS)'),
        ('CTE', 'College of Teacher Education (CTE)'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    student_id = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True)
    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES)
    course = models.CharField(max_length=100)
    year_level = models.CharField(max_length=10, choices=YEAR_CHOICES, default='1st Year')
    section = models.CharField(max_length=20)
    password = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)
    is_archived = models.BooleanField(default=False) 

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_id})"

    def save(self, *args, **kwargs):
        if not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

# ----------------------------
# ✅ Archived Student Model (with FK reference)
# ----------------------------

class ArchivedStudent(models.Model):
    reference = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True)
    archived_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Archived Student ID {self.reference.id if self.reference else 'Unknown'}"

# ----------------------------
# ✅ PresenceLog: Current Month Only
# ----------------------------

class PresenceLog(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=20, default='Student')
    department = models.CharField(max_length=100)
    purpose = models.CharField(max_length=50, default='class')
    edited = models.BooleanField(default=False)
    snapshot = models.ImageField(upload_to='guest_snapshots/', null=True, blank=True)

    def __str__(self):
        if self.student:
            return f"{self.student.student_id} - {self.student.first_name} - {self.date.strftime('%Y-%m-%d %H:%M:%S')}"
        return f"Guest - {self.date.strftime('%Y-%m-%d %H:%M:%S')}"

# ----------------------------
# ✅ Archived Presence Log (with FK reference)
# ----------------------------

class ArchivedPresenceLog(models.Model):
    reference = models.ForeignKey(PresenceLog, on_delete=models.SET_NULL, null=True, blank=True)
    archived_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Archived PresenceLog ID {self.reference.id if self.reference else 'Unknown'}"
