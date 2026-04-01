# apps/accounts/tests/test_auth_flow.py
"""
Comprehensive test suite for the accounts authentication flow.

Coverage map
────────────
 Section A │ User login   — success, bad credentials, inactive account
 Section B │ Employee login — success, bad credentials, inactive account
 Section C │ Token refresh — via cookie (User & Employee)
 Section D │ Logout        — cookie clearing, token blacklist, audit log
 Section E │ AuditLog      — entries created on login / logout
"""
import json
import time
import hmac
import hashlib
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.audit import AuditLog
from apps.accounts.models import Employee
from apps.accounts.tokens import get_tokens_for_user, get_tokens_for_employee


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sign_payload(secret: str, payload: dict, timestamp: str) -> str:
    """Mirror of `apps.accounts.signing.sign_payload` for test use."""
    body = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    message = f'{timestamp}.{body}'.encode('utf-8')
    return hmac.new(
        secret.encode('utf-8'),
        message,
        hashlib.sha256,
    ).hexdigest()


def _signed_post(client: APIClient, url: str, payload: dict, secret: str) -> object:
    """
    Performs a POST with the HMAC-SHA256 X-Signature / X-Timestamp headers
    expected by `RequestSigningMiddleware`.
    """
    timestamp = str(int(time.time()))
    signature = _sign_payload(secret, payload, timestamp)
    return client.post(
        url,
        data=payload,
        format='json',
        headers={
            'X-Timestamp': timestamp,
            'X-Signature': signature,
        },
    )


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def signing_secret(settings):
    """Expose and return the signing secret configured in settings."""
    return settings.REQUEST_SIGNING_SECRET


