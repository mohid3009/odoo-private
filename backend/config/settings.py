import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(key, default=False):
    return os.environ.get(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(key, default=""):
    return [x.strip() for x in os.environ.get(key, default).split(",") if x.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = env_bool("DEBUG", True)
if not DEBUG and SECRET_KEY == "dev-insecure-key-change-me":
    raise RuntimeError("Set DJANGO_SECRET_KEY when DEBUG=false.")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
# Render injects its public hostname/URL; trust it without extra config.
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])
    CSRF_TRUSTED_ORIGINS.append(f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}")
SITE_URL = (os.environ.get("SITE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "http://localhost:5173").rstrip("/")

# --- auth: Firebase (Google + email/password) exchanges an ID token for the Django session ---
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "")
# Dev / tests / seeded demo users keep password login; production sets this false so Firebase is the only way in.
LOCAL_PASSWORD_AUTH = env_bool("LOCAL_PASSWORD_AUTH", True)
# signInWithPopup (Google) needs window.opener; Django's default "same-origin" would break it.
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "apps.core.accounts",
    "apps.core.catalog",
    "apps.core.subscriptions",
    "apps.core.billing",
    "apps.finance.discounts",
    "apps.finance.payments",
    "apps.finance.notifications",
    "apps.finance.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# Postgres in compose / production; sqlite only as a zero-setup dev fallback
# (select_for_update(skip_locked) and the billing concurrency tests need Postgres).
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60, conn_health_checks=True
    )
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [{"NAME": "apps.core.accounts.validators.PasswordRuleValidator"}]  # D-006
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24  # reset links live 24 h; single-use because the hash changes

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- static + built SPA (D-005: one container serves API and React) ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
if FRONTEND_DIST.is_dir():
    WHITENOISE_ROOT = FRONTEND_DIST

# --- sessions + CSRF (D-005) ---
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # the SPA reads csrftoken and echoes it as X-CSRFToken
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# --- email (D-007) ---
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND") or "apps.finance.notifications.email_backend.ConsoleEmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = bool(EMAIL_HOST)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Brightloop <noreply@brightloop.local>")

# --- Odoo (D-003/D-004; never a hard dependency, rule 7) ---
ODOO_ENABLED = env_bool("ODOO_ENABLED", False)
ODOO_URL = os.environ.get("ODOO_URL", "http://localhost:8069").rstrip("/")
ODOO_DB = os.environ.get("ODOO_DB", "odoo_sub")
ODOO_USER = os.environ.get("ODOO_USER", "admin")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD") or os.environ.get("ODOO_API_KEY", "")

# --- payments (D-041): failed attempts allowed per invoice before it is flagged and further attempts are refused ---
PAYMENT_MAX_ATTEMPTS = int(os.environ.get("PAYMENT_MAX_ATTEMPTS", "3"))

# --- staff/admin self-registration (D-044): empty = disabled ---
STAFF_SIGNUP_CODE = os.environ.get("STAFF_SIGNUP_CODE", "")
ADMIN_SIGNUP_CODE = os.environ.get("ADMIN_SIGNUP_CODE", "")

# --- notifications (D-020..D-025) ---
WHATSAPP_PROVIDER = os.environ.get("WHATSAPP_PROVIDER", "console")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "")
META_WA_PHONE_NUMBER_ID = os.environ.get("META_WA_PHONE_NUMBER_ID", "")
META_WA_ACCESS_TOKEN = os.environ.get("META_WA_ACCESS_TOKEN", "")
META_WA_API_VERSION = os.environ.get("META_WA_API_VERSION", "v20.0")
NOTIFY_DUE_SOON_DAYS = int(os.environ.get("NOTIFY_DUE_SOON_DAYS", "3"))
NOTIFY_OVERDUE_DAYS = [int(x) for x in env_list("NOTIFY_OVERDUE_DAYS", "1,7")]
NOTIFY_EXPIRING_DAYS = int(os.environ.get("NOTIFY_EXPIRING_DAYS", "7"))
