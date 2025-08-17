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
    logs_timestamp = models.DateTimeField(default=timezone.now)  # exact datetime of log
    role = models.CharField(max_length=20, default='Student')
    department = models.CharField(max_length=100, blank=True, null=True)
    purpose = models.CharField(max_length=50, default='class')
    snapshot = models.ImageField(upload_to='guest_snapshots/', null=True, blank=True)

    def __str__(self):
        if self.student:
            return f"{self.student.student_id} - {self.student.first_name} - {self.logs_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        return f"Guest - {self.logs_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class ArchivedPresenceLog(models.Model):
    student_id = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    logs_timestamp = models.DateTimeField(default=timezone.now)  # preserve exact log time
    role = models.CharField(max_length=50, default='Student')
    department = models.CharField(max_length=100, blank=True, null=True)
    purpose = models.CharField(max_length=255, blank=True, null=True, default='class')
    archived_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        if self.student_id:
            return f"{self.student_id} - {self.first_name} {self.last_name} ({self.logs_timestamp.strftime('%Y-%m-%d %H:%M:%S')})"
        return f"Guest ({self.logs_timestamp.strftime('%Y-%m-%d %H:%M:%S')})"
    
# ----------------------------
# ✅ Daily, Weekly, Monthly Summaries
# ----------------------------
class DataAnalysis(models.Model):
    SUMMARY_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    summary_type = models.CharField(max_length=10, choices=SUMMARY_TYPE_CHOICES)
    summary_date = models.DateField()  # This will be day, week_start, or month_start
    student_total = models.IntegerField(default=0)
    guest_total = models.IntegerField(default=0)
    analysis_summary = models.TextField()

    class Meta:
        unique_together = ('summary_type', 'summary_date')

    def __str__(self):
        return f"{self.get_summary_type_display().title()} - {self.summary_date}"

class ArchivedDataAnalysis(models.Model):
    reference = models.ForeignKey(DataAnalysis, on_delete=models.SET_NULL, null=True, blank=True)
    archived_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Archived Summary {self.reference_id if self.reference else 'Unknown'}"
