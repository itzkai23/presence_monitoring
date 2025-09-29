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
from .models import DataAnalysis, ArchivedDataAnalysis, ArchivedPresenceLog, PresenceLog, ArchivedStudent
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
from django.core.files import File

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

# ----------------------------
# Admin Login
# ----------------------------
def admin_login_view(request):
    error_message = ''

    if request.method == 'POST':
        username = request.POST.get('username')  # ✅ admin uses username instead of student_id
        password = request.POST.get('password')

        user = User.objects.filter(username=username).first()
        if user and user.check_password(password):
            login(request, user)
            if user.is_superuser:
                return redirect('presence_table')
            elif user.groups.filter(name='monitor').exists():
                return redirect('presence_record')
            else:
                return redirect('home')  # fallback
        else:
            error_message = 'Invalid username or password.'

    return render(request, 'users/Authentication/admin_login.html', {'error': error_message})


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

# -------------------------
# Data Analysis Views
# -------------------------
@login_required
@admin_required
def data_analysis(request):
    import logging
    import json
    import pandas as pd
    from datetime import timedelta, date, datetime
    import calendar as cal
    from django.utils import timezone
    from .models import Student, DataAnalysis, PresenceLog
    from .data_analysis import (
        generate_daily_summary,
        generate_weekly_summary,
        generate_monthly_summary,
    )

    logger = logging.getLogger(__name__)
    today = timezone.localdate()

    # ------------------------
    # Fetch logs
    # ------------------------
    logs_qs = PresenceLog.objects.all().values()
    logs_df = pd.DataFrame(list(logs_qs))
    logger.info(f"Fetched {len(logs_df)} logs from PresenceLog.")

    if not logs_df.empty:
        # Ensure logs_timestamp column with proper timezone handling
        local_tz = timezone.get_current_timezone()
        logs_df["logs_timestamp"] = pd.to_datetime(
            logs_df.get("logs_timestamp", pd.NaT),
            errors="coerce",
            utc=True
        )
        logs_df = logs_df.dropna(subset=["logs_timestamp"])
        logs_df["logs_timestamp"] = logs_df["logs_timestamp"].dt.tz_convert(local_tz)

        # Add date-only column for grouping
        logs_df["log_date"] = logs_df["logs_timestamp"].dt.date

        # Normalize role column
        logs_df["role"] = logs_df.get("role", "").fillna("").astype(str).str.lower()

        # Ensure student_id column
        if "student__student_id" in logs_df.columns and "student_id" not in logs_df.columns:
            logs_df["student_id"] = logs_df["student__student_id"]
        elif "student_id" not in logs_df.columns:
            if "student" in logs_df.columns:
                try:
                    pks = logs_df["student"].dropna().unique().tolist()
                    student_map = dict(
                        Student.objects.filter(pk__in=pks).values_list("pk", "student_id")
                    )
                    logs_df["student_id"] = logs_df["student"].map(student_map).fillna(pd.NA)
                except Exception:
                    logs_df["student_id"] = pd.NA
            else:
                logs_df["student_id"] = pd.NA
    else:
        logs_df = pd.DataFrame(
            columns=["logs_timestamp", "role", "student_id", "purpose", "department"]
        )

    # ------------------------
    # Period helpers
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
        if d == today:
            summary_text = generate_daily_summary(logs_df, d)
            DataAnalysis.objects.update_or_create(
                summary_type="daily",
                summary_date=d,
                defaults={"analysis_summary": summary_text},
            )
        else:
            obj, _ = DataAnalysis.objects.get_or_create(
                summary_type="daily",
                summary_date=d,
                defaults={"analysis_summary": generate_daily_summary(logs_df, d)},
            )
            summary_text = obj.analysis_summary

        summary_text = " ".join(summary_text.split())
        all_summaries.append({
            "summary_date": d,
            "analysis_summary": summary_text,
            "summary_type": "daily",
            "day_of_week": cal.day_name[d.weekday()],
            "is_previous_month": d.month != today.month or d.year != today.year,
        })

    # ------------------------
    # Weekly summaries
    # ------------------------
    for sunday in sundays:
        week_start = max(sunday - timedelta(days=6), month_start)
        if sunday == today:
            summary_text = generate_weekly_summary(logs_df, week_start)
            DataAnalysis.objects.update_or_create(
                summary_type="weekly",
                summary_date=sunday,
                defaults={"analysis_summary": summary_text},
            )
        else:
            obj, _ = DataAnalysis.objects.get_or_create(
                summary_type="weekly",
                summary_date=sunday,
                defaults={"analysis_summary": generate_weekly_summary(logs_df, week_start)},
            )
            summary_text = obj.analysis_summary

        summary_text = " ".join(summary_text.split())
        all_summaries.append({
            "summary_date": sunday,
            "analysis_summary": summary_text,
            "summary_type": "weekly",
            "day_of_week": cal.day_name[sunday.weekday()],
            "is_previous_month": sunday.month != today.month or sunday.year != today.year,
        })

    # ------------------------
    # Monthly summary
    # ------------------------
    last_day_of_month = cal.monthrange(today.year, today.month)[1]
    monthly_summary = None

    if today.day == last_day_of_month:
        summary_text = generate_monthly_summary(logs_df, month_start)
        DataAnalysis.objects.update_or_create(
            summary_type="monthly",
            summary_date=month_start,
            defaults={"analysis_summary": summary_text},
        )
        summary_text = " ".join(summary_text.split())
        monthly_summary = {
            "summary_date": today,
            "analysis_summary": summary_text,
            "summary_type": "monthly",
            "day_of_week": cal.day_name[today.weekday()],
            "is_previous_month": False,
        }
    else:
        try:
            obj = DataAnalysis.objects.get(summary_type="monthly", summary_date=month_start)
            monthly_summary = {
                "summary_date": today,
                "analysis_summary": obj.analysis_summary,
                "summary_type": "monthly",
                "day_of_week": cal.day_name[today.weekday()],
                "is_previous_month": False,
            }
        except DataAnalysis.DoesNotExist:
            pass

    # ------------------------
    # Sort summaries
    # ------------------------
    all_summaries.sort(key=lambda x: x["summary_date"], reverse=True)

    # ------------------------
    # Chart Data
    # ------------------------
    labels = [str(d) for d in days_up_to_today]
    student_counts, guest_counts = [], []

    if not logs_df.empty:
        for d in days_up_to_today:
            daily_logs = logs_df[logs_df["log_date"] == d]
            student_counts.append(int(daily_logs[daily_logs["role"] == "student"]["student_id"].nunique()))
            guest_counts.append(int(len(daily_logs[daily_logs["role"] == "guest"])) )

        # Hourly data for today
        hours = list(range(24))
        # Convert 24-hour to 12-hour format with AM/PM
        hour_labels = [
            datetime.strptime(str(h), "%H").strftime("%I %p").lstrip("0")
            for h in hours
        ]
        hourly_student_counts = []
        hourly_guest_counts = []
        today_logs = logs_df[logs_df["log_date"] == today]
        for h in hours:
            hour_logs = today_logs[today_logs["logs_timestamp"].dt.hour == h]
            hourly_student_counts.append(int(hour_logs[hour_logs["role"] == "student"]["student_id"].nunique()))
            hourly_guest_counts.append(int(len(hour_logs[hour_logs["role"] == "guest"])))

        purpose_counts_series = logs_df["purpose"].value_counts() if "purpose" in logs_df.columns else pd.Series([])
        purposes = purpose_counts_series.index.tolist()
        purpose_counts = purpose_counts_series.values.tolist()
    else:
        student_counts = guest_counts = hourly_student_counts = hourly_guest_counts = [0]*24
        hour_labels = [(datetime.strptime(str(h), "%H").strftime("%I %p").lstrip("0")) for h in range(24)]
        purposes, purpose_counts = [], []

    return render(
        request,
        "users/Admin/data_analysis.html",
        {
            "combined_summaries": all_summaries,
            "monthly_summary": monthly_summary,
            "month_label": today.strftime("%B %Y"),
            "labels": json.dumps(labels),
            "student_values": json.dumps(student_counts),
            "guest_values": json.dumps(guest_counts),
            "hour_labels": json.dumps(hour_labels),
            "hourly_student_values": json.dumps(hourly_student_counts),
            "hourly_guest_values": json.dumps(hourly_guest_counts),
            "purposes": json.dumps(purposes),
            "purpose_counts": json.dumps(purpose_counts),
        },
    )

