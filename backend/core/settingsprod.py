from pathlib import Path
from environ import Env

import os
from datetime import timedelta
import platform

from celery.schedules import crontab
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# Load .env from core/ so it works regardless of CWD (e.g. gunicorn from project root)
# load_dotenv(BASE_DIR / "core" / ".env")
# load_dotenv()  # Also allow CWD .env override

env = Env()
env.read_env(BASE_DIR / ".env")
# core/.env: machine-local DB/password etc. Must overwrite BASE_DIR/.env keys (defaults overwrite=False).
env.read_env(Path(__file__).resolve().parent / ".env", overwrite=True)


ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "") or os.getenv("SECRET_KEY", "")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = ENVIRONMENT == "development"

#! picks the domain that railway provides
# site_domain = env("SITE_DOMAIN", default="")

ALLOWED_HOSTS = [
    "localhost",
    ".localhost",
    "127.0.0.1",
    "localhost",
    "127.0.0.1",
    "[::1]",
    "*",
    "zentroapp-api.uncodedsolutions.com",
    "*.zentroapp-api.uncodedsolutions.com",
    # site_domain,
]

CSRF_TRUSTED_ORIGINS = [
    # "https://backend-production-42041.up.railway.app",
    "https://zentroapp.uncodedsolutions.com",
    "https://*.zentroapp.uncodedsolutions.com",
    "http://localhost:8000",
    "https://zentroapp-api.uncodedsolutions.com",
    "https://*.zentroapp-api.uncodedsolutions.com",
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # f"https://{site_domain}",
]


# Application definition

SHARED_APPS = [
    "anymail",
    "django_tenants",  #! Third Party app mandatory
    # auth + authentication + permissions must be shared because company
    # (SHARED) FKs to CustomUser, and UserGroup M2M needs permissions.
    # django.contrib.admin stays TENANT-only (avoids public admin LogEntry FKs).
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    #! Third party apps
    "admin_searchable_dropdown",
    "widget_tweaks",
    "django_htmx",
    "django.contrib.humanize",  # ? for humanize numbers in templates (1,000,000)
    "django_select2",
    "mptt",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "rest_framework_simplejwt",
    "django_celery_results",
    "django_celery_beat",
    #! Custom apps
    "dimension",
    "permissions",
    "pages",  # authentication.ApplicationProfile FKs to pages.Page
    "authentication",
    "company",
    "home",
    "setup",
    "common",
    "base",  # Objects and ObjectTypes (shared registry)
    "app_updates",
    # "postings",
]

TENANT_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    #! Custom apps
    "permissions",  # Permission system - tenant-specific so each company can manage their own
    "dimension",
    "authentication",
    "home",
    "financials",
    "sales",
    "items",
    "settings",
    "setup",
    "config_packages",
    "postings",
    "purchases",
    "payments",
    "expenses",
    "reports",
    "resources",  # Resources Management for service-based businesses
    "production",
    "bank_account",
    "prepayment",
    "loans",
    "hotel_management",
    "restaurant_management",
    "sync",
    "receipt_templates",
]

# INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]
INSTALLED_APPS = list(set(SHARED_APPS + TENANT_APPS))

MIDDLEWARE = [
    "utils.tenant_middleware.TenantJWTMiddleware",  # Resolve tenant from JWT when no subdomain
    "django_tenants.middleware.main.TenantMainMiddleware",  # ? Third party middleware for multi-tenancy
    "corsheaders.middleware.CorsMiddleware",  # Cors - MUST be before SubscriptionCheckMiddleware so 402 gets CORS headers
    "utils.subscription_middleware.SubscriptionCheckMiddleware",  # Block expired trials/subscriptions
    "utils.middleware.ModuleContextMiddleware",  # Inject request.enabled_modules & request.has_module()
    "django_htmx.middleware.HtmxMiddleware",  # ? Third party middleware for htmx
    "whitenoise.middleware.WhiteNoiseMiddleware",  # ? Third Party middleware for static files
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "utils.sentry_middleware.SentryTenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.getenv("DB_NAME_PROD", ""),
        "USER": os.getenv("DB_USER_PROD", ""),
        "PASSWORD": os.getenv("DB_PASSWORD_PROD", ""),
        "HOST": os.getenv("DB_HOST_PROD", ""),
        "PORT": "5432",
    }
}


# ------------------- End of Database -------------------


# ------------------- Tenant Configuration -------------------
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

TENANT_MODEL = "company.Company"
TENANT_DOMAIN_MODEL = "company.Domain"

