# apps/accounts/utils.py
__all__ = [
    'generate_temp_password',
    'send_user_welcome_email',
    'send_employee_welcome_email',
]
import secrets
import string
from django.core.mail import send_mail
from django.conf      import settings


def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def send_user_welcome_email(user, temp_password):
    send_mail(
        subject='Welcome to Sync — Your Temporary Password',
        message=(
            f'Hello {user.full_name},\n\n'
            f'Your account has been created on the Sync Task Management System.\n\n'
            f'Email:              {user.email}\n'
            f'Temporary Password: {temp_password}\n\n'
            f'Please log in and change your password immediately.\n'
            f'This password is valid for one login only.\n\n'
            f'Sync System'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_employee_welcome_email(employee, temp_password):
    send_mail(
        subject='Welcome to Sync — Your Mobile App Credentials',
        message=(
            f'Hello {employee.full_name},\n\n'
            f'Your employee account has been created on the Sync system.\n\n'
            f'Email:              {employee.email}\n'
            f'Temporary Password: {temp_password}\n\n'
            f'Please log into the mobile app and change your password on first login.\n'
            f'This password is valid for one login only.\n\n'
            f'Sync System'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[employee.email],
        fail_silently=False,
    )