def update_summary(summary_type, reference_date):
    """
    Update only if reference_date is "active" (today for daily,
    today's Sunday for weekly, or last day of month for monthly).
    Otherwise leave past summaries frozen.
    """
    from .models import PresenceLog, DataAnalysis
    import pandas as pd
    from datetime import timedelta
    import calendar
    from .data_analysis import (
        generate_daily_summary,
        generate_weekly_summary,
        generate_monthly_summary,
    )

    today = timezone.localdate()

    # Decide if regeneration allowed
    allow_update = (
        (summary_type == "daily" and reference_date == today)
        or (summary_type == "weekly" and reference_date == today)
        or (
            summary_type == "monthly"
            and reference_date.day == calendar.monthrange(today.year, today.month)[1]
            and reference_date == today.replace(day=1)
        )
    )
    if not allow_update:
        return  # freeze history

    # Normal update process
    if summary_type == "daily":
        start_date = reference_date
        end_date = reference_date
        store_date = start_date
        summary_fn = generate_daily_summary
    elif summary_type == "weekly":
        start_date = reference_date - timedelta(days=reference_date.weekday())
        end_date = start_date + timedelta(days=6)
        store_date = reference_date
        summary_fn = generate_weekly_summary
    elif summary_type == "monthly":
        start_date = reference_date.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)
        store_date = start_date
        summary_fn = generate_monthly_summary

    logs_qs = PresenceLog.objects.filter(
        logs_timestamp__date__range=[start_date, end_date]
    )
    logs_df = pd.DataFrame(list(logs_qs.values()))
    logs_df["logs_timestamp"] = pd.to_datetime(
        logs_df.get("logs_timestamp", pd.NaT), errors="coerce"
    )
    logs_df = logs_df.dropna(subset=["logs_timestamp"])
    logs_df["log_date"] = logs_df["logs_timestamp"].dt.date
    logs_df["role"] = logs_df.get("role", "").fillna("").astype(str).str.lower()

    summary_text = summary_fn(logs_df, start_date)

    DataAnalysis.objects.update_or_create(
        summary_type=summary_type,
        summary_date=store_date,
        defaults={"analysis_summary": summary_text},
    )
    
