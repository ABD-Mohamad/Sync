# apps/accounts/signing.py
import hmac
import hashlib
import json
import time
from django.conf     import settings
from django.http     import JsonResponse


SIGNING_SECRET   = settings.REQUEST_SIGNING_SECRET  # add to settings + .env
TIMESTAMP_TOLERANCE = 30  # seconds — reject requests older than 30s


def sign_payload(payload: dict, timestamp: str) -> str:
    """
    Generates HMAC-SHA256 signature for a request payload.
    Called by the Angular app before sending the request.
    Used in the signing utility on the frontend.
    """
    body    = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    message = f'{timestamp}.{body}'.encode('utf-8')
    return hmac.new(
        SIGNING_SECRET.encode('utf-8'),
        message,
        hashlib.sha256,
    ).hexdigest()


def verify_signature(request) -> bool:
    """
    Verifies the HMAC signature sent by the client.
    Checks:
      1. Signature header exists
      2. Timestamp header exists and is fresh (within 30s)
      3. Signature matches the payload
    """
    signature = request.headers.get('X-Signature')
    timestamp  = request.headers.get('X-Timestamp')

    if not signature or not timestamp:
        return False

    # Reject stale requests
    try:
        request_time = int(timestamp)
    except ValueError:
        return False

    if abs(time.time() - request_time) > TIMESTAMP_TOLERANCE:
        return False

    # Recompute signature from body
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = {}

    expected  = sign_payload(body, timestamp)
    return hmac.compare_digest(expected, signature)


class RequestSigningMiddleware:
    """
    AOP Middleware — verifies HMAC signature on sensitive endpoints.
    Only enforced on auth endpoints (login, change-password).
    All other endpoints are unaffected.
    """
    SIGNED_PATHS = [
        '/api/accounts/auth/login/',
        '/api/accounts/auth/change-password/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path in self.SIGNED_PATHS:
            if not verify_signature(request):
                return JsonResponse(
                    {
                        'detail': 'Invalid or missing request signature.',
                        'code'  : 'invalid_signature',
                    },
                    status=400,
                )
        return self.get_response(request)