SHOW_PUBLIC_IF_NO_TENANT_FOUND = True
ROOT_URLCONF = "core.urls"
PUBLIC_SCHEMA_URLCONF = "core.urls-public"

DOMAIN = "zentroapp.uncodedsolutions.com"
BACKEND_DOMAIN = "zentroapp-api.uncodedsolutions.com"
# ------------------- End of Tenant Configuration -------------------


# ------------------- AWS Configuration -------------------
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = "zentroapp-bucket"
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
AWS_S3_FILE_OVERWRITE = False
AWS_LOCATION = "media"
AWS_S3_REGION_NAME = "sa-east-1"

AWS_S3_VERIFY = True  # Set to False if you're having SSL verification issues
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_S3_ADDRESSING_STYLE = "virtual"

AWS_S3_SIGNATURE_VERSION = "s3v4"  # Use signature version 4
AWS_DEFAULT_ACL = None  # Let your bucket's ACL handle permissions

# Retry configuration
AWS_S3_MAX_RETRY_DELAY = 30
AWS_S3_NUM_RETRIES = 3

# Timeout settings
AWS_S3_CONNECT_TIMEOUT = 5  # Connection timeout in seconds
AWS_S3_READ_TIMEOUT = 15  # Read timeout in seconds

# ------------------- End of AWS Configuration -------------------


# ------------------- FILE STORAGE -------------------

if ENVIRONMENT == "production":

    STORAGES = {
        "default": {
            "BACKEND": "core.storage.CustomSchemaStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

else:
    STORAGES = {
        "default": {
            # "BACKEND": "utils.storage.CustomSchemaStorage",
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
        },
    }


# ------------------- End of FILE STORAGE -------------------


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Kampala"

USE_I18N = True

USE_TZ = True


# ------------------- STATIC FILES -------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MULTITENANT_RELATIVE_MEDIA_ROOT = "tenants/%s"
APP_LANDING_PAGE_URL = "https://zentroapp.uncodedsolutions.com/landing"

# Make sure temp directory exists
TEMP_UPLOAD_DIR = os.path.join(MEDIA_ROOT, "temp")
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

# Static files configuration for production
# if not DEBUG:
# Configure your storage backend
# DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
# ... other storage settings ...

# For development
if DEBUG:
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True

# if DEBUG:
# STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# ------------------- End of STATIC FILES -------------------

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------- REST FRAMEWORK -------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "authentication.authentication.CustomJWTAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_PAGINATION_CLASS": "utils.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_THROTTLE_RATES": {
        "login_pin": "60/min",
    },
}
# ------------------- End of REST FRAMEWORK -------------------

# ------------------- SIMPLE JWT -------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": "",
    "AUDIENCE": None,
    "ISSUER": None,
    "JSON_ENCODER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
    "TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSerializer",
    "TOKEN_VERIFY_SERIALIZER": "rest_framework_simplejwt.serializers.TokenVerifySerializer",
    "TOKEN_BLACKLIST_SERIALIZER": "rest_framework_simplejwt.serializers.TokenBlacklistSerializer",
    "SLIDING_TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainSlidingSerializer",
    "SLIDING_TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSlidingSerializer",
}
# ------------------- End of SIMPLE JWT -------------------


# --------------------  START Stripe  --------------------
STRIPE_SECRET_KEY_TEST = os.getenv("STRIPE_SECRET_KEY_TEST", "")
STRIPE_PUBLISHABLE_KEY_TEST = os.getenv("STRIPE_PUBLISHABLE_KEY_TEST", "")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
# --------------------  END Stripe  --------------------


# -------------------- EMAIL (Mailtrap Transactional Send API - same as scripts/send-mailtrap-curl.sh) --------------------
# POST https://send.api.mailtrap.io/api/send with Bearer token. Real inbox delivery (no sandbox).
# Token from .env: EMAIL_HOST_API_KEY or MAILTRAP_API_TOKEN.
_MAILTRAP_TOKEN = (
    os.getenv("EMAIL_HOST_API_KEY") or os.getenv("MAILTRAP_API_TOKEN") or ""
).strip()

if _MAILTRAP_TOKEN:
    EMAIL_BACKEND = "core.email_backends.MailtrapSendAPIBackend"
    MAILTRAP_SEND_API_KEY = _MAILTRAP_TOKEN