# -------------------------
# SINGLE ARCHIVE
# -------------------------
@admin_required
@require_POST
def archive_data_analysis(request, analysis_id):
    from django.db import transaction

    analysis = get_object_or_404(DataAnalysis, id=analysis_id)
    today = timezone.localdate()

    # Determine if the summary is from a previous month
    is_previous_month = False
    if analysis.summary_type == "daily":
        is_previous_month = (
            analysis.summary_date.month != today.month
            or analysis.summary_date.year != today.year
        )
    elif analysis.summary_type == "weekly":
        # Weekly summaries are anchored to Sunday
        # If that Sunday is still in the current month, don’t archive
        is_previous_month = (
            analysis.summary_date.month != today.month
            or analysis.summary_date.year != today.year
        )
    elif analysis.summary_type == "monthly":
        is_previous_month = not (
            analysis.summary_date.year == today.year
            and analysis.summary_date.month == today.month
        )

    if not is_previous_month:
        return JsonResponse({
            'status': 'error',
            'message': 'Cannot archive current month\'s summary.'
        })

    with transaction.atomic():
        ArchivedDataAnalysis.objects.get_or_create(
            summary_type=analysis.summary_type,
            summary_date=analysis.summary_date,
            defaults={'analysis_summary': analysis.analysis_summary},
        )
        analysis.delete()

    return JsonResponse({'status': 'success', 'message': 'Analysis archived successfully.'})


