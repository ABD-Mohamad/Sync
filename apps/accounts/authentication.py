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


def _get_raw_token(request):
    """
    Tries to get the token from:
    1. httpOnly cookie (preferred)
    2. Authorization header (fallback for mobile / Swagger)
    """
    token = request.COOKIES.get('access_token')
    if token:
        return token

    header = request.META.get('HTTP_AUTHORIZATION', '')
    if header.startswith('Bearer '):
        return header.split(' ')[1]

    return None


class EmployeeJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        raw_token = _get_raw_token(request)
        if not raw_token:
            return None

        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token = AccessToken(raw_token)
        except TokenError:
            return None

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

        return (employee, token)


class UnifiedJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = _get_raw_token(request)
        if not raw_token:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except InvalidToken:
            return None

        if validated_token.get('type') == 'employee':
            return None

        return self.get_user(validated_token), validated_token