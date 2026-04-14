# apps/accounts/signing.py
import hmac
import hashlib
import json
import time
import logging

from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)

def verify_signature(request) -> bool:
    signature = request.META.get('HTTP_X_SIGNATURE', '')
    timestamp = request.META.get('HTTP_X_TIMESTAMP', '')
    secret = getattr(settings, 'REQUEST_SIGNING_SECRET', '')

    if not signature or not timestamp or not secret:
        return False

    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except (ValueError, TypeError):
        return False

    try:
        # Crucial Fix: Access request.body safely. 
        # Django caches this after first access.
        body_content = request.body
        if not body_content:
            body_content = b'{}'
            
        # Parse and re-serialize to match Angular's byte-identical format
        body_json = json.loads(body_content)
        sorted_body = json.dumps(body_json, sort_keys=True, separators=(',', ':'))
        
        message = f'{timestamp}.{sorted_body}'.encode('utf-8')
        expected = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error(f"Signature verification crash: {e}")
        return False

class RequestSigningMiddleware:
    SIGNED_PATHS = [
        '/api/accounts/auth/login/',
        '/api/accounts/auth/change-password/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path in self.SIGNED_PATHS:
            # Allow skipping in DEBUG if headers are totally missing
            if settings.DEBUG and not request.META.get('HTTP_X_SIGNATURE'):
                return self.get_response(request)
            
            if not verify_signature(request):
                return JsonResponse(
                    {'detail': 'Invalid request signature.', 'code': 'invalid_signature'},
                    status=403
                )
        return self.get_response(request)