# -------------------------
# BULK ARCHIVE
# -------------------------
@admin_required
@require_POST
def bulk_archive_data_analysis(request):
    from django.db import transaction

    ids = request.POST.getlist('ids[]')
    today = timezone.localdate()
    success_count, failed_count = 0, 0

    for id_str in ids:
        try:
            analysis = DataAnalysis.objects.get(id=int(id_str))

            # Determine if the summary is from a previous month
            is_previous_month = False
            if analysis.summary_type == "daily":
                is_previous_month = (
                    analysis.summary_date.month != today.month
                    or analysis.summary_date.year != today.year
                )
            elif analysis.summary_type == "weekly":
                is_previous_month = (
                    analysis.summary_date.month != today.month
                    or analysis.summary_date.year != today.year
                )
            elif analysis.summary_type == "monthly":
                is_previous_month = not (
                    analysis.summary_date.year == today.year
                    and analysis.summary_date.month == today.month
                )

            if not is_previous_month:
                failed_count += 1
                continue

            with transaction.atomic():
                ArchivedDataAnalysis.objects.get_or_create(
                    summary_type=analysis.summary_type,
                    summary_date=analysis.summary_date,
                    defaults={'analysis_summary': analysis.analysis_summary},
                )
                analysis.delete()
                success_count += 1

        except DataAnalysis.DoesNotExist:
            failed_count += 1

    return JsonResponse({
        'status': 'success',
        'message': f'{success_count} summaries archived. {failed_count} skipped.'
    })


#Students
@admin_required
@login_required
def admin_page(request):
    students = Student.objects.all()  # ✅ Show all active students (no is_archived check needed)
    return render(request, 'users/Admin/admin_page.html', {
        'students': students,
        'department_course_map': settings.DEPARTMENT_COURSE_MAP
    })

@admin_required
def filter_students(request):
    department = request.GET.get('department', '')
    course = request.GET.get('course', '')

    students = Student.objects.all()  # ✅ No is_archived filter

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
        })

    return JsonResponse(data, safe=False)

# ----------------------------
# Archive a Student
# ----------------------------
@admin_required
@require_POST
def archive_student(request, pk):
    try:
        student = Student.objects.get(id=pk)
        
        # Create snapshot in ArchivedStudent
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
        
        # ✅ No need to mark student as archived
        return JsonResponse({'status': 'success', 'message': 'Student archived.'})
    except Student.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Student not found.'})

