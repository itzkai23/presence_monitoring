from django.contrib import admin
from .models import (
    Student, ArchivedStudent,
    PresenceLog, ArchivedPresenceLog,
    DataAnalysis, ArchivedDataAnalysis
)

# ----------------------------
# ✅ Student Admin
# ----------------------------
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("student_id", "first_name", "last_name",
                    "department", "course", "email")
    search_fields = ("student_id", "first_name", "last_name", "email")
    list_filter = ("department",)
    ordering = ("student_id",)
    actions = ["archive_students"]

    def archive_students(self, request, queryset):
        for student in queryset:
            ArchivedStudent.objects.create(
                student_id=student.student_id,
                first_name=student.first_name,
                last_name=student.last_name,
                email=student.email,
                department=student.department,
                course=student.course,
                password=student.password,
                photo=student.photo
            )
            # Delete the original student
            student.delete()
        self.message_user(request, "Selected students have been archived.")
    archive_students.short_description = "Archive selected students"


# ----------------------------
# ✅ Archived Student Admin
# ----------------------------
@admin.register(ArchivedStudent)
class ArchivedStudentAdmin(admin.ModelAdmin):
    list_display = ("student_id", "first_name", "last_name", "archived_at")
    search_fields = ("student_id", "first_name", "last_name")
    list_filter = ("archived_at",)
    ordering = ("-archived_at",)
    actions = ["retrieve_students"]

    def retrieve_students(self, request, queryset):
        for archived in queryset:
            Student.objects.update_or_create(
                student_id=archived.student_id,
                defaults={
                    "first_name": archived.first_name,
                    "last_name": archived.last_name,
                    "email": archived.email,
                    "department": archived.department,
                    "course": archived.course,
                    "password": archived.password,
                    "photo": archived.photo
                }
            )
            # Delete from archive after restoring
            archived.delete()
        self.message_user(request, "Selected archived students have been restored.")
    retrieve_students.short_description = "Retrieve selected students"


# ----------------------------
# ✅ Presence Log Admin
# ----------------------------
@admin.register(PresenceLog)
class PresenceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "student_name", "role", "purpose", "logs_timestamp", "has_snapshot")
    search_fields = ("student__student_id", "student__first_name", "student__last_name", "role")
    list_filter = ("role", "purpose", "logs_timestamp")
    date_hierarchy = "logs_timestamp"
    ordering = ("-logs_timestamp",)

    def student_name(self, obj):
        if obj.student:
            return f"{obj.student.first_name} {obj.student.last_name}"
        return "Guest"
    student_name.short_description = "Name"

    def has_snapshot(self, obj):
        return bool(obj.snapshot)
    has_snapshot.boolean = True
    has_snapshot.short_description = "Snapshot"


# ----------------------------
# ✅ Archived Presence Log Admin
# ----------------------------
@admin.register(ArchivedPresenceLog)
class ArchivedPresenceLogAdmin(admin.ModelAdmin):
    list_display = (
        "student_id", "first_name", "last_name",
        "role", "department", "purpose",
        "logs_timestamp", "archived_at"
    )
    search_fields = ("student_id", "first_name", "last_name", "role", "department")
    list_filter = ("role", "department", "purpose", "archived_at")
    date_hierarchy = "logs_timestamp"
    ordering = ("-logs_timestamp",)


# ----------------------------
# ✅ Data Analysis Admin
# ----------------------------
@admin.register(DataAnalysis)
class DataAnalysisAdmin(admin.ModelAdmin):
    list_display = ("summary_type", "summary_date", "short_summary")
    search_fields = ("summary_type", "summary_date")
    list_filter = ("summary_type", "summary_date")
    ordering = ("-summary_date",)

    def short_summary(self, obj):
        return (obj.analysis_summary[:75] + "...") if len(obj.analysis_summary) > 75 else obj.analysis_summary
    short_summary.short_description = "Summary"


# ----------------------------
# ✅ Archived Data Analysis Admin
# ----------------------------
@admin.register(ArchivedDataAnalysis)
class ArchivedDataAnalysisAdmin(admin.ModelAdmin):
    list_display = ("summary_type", "summary_date", "archived_at", "short_summary")
    search_fields = ("summary_type", "summary_date")
    list_filter = ("summary_type", "archived_at")
    ordering = ("-archived_at",)

    def short_summary(self, obj):
        return (obj.analysis_summary[:75] + "...") if len(obj.analysis_summary) > 75 else obj.analysis_summary
    short_summary.short_description = "Summary"
