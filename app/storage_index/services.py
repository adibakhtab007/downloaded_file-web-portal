from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from common.utils import safe_relative_path
from .models import FileItem, Folder, StorageRoot, FolderUserPermission


def compute_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b''):
            digest.update(chunk)
    return digest.hexdigest()


def scan_storage_root(storage_root: StorageRoot) -> None:
    base_path = Path(storage_root.absolute_root_path)
    if not base_path.exists():
        return

    seen_folders = set()
    seen_files = set()

    for current_root, dirs, files in os.walk(base_path):
        current_path = Path(current_root)
        rel = '.' if current_path == base_path else str(current_path.relative_to(base_path))

        parent = None
        if rel != '.':
            parent_path = str(current_path.parent)
            parent = Folder.objects.filter(absolute_path=parent_path).first()

        folder, _ = Folder.objects.update_or_create(
            absolute_path=str(current_path),
            defaults={
                'storage_root': storage_root,
                'parent': parent,
                'display_name': current_path.name or storage_root.name,
                'relative_path': rel,
                'is_active': True,
            },
        )
        seen_folders.add(str(current_path))

        for file_name in files:
            full_path = current_path / file_name
            try:
                stat = full_path.stat()
            except FileNotFoundError:
                continue

            file_rel = safe_relative_path(storage_root.absolute_root_path, str(full_path))

            FileItem.objects.update_or_create(
                absolute_path=str(full_path),
                defaults={
                    'folder': folder,
                    'file_name': file_name,
                    'relative_path': file_rel,
                    'size_bytes': stat.st_size,
                    'last_modified_fs': timezone.make_aware(datetime.fromtimestamp(stat.st_mtime)),
                    'is_active': True,
                    'discovered_by_scan': True,
                },
            )
            seen_files.add(str(full_path))

    Folder.objects.filter(storage_root=storage_root).exclude(absolute_path__in=seen_folders).update(is_active=False)
    FileItem.objects.filter(folder__storage_root=storage_root).exclude(absolute_path__in=seen_files).update(is_active=False)


def get_folder_descendants(folder: Folder) -> list[Folder]:
    result = []

    def walk(node: Folder):
        children = Folder.objects.filter(parent=node)
        for child in children:
            result.append(child)
            walk(child)

    walk(folder)
    return result


@transaction.atomic
def revoke_folder_permission_recursive(folder: Folder, user) -> int:
    folders_to_revoke = [folder] + get_folder_descendants(folder)
    deleted_count, _ = FolderUserPermission.objects.filter(
        folder__in=folders_to_revoke,
        user=user,
        permission_type='read',
    ).delete()
    return deleted_count