# ----------------------------
# Retrieve a Student from Archive
# ----------------------------
@admin_required
@require_POST
def retrieve_student(request, archived_id):
    try:
        archived = ArchivedStudent.objects.get(id=archived_id)
        
        # Restore to Student table
        Student.objects.update_or_create(
            student_id=archived.student_id,
            defaults={
                'first_name': archived.first_name,
                'last_name': archived.last_name,
                'email': archived.email,
                'department': archived.department,
                'course': archived.course,
                'password': archived.password,
                'photo': archived.photo,
            }
        )
        
        # Remove from ArchivedStudent table
        archived.delete()

        return JsonResponse({'status': 'success', 'message': 'Student retrieved.'})
    except ArchivedStudent.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Archived student not found.'})

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

    # Decode JSON
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    images = data.get('images', [])
    if not images or len(images) != 5:
        return JsonResponse({
            'status': 'error',
            'message': 'Expected 5 images (left, right, extra1, extra2, front)'
        }, status=400)

    try:
        saved_files = []
        labels = ["left", "right", "extra1", "extra2", "front"]  # match JS order

        # Ensure student_photos directory exists
        student_dir = os.path.join(settings.MEDIA_ROOT, "student_photos")
        os.makedirs(student_dir, exist_ok=True)

        for idx, image_data in enumerate(images):
            format, imgstr = image_data.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f"student_{student.id}_{labels[idx]}.{ext}"
            file_path = os.path.join(student_dir, file_name)

            # Save image locally
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(imgstr))
            saved_files.append(file_name)

            # Use the FRONT image as student.photo
            if labels[idx] == "front":
                student.photo.name = f"student_photos/{file_name}"

        student.save()

        # Regenerate encodings (optional)
        try:
            regenerate_encodings()
        except Exception as e:
            print(f"Warning: Failed to regenerate encodings: {e}")

        return JsonResponse({
            'status': 'success',
            'message': 'All 5 photos saved successfully',
            'files': saved_files
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Failed to save images: {str(e)}'}, status=400)

# -------------------------
# API Endpoints
# -------------------------
@monitor_or_admin_required
def get_presence_logs(request):
    today = localtime(now()).date()
    start_of_day = localtime(now()).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = localtime(now()).replace(hour=23, minute=59, second=59, microsecond=999999)

    logs = (
        PresenceLog.objects.select_related('student')
        .filter(logs_timestamp__gte=start_of_day, logs_timestamp__lte=end_of_day)
        .order_by('-logs_timestamp')
    )

    data = []
    for log in logs:
        timestamp = localtime(log.logs_timestamp)
        formatted_ts = timestamp.strftime("%B %d, %Y - %I:%M %p")

        if log.student:
            data.append({
                'student_id': log.student.student_id,
                'name': f"{log.student.first_name} {log.student.last_name}",
                'logs_timestamp': formatted_ts,
                'role': log.role,
                'department': log.student.department,  # ✅ from Student
                'purpose': log.purpose,
                'edited': log.edited,
                'id': log.id,
                'snapshot': None,
            })
        else:
            data.append({
                'student_id': "Guest",
                'name': "Anonymous Visitor",
                'logs_timestamp': formatted_ts,
                'role': log.role,
                'department': "Unknown",  # ✅ Guests labeled Unknown
                'purpose': log.purpose,
                'edited': log.edited,
                'id': log.id,
                'snapshot': request.build_absolute_uri(log.snapshot.url) if log.snapshot else None,
            })

    return JsonResponse(data, safe=False)


@csrf_exempt
@require_POST
def log_presence_api(request):
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        role = data.get('role', 'Student')
        snapshot_path = data.get('snapshot')

        print(f"📥 Incoming Log: student_id={student_id}, role={role}, snapshot={snapshot_path}")

        if student_id:
            # ✅ Student log
            student = Student.objects.get(student_id=student_id)
            today = now().date()
            already_logged = PresenceLog.objects.filter(
                student=student,
                logs_timestamp__date=today
            ).exists()

            if already_logged:
                return JsonResponse({'status': 'exists', 'message': 'Already logged today'})

            PresenceLog.objects.create(
                student=student,
                role=role,
                purpose="class",  # ✅ default purpose for students
                logs_timestamp=now()
            )
        else:
            # ✅ Guest log
            log = PresenceLog(
                student=None,
                role="Guest",
                purpose="visit",  # ✅ default purpose for guests
                logs_timestamp=now()
            )

            if snapshot_path:
                full_path = os.path.join(settings.MEDIA_ROOT, snapshot_path).replace("\\", "/")
                if os.path.exists(full_path):
                    try:
                        with open(full_path, 'rb') as f:
                            filename = os.path.basename(snapshot_path)
                            log.snapshot.save(filename, File(f), save=False)

                        # cleanup raw snapshot
                        os.remove(full_path)
                        print(f"🧹 Removed raw snapshot: {full_path}")
                    except Exception as e:
                        print(f"⚠️ Failed to save or delete snapshot: {e}")

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
            "department": student.department,  # ✅ pulled directly
        })
    except Student.DoesNotExist:
        return JsonResponse({"error": "Student not found"}, status=404)

from django.http import JsonResponse
from django.utils.timezone import localtime
from .models import PresenceLog, ArchivedPresenceLog, Student

