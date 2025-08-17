# students/data_analysis.py
import os
import csv
import random
from collections import defaultdict
from datetime import timedelta, date
import pandas as pd
import numpy as np
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.conf import settings
import joblib
from students.models import PresenceLog

# ----------------------------
# Phrasebank CSV
# ----------------------------
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
# Lazy-load ML model
# ----------------------------
_ml_model = None
def get_ml_model():
    global _ml_model
    if _ml_model is None:
        try:
            model_path = os.path.join(os.path.dirname(__file__), "model", "ml_model.pkl")
            if os.path.exists(model_path):
                _ml_model = joblib.load(model_path)
        except Exception:
            _ml_model = None
    return _ml_model

# ----------------------------
# Purpose interpreter
# ----------------------------
def interpret_purpose(purpose_counts):
    if not purpose_counts:
        return "No purposes recorded."

    total_purposes = sum(purpose_counts.values())
    sorted_purposes = sorted(purpose_counts.items(), key=lambda x: x[1], reverse=True)

    top_purposes_texts = []
    for i, (purpose, count) in enumerate(sorted_purposes[:3]):
        pct = (count / total_purposes) * 100 if total_purposes > 0 else 0
        meaning = get_phrase(purpose) or "shows a unique activity pattern."
        top_purposes_texts.append(f"**{purpose}** ({pct:.1f}%) which {meaning}")

    if len(top_purposes_texts) == 1:
        return f"The dominant purpose was {top_purposes_texts[0]}"
    else:
        joined = "; ".join(top_purposes_texts)
        return f"The top purposes were: {joined}."

# ----------------------------
# Security suggestions
# ----------------------------
def security_suggestions(guest_count, student_count, total, peak_metric, context):
    suggestions = []
    if guest_count > student_count:
        suggestions.append(get_phrase("security_suggestions") or "Consider tighter guest check-in and ID verification.")
    if peak_metric and peak_metric > (total * 0.3):
        suggestion = get_phrase("security_suggestions") or f"Increase security personnel during peak {context} to manage high traffic."
        suggestions.append(suggestion.replace("{context}", str(context)))
    if total > 50:
        suggestions.append(get_phrase("security_suggestions") or "Install automated counting systems to track movement in real-time.")
    return " ".join(suggestions) if suggestions else (get_phrase("security_suggestions") or "Current security measures appear sufficient for recorded traffic.")

# ----------------------------
# Forecast helper
# ----------------------------
def forecast_next_count(period, reference_date):
    ml = get_ml_model()
    try:
        if period == 'daily':
            qs = PresenceLog.objects.filter(
                date__date__gte=(reference_date - timedelta(days=14)),
                date__date__lt=reference_date
            )
            days = qs.annotate(day=TruncDate('date')).values('day').annotate(cnt=Count('id')).order_by('day')
            counts = [d['cnt'] for d in days]
            if ml and counts:
                total = sum(counts[-7:]) if counts else 0
                try:
                    features = pd.DataFrame([[int(total)]], columns=['total_count'])
                    pred = ml.predict(features)
                    return int(np.round(pred[0]))
                except Exception:
                    return int(round(np.mean(counts[-7:])) if counts else 0)
            else:
                return int(round(np.mean(counts[-7:])) if counts else 0)

        elif period == 'weekly':
            qs = PresenceLog.objects.annotate(week=TruncWeek('date')).values('week').annotate(cnt=Count('id')).order_by('week')
            weeks = [w['cnt'] for w in qs if w['week'].date() < reference_date]
            if ml and weeks:
                total = sum(weeks[-4:]) if weeks else 0
                try:
                    features = pd.DataFrame([[int(total)]], columns=['total_count'])
                    pred = ml.predict(features)
                    return int(np.round(pred[0]))
                except Exception:
                    return int(round(np.mean(weeks[-3:])) if weeks else 0)
            else:
                return int(round(np.mean(weeks[-3:])) if weeks else 0)

        else:  # monthly
            qs = PresenceLog.objects.annotate(month=TruncMonth('date')).values('month').annotate(cnt=Count('id')).order_by('month')
            months = [m['cnt'] for m in qs if m['month'].date() < reference_date]
            if ml and months:
                total = sum(months[-3:]) if months else 0
                try:
                    features = pd.DataFrame([[int(total)]], columns=['total_count'])
                    pred = ml.predict(features)
                    return int(np.round(pred[0]))
                except Exception:
                    return int(round(np.mean(months[-3:])) if months else 0)
            else:
                return int(round(np.mean(months[-3:])) if months else 0)
    except Exception:
        return 0

