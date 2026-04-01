# apps/notifications/middleware.py
from urllib.parse                             import parse_qs
from channels.db                             import database_sync_to_async
from channels.middleware                     import BaseMiddleware
from django.contrib.auth.models              import AnonymousUser
from rest_framework_simplejwt.tokens         import AccessToken
from rest_framework_simplejwt.exceptions     import TokenError


@database_sync_to_async
def get_user_from_token(token_str):
    """
    Validates the JWT access token and returns the corresponding User.
    Returns AnonymousUser if the token is invalid or the user does not exist.
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


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom Channels middleware that authenticates WebSocket connections
    using a JWT token from the query string.

    The Angular client connects like:
        ws://localhost:8000/ws/notifications/?token=<access_token>

    This middleware extracts the token, validates it, and populates
    scope['user'] so the consumer can access request.user normally.
    """
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        params       = parse_qs(query_string)
        token_list   = params.get('token', [])

        if token_list:
            scope['user'] = await get_user_from_token(token_list[0])
        else:
            # Also check cookie as fallback
            headers = dict(scope.get('headers', []))
            cookie  = headers.get(b'cookie', b'').decode()
            token   = _extract_cookie_token(cookie)

            if token:
                scope['user'] = await get_user_from_token(token)
            else:
                scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def _extract_cookie_token(cookie_str):
    """Extracts access_token from cookie string."""
    for part in cookie_str.split(';'):
        part = part.strip()
        if part.startswith('access_token='):
            return part.split('=', 1)[1]
    return None