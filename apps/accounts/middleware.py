# apps/accounts/middleware.py
import time
from django.conf   import settings
from django.http   import JsonResponse
from django.core.cache import cache


EXEMPT_PATHS = [
    '/api/accounts/auth/login/',
    '/api/accounts/auth/refresh/',
    '/api/accounts/auth/change-password/',
    '/api/schema/',
    '/api/docs/',
    '/api/redoc/',
    '/admin/',
]

# 30 minutes in seconds (NFR-SEC-08)
INACTIVITY_TIMEOUT = getattr(settings, 'SESSION_INACTIVITY_TIMEOUT', 60 * 30)


class ForcePasswordChangeMiddleware:
    """
    Blocks all requests when must_change_password=True.
    Reads JWT directly — runs before DRF authentication.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path):
            return self.get_response(request)

        if self._must_change(request):
            return JsonResponse(
                {
                    'detail': 'You must change your password before continuing.',
                    'code'  : 'password_change_required',
                },
                status=403,
            )

        return self.get_response(request)

    def _must_change(self, request):
        raw_token = self._extract_token(request)
        if not raw_token:
            return False
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token = AccessToken(raw_token)
            return bool(token.get('must_change_password', False))
        except Exception:
            return False

    def _extract_token(self, request):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if header.startswith('Bearer '):
            return header.split(' ')[1]
        return None

    def _is_exempt(self, path):
        return any(path.startswith(e) for e in EXEMPT_PATHS)


class InactivityTimeoutMiddleware:
    """
    AOP Middleware — enforces NFR-SEC-08.

    On every authenticated request:
    1. Reads the JWT token to get jti (JWT ID — unique per token)
    2. Checks Redis for the last activity timestamp of this token
    3. If the gap exceeds INACTIVITY_TIMEOUT → return 401
    4. If within timeout → update the last activity timestamp

    Uses jti so each token is tracked independently —
    two tabs with different tokens are tracked separately.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path):
            return self.get_response(request)

        raw_token = self._extract_token(request)
        if not raw_token:
            return self.get_response(request)

        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token = AccessToken(raw_token)
            jti   = token.get('jti')
            if not jti:
                return self.get_response(request)
        except Exception:
            return self.get_response(request)

        cache_key    = f'last_activity:{jti}'
        now          = time.time()
        last_activity = cache.get(cache_key)

        if last_activity is not None:
            elapsed = now - float(last_activity)
            if elapsed > INACTIVITY_TIMEOUT:
                return JsonResponse(
                    {
                        'detail': 'Session expired due to inactivity. Please log in again.',
                        'code'  : 'session_expired',
                    },
                    status=401,
                )

        # Refresh the activity timestamp — sliding window
        cache.set(cache_key, now, timeout=INACTIVITY_TIMEOUT)

        return self.get_response(request)

    def _extract_token(self, request):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if header.startswith('Bearer '):
            return header.split(' ')[1]
        # Also check cookie
        return request.COOKIES.get('access_token')

    def _is_exempt(self, path):
        return any(path.startswith(e) for e in EXEMPT_PATHS)