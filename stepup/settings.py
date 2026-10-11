"""
Django settings for the StepUp Footwear e-commerce project.

Environment variables (SECRET_KEY, DEBUG, ...) are read from a local
`.env` file if present, otherwise from the process environment.
This keeps secrets out of version control while still working
out-of-the-box for local development.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------- paths ---
BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    """
    Minimal `.env` loader (KEY=VALUE per line) so we don't need an extra
    dependency. Values already set in the real environment always win.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        # Never overwrite an existing environment variable
        os.environ.setdefault(key, value)


load_env_file(BASE_DIR / ".env")

# --------------------------------------------------------------- security ---
# Secret key comes from the environment; the fallback below is only for
# first-time local development and MUST be replaced in production.
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-key-change-me-before-deploying",
)

# DEBUG defaults to True for local development, but is controlled by env.
DEBUG = os.environ.get("DEBUG", "True").lower() in ("1", "true", "yes", "on")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

# ------------------------------------------------------------------ apps ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps
    "accounts",
    "store",
    "cart",
    "orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "stepup.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Makes the cart count badge available on every template
                "cart.context_processors.cart_summary",
                # Navbar data: mega-menu categories + audience choices
                "store.context_processors.shop_navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "stepup.wsgi.application"

# --------------------------------------------------------------- database ---
# Default is SQLite. To move to PostgreSQL later, set these env vars:
#   DATABASE_URL=postgres://user:pass@host:5432/stepup
# or fill in the ENGINE/NAME/USER/PASSWORD/HOST/PORT values below.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ----------------------------------------------------------- passwords -----
# Hashed passwords: Django's default PBKDF2 hasher is used as-is.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------- i18n/l10n ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- statics ---
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -------------------------------------------------------------- default pk ---
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------------------------------------------------- custom user ----
AUTH_USER_MODEL = "accounts.User"

# ------------------------------------------------------------- login/urls ---
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "store:home"
LOGOUT_REDIRECT_URL = "store:home"

# ----------------------------------------------------------------- cart -----
# Free shipping threshold + flat fee used by cart/orders totals.
FREE_SHIPPING_THRESHOLD = 1999.00   # INR
SHIPPING_FEE = 99.00                # INR

# Session cookie age: guests keep their cart for 2 weeks.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

if not DEBUG:
    # Hardening defaults for production
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
