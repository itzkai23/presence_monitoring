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
from .models import PresenceLog
from .utils.utils import archive_last_month_logs
from .models import ArchivedPresenceLog
from .models import DataAnalysis
from .utils.encoding_utils import regenerate_encodings  
import os
import sys
from django.http import FileResponse
from django.core.files.storage import default_storage
import traceback
from django.http import HttpResponse
from datetime import datetime, timedelta, date
from django.db.models import Sum
from .decorators import admin_required
from collections import defaultdict
import csv
from django.utils import timezone

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
                    section=registration_data['section'],
                    year_level=registration_data['year_level'],
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

# Generate human summary
def generate_summary_text(students, guests, date_label):
    total = students + guests
    student_pct = (students / total) * 100 if total > 0 else 0
    guest_pct = (guests / total) * 100 if total > 0 else 0

    summary = f"On {date_label}, there were approximately {students} unique students and {guests} guests detected. "

    if students > 100:
        summary += get_phrase('high_student_turnout') + " "
    elif students < 30:
        summary += get_phrase('low_student_turnout') + " "
    else:
        summary += get_phrase('normal_student_turnout') + " "

    if guest_pct > 40:
        summary += get_phrase('guest_surge') + " "
    else:
        summary += get_phrase('normal_guest') + " "

    summary += get_phrase('general_summary')

    return summary.strip()

# Unified updater
def update_summary(summary_type, date_obj):
    if summary_type == 'daily':
        student_count = PresenceLog.objects.filter(date__date=date_obj, role='student').count()
        guest_count = PresenceLog.objects.filter(date__date=date_obj, role='guest').count()
        formatted_label = date_obj.strftime('%Y-%B-%d')
    elif summary_type == 'weekly':
        week_start = date_obj - timedelta(days=date_obj.weekday())
        week_end = week_start + timedelta(days=6)
        student_count = PresenceLog.objects.filter(date__date__range=(week_start, week_end), role='student').values('student_id').distinct().count()
        guest_count = PresenceLog.objects.filter(date__date__range=(week_start, week_end), role='guest').values('snapshot').distinct().count()
        date_obj = week_start
        formatted_label = week_start.strftime('%Y-%B-%d')
    elif summary_type == 'monthly':
        month_start = date_obj.replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        student_count = PresenceLog.objects.filter(date__date__gte=month_start, date__date__lt=next_month, role='student').values('student_id').distinct().count()
        guest_count = PresenceLog.objects.filter(date__date__gte=month_start, date__date__lt=next_month, role='guest').values('snapshot').distinct().count()
        date_obj = month_start
        formatted_label = month_start.strftime('%B %Y')
    else:
        return

    summary_text = generate_summary_text(student_count, guest_count, formatted_label)

    DataAnalysis.objects.update_or_create(
        summary_type=summary_type,
        summary_date=date_obj,
        defaults={
            'student_total': student_count,
            'guest_total': guest_count,
            'analysis_summary': summary_text,
        }
    )

@login_required
@admin_required
def data_analysis(request):
    today = timezone.localdate()

    # Update all summary types
    for s_type in ['daily', 'weekly', 'monthly']:
        update_summary(s_type, today)

    # Collect top summary data (latest entries for each type)
    summary_data = []
    for s_type in ['daily', 'weekly', 'monthly']:
        entry = DataAnalysis.objects.filter(summary_type=s_type).order_by('-summary_date').first()
        if entry:
            total = entry.student_total + entry.guest_total
            summary_data.append((
                s_type,
                {
                    'student': entry.student_total,
                    'guest': entry.guest_total,
                    'student_percent': round((entry.student_total / total) * 100 if total > 0 else 0, 2),
                    'guest_percent': round((entry.guest_total / total) * 100 if total > 0 else 0, 2),
                }
            ))

    # Full table data
    analysis_data = DataAnalysis.objects.all().order_by('-summary_date')

    return render(request, 'users/Admin/data_analysis.html', {
        'summary_data': summary_data,      # used by top summary table
        'analysis_data': analysis_data     # used by bottom full table
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
        'year_levels': settings.YEAR_LEVELS,
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
    year = request.GET.get('year', '')

    students = Student.objects.filter(is_archived=False)  # 👈 exclude archived by default

    if department:
        students = students.filter(department=department)
    if course:
        students = students.filter(course=course)
    if year:
        students = students.filter(year_level=year)

    data = []
    for student in students:
        data.append({
            'id': student.id,
            'student_id': student.student_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'email': student.email,
            'section': student.section,
            'course': student.course,
            'year_level': student.year_level,
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

#API Endpoints
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