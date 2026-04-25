from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models


class UserSessionJourney(models.Model):
    trace_id = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    role_snapshot = models.CharField(max_length=32, blank=True)
    login_at = models.DateTimeField(auto_now_add=True)
    logout_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=64, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_key = models.CharField(max_length=128, blank=True)


class AuditEvent(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    trace_id = models.CharField(max_length=64, blank=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    email_snapshot = models.EmailField(blank=True)
    role_snapshot = models.CharField(max_length=32, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.TextField(blank=True)
    http_method = models.CharField(max_length=10, blank=True)
    action_type = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64)
    target_id = models.CharField(max_length=128, blank=True)
    target_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
