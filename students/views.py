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

# ------------------------
# Load Phrasebank CSV
# ------------------------
def load_phrasebank():
    phrasebank = defaultdict(list)
    file_path = os.path.join(settings.BASE_DIR, 'data', 'phrasebank.csv')
    if os.path.exists(file_path):
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                phrasebank[row['category']].append(row['phrase'])
    return phrasebank

phrasebank = load_phrasebank()

def get_phrase(category):
    return random.choice(phrasebank[category]) if phrasebank[category] else ""

# ----------------------------
# Lazy-load ML model (safe)
# ----------------------------
_ml_model = None
def get_ml_model():
    global _ml_model
    if _ml_model is None:
        try:
            model_path = os.path.join(os.path.dirname(__file__), "model", "ml_model.pkl")
            if os.path.exists(model_path):
                _ml_model = joblib.load(model_path)
            else:
                _ml_model = None
        except Exception:
            _ml_model = None
    return _ml_model

# ----------------------------
# Helper Functions
# ----------------------------
def interpret_purpose(purpose_counts):
    """Return human-friendly interpretation of the dominant and top purposes."""
    if not purpose_counts:
        return "No purposes recorded."

    total_purposes = sum(purpose_counts.values())
    sorted_purposes = sorted(purpose_counts.items(), key=lambda x: x[1], reverse=True)

    meaning_map = {
        "class": "indicates regular academic activity.",
        "study": "suggests students are utilizing campus resources for independent or group work.",
        "appointment": "implies planned meetings or consultations.",
        "event": "may indicate special gatherings affecting traffic flow.",
        "visit": "suggests non-academic guest interactions.",
        "delivery": "highlights logistical and supply movements on campus."
    }

    top_purposes_texts = []
    for i, (purpose, count) in enumerate(sorted_purposes[:3]):
        pct = (count / total_purposes) * 100 if total_purposes > 0 else 0
        meaning = meaning_map.get(purpose, "shows a unique activity pattern.")
        top_purposes_texts.append(f"**{purpose}** ({pct:.1f}%) which {meaning}")

    if len(top_purposes_texts) == 1:
        return f"The dominant purpose was {top_purposes_texts[0]}"
    else:
        joined = "; ".join(top_purposes_texts)
        return f"The top purposes were: {joined}."

def security_suggestions(guest_count, student_count, total, peak_metric, context):
    """Group-level security suggestions based on counts and peaks."""
    suggestions = []
    if guest_count > student_count:
        suggestions.append("Consider tighter guest check-in and ID verification.")
    if peak_metric and peak_metric > (total * 0.3):
        suggestions.append(f"Increase security personnel during peak {context} to manage high traffic.")
    if total > 50:
        suggestions.append("Install automated counting systems to track movement in real-time.")
    return " ".join(suggestions) if suggestions else "Current security measures appear sufficient for recorded traffic."

# ----------------------------
# Forecast helper (tries ML, falls back to rolling mean)
# ----------------------------
def forecast_next_count(period, reference_date):
    """
    period: 'daily', 'weekly', 'monthly'
    reference_date: date object (for daily), week_start date (for weekly), month-start date (for monthly)
    """
    ml = get_ml_model()
    # We will attempt to use a very simple feature (total_count) if model can accept it,
    # otherwise fall back to rolling mean from DB counts.
    try:
        if period == 'daily':
            # get last 14 days counts (excluding reference_date)
            qs = PresenceLog.objects.filter(date__date__gte=(reference_date - timedelta(days=14)),
                                            date__date__lt=reference_date)
            days = qs.annotate(day=TruncDate('date')).values('day').annotate(cnt=Count('id')).order_by('day')
            counts = [d['cnt'] for d in days]
            if ml and counts:
                total = sum(counts[-7:]) if len(counts) >= 1 else 0
                try:
                    pred = ml.predict([[int(total)]])
                    return int(np.round(pred[0]))
                except Exception:
                    return int(round(np.mean(counts[-7:])) if counts else 0)
            else:
                return int(round(np.mean(counts[-7:])) if counts else 0)

        elif period == 'weekly':
            # last 8 weeks counts
            qs = PresenceLog.objects.annotate(week=TruncWeek('date')).values('week').annotate(cnt=Count('id')).order_by('week')
            weeks = [w['cnt'] for w in qs if w['week'].date() < reference_date]
            if ml and weeks:
                total = sum(weeks[-4:]) if len(weeks) >= 1 else 0
                try:
                    pred = ml.predict([[int(total)]])
                    return int(np.round(pred[0]))
                except Exception:
                    return int(round(np.mean(weeks[-3:])) if weeks else 0)
            else:
                return int(round(np.mean(weeks[-3:])) if weeks else 0)

        else:  # monthly
            qs = PresenceLog.objects.annotate(month=TruncMonth('date')).values('month').annotate(cnt=Count('id')).order_by('month')
            months = [m['cnt'] for m in qs if m['month'].date() < reference_date]
            if ml and months:
                total = sum(months[-3:]) if len(months) >= 1 else 0
                try:
                    pred = ml.predict([[int(total)]])
                    return int(np.round(pred[0]))
                except Exception:
                    return int(round(np.mean(months[-3:])) if months else 0)
            else:
                return int(round(np.mean(months[-3:])) if months else 0)

    except Exception:
        return 0

