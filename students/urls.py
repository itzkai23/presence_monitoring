from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Student Registration and OTP
    path('register/', views.register, name='register'),
    path('register/success/', views.register_success, name='register_success'),
    path('OTP/', views.otp_code, name='otp_code'),
    path('verify_otp/', views.verify_otp, name='verify_otp'),

    # Password Reset via OTP
    path('forpass/', views.forgotpass, name='forpass'),
    path('verify_reset_otp/', views.verify_reset_otp, name='verify_reset_otp'),
    path('enternewpass/', views.enternewpass, name='enternewpass'),

    # Admin and Monitor Pages
    path('admin_page/', views.admin_page, name='student_records'),
    path('presence-record/', views.presence_record, name='presence_record'),

    # Dynamic Filtering / AJAX
    path('filter_students/', views.filter_students, name='filter_students'),
    path('get-courses/', views.get_courses_by_department, name='get_courses_by_department'),
    path('upload_student_photo/<int:id>/', views.upload_student_photo, name='upload_student_photo'),

    # Tables
    path('data_analysis/', views.data_analysis, name='data_analysis'),
    path('presence_table/', views.presence_table, name='presence_table'),
    path('presence_logs/month/', views.presence_logs_month, name='presence_logs_month'),
    path('archived-logs/', views.archived_logs, name='archived_logs'),
    path('get-archived-logs/', views.get_archived_logs, name='get_archived_logs'),
    path('api/student_logs/', views.student_logs_api, name='student_logs_api'),
    path('archived-students/', views.archived_students, name='archived_students'),
    path('encodings.pkl', views.serve_encodings, name='serve_encodings'),
    path('archived-analysis/', views.archived_analysis_view, name='archived_analysis'),

    # ✅ NEW: Presence log API for frontend
    path('get-presence-logs/', views.get_presence_logs, name='get_presence_logs'),
    path('api/log_presence/', views.log_presence_api, name='log_presence_api'),
    path('api/student_info/<int:pk>/', views.get_student_info, name='get_student_info'),    

    #action
    path('delete-guest-log/<int:log_id>/', views.delete_guest_log, name='delete_guest_log'),
    path('update-purpose/<int:log_id>/', views.update_purpose, name='update_purpose'),
    path('archive-student/<int:pk>/', views.archive_student, name='archive_student'),
    path('retrieve-student/<int:pk>/', views.retrieve_student, name='retrieve_student'),
]

