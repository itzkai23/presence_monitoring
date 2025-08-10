from django import forms
from django.contrib.auth.hashers import make_password
from django.conf import settings
from .models import Student

class StudentRegistrationForm(forms.ModelForm):
    department = forms.ChoiceField(
        choices=[(key, key) for key in settings.DEPARTMENT_COURSE_MAP.keys()],
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_department'})
    )

    course = forms.ChoiceField(
        choices=[],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_course'})
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        }),
        label='Password'
    )

    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your confirm password'
        }),
        label='Confirm Password'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        department = self.data.get('department') or self.initial.get('department')
        course_choices_by_department = settings.DEPARTMENT_COURSE_MAP

        if department in course_choices_by_department:
            self.fields['course'].choices = [
                (course, course) for course in course_choices_by_department[department]
            ]
        else:
            self.fields['course'].choices = []

    class Meta:
        model = Student
        fields = [
            'student_id', 'first_name', 'last_name', 'email',
            'department', 'course', 'password'
        ]
        labels = {
            'student_id': 'Student ID',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email',
            'department': 'Department',
            'course': 'Course',
            'password': 'Password',
        }
        widgets = {
            'student_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your student id'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Use your university email',
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and not email.endswith('@cityofmalabonuniversity.edu.ph'):
            raise forms.ValidationError("Please use your university email (@cityofmalabonuniversity.edu.ph).")
        return email

    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        confirm = self.cleaned_data.get('password_confirm')

        if password and confirm and password != confirm:
            raise forms.ValidationError("Passwords do not match.")
        return confirm

    def save(self, commit=True):
        student = super().save(commit=False)
        student.password = make_password(self.cleaned_data['password'])
        if commit:
            student.save()
        return student
