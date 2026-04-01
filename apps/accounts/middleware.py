# apps/accounts/middleware.py
from django.http import JsonResponse


EXEMPT_PATHS = [
    '/api/accounts/auth/login/',
    '/api/accounts/auth/refresh/',
    '/api/accounts/auth/change-password/',
    '/api/schema/',
    '/api/docs/',
    '/api/redoc/',
    '/admin/',
]


class ForcePasswordChangeMiddleware:
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
        """
        Reads the JWT token ONLY from the Authorization header.
        Cookies are intentionally ignored here — the authentication
        classes handle cookie reading. Reading cookies in middleware
        would cause false positives for employee tokens sitting in
        the browser cookie jar on unrelated requests.
        """
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if not header.startswith('Bearer '):
            return False

        raw_token = header.split(' ')[1]

        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token = AccessToken(raw_token)
            return bool(token.get('must_change_password', False))
        except Exception:
            return False

    def _is_exempt(self, path):
        return any(path.startswith(exempt) for exempt in EXEMPT_PATHS)