# ----------------------------
# Summary Generators (expect presence_data to be a DataFrame where 'date' is datetime)
# ----------------------------
def generate_daily_summary(presence_data, current_date):
    # Ensure dates are comparable
    current_date_only = current_date if isinstance(current_date, date) else current_date.date()
    day_df = presence_data[presence_data['date'].dt.date == current_date_only].copy()

    # Early return if no records for this date
    if day_df.empty:
        readable_date = current_date_only.strftime("%A, %B %d, %Y")
        return f"No summary to display for {readable_date}."

    # Get previous day's data
    prev_date_only = current_date_only - timedelta(days=1)
    prev_df = presence_data[presence_data['date'].dt.date == prev_date_only].copy()

    total = len(day_df)
    students = int((day_df['role'].str.lower() == 'student').sum()) if 'role' in day_df else 0
    guests = int((day_df['role'].str.lower() == 'guest').sum()) if 'role' in day_df else 0

    top_dept = None
    if not day_df[day_df['role'].str.lower() == 'student'].empty:
        dept_counts = day_df[day_df['role'].str.lower() == 'student']['department'].value_counts()
        top_dept = dept_counts.idxmax() if not dept_counts.empty else None

    purposes = day_df['purpose'].value_counts().to_dict() if 'purpose' in day_df else {}

    peak_hour = None
    try:
        peak_hour = int(day_df['date'].dt.hour.value_counts().idxmax())
    except Exception:
        pass

    # Directly handle trend comparison without compare_to_previous()
    if prev_df.empty:
        trend_text = "No previous day's data available for comparison."
    else:
        prev_total = len(prev_df)
        if prev_total == 0:
            trend_text = "Previous day had zero entries, so no percentage change can be calculated."
        else:
            diff = total - prev_total
            pct_change = (diff / prev_total) * 100
            if diff > 0:
                trend_text = f"An increase of {diff} entries ({pct_change:.1f}%) compared to the previous day."
            elif diff < 0:
                trend_text = f"A decrease of {abs(diff)} entries ({abs(pct_change):.1f}%) compared to the previous day."
            else:
                trend_text = "No change compared to the previous day."

    forecast = forecast_next_count('daily', current_date_only)

    high_traffic = 0
    try:
        ml = get_ml_model()
        if ml is not None:
            try:
                pred = ml.predict([[int(total)]])
                if isinstance(pred[0], (int, float)):
                    high_traffic = int(pred[0] > 0)
                else:
                    high_traffic = 1 if str(pred[0]).lower() in ("high", "1", "true", "yes") else 0
            except Exception:
                pass
    except Exception:
        pass

    readable_date = current_date_only.strftime("%A, %B %d, %Y")
    summary = f"On {readable_date}, a total of {total} presence entries were logged. "
    summary += f"{high_traffic} entries were flagged as high-traffic indicators. " if high_traffic else ""
    summary += f"Out of {total} entries, {students} were students ({(students/total*100):.1f}%) and {guests} were guests ({(guests/total*100):.1f}%). "
    if top_dept:
        summary += f"The department with the most student entries was {top_dept}. "
    if purposes:
        summary += interpret_purpose(purposes) + " "
    if peak_hour is not None:
        summary += f"Peak presence hour was around {peak_hour}:00. "
    summary += trend_text + " "
    summary += f"Forecast for tomorrow: approximately {forecast} entries. "
    summary += security_suggestions(
        guests, students, total,
        day_df['date'].dt.hour.value_counts().max() if not day_df.empty else 0,
        'hour'
    )

    return summary.strip()

