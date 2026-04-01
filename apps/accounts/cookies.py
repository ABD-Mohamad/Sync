# apps/accounts/cookies.py
from django.conf import settings


def set_auth_cookies(response, access_token, refresh_token):
    """
    Sets access and refresh tokens as secure httpOnly cookies.
    Called after every successful login or token refresh.
    """
    response.set_cookie(
        key      = 'access_token',
        value    = access_token,
        max_age  = settings.ACCESS_TOKEN_LIFETIME_SECONDS,
        httponly = settings.COOKIE_HTTPONLY,
        secure   = settings.COOKIE_SECURE,
        samesite = settings.COOKIE_SAMESITE,
    )
    response.set_cookie(
        key      = 'refresh_token',
        value    = refresh_token,
        max_age  = settings.REFRESH_TOKEN_LIFETIME_SECONDS,
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