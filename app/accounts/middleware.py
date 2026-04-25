from __future__ import annotations

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

from audittrail.services import create_audit_event


class TraceIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.trace_id = request.session.get('trace_id')
        return self.get_response(request)


class ActivityTimeoutMiddleware:
    EXEMPT_PREFIXES = ('/auth/login', '/auth/otp', '/auth/logout', '/static/', '/media/', '/django-admin/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now().timestamp()
            timeout_minutes = settings.FILEPORTAL_SESSION_TIMEOUT_MINUTES
            last_activity = request.session.get('last_activity_ts')
            if last_activity and (now - last_activity) > (timeout_minutes * 60):
                create_audit_event(user=request.user, request=request, action_type='SESSION_TIMEOUT', target_type='AUTH', status='SUCCESS', message='Session expired due to inactivity.')
                logout(request)
                return redirect('accounts:login_password')
            request.session['last_activity_ts'] = now
        return self.get_response(request)
