from __future__ import annotations

from django.conf import settings
from django.db import models


class StorageRoot(models.Model):
    STORAGE_LOCAL = 'local'
    STORAGE_NAS = 'nas'
    STORAGE_CHOICES = [(STORAGE_LOCAL, 'Local'), (STORAGE_NAS, 'NAS')]

    name = models.CharField(max_length=100, unique=True)
    storage_type = models.CharField(max_length=16, choices=STORAGE_CHOICES)
    absolute_root_path = models.CharField(max_length=1024, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f'{self.name} ({self.absolute_root_path})'


class Folder(models.Model):
    storage_root = models.ForeignKey(StorageRoot, on_delete=models.CASCADE, related_name='folders')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    display_name = models.CharField(max_length=255)
    relative_path = models.CharField(max_length=1024)
    absolute_path = models.CharField(max_length=1024, unique=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['relative_path']

    def __str__(self) -> str:
        return self.display_name


class FileItem(models.Model):
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    file_name = models.CharField(max_length=255)
    relative_path = models.CharField(max_length=1024)
    absolute_path = models.CharField(max_length=1024, unique=True)
    size_bytes = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    mime_type = models.CharField(max_length=255, blank=True)
    last_modified_fs = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    discovered_by_scan = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['file_name']

    def __str__(self) -> str:
        return self.file_name


class FolderUserPermission(models.Model):
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='user_permissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='folder_permissions')
    permission_type = models.CharField(max_length=16, default='read')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_folder_permissions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('folder', 'user', 'permission_type')
