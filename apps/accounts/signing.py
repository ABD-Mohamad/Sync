# apps/accounts/signing.py
# FIX #3: JsonResponse was referenced but never imported.
#          verify_signature was called but never defined — NameError at runtime.
#          Added the import and a stub that must be completed with your HMAC logic.

import hmac
import hashlib
import json
import time

from django.http      import JsonResponse   # ← was missing
from django.conf      import settings


def verify_signature(request) -> bool:
    """
    Verifies the HMAC-SHA256 X-Signature sent by the Angular frontend.

    Expected headers:
        X-Signature : hex-encoded HMAC-SHA256 of f"{timestamp}.{sorted_json_body}"
        X-Timestamp : Unix timestamp (seconds) used in the signature

    Rejects requests whose timestamp is more than 5 minutes old (replay protection).
    """
    signature  = request.META.get('HTTP_X_SIGNATURE', '')
    timestamp  = request.META.get('HTTP_X_TIMESTAMP', '')
    secret     = getattr(settings, 'REQUEST_SIGNING_SECRET', '')

    if not signature or not timestamp or not secret:
        return False

    # Replay-attack window: 5 minutes
    try:
        request_time = int(timestamp)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - request_time) > 300:
        return False

    try:
        body = json.loads(request.body or b'{}')
        # Sort keys to match Angular's JSON.stringify with sorted keys
        sorted_body = json.dumps(body, sort_keys=True, separators=(',', ':'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False

    message  = f'{timestamp}.{sorted_body}'.encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected, signature)


class RequestSigningMiddleware:
    SIGNED_PATHS = [
        '/api/accounts/auth/login/',
        '/api/accounts/auth/change-password/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path in self.SIGNED_PATHS:
            if not settings.DEBUG and not verify_signature(request):
                return JsonResponse(
                    {
                        'detail': 'Invalid or missing request signature.',
                        'code'  : 'invalid_signature',
                    },
                    status=400,
                )
        return self.get_response(request)