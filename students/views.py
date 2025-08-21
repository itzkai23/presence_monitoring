from django.shortcuts import render, redirect
from .forms import StudentRegistrationForm
from django.contrib.auth.hashers import check_password, make_password
from .models import Student
from django.contrib.auth import logout, login
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from .decorators import admin_required, monitor_or_admin_required
import random
import json
import base64
from django.conf import settings
from django.utils.timezone import now
from .utils.utils import archive_last_month_logs, archive_last_month_analysis
from .models import DataAnalysis, ArchivedDataAnalysis, ArchivedPresenceLog, PresenceLog
from .utils.encoding_utils import regenerate_encodings  
import os
import sys
from django.http import FileResponse
from django.core.files.storage import default_storage
import traceback
import pandas as pd
from django.http import HttpResponse
from datetime import datetime, timedelta, date
from django.db.models import Sum
from .decorators import admin_required
from collections import defaultdict
import csv
from django.utils import timezone
from collections import Counter
import pickle
MODEL_PATH = os.path.join(settings.BASE_DIR, 'students', 'model', 'ml_model.pkl')
with open(MODEL_PATH, 'rb') as file:
    ml_model = pickle.load(file)
import joblib
import numpy as np
from django.db.models import Count
from django.db.models.functions import TruncDate
from calendar import monthrange
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
import calendar
from django.contrib import messages
from django.shortcuts import render, get_object_or_404
from django.utils.timezone import localtime, now, make_aware
from datetime import datetime, time
from students.data_analysis import (
    generate_daily_summary,
    generate_weekly_summary,
    generate_monthly_summary
)


# Login / Logout
def login_view(request):
    error_message = ''

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        password = request.POST.get('password')

        user = User.objects.filter(username=student_id).first()
        if user and user.check_password(password):
            login(request, user)
            if user.is_superuser:
                return redirect('presence_table')
            elif user.groups.filter(name='monitor').exists():
                return redirect('presence_record')
            else:
                return redirect('home')

        student = Student.objects.filter(student_id=student_id).first()
        if student:
            if check_password(password, student.password):
                request.session['student_id'] = student.student_id
                request.session['student_name'] = f"{student.first_name} {student.last_name}"
                return redirect('home')
            else:
                error_message = 'Incorrect password.'
        else:
            error_message = 'Student ID not found.'

    return render(request, 'users/Authentication/login.html', {'error': error_message})

def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('login')

# Registration and OTP
def register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            request.session['pending_registration'] = form.cleaned_data
            otp = str(random.randint(100000, 999999))
            request.session['otp'] = otp
            request.session['otp_email'] = email

            send_mail(
                subject='CMU Registration OTP Code',
                message=f"Dear {form.cleaned_data['first_name']},\n\nYour OTP code is: {otp}\nThis will expire soon.",
                from_email='no-reply@cmu.edu.ph',
                recipient_list=[email],
                fail_silently=False,
            )
            return redirect('otp_code')
    else:
        form = StudentRegistrationForm()
    return render(request, 'users/Authentication/register.html', {'form': form})

def otp_code(request):
    return render(request, 'users/Authentication/OTP.html')

def register_success(request):
    return render(request, 'users/Authentication/register_success.html')

