# apps/accounts/throttles.py
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """
    Limits login attempts to 5 per minute per IP.
    Applies to unauthenticated requests only.
    """
    scope = 'login'


class SensitiveEndpointThrottle(UserRateThrottle):
    """
    Limits sensitive actions (change-password) to 10 per minute
    for authenticated users.
    """
    scope = 'sensitive'