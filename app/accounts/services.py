from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from storage_index.models import FolderUserPermission

from audittrail.services import create_audit_event, create_journey
from audittrail.models import UserSessionJourney
from common.utils import generate_numeric_otp, hash_token, normalize_secret_answer
from notifications.tasks import send_admin_alert_email_task, send_otp_email_task, send_simple_email_task
from .enums import AccountStatus, UserRole
from .models import OtpCode, PasswordHistory, User, UserProfile, UserSecurityAnswer

User = get_user_model()


def validate_password_history(user, raw_password: str) -> None:
    recent_hashes = user.password_histories.order_by('-created_at')[:4]
    for old in recent_hashes:
        if check_password(raw_password, old.password_hash):
            from django.core.exceptions import ValidationError
            raise ValidationError('You cannot reuse any of your last four passwords.')


def store_password_history(user) -> None:
    PasswordHistory.objects.create(user=user, password_hash=user.password)


def user_can_access_admin_portal(user) -> bool:
    return user.is_authenticated and user.profile.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN_READONLY}


def user_is_super_admin(user) -> bool:
    return user.is_authenticated and user.profile.role == UserRole.SUPER_ADMIN


def user_can_access_web_portal(user) -> bool:
    return user.is_authenticated and user.profile.role == UserRole.WEB_USER and user.profile.account_status == AccountStatus.APPROVED


def create_otp(user, otp_type: str, request=None) -> str:
    code = generate_numeric_otp(6)
    OtpCode.objects.create(
        user=user,
        otp_type=otp_type,
        code_hash=hash_token(code),
        expires_at=timezone.now() + timedelta(seconds=settings.FILEPORTAL_OTP_EXPIRY_SECONDS),
        max_attempts=settings.FILEPORTAL_OTP_MAX_ATTEMPTS,
    )
    send_otp_email_task.delay(user.id, otp_type, code)
    create_audit_event(
        user=user,
        request=request,
        action_type='OTP_SENT',
        target_type='AUTH',
        status='SUCCESS',
        message=f'OTP sent for {otp_type}.',
    )
    return code


def verify_otp(user, otp_type: str, raw_code: str, request=None) -> bool:
    otp = user.otp_codes.filter(
        otp_type=otp_type,
        used_at__isnull=True
    ).order_by('-created_at').first()

    if not otp or otp.is_expired:
        create_audit_event(
            user=user,
            request=request,
            action_type='OTP_FAIL',
            target_type='AUTH',
            status='FAILED',
            message='OTP missing or expired.',
        )
        return False

    otp.attempt_count += 1

    if hash_token(raw_code) == otp.code_hash and otp.attempt_count <= otp.max_attempts:
        otp.used_at = timezone.now()
        otp.save(update_fields=['attempt_count', 'used_at'])
        create_audit_event(
            user=user,
            request=request,
            action_type='OTP_OK',
            target_type='AUTH',
            status='SUCCESS',
            message=f'OTP verified for {otp_type}.',
        )
        return True

    otp.save(update_fields=['attempt_count'])
    create_audit_event(
        user=user,
        request=request,
        action_type='OTP_FAIL',
        target_type='AUTH',
        status='FAILED',
        message=f'Invalid OTP attempt for {otp_type}.',
    )
    return False