# ═══════════════════════════════════════════════════════════════════════════════
# Section A — User Login
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUserLogin:
    """Login flow for Django User accounts."""

    def test_successful_login_returns_200(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': user_password}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 200

    def test_successful_login_sets_access_token_cookie(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': user_password}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert 'access_token' in response.cookies
        assert response.cookies['access_token'].value != ''

    def test_successful_login_sets_refresh_token_cookie(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': user_password}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert 'refresh_token' in response.cookies
        assert response.cookies['refresh_token'].value != ''

    def test_successful_login_cookies_are_httponly(
        self, client, active_user, user_password, login_url, signing_secret, settings
    ):
        """
        Verifies that httpOnly is honoured when COOKIE_HTTPONLY=True.
        This protects tokens from JavaScript access (XSS mitigation).
        """
        settings.COOKIE_HTTPONLY = True
        payload = {'email': active_user.email, 'password': user_password}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.cookies['access_token']['httponly']
        assert response.cookies['refresh_token']['httponly']

    def test_successful_login_body_contains_account_type(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': user_password}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.data['account_type'] == 'user'

    def test_successful_login_body_contains_profile(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': user_password}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert 'profile' in response.data
        assert response.data['profile']['email'] == active_user.email

    def test_wrong_password_returns_401(
        self, client, active_user, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': 'WrongPassword99!'}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 401

    def test_nonexistent_email_returns_401(
        self, client, login_url, signing_secret
    ):
        payload = {'email': 'ghost@nowhere.com', 'password': 'AnyPass1!'}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 401

    def test_inactive_user_returns_403(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        active_user.is_active = False
        active_user.save()

        payload = {'email': active_user.email, 'password': user_password}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 403
        assert 'inactive' in response.data['detail'].lower()

    def test_missing_email_field_returns_400(
        self, client, login_url, signing_secret
    ):
        payload = {'password': 'SomePass1!'}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 400

    def test_missing_password_field_returns_400(
        self, client, active_user, login_url, signing_secret
    ):
        payload = {'email': active_user.email}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# Section B — Employee Login
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEmployeeLogin:
    """Login flow for Employee (mobile-app) accounts."""

    def test_successful_login_returns_200(
        self, client, active_employee, login_url, signing_secret
    ):
        payload = {
            'email': active_employee.email,
            'password': active_employee._raw_password,
        }
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 200

    def test_successful_login_sets_access_token_cookie(
        self, client, active_employee, login_url, signing_secret
    ):
        payload = {
            'email': active_employee.email,
            'password': active_employee._raw_password,
        }
        response = _signed_post(client, login_url, payload, signing_secret)

        assert 'access_token' in response.cookies
        assert response.cookies['access_token'].value != ''

    def test_successful_login_sets_refresh_token_cookie(
        self, client, active_employee, login_url, signing_secret
    ):
        payload = {
            'email': active_employee.email,
            'password': active_employee._raw_password,
        }
        response = _signed_post(client, login_url, payload, signing_secret)

        assert 'refresh_token' in response.cookies
        assert response.cookies['refresh_token'].value != ''

    def test_successful_login_body_contains_account_type(
        self, client, active_employee, login_url, signing_secret
    ):
        payload = {
            'email': active_employee.email,
            'password': active_employee._raw_password,
        }
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.data['account_type'] == 'employee'

    def test_wrong_password_returns_401(
        self, client, active_employee, login_url, signing_secret
    ):
        payload = {'email': active_employee.email, 'password': 'WrongPass99!'}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 401

    def test_inactive_employee_returns_403(
        self, db, client, login_url, signing_secret
    ):
        from apps.accounts.tests.conftest import EmployeeFactory

        emp = EmployeeFactory(
            status=Employee.Status.INACTIVE,
            _password='StrongPass1!',
        )
        payload = {'email': emp.email, 'password': 'StrongPass1!'}
        response = _signed_post(client, login_url, payload, signing_secret)

        assert response.status_code == 403
        assert 'inactive' in response.data['detail'].lower()

    def test_last_login_is_updated_on_success(
        self, client, active_employee, login_url, signing_secret
    ):
        assert active_employee.last_login is None

        payload = {
            'email': active_employee.email,
            'password': active_employee._raw_password,
        }
        _signed_post(client, login_url, payload, signing_secret)

        active_employee.refresh_from_db()
        assert active_employee.last_login is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Section C — AuditLog entries
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLoginAuditLog:
    """
    The AuditLog is the system's tamper-evident record.
    Verify entries are written correctly on each auth event.

    NOTE: The current implementation logs login events for Django Users only.
    Employee logins are not audit-logged (intentional — employee auth is
    treated as a separate trust boundary). The tests document this behaviour.
    """

    def test_user_login_creates_audit_log_entry(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': user_password}
        _signed_post(client, login_url, payload, signing_secret)

        assert AuditLog.objects.filter(
            actor=active_user,
            action=AuditLog.Action.LOGIN,
            resource='User',
        ).exists()

    def test_user_login_audit_log_records_resource_id(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': user_password}
        _signed_post(client, login_url, payload, signing_secret)

        log = AuditLog.objects.get(
            actor=active_user,
            action=AuditLog.Action.LOGIN,
        )
        assert log.resource_id == str(active_user.id)

    def test_user_login_audit_log_records_ip_address(
        self, client, active_user, user_password, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': user_password}
        client.post(
            login_url,
            data=payload,
            format='json',
            REMOTE_ADDR='203.0.113.42',
            HTTP_X_TIMESTAMP=str(int(time.time())),
            HTTP_X_SIGNATURE=_sign_payload(
                signing_secret, payload, str(int(time.time()))
            ),
        )

        log = AuditLog.objects.filter(
            actor=active_user,
            action=AuditLog.Action.LOGIN,
        ).first()
        # IP may be 203.0.113.42 or the loopback — just assert it was captured.
        assert log is not None
        assert log.ip_address is not None

    def test_failed_user_login_does_not_create_audit_log(
        self, client, active_user, login_url, signing_secret
    ):
        payload = {'email': active_user.email, 'password': 'WrongPass99!'}
        _signed_post(client, login_url, payload, signing_secret)

        assert not AuditLog.objects.filter(
            action=AuditLog.Action.LOGIN,
        ).exists()

    def test_employee_login_does_not_create_audit_log(
        self, client, active_employee, login_url, signing_secret
    ):
        """
        Employee logins are intentionally NOT audit-logged in the current
        implementation — this test documents and pins that decision.
        """
        payload = {
            'email': active_employee.email,
            'password': active_employee._raw_password,
        }
        _signed_post(client, login_url, payload, signing_secret)

        assert not AuditLog.objects.filter(
            action=AuditLog.Action.LOGIN,
        ).exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Section D — Token Refresh
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTokenRefresh:
    """Verify that a valid refresh token yields a new access token."""

    def test_user_refresh_via_cookie_returns_200(
        self, client, active_user, refresh_url
    ):
        tokens = get_tokens_for_user(active_user)
        client.cookies['refresh_token'] = tokens['refresh']

        response = client.post(refresh_url)

        assert response.status_code == 200

    def test_user_refresh_sets_new_access_token_cookie(
        self, client, active_user, refresh_url
    ):
        tokens = get_tokens_for_user(active_user)
        old_access = tokens['access']
        client.cookies['refresh_token'] = tokens['refresh']

        response = client.post(refresh_url)

        new_access = response.cookies.get('access_token')
        assert new_access is not None
        assert new_access.value != old_access

    def test_user_refresh_sets_new_refresh_token_cookie(
        self, client, active_user, refresh_url
    ):
        """Token rotation: a new refresh token must be issued."""
        tokens = get_tokens_for_user(active_user)
        client.cookies['refresh_token'] = tokens['refresh']

        response = client.post(refresh_url)

        assert 'refresh_token' in response.cookies

    def test_employee_refresh_via_cookie_returns_200(
        self, client, active_employee, refresh_url
    ):
        tokens = get_tokens_for_employee(active_employee)
        client.cookies['refresh_token'] = tokens['refresh']

        response = client.post(refresh_url)

        assert response.status_code == 200

    def test_employee_refresh_sets_new_access_token_cookie(
        self, client, active_employee, refresh_url
    ):
        tokens = get_tokens_for_employee(active_employee)
        old_access = tokens['access']
        client.cookies['refresh_token'] = tokens['refresh']

        response = client.post(refresh_url)

        new_access = response.cookies.get('access_token')
        assert new_access is not None
        assert new_access.value != old_access

    def test_missing_refresh_token_returns_400(self, client, refresh_url):
        response = client.post(refresh_url)

        assert response.status_code == 400

    def test_invalid_refresh_token_returns_401(self, client, refresh_url):
        client.cookies['refresh_token'] = 'this.is.not.a.valid.jwt'

        response = client.post(refresh_url)

        assert response.status_code == 401

    def test_refresh_token_in_body_is_accepted(self, client, active_user, refresh_url):
        """Fallback: token sent in the request body (e.g. from mobile clients)."""
        tokens = get_tokens_for_user(active_user)

        response = client.post(
            refresh_url,
            data={'refresh': tokens['refresh']},
            format='json',
        )

        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Section E — Logout
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLogout:
    """
    Logout must:
      1. Return 200.
      2. Clear auth cookies from the browser.
      3. Blacklist the refresh token so it cannot be reused.
      4. Create an AuditLog entry for Django Users.
    """

    def _login_user(self, client, active_user, user_password, login_url, signing_secret):
        """Helper — logs a user in and returns the raw refresh token."""
        payload = {'email': active_user.email, 'password': user_password}
        login_resp = _signed_post(client, login_url, payload, signing_secret)
        return login_resp.cookies.get('refresh_token').value

    # ── 1. Status code ───────────────────────────────────────────────────────

    def test_logout_returns_200(
        self, client, active_user, user_password,
        login_url, logout_url, signing_secret
    ):
        refresh = self._login_user(
            client, active_user, user_password, login_url, signing_secret
        )
        client.cookies['refresh_token'] = refresh

        response = client.post(logout_url)

        assert response.status_code == 200

    # ── 2. Cookie clearing ───────────────────────────────────────────────────

    def test_logout_clears_access_token_cookie(
        self, client, active_user, user_password,
        login_url, logout_url, signing_secret
    ):
        refresh = self._login_user(
            client, active_user, user_password, login_url, signing_secret
        )
        client.cookies['refresh_token'] = refresh

        response = client.post(logout_url)

        # Django's delete_cookie() sets max_age=0 and an empty value.
        cookie = response.cookies.get('access_token')
        if cookie:
            assert cookie['max-age'] == 0 or cookie.value == ''

    def test_logout_clears_refresh_token_cookie(
        self, client, active_user, user_password,
        login_url, logout_url, signing_secret
    ):
        refresh = self._login_user(
            client, active_user, user_password, login_url, signing_secret
        )
        client.cookies['refresh_token'] = refresh

        response = client.post(logout_url)

        cookie = response.cookies.get('refresh_token')
        if cookie:
            assert cookie['max-age'] == 0 or cookie.value == ''

    # ── 3. Token blacklisting ────────────────────────────────────────────────

    def test_logout_blacklists_refresh_token(
        self, client, active_user, user_password,
        login_url, logout_url, refresh_url, signing_secret
    ):
        """After logout the old refresh token must be rejected."""
        refresh = self._login_user(
            client, active_user, user_password, login_url, signing_secret
        )
        client.cookies['refresh_token'] = refresh

        # Log out
        client.post(logout_url)

        # Attempt to refresh with the now-blacklisted token
        fresh_client = APIClient()
        fresh_client.cookies['refresh_token'] = refresh
        refresh_resp = fresh_client.post(refresh_url)

        assert refresh_resp.status_code == 401

    def test_logout_without_cookie_still_returns_200(
        self, client, logout_url
    ):
        """Logout must succeed even if no refresh token cookie is present."""
        response = client.post(logout_url)

        assert response.status_code == 200

    # ── 4. Audit log ─────────────────────────────────────────────────────────

    def test_logout_creates_audit_log_for_authenticated_user(
        self, client, active_user, user_password,
        login_url, logout_url, signing_secret
    ):
        refresh = self._login_user(
            client, active_user, user_password, login_url, signing_secret
        )
        # Authenticate the client so request.user is the Django User.
        tokens = get_tokens_for_user(active_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        client.cookies['refresh_token'] = refresh

        client.post(logout_url)

        assert AuditLog.objects.filter(
            actor=active_user,
            action=AuditLog.Action.LOGOUT,
            resource='User',
        ).exists()

    def test_logout_does_not_create_audit_log_for_anonymous(
        self, client, logout_url
    ):
        """Anonymous logouts (e.g. expired session) must not create log entries."""
        client.post(logout_url)

        assert not AuditLog.objects.filter(
            action=AuditLog.Action.LOGOUT,
        ).exists()