def generate_weekly_summary(presence_data, reference_date):
    """
    Generates a summary for the week starting Monday and ending Sunday.
    If reference_date is Sunday, use the Monday of that same week.
    """
    # Align to Monday start
    week_start = reference_date - timedelta(days=reference_date.weekday())
    week_end = week_start + timedelta(days=6)

    # Filter for this week's range (Mon → Sun)
    week_df = presence_data[
        (presence_data['date'].dt.date >= week_start) &
        (presence_data['date'].dt.date <= week_end)
    ].copy()

    # Previous week range
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = prev_week_start + timedelta(days=6)
    prev_df = presence_data[
        (presence_data['date'].dt.date >= prev_week_start) &
        (presence_data['date'].dt.date <= prev_week_end)
    ].copy()

    students = len(week_df.loc[week_df['role'].str.lower() == 'student', 'id'].unique()) \
        if 'role' in week_df.columns and 'id' in week_df.columns else 0
    guests = len(week_df.loc[week_df['role'].str.lower() == 'guest', 'id'].unique()) \
        if 'role' in week_df.columns and 'id' in week_df.columns else 0
    total = students + guests

    # Top department
    top_dept = None
    if 'role' in week_df.columns and 'department' in week_df.columns:
        student_df = week_df[week_df['role'].str.lower() == 'student']
        if not student_df.empty:
            dept_counts = student_df['department'].value_counts()
            top_dept = dept_counts.idxmax() if not dept_counts.empty else None

    purposes = week_df['purpose'].value_counts().to_dict() if 'purpose' in week_df.columns else {}
    peak_day = week_df['date'].dt.day_name().value_counts().idxmax() if not week_df.empty else None

    # Compare with previous week
    prev_students = len(prev_df.loc[prev_df['role'].str.lower() == 'student', 'id'].unique())
    prev_guests = len(prev_df.loc[prev_df['role'].str.lower() == 'guest', 'id'].unique())
    prev_total = prev_students + prev_guests

    if prev_total == 0:
        trend_text = "No previous data available for comparison."
    else:
        diff = total - prev_total
        pct = (diff / prev_total) * 100
        if diff > 0:
            trend_text = f"This is an increase of {abs(diff)} entries ({pct:.1f}%) compared to the previous week."
        elif diff < 0:
            trend_text = f"This is a decrease of {abs(diff)} entries ({pct:.1f}%) compared to the previous week."
        else:
            trend_text = "This matches the previous week exactly."

    forecast = forecast_next_count('weekly', week_start)

    summary = (
        f"Week of {week_start.strftime('%B %d, %Y')} to {week_end.strftime('%B %d, %Y')}: "
        f"{total} unique individuals. "
        f"{students} were students ({(students / total * 100 if total else 0):.1f}%) and "
        f"{guests} were guests ({(guests / total * 100 if total else 0):.1f}%). "
    )
    if top_dept:
        summary += f"Top department: {top_dept}. "
    if purposes:
        summary += interpret_purpose(purposes) + " "
    if peak_day:
        summary += f"Peak presence day was {peak_day}. "
    summary += trend_text + " "
    summary += f"Forecast for next week: approximately {forecast} entries. "
    summary += security_suggestions(
        guests, students, total,
        week_df['date'].dt.date.value_counts().max() if not week_df.empty else 0,
        'day'
    )

    return summary.strip()

