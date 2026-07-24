from pathlib import Path
from environ import Env

import os
from datetime import timedelta
import platform

from celery.schedules import crontab

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

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
    "backend-production-42041.up.railway.app",
    "localhost",
    ".localhost",
    "127.0.0.1",
    "localhost",
    "127.0.0.1",
    "[::1]",
    "zentroapp.app",
    ".zentroapp.app",
    "zentroapp-backend.com",
    "*.zentroapp-backend.com",
    "*",
    # site_domain,
]

CSRF_TRUSTED_ORIGINS = [
    # "https://backend-production-42041.up.railway.app",
    "https://zentroapp.app",
    "https://*.zentroapp.app",
    "http://localhost:8000",
    "http://localhost:8002",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8002",
    "https://zentroapp-backend.com",
    "https://*.zentroapp-backend.com",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://*.localhost:5173",
    "http://*.localhost:5174",
    "http://localhost:5123",
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
    "reports",  # Reporting Module - Daily, Weekly, Monthly reports
    "resources",  # Resources Management for service-based businesses
    "production",  # Production BOM Management for service-based businesses
    "prepayment",
    "bank_account",
    "hotel_management",
    "restaurant_management",
    "loans",
    "sync",
    "receipt_templates",
    "pages",
]

# INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]
INSTALLED_APPS = list(set(SHARED_APPS + TENANT_APPS))

# Django's test runner migrates only the public schema. TenantSyncRouter would
# skip TENANT_APPS there, so ORM tests fail with missing relations (e.g.
# items_location). Merge tenant apps into SHARED_APPS under manage.py test / CI
# so migrate creates a flat public schema suitable for TestCase.
import sys

if "test" in sys.argv or os.getenv("DJANGO_TEST_FLAT_SCHEMA", "").lower() in (
    "1",
    "true",
    "yes",
):
    SHARED_APPS = list(SHARED_APPS) + [
        app for app in TENANT_APPS if app not in SHARED_APPS
    ]
    INSTALLED_APPS = list(dict.fromkeys(SHARED_APPS + TENANT_APPS))

