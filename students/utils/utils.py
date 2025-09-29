from django.utils.timezone import now
from datetime import timedelta
from ..models import PresenceLog, ArchivedPresenceLog, DataAnalysis, ArchivedDataAnalysis
from django.utils import timezone

def archive_last_month_logs():
    today = now().date()
    if today.day != 1:
        return

    first_day_this_month = today.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)

    logs = PresenceLog.objects.filter(
        date__year=last_day_last_month.year,
        date__month=last_day_last_month.month
    )

    if not logs.exists():
        return

    archived_batch = [
        ArchivedPresenceLog(
            student=log.student,
            logs_timestamp=log.logs_timestamp,
            role=log.role,
            department=log.department,
            purpose=log.purpose,
            snapshot=log.snapshot,
            reference=log  # keep FK for tracking
        )
        for log in logs
    ]
    ArchivedPresenceLog.objects.bulk_create(archived_batch, batch_size=1000)

    # Remove old logs from PresenceLog after archiving
    logs.delete()

def archive_last_month_analysis():
    today = now().date()

    # Run only on the first day of the month
    if today.day != 1:
        return

    # Get the first day of this month and the last day of the previous month
    first_day_this_month = today.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)

    year = last_day_last_month.year
    month = last_day_last_month.month

    # Get all data analysis entries from last month
    analysis_entries = DataAnalysis.objects.filter(
        summary_date__year=year,
        summary_date__month=month
    )

    if not analysis_entries.exists():
        return  # Nothing to archive

    # Move entries to ArchivedDataAnalysis
    ArchivedDataAnalysis.objects.bulk_create([
        ArchivedDataAnalysis(reference=entry)
        for entry in analysis_entries
    ])

    # Delete from original table
    analysis_entries.delete()