def generate_monthly_summary(presence_data, month, year):
    # Filter for current month/year
    month_df = presence_data[
        (presence_data['date'].dt.month == month) &
        (presence_data['date'].dt.year == year)
    ].copy()

    # Get previous month range
    prev_month_end = (date(year, month, 1) - timedelta(days=1))
    prev_month_start = prev_month_end.replace(day=1)
    prev_df = presence_data[
        (presence_data['date'].dt.month == prev_month_start.month) &
        (presence_data['date'].dt.year == prev_month_start.year)
    ].copy()

    total = len(month_df)
    students = int((month_df['role'].str.lower() == 'student').sum()) if 'role' in month_df else 0
    guests = int((month_df['role'].str.lower() == 'guest').sum()) if 'role' in month_df else 0

    # Top department among students
    top_dept = None
    if not month_df[month_df['role'].str.lower() == 'student'].empty:
        dept_counts = month_df[month_df['role'].str.lower() == 'student']['department'].value_counts()
        top_dept = dept_counts.idxmax() if not dept_counts.empty else None

    purposes = month_df['purpose'].value_counts().to_dict() if 'purpose' in month_df else {}

    # Week-of-month peak using Sunday-based weeks
    peak_week = None
    if not month_df.empty:
        # Shift dates so Sunday is treated as the first day of the week
        month_df['week_of_month'] = (
            ((month_df['date'] - pd.offsets.Week(weekday=6))
             .dt.day - 1) // 7 + 1
        )
        peak_week = int(month_df['week_of_month'].value_counts().idxmax())

    # Inline comparison to previous month
    prev_total = len(prev_df)
    if prev_total == 0:
        trend_text = "No previous data available for comparison."
    else:
        diff = total - prev_total
        pct = (diff / prev_total) * 100
        if diff > 0:
            trend_text = f"This is an increase of {abs(diff)} entries ({pct:.1f}%) compared to the previous month."
        elif diff < 0:
            trend_text = f"This is a decrease of {abs(diff)} entries ({pct:.1f}%) compared to the previous month."
        else:
            trend_text = "This matches the previous month exactly."

    forecast = forecast_next_count('monthly', date(year, month, 1))

    summary = f"{date(year, month, 1).strftime('%B %Y')}: {total} entries. "
    summary += f"{students} were students ({(students/total*100 if total else 0):.1f}%) and {guests} were guests ({(guests/total*100 if total else 0):.1f}%). "
    if top_dept:
        summary += f"Top department: {top_dept}. "
    if purposes:
        summary += interpret_purpose(purposes) + " "
    if peak_week:
        suffix = {1: '1st', 2: '2nd', 3: '3rd'}.get(peak_week, f"{peak_week}th")
        summary += f"The {suffix} Sunday-based week of the month had the highest presence, indicating the busiest period. "
    summary += trend_text + " "
    summary += f"Forecast for next month: approximately {forecast} entries. "
    summary += security_suggestions(
        guests,
        students,
        total,
        month_df['week_of_month'].value_counts().max() if not month_df.empty else 0,
        'week'
    )

    return summary.strip()

def update_summary(summary_type, summary_date):
    """
    summary_type: 'daily', 'weekly', 'monthly'
    summary_date: a datetime.date for the period.
    """
    if summary_type not in ('daily', 'weekly', 'monthly'):
        raise ValueError("summary_type must be 'daily', 'weekly', or 'monthly'")
    if not isinstance(summary_date, date):
        raise ValueError("summary_date must be a datetime.date")

    normalized_date = normalize_summary_date(summary_date, summary_type)

    # Determine period boundaries
    if summary_type == 'daily':
        start = normalized_date
        end = normalized_date
    elif summary_type == 'weekly':
        start = normalized_date
        end = start + timedelta(days=6)  # Always ends Sunday
    else:  # monthly
        start = normalized_date
        last_day = monthrange(normalized_date.year, normalized_date.month)[1]
        end = date(normalized_date.year, normalized_date.month, last_day)

    # Fetch logs with 90-day lookback for trend analysis
    lookback_days = 90
    logs_qs = PresenceLog.objects.filter(
        date__date__gte=(start - timedelta(days=lookback_days)),
        date__date__lte=end
    )
    df = pd.DataFrame(list(logs_qs.values('date', 'role', 'department', 'purpose', 'id')))

    student_total = PresenceLog.objects.filter(
        date__date__range=(start, end), role__iexact='student'
    ).values('student_id').distinct().count()

    guest_qs = PresenceLog.objects.filter(
        date__date__range=(start, end), role__iexact='guest'
    )
    guest_distinct_snapshots = guest_qs.exclude(snapshot__isnull=True).values('snapshot').distinct().count()
    guest_total = guest_distinct_snapshots if guest_distinct_snapshots > 0 else guest_qs.count()

    if df.empty:
        DataAnalysis.objects.update_or_create(
            summary_type=summary_type,
            summary_date=normalized_date,
            defaults={
                'student_total': student_total,
                'guest_total': guest_total,
                'analysis_summary': "No presence data for this period."
            }
        )
        return

    if summary_type == 'daily':
        analysis_text = generate_daily_summary(df, start)
    elif summary_type == 'weekly':
        analysis_text = generate_weekly_summary(df, summary_date)
    else:
        analysis_text = generate_monthly_summary(df, normalized_date.month, normalized_date.year)

    DataAnalysis.objects.update_or_create(
        summary_type=summary_type,
        summary_date=normalized_date,
        defaults={
            'student_total': student_total,
            'guest_total': guest_total,
            'analysis_summary': analysis_text
        }
    )
