from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from audittrail.models import UserSessionJourney
from audittrail.services import create_audit_event, generate_trace_id
from common.utils import normalize_secret_answer
from django.contrib.auth.hashers import check_password

from .enums import AccountStatus, UserRole
from .forms import (
    ForcedPasswordResetForm,
    LoginPasswordForm,
    OtpVerificationForm,
    RegistrationForm,
    UnlockBySecurityAnswersForm,
)
from .models import User, OtpCode
from .services import (
    create_otp,
    create_pending_web_user,
    password_is_expired,
    record_failed_login,
    reset_login_counters,
    set_new_password,
    start_authenticated_journey,
    user_can_access_admin_portal,
    user_can_access_web_portal,
    verify_otp,
)


class RegisterView(View):
    template_name = 'accounts/register.html'

    def get(self, request):
        request.session['pre_auth_trace_id'] = request.session.get('pre_auth_trace_id') or generate_trace_id()
        return render(request, self.template_name, {'form': RegistrationForm()})

    def post(self, request):
        request.session['pre_auth_trace_id'] = request.session.get('pre_auth_trace_id') or generate_trace_id()

        form = RegistrationForm(request.POST)
        if form.is_valid():
            create_pending_web_user(
                full_name=form.cleaned_data['full_name'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                question_answer_pairs=[
                    (form.cleaned_data['question_1'], form.cleaned_data['answer_1']),
                    (form.cleaned_data['question_2'], form.cleaned_data['answer_2']),
                    (form.cleaned_data['question_3'], form.cleaned_data['answer_3']),
                ],
                request=request,
            )
            messages.success(request, 'Registration submitted. Wait for admin approval.')
            return redirect('accounts:login_password')
        return render(request, self.template_name, {'form': form})


class LoginPasswordView(View):
    template_name = 'accounts/login.html'

    def get(self, request):
        request.session['pre_auth_trace_id'] = request.session.get('pre_auth_trace_id') or generate_trace_id()
        return render(request, self.template_name, {'form': LoginPasswordForm()})

    def post(self, request):
        request.session['pre_auth_trace_id'] = request.session.get('pre_auth_trace_id') or generate_trace_id()

        form = LoginPasswordForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        email = form.cleaned_data['email'].strip().lower()
        password = form.cleaned_data['password']

        existing = User.objects.filter(email=email).select_related('profile').first()

        if existing and (
            existing.profile.account_status == AccountStatus.DELETED or
            not existing.is_active
        ):
            create_audit_event(
                user=existing,
                request=request,
                action_type='LOGIN_PASSWORD_FAIL',
                target_type='AUTH',
                status='DENIED',
                message='Deleted/inactive user attempted login.',
            )
            messages.error(request, 'This user has no permission to access the web portal.')
            return render(request, self.template_name, {'form': form})

        user = authenticate(request, email=email, password=password)

        if not user:
            record_failed_login(existing, email, request=request)

            if existing:
                existing.refresh_from_db()
                if existing.profile.is_locked:
                    messages.error(request, 'Your account has been blocked for wrong password attempts.')
                    return render(request, self.template_name, {'form': form})

            messages.error(request, 'Invalid credentials.')
            return render(request, self.template_name, {'form': form})

        profile = user.profile

        if profile.is_locked:
            messages.error(request, 'Account is currently blocked.')
            return render(request, self.template_name, {'form': form})

        if profile.account_status in {
            AccountStatus.PENDING_APPROVAL,
            AccountStatus.REJECTED,
            AccountStatus.DISABLED_ADMIN,
            AccountStatus.SECURITY_BLOCKED,
            AccountStatus.DELETED,
        }:
            messages.error(request, 'This user has no permission to access the web portal.')
            return render(request, self.template_name, {'form': form})

        if profile.account_status == AccountStatus.DISABLED_PASSWORD_EXPIRED or password_is_expired(user):
            request.session['pending_expired_user_id'] = user.id
            create_otp(user, OtpCode.OTP_PASSWORD_CHANGE, request=request)
            messages.info(request, 'Password expired. Verify OTP and set a new password.')
            return redirect('accounts:expired_password_reset')

        request.session['pre_2fa_user_id'] = user.id

        create_otp(user, OtpCode.OTP_LOGIN, request=request)

        create_audit_event(
            user=user,
            request=request,
            action_type='LOGIN_PASSWORD_OK',
            target_type='AUTH',
            status='SUCCESS',
            message='Password step succeeded. Waiting for OTP.',
        )

        messages.info(request, 'OTP sent to your email.')
        return redirect('accounts:otp_verify')


class OtpVerifyView(View):
    template_name = 'accounts/otp_verify.html'

    def get(self, request):
        return render(request, self.template_name, {'form': OtpVerificationForm()})

    def post(self, request):
        form = OtpVerificationForm(request.POST)
        user_id = request.session.get('pre_2fa_user_id')

        if not user_id:
            messages.error(request, 'Login session not found. Please login again.')
            return redirect('accounts:login_password')

        user = get_object_or_404(User, pk=user_id)

        if form.is_valid() and verify_otp(user, OtpCode.OTP_LOGIN, form.cleaned_data['otp'], request=request):
            login(request, user)
            request.session.pop('pre_2fa_user_id', None)

            reset_login_counters(user)
            start_authenticated_journey(user, request)

            create_audit_event(
                user=user,
                request=request,
                action_type='LOGIN_SUCCESS',
                target_type='AUTH',
                status='SUCCESS',
                message='User logged in successfully.',
            )

            request.session.pop('pre_auth_trace_id', None)
            return redirect('accounts:post_login_router')

        messages.error(request, 'Invalid OTP.')
        return render(request, self.template_name, {'form': form})


class UnlockAccountView(View):
    template_name = 'accounts/unlock.html'

    def get(self, request):
        request.session['pre_auth_trace_id'] = request.session.get('pre_auth_trace_id') or generate_trace_id()
        return render(request, self.template_name, {'form': UnlockBySecurityAnswersForm()})

    def post(self, request):
        request.session['pre_auth_trace_id'] = request.session.get('pre_auth_trace_id') or generate_trace_id()

        form = UnlockBySecurityAnswersForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        email = form.cleaned_data['email'].strip().lower()
        user = get_object_or_404(User, email=email)

        answers = list(
            user.security_answers.select_related('question').order_by(
                'question__sort_order',
                'question__question_text'
            )
        )
        submitted = [
            form.cleaned_data['answer_1'],
            form.cleaned_data['answer_2'],
            form.cleaned_data['answer_3'],
        ]

        ok = len(answers) == 3 and all(
            check_password(normalize_secret_answer(val), ans.answer_hash)
            for val, ans in zip(submitted, answers)
        )

        if ok:
            request.session['pending_unlock_user_id'] = user.id
            create_otp(user, OtpCode.OTP_UNLOCK, request=request)
            messages.info(request, 'OTP sent to your email for account unlock.')
            return redirect('accounts:unlock_otp')

        profile = user.profile
        profile.security_blocked_until = timezone.now() + timedelta(hours=24)
        profile.account_status = AccountStatus.SECURITY_BLOCKED
        profile.save(update_fields=['security_blocked_until', 'account_status', 'updated_at'])

        create_audit_event(
            user=user,
            request=request,
            action_type='ACCOUNT_BLOCKED',
            target_type='AUTH',
            status='FAILED',
            message='User failed security answers and was security-blocked for 24 hours.',
        )

        from notifications.tasks import send_admin_alert_email_task
        send_admin_alert_email_task.delay(
            'Security answer failure',
            f'User {user.email} failed account-unlock security answers and is blocked for 24 hours.'
        )

        messages.error(request, 'Security answers failed. Account blocked for 24 hours. Contact admin.')
        return render(request, self.template_name, {'form': form})


class UnlockOtpView(View):
    template_name = 'accounts/otp_verify.html'

    def get(self, request):
        return render(request, self.template_name, {'form': OtpVerificationForm()})

    def post(self, request):
        form = OtpVerificationForm(request.POST)
        user_id = request.session.get('pending_unlock_user_id')

        if not user_id:
            return redirect('accounts:unlock_account')

        user = get_object_or_404(User, pk=user_id)

        if form.is_valid() and verify_otp(user, OtpCode.OTP_UNLOCK, form.cleaned_data['otp'], request=request):
            profile = user.profile
            profile.failed_login_count = 0
            profile.blocked_until = None
            profile.security_blocked_until = None
            if profile.role == UserRole.WEB_USER:
                profile.account_status = AccountStatus.APPROVED
            profile.save(update_fields=[
                'failed_login_count',
                'blocked_until',
                'security_blocked_until',
                'account_status',
                'updated_at',
            ])

            request.session.pop('pending_unlock_user_id', None)
            request.session.pop('pre_auth_trace_id', None)

            create_audit_event(
                user=user,
                request=request,
                action_type='ACCOUNT_UNBLOCKED',
                target_type='AUTH',
                status='SUCCESS',
                message='User self-unlocked account via security questions and OTP.',
            )

            messages.success(request, 'Account unlocked. Please log in.')
            return redirect('accounts:login_password')

        messages.error(request, 'Invalid OTP.')
        return render(request, self.template_name, {'form': form})


class ExpiredPasswordResetView(View):
    template_name = 'accounts/expired_password_reset.html'

    def get(self, request):
        return render(request, self.template_name, {'form': ForcedPasswordResetForm()})

    def post(self, request):
        user_id = request.session.get('pending_expired_user_id')
        if not user_id:
            return redirect('accounts:login_password')

        user = get_object_or_404(User, pk=user_id)
        form = ForcedPasswordResetForm(request.POST, user=user)
        otp = request.POST.get('otp', '')

        if form.is_valid() and verify_otp(user, OtpCode.OTP_PASSWORD_CHANGE, otp, request=request):
            set_new_password(user, form.cleaned_data['new_password'], request=request)
            request.session.pop('pending_expired_user_id', None)
            request.session.pop('pre_auth_trace_id', None)

            messages.success(request, 'Password updated. Please log in again.')
            return redirect('accounts:login_password')

        messages.error(request, 'Invalid input or OTP.')
        return render(request, self.template_name, {'form': form})


@login_required
def post_login_router(request):
    user = request.user

    if user.profile.must_change_password:
        return redirect('portal_user:forced_password_reset')

    if user_can_access_admin_portal(user):
        return redirect('portal_admin:dashboard')

    if user_can_access_web_portal(user):
        return redirect('portal_user:dashboard')

    logout(request)
    messages.error(request, 'Your account is not allowed to access any portal.')
    return redirect('accounts:login_password')


@login_required
def logout_view(request):
    current_trace_id = request.session.get('trace_id')

    if current_trace_id:
        journey = UserSessionJourney.objects.filter(trace_id=current_trace_id).first()
        if journey and not journey.logout_at:
            journey.logout_at = timezone.now()
            journey.end_reason = 'LOGOUT'
            journey.save(update_fields=['logout_at', 'end_reason'])

    create_audit_event(
        user=request.user,
        request=request,
        action_type='LOGOUT',
        target_type='AUTH',
        status='SUCCESS',
        message='User logged out.',
    )

    request.session.pop('trace_id', None)
    request.session.pop('pre_auth_trace_id', None)

    logout(request)
    return redirect('accounts:login_password')
