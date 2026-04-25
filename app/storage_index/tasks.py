from celery import shared_task
from .models import StorageRoot
from .services import scan_storage_root


@shared_task
def scan_storage_roots_task():
    for root in StorageRoot.objects.filter(is_active=True):
        scan_storage_root(root)
