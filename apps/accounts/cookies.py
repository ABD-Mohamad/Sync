# apps/accounts/cookies.py
from django.conf import settings


def set_auth_cookies(response, access_token, refresh_token):
    """
    Sets access and refresh tokens as secure httpOnly cookies.
    Called after every successful login or token refresh.
    """
    # Extract lifetime from SIMPLE_JWT dict and convert timedelta to seconds
    access_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME')
    refresh_lifetime = settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME')

    response.set_cookie(
        key      = 'access_token',
        value    = str(access_token),
        max_age  = int(access_lifetime.total_seconds()) if access_lifetime else 3600,
        httponly = settings.COOKIE_HTTPONLY,
        secure   = settings.COOKIE_SECURE,
        samesite = settings.COOKIE_SAMESITE,
    )
    response.set_cookie(
        key      = 'refresh_token',
        value    = str(refresh_token),
        max_age  = int(refresh_lifetime.total_seconds()) if refresh_lifetime else 86400 * 7,
        httponly = settings.COOKIE_HTTPONLY,
        secure   = settings.COOKIE_SECURE,
        samesite = settings.COOKIE_SAMESITE,
    )
    return response


def clear_auth_cookies(response):
    """
    Clears both tokens from the browser.
    Called on logout.
    """
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    return response