# ----------------------------
# Daily Summary
# ----------------------------
def generate_daily_summary(presence_df, current_date):
    from datetime import timedelta, date
    import pandas as pd

    current_date_only = current_date if isinstance(current_date, date) else current_date.date()

    # Ensure logs_timestamp is datetime
    presence_df['logs_timestamp'] = pd.to_datetime(presence_df['logs_timestamp'], errors='coerce')
    presence_df.dropna(subset=['logs_timestamp'], inplace=True)

    # Use explicit log_date column for filtering
    presence_df['log_date'] = presence_df['logs_timestamp'].dt.date
    day_df = presence_df[presence_df['log_date'] == current_date_only].copy()
    prev_df = presence_df[presence_df['log_date'] == (current_date_only - timedelta(days=1))].copy()

    if day_df.empty:
        return f"No summary to display for {current_date_only.strftime('%A, %B %d, %Y')}."

    # Standardize roles
    day_df['role'] = day_df['role'].str.lower().str.strip()
    prev_df['role'] = prev_df['role'].str.lower().str.strip()

    # Counts
    students = day_df.loc[day_df['role'] == 'student', 'student_id'].nunique()
    guests = day_df.loc[day_df['role'] == 'guest'].shape[0]
    total = students + guests

    # Department info
    top_dept = None
    student_df = day_df[day_df['role'] == 'student']
    if not student_df.empty and 'department' in student_df.columns:
        dept_counts = student_df['department'].dropna().value_counts()
        top_dept = dept_counts.idxmax() if not dept_counts.empty else None

    # Purposes
    purposes = day_df['purpose'].dropna().value_counts().to_dict() if 'purpose' in day_df.columns else {}

    # Peak hour
    peak_hour = None
    hour_counts = day_df['logs_timestamp'].dt.hour.value_counts() if not day_df.empty else pd.Series()
    if not hour_counts.empty:
        peak_hour = int(hour_counts.idxmax())

    # Trend vs previous day
    prev_students = prev_df.loc[prev_df['role'] == 'student', 'student_id'].nunique() if not prev_df.empty else 0
    prev_guests = prev_df.loc[prev_df['role'] == 'guest'].shape[0] if not prev_df.empty else 0
    prev_total = prev_students + prev_guests

    trend_text = "No previous day's data available for comparison."
    if prev_total > 0:
        diff = total - prev_total
        pct_change = (diff / prev_total) * 100
        trend_text = f"An increase of {diff} entries ({pct_change:.1f}%)" if diff > 0 else \
                     f"A decrease of {abs(diff)} entries ({abs(pct_change):.1f}%)" if diff < 0 else \
                     "No change compared to the previous day."

    # --- Forecast with fallback to 7-day average ---
    forecast = forecast_next_count('daily', current_date_only)
    if forecast == 0:
        last_7_days = presence_df[(presence_df['log_date'] < current_date_only) & 
                                  (presence_df['log_date'] >= current_date_only - timedelta(days=7))]
        if not last_7_days.empty:
            forecast = int(round(len(last_7_days) / 7))
        else:
            forecast = total  # fallback to today's total if no history

    readable_date = current_date_only.strftime("%A, %B %d, %Y")

    # Build summary parts with placeholder replacement
    summary_parts = []

    intro_text = get_phrase('intro').replace('{date}', readable_date)
    summary_parts.append(f"{intro_text} On {readable_date}, a total of {total} presence entries were logged.")

    role_text = get_phrase('role_breakdown')
    role_text = role_text.replace('{students}', str(students)).replace('{guests}', str(guests)).replace('{total}', str(total))
    summary_parts.append(f"{role_text} Out of {total}, {students} were students ({(students / total * 100 if total else 0):.1f}%) "
                         f"and {guests} were guests ({(guests / total * 100 if total else 0):.1f}%).")

    if top_dept:
        dept_text = get_phrase('department').replace('{top_dept}', top_dept)
        summary_parts.append(f"{dept_text} The department with the most student entries was {top_dept}.")

    if purposes:
        summary_parts.append(f"{get_phrase('purpose_intro')} {interpret_purpose(purposes)}")

    if peak_hour is not None:
        peak_text = get_phrase('peak_time').replace('{hour}', str(peak_hour))
        summary_parts.append(f"{peak_text} Peak presence hour was around {peak_hour}:00.")

    trend_phrase = get_phrase('trend').replace('{trend}', trend_text)
    summary_parts.append(f"{trend_phrase} {trend_text}")

    forecast_phrase = get_phrase('forecast').replace('{forecast}', str(forecast))
    summary_parts.append(f"{forecast_phrase} Forecast for tomorrow: approximately {forecast} entries.")

    security_text = get_phrase('security')
    summary_parts.append(f"{security_text} {security_suggestions(guests, students, total, hour_counts.max() if not hour_counts.empty else 0, 'hour')}")

    # Join into paragraph
    summary_text = ' '.join(summary_parts)
    return summary_text.strip()