def create_pending_web_user(full_name: str, email: str, password: str, question_answer_pairs: Iterable[tuple], request=None) -> User:
    with transaction.atomic():
        email = email.strip().lower()
        existing_user = User.objects.filter(email=email).select_related('profile').first()

        if existing_user:
            if existing_user.profile.account_status != AccountStatus.DELETED:
                from django.core.exceptions import ValidationError
                raise ValidationError('A user with this email already exists.')

            user = existing_user
            user.is_active = True
            user.is_staff = False
            user.set_password(password)
            user.save(update_fields=['is_active', 'is_staff', 'password'])

            profile = user.profile
            profile.full_name = full_name
            profile.role = UserRole.WEB_USER
            profile.account_status = AccountStatus.PENDING_APPROVAL
            profile.failed_login_count = 0
            profile.blocked_until = None
            profile.security_failure_count = 0
            profile.security_blocked_until = None
            profile.must_change_password = False
            profile.approved_by = None
            profile.approved_at = None
            profile.enabled_by = None
            profile.enabled_at = None
            profile.password_changed_at = timezone.now()
            profile.password_expires_at = timezone.now() + timedelta(days=90)
            profile.save()

            user.password_histories.all().delete()
            user.security_answers.all().delete()

            store_password_history(user)

            for question, answer in question_answer_pairs:
                UserSecurityAnswer.objects.create(
                    user=user,
                    question=question,
                    answer_hash=make_password(normalize_secret_answer(answer)),
                )

            send_simple_email_task.delay(
                user.email,
                'Registration received',
                'Your registration was received and is awaiting approval.'
            )
            send_admin_alert_email_task.delay(
                'Re-registration received',
                f'Deleted web user re-registered and is pending approval: {user.email}'
            )
            create_audit_event(
                user=user,
                request=request,
                action_type='REGISTER_SUBMITTED',
                target_type='AUTH',
                status='SUCCESS',
                message='Deleted web user re-registered and is pending approval.'
            )
            return user

        user = User.objects.create_user(email=email, password=password)
        profile = user.profile
        profile.full_name = full_name
        profile.role = UserRole.WEB_USER
        profile.account_status = AccountStatus.PENDING_APPROVAL
        profile.password_changed_at = timezone.now()
        profile.password_expires_at = timezone.now() + timedelta(days=90)
        profile.save()

        store_password_history(user)

        for question, answer in question_answer_pairs:
            UserSecurityAnswer.objects.create(
                user=user,
                question=question,
                answer_hash=make_password(normalize_secret_answer(answer)),
            )

        send_simple_email_task.delay(
            user.email,
            'Registration received',
            'Your registration was received and is awaiting approval.'
        )
        send_admin_alert_email_task.delay(
            'New web portal registration',
            f'New web user pending approval: {user.email}'
        )
        create_audit_event(
            user=user,
            request=request,
            action_type='REGISTER_SUBMITTED',
            target_type='AUTH',
            status='SUCCESS',
            message='Web user registration submitted.'
        )
        return user


def approve_web_user(target_user, admin_user, request=None) -> None:
    profile = target_user.profile
    profile.account_status = AccountStatus.APPROVED
    profile.approved_by = admin_user
    profile.approved_at = timezone.now()
    profile.save(update_fields=['account_status', 'approved_by', 'approved_at', 'updated_at'])
    send_simple_email_task.delay(target_user.email, 'Registration approved', 'Your registration has been approved. You can now log in.')
    create_audit_event(
        user=admin_user,
        request=request,
        action_type='USER_APPROVED',
        target_type='USER',
        target_id=str(target_user.id),
        target_name=target_user.email,
        status='SUCCESS',
        message='User approved.',
    )


def reject_web_user(target_user, admin_user, request=None) -> None:
    profile = target_user.profile
    profile.account_status = AccountStatus.REJECTED
    profile.save(update_fields=['account_status', 'updated_at'])
    send_simple_email_task.delay(target_user.email, 'Registration rejected', 'Your registration was not approved.')
    create_audit_event(
        user=admin_user,
        request=request,
        action_type='USER_REJECTED',
        target_type='USER',
        target_id=str(target_user.id),
        target_name=target_user.email,
        status='SUCCESS',
        message='User rejected.',
    )


def record_failed_login(user_or_none, email: str, request=None) -> None:
    if user_or_none:
        profile = user_or_none.profile
        profile.failed_login_count += 1
        updates = ['failed_login_count', 'updated_at']
        if profile.failed_login_count >= 3:
            profile.blocked_until = timezone.now() + timedelta(hours=1)
            profile.account_status = AccountStatus.BLOCKED
            updates.extend(['blocked_until', 'account_status'])
            send_simple_email_task.delay(user_or_none.email, 'Account blocked', 'Your account was blocked for 1 hour after repeated failed login attempts.')
            send_admin_alert_email_task.delay('User blocked after failed login attempts', f'User {user_or_none.email} was blocked for 1 hour.')
        profile.save(update_fields=updates)
        create_audit_event(
            user=user_or_none,
            request=request,
            action_type='LOGIN_PASSWORD_FAIL',
            target_type='AUTH',
            status='FAILED',
            message=f'Failed login for {email}.',
        )
    else:
        create_audit_event(
            user=None,
            request=request,
            action_type='LOGIN_PASSWORD_FAIL',
            target_type='AUTH',
            status='FAILED',
            message=f'Failed login for unknown email {email}.',
        )


def reset_login_counters(user) -> None:
    profile = user.profile
    profile.failed_login_count = 0
    profile.blocked_until = None
    if profile.account_status == AccountStatus.BLOCKED:
        profile.account_status = AccountStatus.APPROVED
    profile.save(update_fields=['failed_login_count', 'blocked_until', 'account_status', 'updated_at'])


