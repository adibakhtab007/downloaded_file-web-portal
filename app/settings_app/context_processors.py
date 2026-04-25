from django.conf import settings


def portal_settings(request):
    return {
        'PORTAL_SESSION_TIMEOUT_MINUTES': settings.FILEPORTAL_SESSION_TIMEOUT_MINUTES,
    }
