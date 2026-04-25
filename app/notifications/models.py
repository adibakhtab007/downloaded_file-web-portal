from django.db import models
from django.conf import settings


class EmailNotificationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    email_type = models.CharField(max_length=64)
    recipient_email = models.EmailField()
    subject_snapshot = models.CharField(max_length=255)
    status = models.CharField(max_length=32)
    sent_at = models.DateTimeField(auto_now_add=True)
    error_text = models.TextField(blank=True)
