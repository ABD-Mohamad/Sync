# apps/accounts/authentication.py
__all__ = [
    'EmployeeJWTAuthentication',
    'UnifiedJWTAuthentication',
]
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions     import InvalidToken, TokenError
from rest_framework.authentication           import BaseAuthentication
from rest_framework.exceptions               import AuthenticationFailed
from apps.accounts.models                    import Employee


class EmployeeJWTAuthentication(BaseAuthentication):
    """
    Intercepts employee tokens BEFORE the default JWT authenticator.
    Returns (None, token) — no Django user, just the validated token.
    """
    def authenticate(self, request):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if not header.startswith('Bearer '):
            return None

        raw_token = header.split(' ')[1]

        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token = AccessToken(raw_token)
        except TokenError:
            return None

        # Only handle employee tokens — skip everything else
        if token.get('type') != 'employee':
            return None

        employee_id = token.get('employee_id')
        if not employee_id:
            raise AuthenticationFailed('Employee ID not found in token.')

        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            raise AuthenticationFailed('Employee not found.')

        if employee.status != Employee.Status.ACTIVE:
            raise AuthenticationFailed('Employee account is inactive.')

        # (user=None, auth=token) — view reads employee from token
        return (None, token)


class UnifiedJWTAuthentication(JWTAuthentication):
    """
    Standard JWT auth for Django Users.
    Skips gracefully if the token belongs to an employee.
    """
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except InvalidToken:
            return None

        # Employee tokens are handled by EmployeeJWTAuthentication
        if validated_token.get('type') == 'employee':
            return None

        return self.get_user(validated_token), validated_token