def update_summary(summary_type, summary_date):
    """
    summary_type: 'daily', 'weekly', 'monthly'
    summary_date: a datetime.date for the period.
    """
    if summary_type not in ('daily', 'weekly', 'monthly'):
        raise ValueError("summary_type must be 'daily', 'weekly', or 'monthly'")
    if not isinstance(summary_date, date):
        raise ValueError("summary_date must be a datetime.date")

    normalized_date = normalize_summary_date(summary_date, summary_type)

    # Determine period boundaries
    if summary_type == 'daily':
        start = normalized_date
        end = normalized_date
    elif summary_type == 'weekly':
        start = normalized_date
        end = start + timedelta(days=6)  # Always ends Sunday
    else:  # monthly
        start = normalized_date
        last_day = monthrange(normalized_date.year, normalized_date.month)[1]
        end = date(normalized_date.year, normalized_date.month, last_day)

    # Fetch logs with 90-day lookback for trend analysis
    lookback_days = 90
    logs_qs = PresenceLog.objects.filter(
        date__date__gte=(start - timedelta(days=lookback_days)),
        date__date__lte=end
    )
    df = pd.DataFrame(list(logs_qs.values('date', 'role', 'department', 'purpose', 'id')))

    student_total = PresenceLog.objects.filter(
        date__date__range=(start, end), role__iexact='student'
    ).values('student_id').distinct().count()

    guest_qs = PresenceLog.objects.filter(
        date__date__range=(start, end), role__iexact='guest'
    )
    guest_distinct_snapshots = guest_qs.exclude(snapshot__isnull=True).values('snapshot').distinct().count()
    guest_total = guest_distinct_snapshots if guest_distinct_snapshots > 0 else guest_qs.count()

    if df.empty:
        DataAnalysis.objects.update_or_create(
            summary_type=summary_type,
            summary_date=normalized_date,
            defaults={
                'student_total': student_total,
                'guest_total': guest_total,
                'analysis_summary': "No presence data for this period."
            }
        )
        return

    if summary_type == 'daily':
        analysis_text = generate_daily_summary(df, start)
    elif summary_type == 'weekly':
        analysis_text = generate_weekly_summary(df, summary_date)
    else:
        analysis_text = generate_monthly_summary(df, normalized_date.month, normalized_date.year)

    DataAnalysis.objects.update_or_create(
        summary_type=summary_type,
        summary_date=normalized_date,
        defaults={
            'student_total': student_total,
            'guest_total': guest_total,
            'analysis_summary': analysis_text
        }
    )

