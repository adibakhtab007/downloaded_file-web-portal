from django.core.management.base import BaseCommand
from accounts.models import SecurityQuestion


QUESTIONS = [
    'What was the name of your first school?',
    'What is the name of the town where you were born?',
    'What is your favorite childhood nickname?',
    'What is the first name of your oldest childhood friend?',
    'What is your favorite teacher name?',
    'What was the make of your first bicycle?',
]


class Command(BaseCommand):
    help = 'Seed default security questions.'

    def handle(self, *args, **options):
        for idx, question in enumerate(QUESTIONS, start=1):
            SecurityQuestion.objects.get_or_create(question_text=question, defaults={'sort_order': idx, 'is_active': True})
        self.stdout.write(self.style.SUCCESS('Security questions seeded.'))
