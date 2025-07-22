from django.contrib import admin
from .models import Student, ArchivedStudent, PresenceLog, ArchivedPresenceLog

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'student_id', 'first_name', 'last_name', 'email', 
        'year_level', 'section', 'course'
    )
    search_fields = ('student_id', 'first_name', 'last_name', 'email')
    list_filter = ('year_level', 'course', 'department')
    ordering = ('year_level', 'last_name', 'first_name')
    list_per_page = 25


@admin.register(ArchivedStudent)
class ArchivedStudentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'archived_at')
    readonly_fields = ('archived_at',)
    list_filter = ('archived_at',)
    ordering = ('-archived_at',)


@admin.register(PresenceLog)
class PresenceLogAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'role', 'department', 'purpose', 'edited')
    search_fields = ('student__student_id', 'student__first_name', 'student__last_name')
    list_filter = ('role', 'department', 'purpose', 'edited', 'date')
    date_hierarchy = 'date'
    ordering = ('-date',)


@admin.register(ArchivedPresenceLog)
class ArchivedPresenceLogAdmin(admin.ModelAdmin):
    list_display = ('reference', 'archived_at')
    readonly_fields = ('archived_at',)
    ordering = ('-archived_at',)