# ----------------------------
# Weekly Summary
# ----------------------------
def generate_weekly_summary(presence_df, week_start_date):
    from datetime import timedelta, date
    import pandas as pd

    # --- Set start and end dates ---
    start_date = week_start_date if isinstance(week_start_date, date) else week_start_date.date()
    end_date = start_date + timedelta(days=6)

    # --- Prepare dataframe ---
    presence_df['logs_timestamp'] = pd.to_datetime(presence_df['logs_timestamp'], errors='coerce')
    presence_df.dropna(subset=['logs_timestamp'], inplace=True)
    presence_df['log_date'] = presence_df['logs_timestamp'].dt.date

    week_df = presence_df[(presence_df['log_date'] >= start_date) & (presence_df['log_date'] <= end_date)].copy()
    if week_df.empty:
        return f"No summary to display for the week starting {start_date.strftime('%B %d, %Y')}."

    week_df['role'] = week_df['role'].str.lower().str.strip()

    # --- Counts ---
    students = week_df.loc[week_df['role'] == 'student', 'student_id'].nunique()
    guests = week_df.loc[week_df['role'] == 'guest'].shape[0]
    total = students + guests

    # --- Top department ---
    top_dept = None
    student_df = week_df[week_df['role'] == 'student']
    if not student_df.empty and 'department' in student_df.columns:
        dept_counts = student_df['department'].dropna().value_counts()
        if not dept_counts.empty:
            top_dept = dept_counts.idxmax()

    # --- Purposes ---
    purposes = week_df['purpose'].dropna().value_counts().to_dict() if 'purpose' in week_df.columns else {}

    # --- Peak day ---
    day_counts = week_df['log_date'].value_counts()
    peak_day = day_counts.idxmax().strftime("%A, %B %d") if not day_counts.empty else None

    # --- Trend vs previous week ---
    prev_start = start_date - timedelta(days=7)
    prev_end = prev_start + timedelta(days=6)
    prev_df = presence_df[(presence_df['log_date'] >= prev_start) & (presence_df['log_date'] <= prev_end)].copy()
    prev_students = prev_df.loc[prev_df['role'] == 'student', 'student_id'].nunique() if not prev_df.empty else 0
    prev_guests = prev_df.loc[prev_df['role'] == 'guest'].shape[0] if not prev_df.empty else 0
    prev_total = prev_students + prev_guests

    trend_text = "No previous week's data available for comparison."
    if prev_total > 0:
        diff = total - prev_total
        pct_change = (diff / prev_total) * 100
        trend_text = (f"An increase of {diff} entries ({pct_change:.1f}%)" if diff > 0 else
                      f"A decrease of {abs(diff)} entries ({abs(pct_change):.1f}%)" if diff < 0 else
                      "No change compared to previous week.")

    # --- Forecast ---
    forecast = forecast_next_count('weekly', start_date)
    # Fallback if forecast returns 0
    if forecast == 0 and not week_df.empty:
        forecast = int(round(total / 7))  # crude weekly average

    # --- Build summary ---
    summary_parts = [
        f"{get_phrase('intro')} For the week starting {start_date.strftime('%B %d, %Y')}, a total of {total} presence entries were logged.",
        f"{get_phrase('role_breakdown')} Out of {total}, {students} were students ({(students / total * 100 if total else 0):.1f}%) "
        f"and {guests} were guests ({(guests / total * 100 if total else 0):.1f}%)."
    ]

    if top_dept:
        summary_parts.append(f"{get_phrase('department')} The department with the most student entries was {top_dept}.")
    if purposes:
        summary_parts.append(f"{get_phrase('purpose_intro')} {interpret_purpose(purposes)}")
    if peak_day:
        summary_parts.append(f"Peak presence day was {peak_day}.")
    summary_parts.append(f"{get_phrase('trend')} {trend_text}")
    summary_parts.append(f"Forecast for next week: approximately {forecast} entries.")
    summary_parts.append(f"{get_phrase('security')} {security_suggestions(guests, students, total, day_counts.max() if not day_counts.empty else 0, 'week')}")

    return ' '.join(summary_parts).strip()

