"""
WSGI config for student_registration project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information, see:
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys
import traceback

debug_log = "C:/Apache24/logs/wsgi_debug.txt"

try:
    with open(debug_log, "a") as f:
        f.write("WSGI file loaded successfully.\n")

    # Add the outer project directory to sys.path
    current_path = os.path.dirname(os.path.abspath(__file__))            # .../student_registration/student_registration
    project_root = os.path.dirname(current_path)                         # .../student_registration
    sys.path.append(project_root)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'student_registration.settings')

    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()

    with open(debug_log, "a") as f:
        f.write("Django application loaded successfully.\n")

except Exception as e:
    with open(debug_log, "a") as f:
        f.write("Error loading WSGI application:\n")
        f.write(traceback.format_exc())
    raise