def student_logs_api(request):
    # Get student from session
    student_id = request.session.get("student_id")
    if not student_id:
        return JsonResponse({"error": "Not logged in"}, status=403)

    student = Student.objects.filter(student_id=student_id).first()
    if not student:
        return JsonResponse({"error": "Student not found"}, status=404)

    # ------------------------
    # Active logs (PresenceLog)
    # ------------------------
    active_logs = PresenceLog.objects.filter(student=student).order_by("-logs_timestamp")

    active_data = [
        {
            "id": log.id,
            "logs_timestamp": localtime(log.logs_timestamp).isoformat(),
            "logs_timestamp_display": localtime(log.logs_timestamp).strftime("%B %d, %Y - %I:%M %p"),
            "purpose": log.purpose,
            "role": "Student",
            "edited": log.edited,
        }
        for log in active_logs
    ]

    # ------------------------
    # Archived logs (ArchivedPresenceLog)
    # ------------------------
    archived_logs = ArchivedPresenceLog.objects.filter(student_id=student_id).order_by("-logs_timestamp")

    archived_data = [
        {
            "id": log.id,
            "logs_timestamp": localtime(log.logs_timestamp).isoformat(),
            "logs_timestamp_display": localtime(log.logs_timestamp).strftime("%B %d, %Y - %I:%M %p"),
            "purpose": log.purpose,
            "role": "Student",
            "edited": getattr(log, "edited", False),  # fallback if not in model
        }
        for log in archived_logs
    ]

    # Merge both
    all_logs = active_data + archived_data

    # Sort descending by timestamp
    all_logs.sort(key=lambda x: x["logs_timestamp"], reverse=True)

    return JsonResponse(all_logs, safe=False)

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

        # ✅ Restrict editing only to today's logs
        if log.logs_timestamp.date() != now().date():
            return JsonResponse({"status": "error", "message": "You can only edit your purpose today."})

        if log.role == "Student":
            session_id = request.session.get("student_id")
            if session_id != (log.student.student_id if log.student else None):
                return JsonResponse({"status": "error", "message": "You can only edit your own purpose."})

            # ✅ Restrict to only one edit
            if log.edited:
                return JsonResponse({"status": "error", "message": "You can only edit your purpose once!"})

            if new_purpose not in allowed_student_purposes:
                return JsonResponse({"status": "error", "message": "Invalid purpose selection."})

            log.purpose = new_purpose
            log.edited = True   # ✅ mark as edited

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


#PresenceRecords
@monitor_or_admin_required
@login_required
def presence_record(request):
    return render(request, 'users/Admin/presence_record.html')

@login_required
@admin_required
def presence_table(request):
    # If student is logged in via session (not Django auth), redirect them to their UI
    if request.session.get('student_id'):
        return redirect('home')

    # ✅ Allow admin
    if request.user.is_superuser:
        return render(request, 'users/Admin/presence_table.html')

    # Redirect monitor to their UI
    if request.user.groups.filter(name='monitor').exists():
        return redirect('presence-record')

    # Fallback for any other case
    return redirect('login')

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
            department = "Unknown"

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
        department=log.student.department if log.student else "Unknown",   # ✅ fix here
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
                department=log.student.department if log.student else "Unknown",  # ✅ fixed here
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