# ----------------------------
# Monthly Summary (with peak week)
# ----------------------------
def generate_monthly_summary(presence_df, month_start_date):
    from datetime import timedelta, date
    import pandas as pd

    # --- Set start and end dates ---
    start_date = month_start_date if isinstance(month_start_date, date) else month_start_date.date()
    if start_date.day != 1:
        start_date = start_date.replace(day=1)
    next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)

    # --- Prepare dataframe ---
    presence_df['logs_timestamp'] = pd.to_datetime(presence_df['logs_timestamp'], errors='coerce')
    presence_df.dropna(subset=['logs_timestamp'], inplace=True)
    presence_df['log_date'] = presence_df['logs_timestamp'].dt.date

    month_df = presence_df[(presence_df['log_date'] >= start_date) & (presence_df['log_date'] < next_month)].copy()
    if month_df.empty:
        return f"No summary to display for {start_date.strftime('%B %Y')}."

    month_df['role'] = month_df['role'].str.lower().str.strip()

    # --- Counts ---
    students = month_df.loc[month_df['role'] == 'student', 'student_id'].nunique()
    guests = month_df.loc[month_df['role'] == 'guest'].shape[0]
    total = students + guests

    # --- Top department ---
    top_dept = None
    student_df = month_df[month_df['role'] == 'student']
    if not student_df.empty and 'department' in student_df.columns:
        dept_counts = student_df['department'].dropna().value_counts()
        if not dept_counts.empty:
            top_dept = dept_counts.idxmax()

    # --- Purposes ---
    purposes = month_df['purpose'].dropna().value_counts().to_dict() if 'purpose' in month_df.columns else {}

    # --- Peak week ---
    month_df['week_num'] = month_df['logs_timestamp'].dt.isocalendar().week
    week_counts = month_df['week_num'].value_counts()
    peak_week = int(week_counts.idxmax()) if not week_counts.empty else None

    # --- Previous month trend ---
    prev_month_end = start_date - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    prev_df = presence_df[(presence_df['log_date'] >= prev_month_start) & (presence_df['log_date'] <= prev_month_end)].copy()
    prev_students = prev_df.loc[prev_df['role'] == 'student', 'student_id'].nunique() if not prev_df.empty else 0
    prev_guests = prev_df.loc[prev_df['role'] == 'guest'].shape[0] if not prev_df.empty else 0
    prev_total = prev_students + prev_guests

    trend_text = "No previous month's data available for comparison."
    if prev_total > 0:
        diff = total - prev_total
        pct_change = (diff / prev_total) * 100
        trend_text = (f"An increase of {diff} entries ({pct_change:.1f}%)" if diff > 0 else
                      f"A decrease of {abs(diff)} entries ({abs(pct_change):.1f}%)" if diff < 0 else
                      "No change compared to previous month.")

    # --- Forecast ---
    forecast = forecast_next_count('monthly', start_date)
    if forecast == 0 and not month_df.empty:
        forecast = int(round(total / 4))  # crude monthly weekly average

    # --- Build summary ---
    summary_parts = [
        f"{get_phrase('intro')} For {start_date.strftime('%B %Y')}, a total of {total} presence entries were logged.",
        f"{get_phrase('role_breakdown')} Out of {total}, {students} were students ({(students / total * 100 if total else 0):.1f}%) "
        f"and {guests} were guests ({(guests / total * 100 if total else 0):.1f}%)."
    ]

    if top_dept:
        summary_parts.append(f"{get_phrase('department')} The department with the most student entries was {top_dept}.")
    if purposes:
        summary_parts.append(f"{get_phrase('purpose_intro')} {interpret_purpose(purposes)}")
    if peak_week:
        summary_parts.append(f"Peak presence occurred in week number {peak_week}.")
    summary_parts.append(f"{get_phrase('trend')} {trend_text}")
    summary_parts.append(f"Forecast for next month: approximately {forecast} entries.")
    summary_parts.append(f"{get_phrase('security')} {security_suggestions(guests, students, total, week_counts.max() if not week_counts.empty else 0, 'week')}")

    return ' '.join(summary_parts).strip()
