from django.db import models


class UserRole(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    ADMIN_READONLY = 'ADMIN_READONLY', 'Admin Read Only'
    WEB_USER = 'WEB_USER', 'Web User'


class AccountStatus(models.TextChoices):
    PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    BLOCKED = 'BLOCKED', 'Blocked'
    SECURITY_BLOCKED = 'SECURITY_BLOCKED', 'Security Blocked'
    DISABLED_PASSWORD_EXPIRED = 'DISABLED_PASSWORD_EXPIRED', 'Disabled - Password Expired'
    DISABLED_ADMIN = 'DISABLED_ADMIN', 'Disabled by Admin'
    REJECTED = 'REJECTED', 'Rejected'
    DELETED = "deleted", "Deleted"
