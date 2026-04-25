from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'change-me')
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() == 'true'
DJANGO_SUPERUSER_EMAIL = os.getenv("DJANGO_SUPERUSER_EMAIL", "")
DJANGO_SUPERUSER_FULL_NAME = os.getenv("DJANGO_SUPERUSER_FULL_NAME", "Initial Admin")
DJANGO_SUPERUSER_PASSWORD = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [u.strip() for u in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if u.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'accounts',
    'portal_admin',
    'portal_user',
    'storage_index',
    'audittrail',
    'notifications',
    'settings_app',
    'common',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.TraceIdMiddleware',
    'accounts.middleware.ActivityTimeoutMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'settings_app.context_processors.portal_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME', 'fileportal'),
        'USER': os.getenv('DATABASE_USER', 'fileportal'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', 'fileportal'),
        'HOST': os.getenv('DATABASE_HOST', 'db'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'accounts.validators.ComplexityPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
]

AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = ['accounts.backends.EmailBackend']

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'accounts:login_password'
LOGIN_REDIRECT_URL = 'accounts:post_login_router'
LOGOUT_REDIRECT_URL = 'accounts:login_password'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.office365.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = not DEBUG

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

FILEPORTAL_SESSION_TIMEOUT_MINUTES = int(os.getenv('FILEPORTAL_SESSION_TIMEOUT_MINUTES', '5'))
FILEPORTAL_OTP_EXPIRY_SECONDS = int(os.getenv('FILEPORTAL_OTP_EXPIRY_SECONDS', '120'))
FILEPORTAL_OTP_MAX_ATTEMPTS = int(os.getenv('FILEPORTAL_OTP_MAX_ATTEMPTS', '3'))
FILEPORTAL_UPLOAD_MAX_BYTES = int(os.getenv('FILEPORTAL_UPLOAD_MAX_BYTES', str(5 * 1024 * 1024 * 1024)))
LOCAL_STORAGE_ROOT = os.getenv('LOCAL_STORAGE_ROOT', '/srv/fileportal/local')
NAS_STORAGE_ROOT = os.getenv('NAS_STORAGE_ROOT', '/srv/fileportal/nas')
PROTECTED_NGINX_PREFIX = os.getenv('PROTECTED_NGINX_PREFIX', '/protected-download')

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/1')
CELERY_BEAT_SCHEDULE = {
    'send-password-expiry-reminders': {
        'task': 'notifications.tasks.send_password_expiry_reminders_task',
        'schedule': 86400.0,
    },
    'cleanup-expired-otps': {
        'task': 'notifications.tasks.cleanup_expired_otps_task',
        'schedule': 60.0,
    },
    'scan-storage-roots': {
        'task': 'storage_index.tasks.scan_storage_roots_task',
        'schedule': 600.0,
    },
}

from .celery import app as celery_app