def start_authenticated_journey(user, request):
    trace_id = request.session.get('pre_auth_trace_id') or request.session.get('trace_id')

    if trace_id:
        if not UserSessionJourney.objects.filter(trace_id=trace_id).exists():
            create_journey(user=user, request=request, trace_id=trace_id)
    else:
        trace_id = create_journey(user=user, request=request)

    request.session['trace_id'] = trace_id
    return trace_id


def password_is_expired(user) -> bool:
    return user.profile.password_expires_at <= timezone.now()


def set_new_password(user, raw_password: str, changed_by=None, force_change=False, request=None) -> None:
    validate_password_history(user, raw_password)
    user.set_password(raw_password)
    user.save(update_fields=['password'])
    store_password_history(user)
    profile = user.profile
    profile.password_changed_at = timezone.now()
    profile.password_expires_at = timezone.now() + timedelta(days=90)
    profile.must_change_password = force_change
    if profile.account_status == AccountStatus.DISABLED_PASSWORD_EXPIRED:
        profile.account_status = AccountStatus.APPROVED
    profile.save(update_fields=['password_changed_at', 'password_expires_at', 'must_change_password', 'account_status', 'updated_at'])
    create_audit_event(
        user=changed_by or user,
        request=request,
        action_type='PASSWORD_CHANGED',
        target_type='USER',
        target_id=str(user.id),
        target_name=user.email,
        status='SUCCESS',
        message='Password updated.',
    )


@transaction.atomic
def disable_user_by_admin(target_user: User, acting_user: User, request=None) -> None:
    profile = target_user.profile
    profile.account_status = AccountStatus.DISABLED_ADMIN
    profile.blocked_until = None
    profile.security_blocked_until = None
    profile.save(update_fields=['account_status', 'blocked_until', 'security_blocked_until', 'updated_at'])

    create_audit_event(
        user=acting_user,
        request=request,
        action_type='USER_DISABLED_BY_ADMIN',
        target_type='USER',
        target_id=str(target_user.id),
        target_name=target_user.email,
        status='SUCCESS',
        message=f'User {target_user.email} disabled by admin.',
    )


@transaction.atomic
def mark_rejected_user_reregisterable(target_user: User, acting_user: User, request=None) -> None:
    profile = target_user.profile

    target_user.is_active = False
    target_user.is_staff = False
    target_user.save(update_fields=['is_active', 'is_staff'])

    profile.account_status = AccountStatus.DELETED
    profile.enabled_by = acting_user
    profile.enabled_at = timezone.now()
    profile.save(update_fields=['account_status', 'enabled_by', 'enabled_at', 'updated_at'])

    create_audit_event(
        user=acting_user,
        request=request,
        action_type='USER_REREGISTER_ENABLED',
        target_type='USER',
        target_id=str(target_user.id),
        target_name=target_user.email,
        status='SUCCESS',
        message=f'Rejected user {target_user.email} marked deleted so they can register again.',
    )


@transaction.atomic
def soft_delete_user(target_user: User, acting_user: User, request=None) -> None:
    profile = target_user.profile

    if profile.role == UserRole.SUPER_ADMIN:
        active_super_admins = UserProfile.objects.filter(
            role=UserRole.SUPER_ADMIN,
            account_status=AccountStatus.APPROVED,
            user__is_active=True,
        ).exclude(user=target_user).count()

        if active_super_admins < 1:
            raise ValueError('Cannot delete the last active super admin.')

    removed_permission_count = 0

    # Only WEB_USER loses folder permissions automatically on delete
    if profile.role == UserRole.WEB_USER:
        removed_permission_count, _ = FolderUserPermission.objects.filter(
            user=target_user
        ).delete()

    target_user.is_active = False
    target_user.is_staff = False
    target_user.save(update_fields=['is_active', 'is_staff'])

    profile.account_status = AccountStatus.DELETED
    profile.enabled_by = acting_user
    profile.enabled_at = timezone.now()
    profile.save(update_fields=['account_status', 'enabled_by', 'enabled_at', 'updated_at'])

    create_audit_event(
        user=acting_user,
        request=request,
        action_type='USER_DELETED',
        target_type='USER',
        target_id=str(target_user.id),
        target_name=target_user.email,
        status='SUCCESS',
        message=(
            f'Soft deleted user {target_user.email}. '
            f'Removed {removed_permission_count} folder permission row(s).'
            if profile.role == UserRole.WEB_USER
            else f'Soft deleted user {target_user.email}.'
        ),
    )
