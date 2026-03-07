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
    """
    AOP Middleware — blocks ALL account types (User and Employee)
    from accessing the API if must_change_password is True.

    Detection strategy:
      - Django User  → checked via request.user (set by DRF authentication)
      - Employee     → checked via JWT token payload (type == 'employee')
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path):
            return self.get_response(request)

        # ── Check Django User ─────────────────────────────────
        if (hasattr(request, 'user')
                and request.user.is_authenticated
                and getattr(request.user, 'must_change_password', False)):
            return self._force_change_response()

        # ── Check Employee via JWT payload ────────────────────
        if self._employee_must_change(request):
            return self._force_change_response()

        return self.get_response(request)

    def _employee_must_change(self, request):
        """
        Reads the Authorization header directly — before DRF
        authentication runs — to check employee must_change_password.
        """
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if not header.startswith('Bearer '):
            return False

        raw_token = header.split(' ')[1]

        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token = AccessToken(raw_token)
        except Exception:
            return False

        if token.get('type') != 'employee':
            return False

        return bool(token.get('must_change_password', False))

    def _force_change_response(self):
        return JsonResponse(
            {
                'detail': 'You must change your password before continuing.',
                'code'  : 'password_change_required',
            },
            status=403,
        )

    def _is_exempt(self, path):
        return any(path.startswith(exempt) for exempt in EXEMPT_PATHS)