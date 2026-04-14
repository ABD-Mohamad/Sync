# apps/notifications/fcm_utils.py
#

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Firebase Admin SDK initialisation ────────────────────────────────────────

_firebase_app = None


def _get_firebase_app():
    """
    Lazy-initialises the Firebase Admin SDK app exactly once.
    Skips initialisation if FIREBASE_CREDENTIALS_PATH is not configured
    (prevents crashes in CI / development environments without credentials).
    """
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials
        from django.conf import settings

        cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
        if not cred_path:
            logger.warning(
                '[FCM] FIREBASE_CREDENTIALS_PATH not set in settings.py. '
                'FCM notifications will be silently skipped.'
            )
            return None

        if not firebase_admin._apps:
            cred      = credentials.Certificate(str(cred_path))
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            _firebase_app = firebase_admin.get_app()

        return _firebase_app

    except ImportError:
        logger.error(
            '[FCM] firebase-admin is not installed. '
            'Run: pip install firebase-admin'
        )
        return None
    except Exception as exc:
        logger.error('[FCM] Firebase initialisation failed: %s', exc)
        return None


# ── Core send function ────────────────────────────────────────────────────────

def _send_fcm_message(
    token   : str,
    title   : str,
    body    : str,
    data    : Optional[dict] = None,
) -> bool:
    """
    Low-level: sends a single FCM Web Push message to one browser token.

    Returns True on success, False on any error.
    Token validation errors (invalid / expired) are logged as warnings —
    callers should clear the stale token from the DB.
    """
    if not token or not token.strip():
        return False

    app = _get_firebase_app()
    if app is None:
        return False

    try:
        from firebase_admin import messaging

        message = messaging.Message(
            notification = messaging.Notification(title=title, body=body),
            data         = {k: str(v) for k, v in (data or {}).items()},
            token        = token,
            webpush      = messaging.WebpushConfig(
                notification = messaging.WebpushNotification(
                    title = title,
                    body  = body,
                    icon  = '/icons/icon-192x192.png',   # adjust to your PWA icon path
                    badge = '/icons/badge-72x72.png',
                ),
                fcm_options = messaging.WebpushFCMOptions(
                    link = data.get('link', '/') if data else '/',
                ),
            ),
        )
        messaging.send(message)
        logger.info('[FCM] Sent to token …%s | "%s"', token[-8:], title)
        return True

    except Exception as exc:
        err_str = str(exc)
        if 'UNREGISTERED' in err_str or 'INVALID_ARGUMENT' in err_str:
            logger.warning('[FCM] Stale token …%s — mark for deletion.', token[-8:])
        else:
            logger.error('[FCM] Send failed: %s', exc)
        return False


# ── Public helpers ────────────────────────────────────────────────────────────

def send_fcm_to_user(user, title: str, body: str, data: Optional[dict] = None) -> bool:
    """
    Send an FCM Web Push notification to a User (DH / IT Manager).

    `user` must be an accounts.User instance.
    The user must have a valid fcm_token stored in user.fcm_token.
    """
    token = getattr(user, 'fcm_token', None)
    if not token:
        logger.debug('[FCM] User %s has no fcm_token — skipping.', user.id)
        return False
    return _send_fcm_message(token, title, body, data)


def send_fcm_to_employee(employee, title: str, body: str, data: Optional[dict] = None) -> bool:
    """
    Send an FCM Web Push notification to an Employee.

    `employee` must be an accounts.Employee instance.
    The employee must have a valid fcm_token stored in employee.fcm_token.
    """
    token = getattr(employee, 'fcm_token', None)
    if not token:
        logger.debug('[FCM] Employee %s has no fcm_token — skipping.', employee.id)
        return False
    return _send_fcm_message(token, title, body, data)


def send_fcm_to_tokens(
    tokens  : list[str],
    title   : str,
    body    : str,
    data    : Optional[dict] = None,
) -> dict:
    """
    Multicast: send the same notification to a list of FCM tokens.
    Returns a dict { 'success': int, 'failure': int }.
    """
    if not tokens:
        return {'success': 0, 'failure': 0}

    app = _get_firebase_app()
    if app is None:
        return {'success': 0, 'failure': len(tokens)}

    try:
        from firebase_admin import messaging

        clean_tokens = [t for t in tokens if t and t.strip()]
        if not clean_tokens:
            return {'success': 0, 'failure': 0}

        message = messaging.MulticastMessage(
            notification = messaging.Notification(title=title, body=body),
            data         = {k: str(v) for k, v in (data or {}).items()},
            tokens       = clean_tokens,
            webpush      = messaging.WebpushConfig(
                notification = messaging.WebpushNotification(
                    title = title,
                    body  = body,
                    icon  = '/icons/icon-192x192.png',
                ),
            ),
        )
        response = messaging.send_each_for_multicast(message)
        logger.info(
            '[FCM] Multicast: %d success / %d failure for %d tokens.',
            response.success_count, response.failure_count, len(clean_tokens),
        )
        return {
            'success': response.success_count,
            'failure': response.failure_count,
        }

    except Exception as exc:
        logger.error('[FCM] Multicast failed: %s', exc)
        return {'success': 0, 'failure': len(tokens)}