from generate_encodings import generate_encodings
# ----------------------------
# Trigger generate_encodings script
# ----------------------------
@login_required
def run_generate_encodings(request):
    """
    Trigger the encoding generation and return stats for frontend badge.
    Returns JSON with added encodings, total students, and pending images.
    """
    try:
        added, total = generate_encodings()

        # Compute pending count after generation
        pending_count = _compute_pending_count()
        
        return JsonResponse({
            "status": "success",
            "message": f"Encodings updated. Added {added}, total {total} students.",
            "pending_count": pending_count
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# ----------------------------
# Serve the encodings.pkl file
# ----------------------------
@login_required
def serve_encodings(request):
    """
    Serve encodings.pkl as a binary file.
    """
    enc_path = os.path.join(settings.MEDIA_ROOT, "encodings.pkl")
    if os.path.exists(enc_path):
        return FileResponse(open(enc_path, 'rb'), content_type='application/octet-stream')
    return JsonResponse({'error': 'Encodings file not found'}, status=404)


# ----------------------------
# Check for pending encodings
# ----------------------------
@login_required
def check_pending_encodings(request):
    """
    Count students who still have < 10 images (permanent + snapshots).
    Returns pending_count and list of pending student PKs.
    """
    pending_ids = _compute_pending_ids()
    return JsonResponse({
        "pending_count": len(pending_ids),
        "pending_ids": pending_ids
    })


# ----------------------------
# Internal helpers
# ----------------------------
def _compute_pending_ids():
    """
    Helper: returns list of student PKs with < 10 total images.
    Counts both permanent photos and snapshots.
    """
    photo_dir = os.path.join(settings.MEDIA_ROOT, "student_photos")
    snapshot_dir = os.path.join(settings.MEDIA_ROOT, "student_snapshots")
    enc_file = os.path.join(settings.MEDIA_ROOT, "encodings.pkl")

    total_count = defaultdict(int)  # {pk: total_images_count}

    # Count existing encodings
    if os.path.exists(enc_file):
        with open(enc_file, "rb") as f:
            data = pickle.load(f)
            for meta in data.get("metadata", []):
                pk = meta.get("pk")
                if pk is not None:
                    total_count[pk] += 1

    # Count snapshots
    if os.path.exists(snapshot_dir):
        for filename in os.listdir(snapshot_dir):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            parts = filename.split("_")
            if len(parts) < 3 or parts[0] != "student":
                continue
            try:
                pk = int(parts[1])
                total_count[pk] += 1
            except ValueError:
                continue

    # Identify pending students based on permanent photos
    pending_ids = []
    if os.path.exists(photo_dir):
        for filename in os.listdir(photo_dir):
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            try:
                pk = int(filename.split("_")[1].split(".")[0])
            except (IndexError, ValueError):
                continue
            if total_count[pk] < 10:
                pending_ids.append(pk)

    return pending_ids


def _compute_pending_count():
    """Helper: returns count of students pending new images."""
    return len(_compute_pending_ids())

import subprocess
from django.http import JsonResponse
import sys

face_recognition_process = None

def start_face_recognition(request):
    global face_recognition_process
    if face_recognition_process is None:
        # Get project root (one level up from students/)
        base_dir = os.path.dirname(os.path.dirname(__file__))
        script_path = os.path.join(base_dir, "live_face_recognition.py")
        python_exe = sys.executable  # ensures it runs with your Django venv Python

        face_recognition_process = subprocess.Popen(
            [python_exe, script_path],
            cwd=base_dir,  # run from project root
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        return JsonResponse({"message": f"✅ Face recognition started (PID {face_recognition_process.pid})"})
    return JsonResponse({"message": "⚠️ Already running"})

def stop_face_recognition(request):
    global face_recognition_process
    if face_recognition_process:
        face_recognition_process.terminate()
        output, _ = face_recognition_process.communicate(timeout=5)
        print("🔴 Face recognition logs:\n", output.decode())  # debug: see errors in Django terminal
        face_recognition_process = None
        return JsonResponse({"message": "🛑 Face recognition stopped"})
    return JsonResponse({"message": "⚠️ Not running"})

#StudentUI
def student_logs_percentage(request):
    student_id = request.session.get("student_id")
    if not student_id:
        return JsonResponse({"error": "Not logged in"}, status=403)

    # Resolve student.pk from the custom student_id in session
    student = Student.objects.filter(student_id=student_id).first()
    if not student:
        return JsonResponse({"error": "Student not found"}, status=404)

    # Use timezone-aware datetimes
    today = timezone.localdate()
    month_start = timezone.make_aware(datetime.combine(today.replace(day=1), datetime.min.time()))
    next_month = (month_start + timezone.timedelta(days=32)).replace(day=1)

    # Total days so far in the month
    total_days = (today - month_start.date()).days + 1  

    # Query presence logs using PK
    logs = PresenceLog.objects.filter(
        student_id=student.pk,   # ✅ now using the PK
        logs_timestamp__gte=month_start,
        logs_timestamp__lt=next_month
    ).dates("logs_timestamp", "day")

    attended_days = len(logs)
    percentage = int((attended_days / total_days) * 100) if total_days > 0 else 0

    # Debug prints
    print("DEBUG student_logs_percentage →")
    print(" session student_id:", student_id)
    print(" resolved pk:", student.pk)
    print(" month_start:", month_start)
    print(" next_month:", next_month)
    print(" total_days:", total_days)
    print(" attended_days:", attended_days)
    print(" logs:", list(logs))

    return JsonResponse({"percentage": percentage})

#BackupCloud (Guest Only)
import os
from datetime import datetime
from django.http import JsonResponse
from django.conf import settings
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# ----------------------------
# Google Drive Folder IDs
# ----------------------------
GUEST_FOLDER_ID = "1Fa2ZCYWBI7dR5KtS9Skdkz6V3aPHffXk"  

def get_or_create_drive_folder(drive, parent_id, folder_name):
    """Find existing folder or create a new one under parent_id."""
    query = (
        f"'{parent_id}' in parents and trashed=false "
        f"and title='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
    )
    file_list = drive.ListFile({'q': query}).GetList()
    if file_list:
        return file_list[0]['id']
    folder = drive.CreateFile({
        'title': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [{'id': parent_id}]
    })
    folder.Upload()
    return folder['id']

def authenticate_drive():
    """Handles Google Drive authentication with token.json."""
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token_path = os.path.join(PROJECT_ROOT, "token.json")

    gauth = GoogleAuth()
    gauth.LoadCredentialsFile(token_path)
    if gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    return GoogleDrive(gauth)

# ----------------------------
# BACKUP GUEST SNAPSHOTS
# ----------------------------
def backup_guest_images_to_drive(request):
    """
    Upload all guest snapshots to Google Drive (grouped by month).
    Delete them locally after success.
    """
    try:
        drive = authenticate_drive()
        uploaded, deleted, errors = [], [], []

        guest_path = os.path.join(settings.MEDIA_ROOT, "guest_snapshots")

        if os.path.exists(guest_path):
            for filename in os.listdir(guest_path):
                file_path = os.path.join(guest_path, filename)
                if os.path.isfile(file_path):
                    try:
                        ts = datetime.fromtimestamp(os.path.getmtime(file_path))
                        month_folder = ts.strftime("%Y-%m")

                        month_folder_id = get_or_create_drive_folder(drive, GUEST_FOLDER_ID, month_folder)

                        gfile = drive.CreateFile({
                            'title': filename,
                            'parents': [{'id': month_folder_id}]
                        })
                        gfile.SetContentFile(file_path)
                        gfile.Upload()
                        uploaded.append(f"guest_snapshots/{month_folder}/{filename}")

                        if hasattr(gfile, "content") and gfile.content:
                            gfile.content.close()
                        del gfile

                        os.remove(file_path)
                        deleted.append(filename)

                    except Exception as inner_e:
                        errors.append(f"{filename}: {str(inner_e)}")

        return JsonResponse({
            "status": "success",
            "uploaded": uploaded,
            "deleted": deleted,
            "errors": errors
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

@monitor_or_admin_required
def count_guest_snapshots(request):
    guest_path = os.path.join(settings.MEDIA_ROOT, "guest_snapshots")
    count = 0
    if os.path.exists(guest_path):
        count = len([
            f for f in os.listdir(guest_path)
            if os.path.isfile(os.path.join(guest_path, f))
        ])
    return JsonResponse({"count": count})


from django.shortcuts import render

def test_camera(request):
    return render(request, "users/Interface/test_camera.html")
