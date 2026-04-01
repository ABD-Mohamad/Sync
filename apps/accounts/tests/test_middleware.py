# apps/accounts/tests/test_middleware.py
import pytest
from rest_framework.test import APIClient

from apps.accounts.tokens import get_tokens_for_user, get_tokens_for_employee
from apps.accounts.tests.conftest import UserFactory, EmployeeFactory
from apps.accounts.models import Role


# ─── Constants ────────────────────────────────────────────────────────────────

PROTECTED_URL = '/api/accounts/users/'

EXEMPT_URLS = [
    '/api/accounts/auth/login/',
    '/api/accounts/auth/refresh/',
    '/api/accounts/auth/change-password/',
    '/api/schema/',
    '/api/docs/',
    '/api/redoc/',
    '/admin/',
]

EXPECTED_CODE = 'password_change_required'


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_code(response):
    """
    Safely extracts the error code from a response.
    Returns None if the response is not JSON (e.g. HTML pages like /admin/, /docs/).
    """
    if 'application/json' in response.get('Content-Type', ''):
        return response.json().get('code')
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Django User — must_change_password checks
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestForcePasswordChangeMiddlewareForUsers:

    @pytest.fixture
    def forced_user(self, db, it_role):
        return UserFactory(role=it_role, must_change_password=True)

    @pytest.fixture
    def normal_user(self, db, it_role):
        return UserFactory(role=it_role, must_change_password=False)

    # ── Blocked scenarios ────────────────────────────────────────────────────

    def test_user_with_flag_is_blocked(self, forced_user):
        client = APIClient()
        tokens = get_tokens_for_user(forced_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(PROTECTED_URL)

        assert response.status_code == 403

    def test_blocked_response_has_correct_error_code(self, forced_user):
        client = APIClient()
        tokens = get_tokens_for_user(forced_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(PROTECTED_URL)

        assert _get_code(response) == EXPECTED_CODE

    def test_blocked_response_has_descriptive_detail(self, forced_user):
        client = APIClient()
        tokens = get_tokens_for_user(forced_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(PROTECTED_URL)

        assert 'detail' in response.json()
        assert len(response.json()['detail']) > 0

    def test_user_blocks_all_http_methods(self, forced_user):
        client = APIClient()
        tokens = get_tokens_for_user(forced_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        for method in ('get', 'post', 'put', 'patch', 'delete'):
            response = getattr(client, method)(PROTECTED_URL)
            assert response.status_code == 403, (
                f'Expected 403 for {method.upper()} but got {response.status_code}'
            )

    # ── Allowed scenarios ────────────────────────────────────────────────────

    def test_normal_user_is_not_blocked(self, normal_user):
        client = APIClient()
        tokens = get_tokens_for_user(normal_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(PROTECTED_URL)

        assert _get_code(response) != EXPECTED_CODE

    def test_unauthenticated_request_is_not_blocked_by_middleware(self):
        client = APIClient()
        response = client.get(PROTECTED_URL)

        assert _get_code(response) != EXPECTED_CODE

    # ── Exempt path passthrough ──────────────────────────────────────────────

    @pytest.mark.parametrize('url', EXEMPT_URLS)
    def test_exempt_path_not_blocked_for_forced_user(self, forced_user, url):
        client = APIClient()
        tokens = get_tokens_for_user(forced_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(url)

        assert _get_code(response) != EXPECTED_CODE, (
            f'Middleware incorrectly blocked exempt path: {url}'
        )

    def test_change_password_post_not_blocked_for_forced_user(self, forced_user):
        client = APIClient()
        tokens = get_tokens_for_user(forced_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.post(
            '/api/accounts/auth/change-password/',
            data={},
            format='json',
        )

        assert _get_code(response) != EXPECTED_CODE


# ═══════════════════════════════════════════════════════════════════════════════
# Employee — must_change_password checks (JWT payload path)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestForcePasswordChangeMiddlewareForEmployees:

    @pytest.fixture
    def forced_employee(self, db):
        return EmployeeFactory(must_change_password=True)

    @pytest.fixture
    def normal_employee(self, db):
        return EmployeeFactory(must_change_password=False)

    # ── Blocked scenarios ────────────────────────────────────────────────────

    def test_employee_with_flag_is_blocked(self, forced_employee):
        client = APIClient()
        tokens = get_tokens_for_employee(forced_employee)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(PROTECTED_URL)

        assert response.status_code == 403

    def test_employee_blocked_response_has_correct_code(self, forced_employee):
        client = APIClient()
        tokens = get_tokens_for_employee(forced_employee)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(PROTECTED_URL)

        assert _get_code(response) == EXPECTED_CODE

    # ── Allowed scenarios ────────────────────────────────────────────────────

    def test_normal_employee_is_not_blocked(self, normal_employee):
        client = APIClient()
        tokens = get_tokens_for_employee(normal_employee)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(PROTECTED_URL)

        assert _get_code(response) != EXPECTED_CODE

    # ── Exempt path passthrough ──────────────────────────────────────────────

    @pytest.mark.parametrize('url', EXEMPT_URLS)
    def test_exempt_path_not_blocked_for_forced_employee(self, forced_employee, url):
        client = APIClient()
        tokens = get_tokens_for_employee(forced_employee)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(url)

        assert _get_code(response) != EXPECTED_CODE, (
            f'Middleware incorrectly blocked exempt path: {url}'
        )

    def test_cookie_path_not_checked_for_employee(self, forced_employee):
        """
        A forced employee token in a cookie alone (no Authorization header)
        must not trigger the block — avoids false-positives on anonymous requests.
        """
        client = APIClient()
        tokens = get_tokens_for_employee(forced_employee)
        client.cookies['access_token'] = tokens['access']

        response = client.get(PROTECTED_URL)

        assert _get_code(response) != EXPECTED_CODE


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMiddlewareEdgeCases:

    def test_malformed_bearer_token_does_not_crash_middleware(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer not.a.jwt')

        response = client.get(PROTECTED_URL)

        assert response.status_code in (400, 401, 403)
        assert _get_code(response) != EXPECTED_CODE

    def test_flag_reset_to_false_allows_access(self, it_role):
        user = UserFactory(role=it_role, must_change_password=True)
        user.must_change_password = False
        user.save()

        # Re-issue token AFTER the flag is cleared so the token payload reflects False
        from apps.accounts.tokens import get_tokens_for_user
        tokens = get_tokens_for_user(user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        response = client.get(PROTECTED_URL)

        assert _get_code(response) != EXPECTED_CODE