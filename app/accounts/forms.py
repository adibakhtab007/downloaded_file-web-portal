from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError

from .enums import AccountStatus
from .models import SecurityQuestion
from .services import validate_password_history

User = get_user_model()


class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    question_1 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.filter(is_active=True))
    answer_1 = forms.CharField(widget=forms.PasswordInput(render_value=True))
    question_2 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.filter(is_active=True))
    answer_2 = forms.CharField(widget=forms.PasswordInput(render_value=True))
    question_3 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.filter(is_active=True))
    answer_3 = forms.CharField(widget=forms.PasswordInput(render_value=True))

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        existing_user = User.objects.filter(email=email).select_related('profile').first()

        if existing_user:
            # Allow re-registration only for soft-deleted users
            if existing_user.profile.account_status != AccountStatus.DELETED:
                raise ValidationError('A user with this email already exists.')

        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirm_password = cleaned.get('confirm_password')
        questions = [cleaned.get('question_1'), cleaned.get('question_2'), cleaned.get('question_3')]

        if password and confirm_password and password != confirm_password:
            raise ValidationError('Password and confirm password must match.')

        if password:
            password_validation.validate_password(password)

        if len({q.id for q in questions if q}) != 3:
            raise ValidationError('Please select three different security questions.')

        return cleaned


class LoginPasswordForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class OtpVerificationForm(forms.Form):
    otp = forms.CharField(max_length=6, min_length=6)


class UnlockBySecurityAnswersForm(forms.Form):
    email = forms.EmailField()
    answer_1 = forms.CharField(widget=forms.PasswordInput(render_value=True))
    answer_2 = forms.CharField(widget=forms.PasswordInput(render_value=True))
    answer_3 = forms.CharField(widget=forms.PasswordInput(render_value=True))


class PasswordChangeWithOtpForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    otp = forms.CharField(max_length=6, min_length=6)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        current_password = cleaned.get('current_password')
        new_password = cleaned.get('new_password')
        confirm_password = cleaned.get('confirm_password')

        if self.user and current_password and not self.user.check_password(current_password):
            raise ValidationError('Current password is incorrect.')

        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError('New password and confirm password must match.')

        if new_password:
            password_validation.validate_password(new_password, self.user)
            validate_password_history(self.user, new_password)

        return cleaned


class ForcedPasswordResetForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        new_password = cleaned.get('new_password')
        confirm_password = cleaned.get('confirm_password')

        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError('New password and confirm password must match.')

        if new_password:
            password_validation.validate_password(new_password, self.user)
            validate_password_history(self.user, new_password)

        return cleaned


class SecurityAnswersUpdateForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput)
    otp = forms.CharField(max_length=6, min_length=6)
    question_1 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.filter(is_active=True))
    answer_1 = forms.CharField(widget=forms.PasswordInput(render_value=True))
    question_2 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.filter(is_active=True))
    answer_2 = forms.CharField(widget=forms.PasswordInput(render_value=True))
    question_3 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.filter(is_active=True))
    answer_3 = forms.CharField(widget=forms.PasswordInput(render_value=True))

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()

        if self.user and not self.user.check_password(cleaned.get('current_password', '')):
            raise ValidationError('Current password is incorrect.')

        questions = [cleaned.get('question_1'), cleaned.get('question_2'), cleaned.get('question_3')]
        if len({q.id for q in questions if q}) != 3:
            raise ValidationError('Please select three different security questions.')

        return cleaned
