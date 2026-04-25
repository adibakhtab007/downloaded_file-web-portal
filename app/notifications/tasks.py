from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailNotificationLog
from accounts.models import OtpCode
from accounts.enums import AccountStatus

User = get_user_model()


def _send_email(recipient: str, subject: str, body: str, email_type: str, user=None):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
        EmailNotificationLog.objects.create(user=user, recipient_email=recipient, subject_snapshot=subject, email_type=email_type, status='SENT')
    except Exception as exc:
        EmailNotificationLog.objects.create(user=user, recipient_email=recipient, subject_snapshot=subject, email_type=email_type, status='FAILED', error_text=str(exc))
        raise


@shared_task
def send_otp_email_task(user_id: int, otp_type: str, code: str):
    user = User.objects.get(pk=user_id)
    _send_email(user.email, f'Your OTP for {otp_type}', f'Your OTP code is {code}. It expires in {settings.FILEPORTAL_OTP_EXPIRY_SECONDS // 60 or 1} minute(s).', 'OTP', user)


@shared_task
def send_simple_email_task(recipient: str, subject: str, body: str):
    _send_email(recipient, subject, body, 'GENERIC', None)


@shared_task
def send_admin_alert_email_task(subject: str, body: str):
    admins = User.objects.filter(profile__role='SUPER_ADMIN', is_active=True)
    for admin in admins:
        _send_email(admin.email, subject, body, 'ADMIN_ALERT', admin)


@shared_task
def send_password_expiry_reminders_task():
    now = timezone.now()
    users = User.objects.select_related('profile').filter(is_active=True)
    for user in users:
        profile = user.profile
        if profile.account_status in {AccountStatus.REJECTED, AccountStatus.DISABLED_ADMIN}:
            continue
        days_left = (profile.password_expires_at.date() - now.date()).days
        if 0 <= days_left <= 7:
            _send_email(user.email, 'Password expiry reminder', f'Your password will expire in {days_left} day(s). Please change it through the portal.', 'PASSWORD_REMINDER', user)
        elif days_left < 0 and profile.role == 'WEB_USER' and profile.account_status != AccountStatus.DISABLED_PASSWORD_EXPIRED:
            profile.account_status = AccountStatus.DISABLED_PASSWORD_EXPIRED
            profile.save(update_fields=['account_status', 'updated_at'])
            _send_email(user.email, 'Password expired', 'Your account is disabled because your password expired. Contact an admin.', 'PASSWORD_EXPIRED', user)


@shared_task
def cleanup_expired_otps_task():
    OtpCode.objects.filter(expires_at__lt=timezone.now(), used_at__isnull=True).delete()
