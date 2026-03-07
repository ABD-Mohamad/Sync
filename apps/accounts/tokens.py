# apps/accounts/tokens.py
__all__ = [
    'get_tokens_for_user',
    'get_tokens_for_employee',
    'refresh_employee_token',
]

from rest_framework_simplejwt.tokens     import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError



def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh['full_name']            = user.full_name
    refresh['role']                 = user.role.name if user.role else None
    refresh['must_change_password'] = user.must_change_password
    return {
        'refresh': str(refresh),
        'access' : str(refresh.access_token),
    }


def get_tokens_for_employee(employee):
    refresh = RefreshToken()
    refresh['type']                 = 'employee'
    refresh['employee_id']          = employee.id
    refresh['email']                = employee.email
    refresh['full_name']            = employee.full_name
    refresh['must_change_password'] = employee.must_change_password
    return {
        'refresh': str(refresh),
        'access' : str(refresh.access_token),
    }


def refresh_employee_token(raw_refresh_token):
    """
    Validates an employee refresh token and issues a new access token.
    Raises TokenError if the token is invalid or not an employee token.
    """
    try:
        refresh = RefreshToken(raw_refresh_token)
    except TokenError as e:
        raise TokenError('Invalid or expired refresh token.') from e

    if refresh.get('type') != 'employee':
        raise TokenError('Not an employee token.')

    # Rotate — blacklist old, issue new
    refresh.blacklist()

    from apps.accounts.models import Employee
    try:
        employee = Employee.objects.get(id=refresh['employee_id'])
    except Employee.DoesNotExist:
        raise TokenError('Employee not found.')

    return get_tokens_for_employee(employee)