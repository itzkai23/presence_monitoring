import os
import sys
import traceback

debug_log = r"C:/presence_monitoring/wsgi_debug.txt"

try:
    with open(debug_log, "a") as f:
        f.write("WSGI file loaded\n")

    # Ensure both outer and inner project directories are on sys.path
    outer_project_root = r"C:/presence_monitoring"
    inner_project_root = r"C:/presence_monitoring/student_registration"

    if outer_project_root not in sys.path:
        sys.path.insert(0, outer_project_root)
    if inner_project_root not in sys.path:
        sys.path.insert(0, inner_project_root)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'student_registration.settings')

    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()

    with open(debug_log, "a") as f:
        f.write("Django WSGI application loaded successfully\n")

except Exception:
    with open(debug_log, "a") as f:
        f.write("Error loading WSGI application:\n")
        f.write(traceback.format_exc())
    raise
