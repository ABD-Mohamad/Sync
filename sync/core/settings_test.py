# core/settings_test.py
"""
Test-specific Django settings.

Inherits everything from the production settings and overrides only
what is necessary to run tests without external services:
  - SQLite in-memory database   (no PostgreSQL needed)
  - Dummy cache backend          (no Redis needed)
  - Dummy email backend          (no Mailpit needed)
  - Dummy S3 storage             (no Supabase/S3 needed)
  - Dummy signing secret
  - Disabled throttling          (keeps tests fast and deterministic)
"""
import os
from datetime import timedelta

# ── Provide required env vars before importing the base settings ──────────────
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver')
os.environ.setdefault('DB_NAME', 'test_db')
os.environ.setdefault('DB_USER', 'test_user')
os.environ.setdefault('DB_PASSWORD', 'test_pass')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('REQUEST_SIGNING_SECRET', 'test-signing-secret-32-chars-long')
os.environ.setdefault('SUPABASE_ACCESS_KEY_ID', 'dummy-access-key')
os.environ.setdefault('SUPABASE_SECRET_ACCESS_KEY', 'dummy-secret-key')
os.environ.setdefault('SUPABASE_BUCKET_NAME', 'dummy-bucket')
os.environ.setdefault('SUPABASE_ENDPOINT_URL', 'https://dummy.supabase.co/storage/v1')
os.environ.setdefault('SUPABASE_REGION', 'ap-southeast-1')

# ── Base settings ─────────────────────────────────────────────────────────────
from core.settings import *  # noqa: F401, F403, E402

# ── Database — SQLite in-memory (fast, no external service) ───────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME':   ':memory:',
    }
}

# ── Cache — in-memory dummy (no Redis) ───────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ── Email — captured in memory, never sent ────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# ── Storage — in-memory file system (no S3 / Supabase calls) ─────────────────
DEFAULT_FILE_STORAGE = 'django.core.files.storage.InMemoryStorage'

# ── Signing secret (deterministic for tests) ──────────────────────────────────
REQUEST_SIGNING_SECRET = os.environ['REQUEST_SIGNING_SECRET']

# ── Throttling — disable globally so tests are not rate-limited ───────────────
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'login'    : '10000/minute',   # effectively unlimited in tests
    'sensitive': '10000/minute',
}

# ── Password hashing — use the fastest hasher in tests ───────────────────────
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# ── JWT — short lifetimes to keep token-expiry tests fast ────────────────────
SIMPLE_JWT.update({                                       # noqa: F405
    'ACCESS_TOKEN_LIFETIME' : timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=10),
    'ROTATE_REFRESH_TOKENS' : True,
})

# ── Cookie settings ───────────────────────────────────────────────────────────
COOKIE_SECURE  = False   # HTTPS not available in test runner
COOKIE_SAMESITE = 'Lax'

# ── Media ─────────────────────────────────────────────────────────────────────
MEDIA_ROOT = '/tmp/sync_test_media'

SESSION_INACTIVITY_TIMEOUT = 60 * 60 * 24