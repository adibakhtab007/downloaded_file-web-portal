from __future__ import annotations

import uuid
from django.utils import timezone
from .models import AuditEvent, UserSessionJourney


def _client_ip(request):
    if not request:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def generate_trace_id(prefix: str = 'TRC') -> str:
    return f'{prefix}-{timezone.now().strftime("%Y%m%d%H%M%S")}-{uuid.uuid4().hex[:16]}'


def create_journey(user, request, trace_id: str | None = None) -> str:
    trace_id = trace_id or generate_trace_id()

    journey, created = UserSessionJourney.objects.get_or_create(
        trace_id=trace_id,
        defaults={
            'user': user,
            'role_snapshot': getattr(getattr(user, 'profile', None), 'role', ''),
            'source_ip': _client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '') if request else '',
            'session_key': request.session.session_key or '' if request else '',
        }
    )

    if not created:
        updated = False

        if user and journey.user_id is None:
            journey.user = user
            updated = True

        role_snapshot = getattr(getattr(user, 'profile', None), 'role', '')
        if role_snapshot and not journey.role_snapshot:
            journey.role_snapshot = role_snapshot
            updated = True

        if request:
            source_ip = _client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            session_key = request.session.session_key or ''

            if source_ip and not journey.source_ip:
                journey.source_ip = source_ip
                updated = True
            if user_agent and not journey.user_agent:
                journey.user_agent = user_agent
                updated = True
            if session_key and not journey.session_key:
                journey.session_key = session_key
                updated = True

        if updated:
            journey.save()

    return trace_id


def create_audit_event(
    *,
    user=None,
    request=None,
    action_type: str,
    target_type: str,
    status: str,
    message: str = '',
    target_id: str = '',
    target_name: str = '',
    trace_id: str = '',
) -> None:
    resolved_trace_id = trace_id

    if not resolved_trace_id and request is not None:
        resolved_trace_id = (
            request.session.get('trace_id')
            or request.session.get('pre_auth_trace_id', '')
        )

    if resolved_trace_id:
        create_journey(user=user, request=request, trace_id=resolved_trace_id)

    AuditEvent.objects.create(
        trace_id=resolved_trace_id,
        user=user,
        email_snapshot=getattr(user, 'email', ''),
        role_snapshot=getattr(getattr(user, 'profile', None), 'role', ''),
        source_ip=_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
        request_path=request.path if request else '',
        http_method=request.method if request else '',
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        status=status,
        message=message,
    )