MIDDLEWARE = [
    "utils.tenant_middleware.TenantJWTMiddleware",  # Set tenant from JWT token for mobile apps
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


# ------------------- Database -------------------

if ENVIRONMENT == "development":
    DATABASES = {
        "default": {
            "ENGINE": "django_tenants.postgresql_backend",
            # "NAME": "zentro_dev",
            # "USER": "postgres",
            # "PASSWORD": "mukiibi!",
            # "HOST": "db",
            # "PORT": "5432",
            # "NAME": "zentro-pos",
            "NAME": os.getenv("DB_NAME", "zentroapp_db_v2"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", "root"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": "5432",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django_tenants.postgresql_backend",
            "NAME": os.getenv("DB_NAME", ""),
            "USER": os.getenv("DB_USER", ""),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", ""),
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

DOMAIN = "zentroapp.app"
BACKEND_DOMAIN = "zentroapp-backend.com"
FRONTEND_DOMAINS = (
    "zentroapp.app",
    "zentroapp.uncodedsolutions.com",
)
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
            "BACKEND": "utils.storage.CustomSchemaStorage",
            # "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

else:
    # pass
    STORAGES = {
        "default": {
            "BACKEND": "core.storage.CustomSchemaStorage",
            # "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    # pass
    # STORAGES = {
    #     "default": {
    #         # "BACKEND": "utils.storage.CustomSchemaStorage",
    #         "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    #     },
    #     "staticfiles": {
    #         "BACKEND": "storages.backends.s3.S3Storage",
    #     },
    # }


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
    "DEFAULT_PAGINATION_CLASS": "utils.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_THROTTLE_RATES": {
        "login_pin": "60/min",
    },
    # "EXCEPTION_HANDLER": "base.exceptions.custom_exception_handler",
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
    "TOKEN_REFRESH_SERIALIZER": "authentication.serializers.CustomTokenRefreshSerializer",
    "TOKEN_VERIFY_SERIALIZER": "rest_framework_simplejwt.serializers.TokenVerifySerializer",
    "TOKEN_BLACKLIST_SERIALIZER": "rest_framework_simplejwt.serializers.TokenBlacklistSerializer",
    "SLIDING_TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainSlidingSerializer",
    "SLIDING_TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSlidingSerializer",
}
# ------------------- End of SIMPLE JWT -------------------


# --------------------  START Stripe  --------------------
STRIPE_SECRET_KEY_TEST = env("STRIPE_SECRET_KEY_TEST", default="")
STRIPE_PUBLISHABLE_KEY_TEST = env("STRIPE_PUBLISHABLE_KEY_TEST", default="")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
# --------------------  END Stripe  --------------------

# --------------------  SUBSCRIPTION MOBILE MONEY  --------------------
SUBSCRIPTION_MOBILE_MONEY_NUMBER = env(
    "SUBSCRIPTION_MOBILE_MONEY_NUMBER",
    default="+256 700 000 000",
)
# Comma-separated list for multiple numbers, e.g. "0750440865,0779899789"
SUBSCRIPTION_MOBILE_MONEY_NUMBERS = env(
    "SUBSCRIPTION_MOBILE_MONEY_NUMBERS",
    default="0750440865,0779899789",
)
SUBSCRIPTION_MOBILE_MONEY_ACCOUNT_NAME = env(
    "SUBSCRIPTION_MOBILE_MONEY_ACCOUNT_NAME",
    default="ZentroApp",
)
SUBSCRIPTION_NOTIFY_EMAIL = env(
    "SUBSCRIPTION_NOTIFY_EMAIL",
    default="mukiibijoseph19@gmail.com",
)
SUBSCRIPTION_NOTIFY_PHONE = env(
    "SUBSCRIPTION_NOTIFY_PHONE",
    default="0750440865",
)
# --------------------  END SUBSCRIPTION MOBILE MONEY  --------------------

# --------------------  CUSTOM USER MODEL  --------------------
AUTH_USER_MODEL = "authentication.CustomUser"

# --------------------  END CUSTOM USER MODEL  --------------------


# -------------------- REDIS CACHING --------------------
# Django cache configuration using Redis for report caching
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": (
            env("DEV_REDIS_URL", default="redis://localhost:6379/1")
            if ENVIRONMENT == "development"
            else "redis://localhost:6379/1"
        ),
        "KEY_PREFIX": "zentro_cache",
        "TIMEOUT": 300,  # Default timeout: 5 minutes
        # Passed to redis.ConnectionPool.from_url() (not django-redis).
        "OPTIONS": {
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
            "retry_on_timeout": True,
        },
    }
}

# -------------------- CELERY --------------------
if ENVIRONMENT == "development":
    CELERY_BROKER_URL = env("DEV_REDIS_URL", default="redis://localhost:6379/0")
else:
    CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_EXTENDED = True

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
    # Use solo pool on Windows to avoid permission errors.
    # On Linux production, prefer prefork + concurrency > 1 (see docs/COMPANY_CREATION_PERFORMANCE.md).
    CELERY_WORKER_POOL = "solo"
    # Reduce concurrency for Windows
    CELERY_WORKER_CONCURRENCY = 1
    # Disable prefetch for solo pool
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    # Increase task time limits for Windows
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

# -------------------- EMAIL (Mailtrap Transactional Send API - same as scripts/send-mailtrap-curl.sh) --------------------
# POST https://send.api.mailtrap.io/api/send with Bearer token. Real inbox delivery (no sandbox).
# Token: EMAIL_HOST_API_KEY or MAILTRAP_API_TOKEN.
_MAILTRAP_TOKEN = (
    env("EMAIL_HOST_API_KEY", default="") or env("MAILTRAP_API_TOKEN", default="") or ""
).strip()

if _MAILTRAP_TOKEN:
    EMAIL_BACKEND = "core.email_backends.MailtrapSendAPIBackend"
    MAILTRAP_SEND_API_KEY = _MAILTRAP_TOKEN
else:
    EMAIL_BACKEND = "core.email_backends.MailtrapEmailBackend"
    EMAIL_HOST = env(
        "PROD_EMAIL_HOST", default=env("EMAIL_HOST", default="sandbox.smtp.mailtrap.io")
    )
    EMAIL_HOST_USER = env(
        "PROD_EMAIL_HOST_USER", default=env("EMAIL_HOST_USER", default="")
    )
    EMAIL_HOST_PASSWORD = env(
        "PROD_EMAIL_HOST_PASSWORD", default=env("EMAIL_HOST_PASSWORD", default="")
    )
    EMAIL_PORT = env.int("PROD_EMAIL_PORT", default=env.int("EMAIL_PORT", default=587))
    EMAIL_USE_TLS = True
    EMAIL_USE_SSL = False

DEFAULT_FROM_EMAIL = env(
    "PROD_DEFAULT_FROM_EMAIL",
    default=env("DEFAULT_FROM_EMAIL", default="noreply@zentroapp.app"),
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# --------------------  END EMAIL  --------------------

TRIAL_REMINDER_PAYMENT_URL = env(
    "TRIAL_REMINDER_PAYMENT_URL",
    default="https://zentroapp.app/subscription",
)

# Firebase Cloud Messaging (backend push). Download service account JSON from
# Firebase Console → Project settings → Service accounts → Generate new private key.
FIREBASE_CREDENTIALS_PATH = env("FIREBASE_CREDENTIALS_PATH", default="")
FIREBASE_CREDENTIALS_JSON = env("FIREBASE_CREDENTIALS_JSON", default="")

APP_LANDING_PAGE_URL = "https://zentroapp.app/landing"

INSTALLMENT_PAYMENT_URL = env(
    "INSTALLMENT_PAYMENT_URL",
    default="https://zentroapp.app/subscription",
)

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
    # Override with SECURE_SSL_REDIRECT=false for SSH/Cursor localhost tunnels.
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Add these settings after your ALLOWED_HOSTS configuration

CORS_ALLOWED_ORIGINS = [
    "https://zentroapp.app",
    "https://*.zentroapp.app",
    "https://www.zentroapp.app",
    "https://zentroapp-backend.com",
    "https://*.zentroapp-backend.com",
    "http://localhost:5173",  # React development server
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5174",  # React development server
    "http://localhost:3000",
    "http://127.0.0.1:5174",
    "http://*.localhost:5173",
    "http://*.localhost:5174",
    "http://localhost:5123",
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://([a-zA-Z0-9-]+)\.zentroapp\.app$",
    r"^https://zentroapp\.app$",
    r"^https://www\.zentroapp\.app$",
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
    "x-branch-scope",  # Report/financial filters: X-Branch-Scope: all
    "x-csrftoken",
    "x-requested-with",
]

# If you're in development and want to allow all origins (not recommended for production)
if ENVIRONMENT == "development":
    CORS_ALLOW_ALL_ORIGINS = True
    # Chrome may send Access-Control-Request-Private-Network on cross-port localhost
    # preflights; without this, DevTools shows "CORS error" even when Allow-Origin is set.
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
