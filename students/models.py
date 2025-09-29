from django.db import models
from django.contrib.auth.hashers import make_password
from django.utils import timezone

# ----------------------------
# ✅ Student Model 
# ----------------------------
class Student(models.Model):
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
    password = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_id})"

    def save(self, *args, **kwargs):
        if not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)


# ----------------------------
# ✅ Archived Student Model
# ----------------------------
class ArchivedStudent(models.Model):
    student_id = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    department = models.CharField(max_length=10, blank=True, null=True)
    course = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)
    archived_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Archived {self.student_id} - {self.first_name} {self.last_name}"

# ----------------------------
# ✅ PresenceLog: Current Month Only
# ----------------------------
class PresenceLog(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    logs_timestamp = models.DateTimeField(default=timezone.now)
    role = models.CharField(max_length=20, default='Student')
    purpose = models.CharField(max_length=50, default='class')
    edited = models.BooleanField(default=False)
    snapshot = models.ImageField(upload_to='guest_snapshots/', null=True, blank=True)

    def __str__(self):
        formatted_time = self.logs_timestamp.strftime("%B %d, %Y - %I:%M %p")
        if self.student:
            return f"{self.student.student_id} - {self.student.first_name} ({formatted_time})"
        return f"Guest ({formatted_time})"


# ----------------------------
# ✅ ArchivedPresenceLog: Full Snapshot
# ----------------------------
class ArchivedPresenceLog(models.Model):
    student_id = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    logs_timestamp = models.DateTimeField(default=timezone.now)
    role = models.CharField(max_length=50, default='Student')
    department = models.CharField(max_length=100, blank=True, null=True)
    purpose = models.CharField(max_length=255, blank=True, null=True, default='class')
    archived_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        formatted_time = self.logs_timestamp.strftime("%B %d, %Y - %I:%M %p")
        if self.student_id:
            return f"{self.student_id} - {self.first_name} {self.last_name} ({formatted_time})"
        return f"Guest ({formatted_time})"
    

#DataAnalysis
class DataAnalysis(models.Model):
    SUMMARY_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    summary_type = models.CharField(max_length=10, choices=SUMMARY_TYPE_CHOICES)
    summary_date = models.DateField(default=timezone.now)  # day, week_start, or month_start
    analysis_summary = models.TextField(default="")

    class Meta:
        unique_together = ('summary_type', 'summary_date')

    def __str__(self):
        return f"{self.get_summary_type_display().title()} - {self.summary_date}"

#ArchiveDataAnalysis
class ArchivedDataAnalysis(models.Model):
    # instead of just a reference, keep a snapshot
    summary_type = models.CharField(max_length=10,  default="")
    summary_date = models.DateField(default=timezone.now)
    analysis_summary = models.TextField(default="")
    archived_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Archived {self.summary_type.title()} - {self.summary_date}"
