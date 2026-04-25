import re
from django.core.exceptions import ValidationError


class ComplexityPasswordValidator:
    def validate(self, password, user=None):
        if len(password) < 8 or len(password) > 12:
            raise ValidationError('Password must be 8 to 12 characters long.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must contain at least one number.')
        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValidationError('Password must contain at least one special character.')

    def get_help_text(self):
        return '8-12 characters, including uppercase, lowercase, number, and special character.'