else:
    EMAIL_BACKEND = "core.email_backends.MailtrapEmailBackend"
    EMAIL_HOST = os.getenv(
        "PROD_EMAIL_HOST", os.getenv("EMAIL_HOST", "sandbox.smtp.mailtrap.io")
    )
    EMAIL_HOST_USER = os.getenv(
        "PROD_EMAIL_HOST_USER", os.getenv("EMAIL_HOST_USER", "")
    )
    EMAIL_HOST_PASSWORD = os.getenv(
        "PROD_EMAIL_HOST_PASSWORD", os.getenv("EMAIL_HOST_PASSWORD", "")
    )
    EMAIL_PORT = int(os.getenv("PROD_EMAIL_PORT", os.getenv("EMAIL_PORT", "587")))
    EMAIL_USE_TLS = True
    EMAIL_USE_SSL = False

DEFAULT_FROM_EMAIL = os.getenv(
    "PROD_DEFAULT_FROM_EMAIL",
    os.getenv("DEFAULT_FROM_EMAIL", "noreply@zentroapp.app"),
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# --------------------  END EMAIL  --------------------

FIREBASE_CREDENTIALS_PATH = env("FIREBASE_CREDENTIALS_PATH", default="")
FIREBASE_CREDENTIALS_JSON = env("FIREBASE_CREDENTIALS_JSON", default="")


# --------------------  CUSTOM USER MODEL  --------------------
AUTH_USER_MODEL = "authentication.CustomUser"

# --------------------  END CUSTOM USER MODEL  --------------------


# -------------------- REDIS CACHING --------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "zentro_cache",
        "TIMEOUT": 300,
        "OPTIONS": {
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
            "retry_on_timeout": True,
        },
    }
}


# -------------------- CELERY --------------------
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_EXTENDED = True

# -------------------- new celery settings --------------------
# Additional Celery settings for better task handling
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

# Task state update settings
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_IGNORE_RESULT = False

# Worker settings
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Result backend settings
CELERY_RESULT_EXPIRES = 3600  # 1 hour
CELERY_RESULT_PERSISTENT = True

# Windows-specific settings for solo pool
if platform.system() == "Windows":
    # Windows only; on Linux use prefork + concurrency (see docs/COMPANY_CREATION_PERFORMANCE.md).
    CELERY_WORKER_POOL = "solo"
    CELERY_WORKER_CONCURRENCY = 1
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    CELERY_TASK_SOFT_TIME_LIMIT = 600  # 10 minutes
    CELERY_TASK_TIME_LIMIT = 1200  # 20 minutes

CELERY_BEAT_SCHEDULE = {
    "database-backup-daily-utc": {
        "task": "base.tasks.database_backup_task",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {"tier": "daily"},
    },
    "database-backup-weekly-utc": {
        "task": "base.tasks.database_backup_task",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
        "kwargs": {"tier": "weekly"},
    },
}

# --------------------  END CELERY  --------------------


# Add these settings for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# LOGIN_URL = "authentication:login"  # URL where users will be redirected to log in
# LOGIN_REDIRECT_URL = "home:dashboard"  # URL to redirect after successful login
# LOGOUT_REDIRECT_URL = "authentication:login"

# LOGIN_EXEMPT_URLS = [
#     'authentication:login',
#     'authentication:register',
#     'authentication:password_reset',
#     'authentication:password_reset_done',
#     'authentication:password_reset_confirm',
#     'authentication:password_reset_complete',
#     # Add other URLs that should be accessible without login
# ]

# Production security settings
if ENVIRONMENT == "production":
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Add these settings after your ALLOWED_HOSTS configuration

CORS_ALLOWED_ORIGINS = [
    "https://zentroapp.uncodedsolutions.com",
    "https://www.zentroapp.uncodedsolutions.com",
    "https://zentroapp-api.uncodedsolutions.com",
    "https://*.zentroapp-api.uncodedsolutions.com",
    "http://localhost:5173",  # React development server
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5174",  # React development server
    "http://localhost:3000",
    "http://127.0.0.1:5174",
    "http://*.localhost:5173",
    "http://*.localhost:5174",
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://zentroapp\.uncodedsolutions\.com$",
    r"^https://www\.zentroapp\.uncodedsolutions\.com$",
    r"^https://([a-zA-Z0-9-]+)\.zentroapp\.uncodedsolutions\.com$",
]

CORS_ALLOW_CREDENTIALS = True

# Optional: If you need more specific CORS settings
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-branch-id",
    "x-csrftoken",
    "x-requested-with",
]

# If you're in development and want to allow all origins (not recommended for production)
if ENVIRONMENT == "development":
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_PRIVATE_NETWORK = True

# --------------------  SENTRY  --------------------
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

_sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", ENVIRONMENT),
        send_default_pii=True,
        integrations=[DjangoIntegration(), CeleryIntegration()],
    )
