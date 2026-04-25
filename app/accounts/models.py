from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from .enums import AccountStatus, UserRole


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        UserProfile.objects.get_or_create(user=user)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        user = self.create_user(email=email, password=password, **extra_fields)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.full_name = extra_fields.get('full_name') or 'Super Admin'
        profile.role = UserRole.SUPER_ADMIN
        profile.account_status = AccountStatus.APPROVED
        profile.password_changed_at = timezone.now()
        profile.password_expires_at = timezone.now() + timedelta(days=90)
        profile.save()
        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:
        return self.email


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=32, choices=UserRole.choices, default=UserRole.WEB_USER)
    account_status = models.CharField(max_length=64, choices=AccountStatus.choices, default=AccountStatus.PENDING_APPROVAL)
    failed_login_count = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    security_failure_count = models.PositiveIntegerField(default=0)
    security_blocked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    password_expires_at = models.DateTimeField(default=timezone.now)
    must_change_password = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_users')
    approved_at = models.DateTimeField(null=True, blank=True)
    enabled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='enabled_users')
    enabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_admin_role(self) -> bool:
        return self.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN_READONLY}

    @property
    def is_locked(self) -> bool:
        now = timezone.now()
        return bool((self.blocked_until and self.blocked_until > now) or (self.security_blocked_until and self.security_blocked_until > now))

    def reset_failed_login_state(self) -> None:
        self.failed_login_count = 0
        self.blocked_until = None
        self.save(update_fields=['failed_login_count', 'blocked_until', 'updated_at'])

    def set_password_expiry(self, days: int = 90) -> None:
        now = timezone.now()
        self.password_changed_at = now
        self.password_expires_at = now + timedelta(days=days)
        self.must_change_password = False
        self.save(update_fields=['password_changed_at', 'password_expires_at', 'must_change_password', 'updated_at'])

    def __str__(self) -> str:
        return f'{self.full_name} <{self.user.email}>'


class PasswordHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_histories')
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class SecurityQuestion(models.Model):
    question_text = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'question_text']

    def __str__(self) -> str:
        return self.question_text


class UserSecurityAnswer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='security_answers')
    question = models.ForeignKey(SecurityQuestion, on_delete=models.CASCADE)
    answer_hash = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'question')


class OtpCode(models.Model):
    OTP_LOGIN = 'LOGIN_2FA'
    OTP_UNLOCK = 'ACCOUNT_UNLOCK'
    OTP_PASSWORD_CHANGE = 'PASSWORD_CHANGE'
    OTP_CHOICES = [
        (OTP_LOGIN, 'Login 2FA'),
        (OTP_UNLOCK, 'Account Unlock'),
        (OTP_PASSWORD_CHANGE, 'Password Change'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otp_codes')
    otp_type = models.CharField(max_length=32, choices=OTP_CHOICES)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=settings.FILEPORTAL_OTP_MAX_ATTEMPTS)
    created_at = models.DateTimeField(auto_now_add=True)
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and not self.is_expired and self.attempt_count < self.max_attempts
