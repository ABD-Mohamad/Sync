# apps/accounts/validators.py
import re
from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    """
    Enforces NFR-SEC-07:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """

    def validate(self, password, user=None):
        errors = []

        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter.')
        if not re.search(r'\d', password):
            errors.append('Password must contain at least one digit.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~/]', password):
            errors.append('Password must contain at least one special character (!@#$%^&* etc).')

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            'Password must be at least 8 characters and contain: '
            'uppercase, lowercase, digit, and special character.'
        )