@login_required
@admin_required
def data_analysis(request):
    archive_last_month_analysis()
    today = timezone.localdate()

    # Update today's summaries
    for summary_type in ['daily', 'weekly', 'monthly']:
        update_summary(summary_type, today)

    def get_last_day_of_month(d):
        last_day = monthrange(d.year, d.month)[1]
        return d.replace(day=last_day)

    month_start = today.replace(day=1)
    month_last = get_last_day_of_month(today)

    # Fetch entries
    daily_entries = DataAnalysis.objects.filter(
        summary_type='daily',
        summary_date__range=(month_start, month_last)
    ).order_by('summary_date')

    weekly_entries = DataAnalysis.objects.filter(
        summary_type='weekly',
        summary_date__range=(month_start, month_last)
    ).order_by('summary_date')

    monthly_entries = DataAnalysis.objects.filter(
        summary_type='monthly',
        summary_date=month_start
    )

    daily_map = {entry.summary_date: entry for entry in daily_entries}
    weekly_map = {entry.summary_date: entry for entry in weekly_entries}
    monthly_map = {entry.summary_date: entry for entry in monthly_entries}

    # Generate all dates for this month
    days_in_month = [month_start + timedelta(days=i) for i in range((month_last - month_start).days + 1)]
    days_up_to_today = [d for d in days_in_month if d <= today]

    # --- DAILY ---
    full_daily_list = []
    for d in days_up_to_today:
        entry = daily_map.get(d)
        full_daily_list.append({
            'summary_date': d,
            'analysis_summary': entry.analysis_summary if entry else "No summary to display.",
            'student_total': entry.student_total if entry else 0,
            'guest_total': entry.guest_total if entry else 0,
            'summary_type': 'daily',
            'day_of_week': calendar.day_name[d.weekday()]
        })

    # --- WEEKLY (store Monday, display Sunday) ---
    def get_sundays(year, month, up_to_date):
        sundays = []
        d = date(year, month, 1)
        while d.weekday() != 6:  # find first Sunday
            d += timedelta(days=1)
        while d.month == month and d <= up_to_date:
            sundays.append(d)
            d += timedelta(days=7)
        return sundays

    week_ends_up_to_today = get_sundays(today.year, today.month, today)

    full_weekly_list = []
    for sunday in week_ends_up_to_today:
        monday = sunday - timedelta(days=6)  # stored summary_date
        entry = weekly_map.get(monday)
        full_weekly_list.append({
            'summary_date': sunday,  # display Sunday
            'analysis_summary': entry.analysis_summary if entry else "No summary to display.",
            'student_total': entry.student_total if entry else 0,
            'guest_total': entry.guest_total if entry else 0,
            'summary_type': 'weekly',
            'day_of_week': calendar.day_name[sunday.weekday()]
        })

    # --- MONTHLY ---
    if month_start in monthly_map:
        entry = monthly_map[month_start]
        monthly_summary = {
            'summary_date': get_last_day_of_month(entry.summary_date),
            'analysis_summary': entry.analysis_summary,
            'student_total': entry.student_total,
            'guest_total': entry.guest_total,
            'summary_type': 'monthly',
            'day_of_week': calendar.day_name[get_last_day_of_month(entry.summary_date).weekday()]
        }
    else:
        monthly_summary = {
            'summary_date': month_last,
            'analysis_summary': "No summary to display.",
            'student_total': 0,
            'guest_total': 0,
            'summary_type': 'monthly',
            'day_of_week': calendar.day_name[month_last.weekday()]
        }

    # Prepare "Today's Presence Summary"
    summary_data = []
    for s_type in ['daily', 'weekly', 'monthly']:
        norm_date = normalize_summary_date(today, s_type)
        entry = DataAnalysis.objects.filter(summary_type=s_type, summary_date=norm_date).first()
        if entry:
            total = entry.student_total + entry.guest_total
            summary_data.append({
                'period': s_type,
                'student_count': entry.student_total,
                'guest_count': entry.guest_total,
                'student_percent': round((entry.student_total / total) * 100 if total else 0, 2),
                'guest_percent': round((entry.guest_total / total) * 100 if total else 0, 2),
            })

    # Combine all summaries for single table
    combined_summaries = full_daily_list + full_weekly_list
    combined_summaries.sort(key=lambda x: x['summary_date'], reverse=True)

    return render(request, 'users/Admin/data_analysis.html', {
        'summary_data': summary_data,
        'monthly_summary': monthly_summary,
        'combined_summaries': combined_summaries,
    })

def normalize_summary_date(summary_date, period):
    """
    Aligns summary_date to the correct start date for the given period.
    - daily: same date
    - weekly: Monday of the week containing summary_date
    - monthly: first day of the month
    """
    if period == "daily":
        return summary_date
    elif period == "weekly":
        # Always align to Monday start
        return summary_date - timedelta(days=summary_date.weekday())
    elif period == "monthly":
        return summary_date.replace(day=1)
    else:
        raise ValueError(f"Invalid period: {period}")

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

from django.db.models import Q

@admin_required
@login_required
def admin_page(request):
    students = Student.objects.filter(is_archived=False).order_by('last_name', 'first_name')
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

    filters = Q(is_archived=False)
    if department:
        filters &= Q(department=department)
    if course:
        filters &= Q(course=course)

    students = Student.objects.filter(filters).order_by('last_name', 'first_name')

    data = list(students.values(
        'id', 'student_id', 'first_name', 'last_name', 'email',
        'course', 'department', 'is_archived'
    ))

    # Add photo URL manually since `.values()` can't do conditional logic
    for student, obj in zip(students, data):
        obj['photo_url'] = student.photo.url if student.photo else ''

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

