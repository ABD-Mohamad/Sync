# sync/core/settings.py
from pathlib import Path
from decouple import config
 
BASE_DIR = Path(__file__).resolve().parent.parent
 
# ─── Security ────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')
 
# ─── Applications ────────────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
 
THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'django_celery_beat',
    'django_celery_results',
    'drf_spectacular',
    'rest_framework_simplejwt.token_blacklist',
]
 
LOCAL_APPS = [
    'apps.accounts',
    'apps.tasks',
]
 
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
 
# ─── Middleware ───────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.accounts.middleware.ForcePasswordChangeMiddleware',  
]
 
ROOT_URLCONF = 'core.urls'
 
TEMPLATES = [
    {'BACKEND': 'django.template.backends.django.DjangoTemplates',
     'DIRS': [BASE_DIR / 'templates'],
     'APP_DIRS': True,
     'OPTIONS': {'context_processors': [
         'django.template.context_processors.debug',
         'django.template.context_processors.request',
         'django.contrib.auth.context_processors.auth',
         'django.contrib.messages.context_processors.messages',
     ]},},
]
 
WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'
 
# ─── Database (PostgreSQL) ────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':     config('DB_NAME'),
        'USER':     config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST':     config('DB_HOST', default='db'),
        'PORT':     config('DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
 
# ─── Cache (Redis) ────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://redis:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 300,
    }
}
 
# ─── Celery Configuration ─────────────────────────────────
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/1')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Riyadh'   # ← adjust to your timezone
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
 
# ─── Auth & Password ──────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
 
# ─── DRF & JWT ────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.accounts.authentication.EmployeeJWTAuthentication',
        'apps.accounts.authentication.UnifiedJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

    # ── Throttling ────────────────────────────────────────────
    'DEFAULT_THROTTLE_CLASSES': [],   # applied per-view, not globally
    'DEFAULT_THROTTLE_RATES': {
        'login'    : '5/minute',   # max 5 login attempts per minute per IP
        'sensitive': '10/minute',  # max 10 change-password attempts per minute
    },
}
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}
 
# ─── CORS ─────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',   # React/Vue frontend dev server
    'http://localhost:5173',   # Vite dev server
]
 
# ─── Internationalization ─────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Riyadh'    # ← adjust to your timezone
USE_I18N = True
USE_TZ = True
 
# ─── Static & Media Files ─────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'
 
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'

# ─── Email (Mailpit in dev) ───────────────────────────
EMAIL_BACKEND   = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST      = config('EMAIL_HOST', default='mailpit')
EMAIL_PORT      = config('EMAIL_PORT', default=1025, cast=int)
EMAIL_USE_TLS   = False
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
DEFAULT_FROM_EMAIL = 'Sync System <no-reply@sync.com>'

# ─── Swagger (drf-spectacular) ────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE'                  : 'Sync API',
    'DESCRIPTION'            : 'Task Management System API',
    'VERSION'                : '1.0.0',
    'SERVE_INCLUDE_SCHEMA'   : False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS'    : {
        'persistAuthorization': True,
    },
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type'        : 'http',
                'scheme'      : 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
    'SECURITY': [{'BearerAuth': []}],
}