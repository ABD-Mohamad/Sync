# apps/notifications/middleware.py
#
# UPDATED: Now authenticates both User and Employee JWT tokens.
#
# The Angular employee portal connects with:
#     ws://localhost:8000/ws/notifications/?token=<employee_access_token>
#
# EmployeeJWTAuthentication (apps.accounts.authentication) issues tokens with:
#     { "type": "employee", "employee_id": <id>, ... }
#
# This middleware reads the `type` claim and sets either:
#     scope['user']     → for User tokens    (type = 'user' or no type = legacy)
#     scope['employee'] → for Employee tokens (type = 'employee')

from urllib.parse             import parse_qs
from channels.db              import database_sync_to_async
from channels.middleware       import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens    import AccessToken
from rest_framework_simplejwt.exceptions import TokenError


@database_sync_to_async
def get_user_from_token(token_str: str):
    """
    Validates a User JWT and returns the User.
    Returns AnonymousUser on any error.
    """
    try:
        token   = AccessToken(token_str)
        user_id = token.get('user_id')

        if user_id is None:
            return AnonymousUser()

        from apps.accounts.models import User
        return User.objects.select_related('role').get(id=user_id)

    except (TokenError, Exception):
        return AnonymousUser()


@database_sync_to_async
def get_employee_from_token(token_str: str):
    """
    Validates an Employee JWT and returns the Employee instance.
    Employee JWTs carry { type: 'employee', employee_id: <id> }.
    Returns None on any error.
    """
    try:
        token       = AccessToken(token_str)
        token_type  = token.get('type')
        employee_id = token.get('employee_id')

        if token_type != 'employee' or employee_id is None:
            return None

        from apps.accounts.models import Employee
        return Employee.objects.select_related('department').get(id=employee_id)

    except (TokenError, Exception):
        return None


class JWTAuthMiddleware(BaseMiddleware):
    """
    Channels middleware that authenticates WebSocket connections
    using a JWT token from the query string or httpOnly cookie.

    User connections:
        ws://.../ws/notifications/?token=<user_access_token>
        → scope['user'] = User instance

    Employee connections:
        ws://.../ws/notifications/?token=<employee_access_token>
        → scope['employee'] = Employee instance
        → scope['user']     = AnonymousUser
    """
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        params       = parse_qs(query_string)
        token_list   = params.get('token', [])

        token = token_list[0] if token_list else None

        if not token:
            # Fallback: try to extract from cookie header
            headers = dict(scope.get('headers', []))
            cookie  = headers.get(b'cookie', b'').decode()
            token   = _extract_cookie_token(cookie)

        if token:
            # Determine token type by peeking at the payload (no DB hit yet)
            token_type = _peek_token_type(token)

            if token_type == 'employee':
                employee = await get_employee_from_token(token)
                scope['employee'] = employee
                scope['user']     = AnonymousUser()
            else:
                # Default: treat as User token (legacy + it/dh tokens)
                user = await get_user_from_token(token)
                scope['user']     = user
                scope['employee'] = None
        else:
            scope['user']     = AnonymousUser()
            scope['employee'] = None

        return await super().__call__(scope, receive, send)


def _peek_token_type(token_str: str) -> str:
    """
    Reads the 'type' claim from a JWT without full validation.
    Returns 'employee' or 'user' (default).
    This avoids a DB hit just to decide which model to query.
    """
    try:
        import base64, json
        parts   = token_str.split('.')
        if len(parts) < 2:
            return 'user'
        padding = 4 - len(parts[1]) % 4
        decoded = base64.b64decode(parts[1] + '=' * padding)
        payload = json.loads(decoded)
        return payload.get('type', 'user')
    except Exception:
        return 'user'


def _extract_cookie_token(cookie_str: str):
    """Extracts access_token from a Cookie header string."""
    for part in cookie_str.split(';'):
        part = part.strip()
        if part.startswith('access_token='):
            return part.split('=', 1)[1]
    return None