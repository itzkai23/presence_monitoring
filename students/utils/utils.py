from django.utils.timezone import now
from datetime import timedelta
from ..models import PresenceLog, ArchivedPresenceLog, DataAnalysis, ArchivedDataAnalysis

def archive_last_month_logs():
    today = now().date()

    # Only archive on the 1st day of each month
    if today.day != 1:
        return

    # Get last month’s year and month
    first_day_this_month = today.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    year = last_day_last_month.year
    month = last_day_last_month.month

    # Get logs from last month only
    logs = PresenceLog.objects.filter(date__year=year, date__month=month)
    if not logs.exists():
        return  # Nothing to archive

    # Copy to archive
    ArchivedPresenceLog.objects.bulk_create([
        ArchivedPresenceLog(
            student=log.student,
            date=log.date,
            role=log.role,
            department=log.department,
            purpose=log.purpose,
            edited=log.edited
        ) for log in logs
    ])

    # Remove from current logs
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