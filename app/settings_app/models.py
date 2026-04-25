from django.conf import settings
from django.db import models


class AppSetting(models.Model):
    key = models.CharField(max_length=128, unique=True)
    value = models.CharField(max_length=255)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'{self.key}={self.value}'