def forgotpass(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        student = Student.objects.filter(email=email).first()
        if not student:
            return JsonResponse({'status': 'error', 'message': 'Email not registered as a CMU student.'})

        otp = str(random.randint(100000, 999999))
        request.session['otp'] = otp
        request.session['otp_email'] = email

        send_mail(
            subject='CMU OTP Verification Code',
            message=f'Dear {student.first_name},\n\nYour OTP is: {otp}\nThis code will expire in 5 minutes.',
            from_email='no-reply@cmu.edu.ph',
            recipient_list=[email],
            fail_silently=False,
        )

        return JsonResponse({'status': 'otp_sent', 'message': 'OTP sent to your email address.'})

    return render(request, 'users/Authentication/forpass.html')

def enternewpass(request):
    if not request.session.get('verified_reset'):
        return redirect('forgotpass')

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            return JsonResponse({'status': 'error', 'message': 'Passwords do not match.'})

        email = request.session.get('otp_email')
        try:
            student = Student.objects.get(email=email)
            student.password = make_password(new_password)
            student.save()
            request.session.flush()
            return JsonResponse({'status': 'success', 'message': 'Password updated successfully.'})
        except Student.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Student not found.'})

    return render(request, 'users/Authentication/enternewpass.html')

@csrf_protect
def verify_reset_otp(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        otp_input = request.POST.get('otp')

        otp_stored = request.session.get('otp')
        otp_email = request.session.get('otp_email')

        if otp_input == otp_stored and email == otp_email:
            request.session['verified_reset'] = True
            return JsonResponse({
                'status': 'success',
                'message': 'OTP verified. You may now reset your password.',
                'redirect_url': '/enternewpass/'
            })

        return JsonResponse({'status': 'error', 'message': 'Invalid OTP or email.'})

    if request.session.get('otp') and request.session.get('otp_email'):
        return render(request, 'users/Authentication/verify_reset_otp.html')
    else:
        return redirect('forgotpass')

@csrf_protect
def verify_otp(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        otp_input = request.POST.get('otp')

        otp_stored = request.session.get('otp')
        otp_email = request.session.get('otp_email')
        registration_data = request.session.get('pending_registration')

        if otp_input == otp_stored and email == otp_email:
            if registration_data:
                new_student = Student(
                    student_id=registration_data['student_id'],
                    first_name=registration_data['first_name'],
                    last_name=registration_data['last_name'],
                    email=registration_data['email'],
                    course=registration_data['course'],
                    department=registration_data['department'],
                    password=make_password(registration_data['password'])
                )
                new_student.save()
                request.session.flush()
                return JsonResponse({'status': 'success', 'message': 'OTP verified and registration completed.'})
            return JsonResponse({'status': 'error', 'message': 'No registration data found in session.'})
        return JsonResponse({'status': 'error', 'message': 'Invalid OTP or email.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

# Interfaces
def home(request):
    if not request.session.get('student_id'):
        return redirect('login')
    return render(request, 'users/Interface/home.html')

@login_required
@admin_required
def data_analysis(request):
    import logging
    logger = logging.getLogger(__name__)
    today = timezone.localdate()

    # ------------------------
    # Fetch logs
    # ------------------------
    logs_qs = PresenceLog.objects.all().values()
    logs_df = pd.DataFrame(list(logs_qs))
    logger.info(f"Fetched {len(logs_df)} logs from PresenceLog.")

    if not logs_df.empty:
        if 'logs_timestamp' not in logs_df.columns:
            logs_df['logs_timestamp'] = pd.NaT
        else:
            logs_df['logs_timestamp'] = pd.to_datetime(logs_df['logs_timestamp'], errors='coerce')
        logs_df = logs_df.dropna(subset=['logs_timestamp'])
        logs_df['log_date'] = logs_df['logs_timestamp'].dt.date
    else:
        logs_df = pd.DataFrame(columns=['logs_timestamp', 'role', 'student_id', 'purpose', 'department'])

    from .data_analysis import generate_daily_summary, generate_weekly_summary, generate_monthly_summary
    from datetime import timedelta, date
    import calendar
    import calendar as cal

    # ------------------------
    # Helper: month info
    # ------------------------
    month_start = today.replace(day=1)
    days_up_to_today = [month_start + timedelta(days=i) for i in range((today - month_start).days + 1)]

    def get_sundays(year, month, up_to_date):
        sundays = []
        d = date(year, month, 1)
        while d.weekday() != 6:
            d += timedelta(days=1)
        while d.month == month and d <= up_to_date:
            sundays.append(d)
            d += timedelta(days=7)
        return sundays

    sundays = get_sundays(today.year, today.month, today)

    all_summaries = []

    # ------------------------
    # Daily summaries
    # ------------------------
    for d in days_up_to_today:
        try:
            summary_text = generate_daily_summary(logs_df, d)
        except Exception as e:
            summary_text = f"Error generating daily summary: {e}"
            logger.error(summary_text)
        # Convert to single paragraph
        summary_text = ' '.join(summary_text.split())
        all_summaries.append({
            'summary_date': d,
            'analysis_summary': summary_text,
            'summary_type': 'daily',
            'day_of_week': calendar.day_name[d.weekday()]
        })

    # ------------------------
    # Weekly summaries (only Sundays)
    # ------------------------
    for sunday in sundays:
        week_start = sunday - timedelta(days=6)
        if week_start < month_start:
            week_start = month_start
        try:
            summary_text = generate_weekly_summary(logs_df, week_start)
        except Exception as e:
            summary_text = f"Error generating weekly summary: {e}"
            logger.error(summary_text)
        summary_text = ' '.join(summary_text.split())
        all_summaries.append({
            'summary_date': sunday,
            'analysis_summary': summary_text,
            'summary_type': 'weekly',
            'day_of_week': calendar.day_name[sunday.weekday()]
        })

    # ------------------------
    # Monthly summary
    # ------------------------
    # Check if today is the last day of the month
    last_day_of_month = cal.monthrange(today.year, today.month)[1]
    monthly_summary = None
    if today.day == last_day_of_month:
        try:
            monthly_summary_text = generate_monthly_summary(logs_df, month_start)
        except Exception as e:
            monthly_summary_text = f"Error generating monthly summary: {e}"
            logger.error(monthly_summary_text)
        monthly_summary_text = ' '.join(monthly_summary_text.split())

        monthly_summary = {
            'summary_date': today,
            'analysis_summary': monthly_summary_text,
            'summary_type': 'monthly',
            'day_of_week': calendar.day_name[today.weekday()]
        }

    # ------------------------
    # Sort all summaries: latest first
    # ------------------------
    all_summaries.sort(key=lambda x: x['summary_date'], reverse=True)

    # ------------------------
    # Debug: fallback if logs_df empty
    # ------------------------
    if logs_df.empty:
        logger.warning("PresenceLog table is empty. No summaries will be generated.")

    return render(request, 'users/Admin/data_analysis.html', {
        'combined_summaries': all_summaries,
        'monthly_summary': monthly_summary,
    })


def normalize_summary_date(summary_date, period):
    """
    Aligns summary_date to the correct start date for the given period.
    - daily: same date
    - weekly: Monday of the week containing summary_date (matches update_summary storage)
    - monthly: first day of the month
    """
    if period == "daily":
        return summary_date
    elif period == "weekly":
        # Return Monday of the week containing the date
        return summary_date - timedelta(days=summary_date.weekday())
    elif period == "monthly":
        return summary_date.replace(day=1)
    else:
        raise ValueError(f"Invalid period: {period}")
    
def update_summary(summary_type, reference_date):
    """Update DataAnalysis with consistent counting rules for students (unique) and guests (row count)."""
    from .models import PresenceLog, DataAnalysis
    import pandas as pd
    from datetime import timedelta, date
    from .data_analysis import generate_daily_summary, generate_weekly_summary, generate_monthly_summary

    # 1️⃣ Determine date range
    if summary_type == 'daily':
        start_date = reference_date
        end_date = reference_date
        store_date = start_date
    elif summary_type == 'weekly':
        start_date = reference_date - timedelta(days=reference_date.weekday())  # Monday
        end_date = start_date + timedelta(days=6)  # Sunday
        store_date = end_date  # store weekly summary under Sunday
    elif summary_type == 'monthly':
        start_date = reference_date.replace(day=1)
        # end_date = last day of month
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)
        store_date = start_date
    else:
        raise ValueError("Invalid summary type")

    # 2️⃣ Fetch logs for the date range
    logs_qs = PresenceLog.objects.filter(logs_timestamp__date__range=[start_date, end_date])
    logs_df = pd.DataFrame(list(logs_qs.values()))

    # 3️⃣ Ensure datetime column exists
    if not logs_df.empty:
        if 'logs_timestamp' not in logs_df.columns:
            logs_df['logs_timestamp'] = pd.NaT
        else:
            logs_df['logs_timestamp'] = pd.to_datetime(logs_df['logs_timestamp'], errors='coerce')
        logs_df = logs_df.dropna(subset=['logs_timestamp'])
        # Add log_date column for summaries
        logs_df['log_date'] = logs_df['logs_timestamp'].dt.date
    else:
        logs_df = pd.DataFrame(columns=['logs_timestamp', 'role', 'student_id', 'purpose', 'department', 'log_date'])

    # 4️⃣ Ensure role column exists
    if 'role' not in logs_df.columns:
        logs_df['role'] = ''

    # 5️⃣ Counting logic
    students_count = logs_df.loc[logs_df['role'].str.lower() == 'student', 'student_id'].nunique() if not logs_df.empty else 0
    guests_count = int((logs_df['role'].str.lower() == 'guest').sum()) if not logs_df.empty else 0

    # 6️⃣ Generate textual summary
    try:
        if summary_type == 'daily':
            summary_text = generate_daily_summary(logs_df, start_date)
        elif summary_type == 'weekly':
            summary_text = generate_weekly_summary(logs_df, start_date)
        elif summary_type == 'monthly':
            summary_text = generate_monthly_summary(logs_df, start_date)
    except Exception as e:
        summary_text = f"Error generating summary: {e}"

    # 7️⃣ Save or update DataAnalysis
    DataAnalysis.objects.update_or_create(
        summary_type=summary_type,
        summary_date=store_date,
        defaults={
            'student_total': students_count,
            'guest_total': guests_count,
            'analysis_summary': summary_text
        }
    )

@admin_required
def archived_analysis_view(request):
    archived_entries = ArchivedDataAnalysis.objects.select_related('reference').order_by('-archived_at')

    return render(request, 'users/Admin/archived_analysis.html', {
        'archived_entries': archived_entries
    })


@login_required
@admin_required
def presence_table(request):
    # If student is logged in via session (not Django auth), redirect them to their UI
    if request.session.get('student_id'):
        return redirect('home')

    # ✅ Allow admin
    if request.user.is_superuser:
        archive_last_month_logs()                       # ⬅️ run auto‑archive if today is the 1st
        return render(request, 'users/Admin/presence_table.html')

    # Redirect monitor to their UI
    if request.user.groups.filter(name='monitor').exists():
        return redirect('presence-record')

    # Fallback for any other case
    return redirect('login')

@admin_required
@login_required
def admin_page(request):
    students = Student.objects.filter(is_archived=False)  # 🟢 Show only active
    return render(request, 'users/Admin/admin_page.html', {
        'students': students,
        'department_course_map': settings.DEPARTMENT_COURSE_MAP
    })

@monitor_or_admin_required
@login_required
def presence_record(request):
    return render(request, 'users/Admin/presence_record.html')

@admin_required
def filter_students(request):
    department = request.GET.get('department', '')
    course = request.GET.get('course', '')

    students = Student.objects.filter(is_archived=False)  # 👈 exclude archived by default

    if department:
        students = students.filter(department=department)
    if course:
        students = students.filter(course=course)

    data = []
    for student in students:
        data.append({
            'id': student.id,
            'student_id': student.student_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'email': student.email,
            'course': student.course,
            'photo_url': student.photo.url if student.photo else '',
            'is_archived': student.is_archived,  # optional but useful
        })

    return JsonResponse(data, safe=False)

@admin_required
def get_courses_by_department(request):
    department = request.GET.get('department')
    courses = settings.DEPARTMENT_COURSE_MAP.get(department, [])
    return JsonResponse({'courses': courses})

@csrf_protect
@require_POST
def upload_student_photo(request, id):
    try:
        student = Student.objects.get(id=id)
    except Student.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Student not found'}, status=404)

    data = json.loads(request.body)
    image_data = data.get('image_data')
    if not image_data:
        return JsonResponse({'status': 'error', 'message': 'No image data received'}, status=400)

    format, imgstr = image_data.split(';base64,')
    ext = format.split('/')[-1]
    image = ContentFile(base64.b64decode(imgstr), name=f'student_{student.id}.{ext}')
    student.photo = image
    student.save()

    regenerate_encodings()  # 👈 automatically update encodings

    return JsonResponse({
        'status': 'success',
        'new_photo_url': request.build_absolute_uri(student.photo.url)
    })

# API Endpoints
@monitor_or_admin_required
def get_presence_logs(request):
    # Use localtime to get today in your timezone
    today = localtime(now()).date()

    # Use range filtering with start and end of day in localtime
    start_of_day = localtime(now()).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = localtime(now()).replace(hour=23, minute=59, second=59, microsecond=999999)

    logs = (
        PresenceLog.objects.select_related('student')
        .filter(logs_timestamp__gte=start_of_day, logs_timestamp__lte=end_of_day)
        .exclude(student__is_archived=True)
        .order_by('-logs_timestamp')
    )

    data = []
    for log in logs:
        timestamp = localtime(log.logs_timestamp)  # convert each log to localtime
        if log.student:
            data.append({
                'student_id': log.student.student_id,
                'name': f"{log.student.first_name} {log.student.last_name}",
                'date': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'role': log.role,
                'department': log.student.department,
                'purpose': log.purpose,
                'id': log.id,
                'snapshot': None,
            })
        else:
            data.append({
                'student_id': "Guest",
                'name': "Anonymous Visitor",
                'date': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'role': log.role,
                'department': log.department or "Unknown",
                'purpose': log.purpose,
                'id': log.id,
                'snapshot': log.snapshot.url if log.snapshot else None,
            })

    return JsonResponse(data, safe=False)

@csrf_exempt
@require_POST
def log_presence_api(request):
    try:
        # Support both JSON and multipart/form-data
        if request.content_type == "application/json":
            data = json.loads(request.body)
            student_id = data.get('student_id')
            role = data.get('role', 'Student')
            department = data.get('department', 'Unknown')
            snapshot_file = None  # No snapshot in JSON
        else:
            student_id = request.POST.get('student_id')
            role = request.POST.get('role', 'Student')
            department = request.POST.get('department', 'Unknown')
            snapshot_file = request.FILES.get('snapshot')

        print(f"📥 Incoming Log: student_id={student_id}, role={role}, department={department}, file={snapshot_file}")

        if student_id:
            # Student presence logging
            student = Student.objects.get(student_id=student_id)
            today = now().date()
            already_logged = PresenceLog.objects.filter(student=student, logs_timestamp__date=today).exists()
            if already_logged:
                return JsonResponse({'status': 'exists', 'message': 'Already logged today'})

            PresenceLog.objects.create(
                student=student,
                role=role,
                department=student.department,
                purpose="class",
                logs_timestamp=now()
            )
        else:
            # Guest presence logging
            log = PresenceLog(
                student=None,
                role="Guest",
                department=department,
                purpose="visit",
                logs_timestamp=now()
            )

            if snapshot_file:
                filename = snapshot_file.name
                log.snapshot.save(filename, snapshot_file, save=False)

            log.save()

        return JsonResponse({'status': 'success', 'message': 'Logged successfully'})

    except Exception as e:
        print(f"❌ Exception during presence logging: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)})

def get_student_info(request, pk):
    try:
        student = Student.objects.get(pk=pk)
        return JsonResponse({
            "name": f"{student.first_name} {student.last_name}",
            "student_id": student.student_id,
            "department": student.department
        })
    except Student.DoesNotExist:
        return JsonResponse({"error": "Student not found"}, status=404)


def student_logs_api(request):
    student_id = request.session.get("student_id")
    if not student_id:
        return JsonResponse([], safe=False)

    logs = PresenceLog.objects.filter(student__student_id=student_id).order_by("-date")
    data = [
        {
            "id": log.id,
            "date": log.date.strftime("%Y-%m-%dT%H:%M:%S"),
            "purpose": log.purpose,
            "role": log.role,
        }
        for log in logs
    ]
    return JsonResponse(data, safe=False)


@csrf_exempt
@require_POST
@admin_required
def delete_guest_log(request, log_id):
    try:
        log = PresenceLog.objects.get(id=log_id)

        if log.student is not None:
            return JsonResponse({"status": "error", "message": "Only guest logs can be deleted."})

        # Delete snapshot image if it exists
        if log.snapshot and os.path.isfile(log.snapshot.path):
            try:
                os.remove(log.snapshot.path)
                print(f"🗑️ Deleted snapshot: {log.snapshot.path}")
            except Exception as e:
                print(f"⚠️ Failed to delete snapshot: {e}")

        # Delete the log entry
        log.delete()
        return JsonResponse({"status": "success", "message": "Guest log and snapshot deleted."})

    except PresenceLog.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Log not found."})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


@csrf_exempt
@require_POST
def update_purpose(request, log_id):
    try:
        data = json.loads(request.body)
        new_purpose = data.get("purpose", "").strip()

        allowed_student_purposes = ["class", "appointment", "event", "study", "library"]

        log = PresenceLog.objects.get(id=log_id)

        if log.date.date() != now().date():
            return JsonResponse({"status": "error", "message": "Only today's logs can be edited."})

        if log.role == "Student":
            session_id = request.session.get("student_id")
            if session_id != (log.student.student_id if log.student else None):
                return JsonResponse({"status": "error", "message": "You can only edit your own purpose."})
            if log.edited:
                return JsonResponse({"status": "error", "message": "Students can only edit once."})
            if new_purpose not in allowed_student_purposes:
                return JsonResponse({"status": "error", "message": "Invalid purpose selection."})

            log.purpose = new_purpose
            log.edited = True

        elif log.role == "Guest":
            if not request.user.is_authenticated or not request.user.is_superuser:
                return JsonResponse({"status": "error", "message": "Only admins can edit guest purposes."})
            log.purpose = new_purpose

        log.save()
        return JsonResponse({"status": "success", "message": "Purpose updated successfully."})

    except PresenceLog.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Presence log not found."})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

# -------------------------
# PRESENCE LOG LISTING
# -------------------------
@admin_required
@login_required
def presence_logs_month(request):
    today = now().date()  # today's date
    logs = (
        PresenceLog.objects.select_related('student')
        .filter(logs_timestamp__date__lt=today)  # ONLY before today
        .exclude(student__is_archived=True)
        .order_by('-logs_timestamp')
    )

    data = []
    has_previous_month_records = False

    current_month = today.month
    current_year = today.year

    for log in logs:
        is_previous_month = log.logs_timestamp.month != current_month or log.logs_timestamp.year != current_year
        if is_previous_month:
            has_previous_month_records = True

        # Prepare name and other fields safely
        if log.student:
            full_name = f"{log.student.first_name} {log.student.last_name}"
            student_id = log.student.student_id
            department = log.student.department
        else:
            full_name = "Anonymous Visitor"
            student_id = "Guest"
            department = log.department or "Unknown"

        data.append({
            'id': log.id,
            'student_id': student_id,
            'name': full_name,
            'logs_timestamp': log.logs_timestamp,  # <-- pass datetime object
            'role': log.role,
            'department': department,
            'purpose': log.purpose,
            'is_previous_month': is_previous_month,
        })

    if has_previous_month_records:
        messages.info(request, "There are records from previous months ready to archive.")

    return render(request, 'users/Admin/presence_logs_month.html', {
        'logs': data,
        'month': today.strftime('%B %Y'),
    })

# -------------------------
# SINGLE ARCHIVE
# -------------------------
@admin_required
@require_POST
def archive_log(request, log_id):
    log = get_object_or_404(PresenceLog, id=log_id)
    today = now()

    if log.logs_timestamp.year == today.year and log.logs_timestamp.month == today.month:
        return JsonResponse({'status': 'error', 'message': 'Cannot archive current month records.'})

    # Safely copy data into archive
    ArchivedPresenceLog.objects.create(
        student_id=log.student.student_id if log.student else None,
        first_name=log.student.first_name if log.student else None,
        last_name=log.student.last_name if log.student else None,
        logs_timestamp=log.logs_timestamp,
        role=log.role,
        department=log.student.department if log.student else log.department,
        purpose=log.purpose,
    )

    log.delete()
    return JsonResponse({'status': 'success', 'message': 'Record archived successfully.'})


# -------------------------
# BULK ARCHIVE
# -------------------------
@admin_required
@require_POST
def bulk_archive_logs(request):
    ids = request.POST.getlist('ids[]')
    today = now()
    success_count = 0
    failed_count = 0

    for id_str in ids:
        try:
            log = PresenceLog.objects.get(id=int(id_str))

            # Skip current month
            if log.logs_timestamp.year == today.year and log.logs_timestamp.month == today.month:
                failed_count += 1
                continue

            # Safely copy data into archive
            ArchivedPresenceLog.objects.create(
                student_id=log.student.student_id if log.student else None,
                first_name=log.student.first_name if log.student else None,
                last_name=log.student.last_name if log.student else None,
                logs_timestamp=log.logs_timestamp,
                role=log.role,
                department=log.student.department if log.student else log.department,
                purpose=log.purpose,
            )

            log.delete()
            success_count += 1
        except PresenceLog.DoesNotExist:
            failed_count += 1

    return JsonResponse({
        'status': 'success',
        'message': f'{success_count} records archived. {failed_count} records failed or skipped.'
    })


# -------------------------
# ARCHIVED LOG LISTING
# -------------------------
@admin_required
def archived_logs(request):
    archived_logs = ArchivedPresenceLog.objects.order_by('-archived_at')
    return render(request, 'users/Admin/archived_logs.html', {
        'archived_logs': archived_logs
    })

@monitor_or_admin_required
def get_archived_logs(request):
    logs = ArchivedPresenceLog.objects.order_by('-archived_at')
    data = []

    for log in logs:
        data.append({
            'student_id': log.student_id or 'Guest',
            'name': f"{log.first_name} {log.last_name}".strip() or 'Anonymous Visitor',
            'date': log.logs_timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.logs_timestamp else '',
            'role': log.role or '',
            'department': log.department or "Unknown",
            'purpose': log.purpose or '',
            'archived_at': log.archived_at.strftime('%Y-%m-%d %H:%M:%S'),
        })

    return JsonResponse(data, safe=False)

@admin_required
def archived_students(request):
    archived_students = Student.objects.filter(is_archived=True)
    return render(request, 'users/Admin/archived_students.html', {
        'archived_students': archived_students
    })

@admin_required
@require_POST
def archive_student(request, pk):
    try:
        student = Student.objects.get(id=pk)
        student.is_archived = True
        student.save()
        return JsonResponse({'status': 'success', 'message': 'Student archived.'})
    except Student.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Student not found.'})

@admin_required
@require_POST
def retrieve_student(request, pk):
    try:
        student = Student.objects.get(id=pk, is_archived=True)
        student.is_archived = False
        student.save()
        return JsonResponse({'status': 'success', 'message': 'Student retrieved.'})
    except Student.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Archived student not found.'})

def serve_encodings(request):
    enc_path = os.path.join(settings.BASE_DIR, "encodings.pkl")
    if os.path.exists(enc_path):
        return FileResponse(open(enc_path, 'rb'), content_type='application/octet-stream')
    return JsonResponse({'error': 'Encodings file not found'}, status=404)