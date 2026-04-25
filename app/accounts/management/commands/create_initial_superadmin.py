from django.core.management.base import BaseCommand
from django.conf import settings
from accounts.models import User, UserProfile
from accounts.enums import UserRole, AccountStatus


class Command(BaseCommand):
    help = "Create the initial super admin from environment variables"

    def handle(self, *args, **options):
        email = getattr(settings, "DJANGO_SUPERUSER_EMAIL", None)
        password = getattr(settings, "DJANGO_SUPERUSER_PASSWORD", None)
        full_name = getattr(settings, "DJANGO_SUPERUSER_FULL_NAME", "Initial Admin")

        if not email or not password:
            self.stdout.write(self.style.WARNING("Superadmin env vars are missing. Skipping."))
            return

        user = User.objects.filter(email=email).first()
        if user:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if not profile.full_name:
                profile.full_name = full_name
            profile.role = UserRole.SUPER_ADMIN
            profile.account_status = AccountStatus.APPROVED
            profile.save()
            self.stdout.write(self.style.SUCCESS(f"Superadmin already exists: {email}"))
            return

        user = User.objects.create_superuser(
            email=email,
            password=password,
        )

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.full_name = full_name
        profile.role = UserRole.SUPER_ADMIN
        profile.account_status = AccountStatus.APPROVED
        profile.save()

        self.stdout.write(self.style.SUCCESS(f"Superadmin created: {email}"))