#API Endpoints
def check_log_today(request):
    student_id = request.GET.get("student_id")
    date_str = request.GET.get("date")  # Expecting YYYY-MM-DD

    if not student_id or not date_str:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    try:
        date_obj = parse_date(date_str)
        if not date_obj:
            return JsonResponse({"error": "Invalid date format"}, status=400)

        logs = PresenceLog.objects.filter(
            student_id=student_id,
            timestamp__date=date_obj
        )

        return JsonResponse({"count": logs.count()})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@monitor_or_admin_required
def get_presence_logs(request):
    today = now().date()
    logs = (
        PresenceLog.objects.select_related('student')
        .filter(date__date=today)
        .exclude(student__is_archived=True)
        .order_by('-date')
    )

    data = []
    for log in logs:
        if log.student:
            data.append({
                'student_id': log.student.student_id,
                'name': f"{log.student.first_name} {log.student.last_name}",
                'date': log.date.strftime('%Y-%m-%d %H:%M:%S'),
                'role': log.role,
                'department': log.student.department,
                'purpose': log.purpose,
                'edited': log.edited,
                'id': log.id,
                'snapshot': None,
            })
        else:
            data.append({
                'student_id': "Guest",
                'name': "Anonymous Visitor",
                'date': log.date.strftime('%Y-%m-%d %H:%M:%S'),
                'role': log.role,
                'department': log.department or "Unknown",
                'purpose': log.purpose,
                'edited': log.edited,
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
            already_logged = PresenceLog.objects.filter(student=student, date__date=today).exists()
            if already_logged:
                return JsonResponse({'status': 'exists', 'message': 'Already logged today'})

            PresenceLog.objects.create(
                student=student,
                role=role,
                department=student.department,
                purpose="class",
                date=now()
            )
        else:
            # Guest presence logging
            log = PresenceLog(
                student=None,
                role="Guest",
                department=department,
                purpose="visit",
                date=now()
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
            "edited": log.edited,
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

@admin_required
@login_required
def presence_logs_month(request):
    archive_last_month_logs()

    today = now()
    logs = PresenceLog.objects.select_related('student').filter(
        date__year=today.year,
        date__month=today.month
    ).exclude(student__is_archived=True).order_by('-date')

    data = []
    for log in logs:
        if log.student:
            data.append({
                'student_id': log.student.student_id,
                'name': f"{log.student.first_name} {log.student.last_name}",
                'date': log.date.strftime('%Y-%m-%d %H:%M:%S'),
                'role': log.role,
                'department': log.student.department,
                'purpose': log.purpose,
                'edited': log.edited,
                'id': log.id,
            })
        else:
            data.append({
                'student_id': "Guest",
                'name': "Anonymous Visitor",
                'date': log.date.strftime('%Y-%m-%d %H:%M:%S'),
                'role': log.role,
                'department': log.department or "Unknown",
                'purpose': log.purpose,
                'edited': log.edited,
                'id': log.id,
            })

    return render(request, 'users/Admin/presence_logs_month.html', {
        'logs': data,
        'month': today.strftime('%B %Y'),
    })

@admin_required
def archived_logs(request):
    return render(request, 'users/Admin/archived_logs.html')

@monitor_or_admin_required
def get_archived_logs(request):
    logs = ArchivedPresenceLog.objects.select_related('reference__student').order_by('-archived_at')
    data = []

    for log in logs:
        ref = log.reference
        if ref:
            if ref.student:
                data.append({
                    'student_id': ref.student.student_id,
                    'name': f"{ref.student.first_name} {ref.student.last_name}",
                    'date': ref.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'role': ref.role,
                    'department': ref.student.department,
                    'purpose': ref.purpose,
                    'archived_at': log.archived_at.strftime('%Y-%m-%d %H:%M:%S'),
                })
            else:
                data.append({
                    'student_id': 'Guest',
                    'name': 'Anonymous Visitor',
                    'date': ref.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'role': ref.role,
                    'department': ref.department or "Unknown",
                    'purpose': ref.purpose,
                    'archived_at': log.archived_at.strftime('%Y-%m-%d %H:%M:%S'),
                })
        else:
            data.append({
                'student_id': 'Unknown',
                'name': 'Missing Reference',
                'date': '',
                'role': '',
                'department': '',
                'purpose': '',
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