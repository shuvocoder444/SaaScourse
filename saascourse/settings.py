"""
Django settings for saascourse project.

Multi-Tenant Course/LMS SaaS Platform Architecture
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-gn+hen(x0wa$yr5wc_6n8m9=)e9j&_641o^t1((_0-!8)*==47"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Main Platform Root Domain configuration
# Override via environment variable PLATFORM_MAIN_DOMAIN in production (e.g. course.webkoders.com)
PLATFORM_MAIN_DOMAIN = os.environ.get("PLATFORM_MAIN_DOMAIN", "course.webkoders.com").strip().lower()
_MAIN_HOST = PLATFORM_MAIN_DOMAIN.split(":")[0]

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".localhost",       # Wildcard for subdomains on localhost (e.g. alpha.localhost)
    _MAIN_HOST,
    f".{_MAIN_HOST}",   # Wildcard for subdomains in production
    "course.webkoders.com",
    ".course.webkoders.com",
    "*",               # Allow custom domains (routed by reverse proxy/load balancer)
]

# Referrer Policy for YouTube Embed Player & External Media Security
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"



# Custom User Model
AUTH_USER_MODEL = "users.User"

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Architecture & Core Apps
    "core",
    "apps.tenants.apps.TenantsConfig",
    "apps.users.apps.UsersConfig",
    "apps.courses.apps.CoursesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # Multi-tenancy Resolution Middleware (runs after Auth, before Views)
    "core.tenancy.middleware.TenantResolutionMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "saascourse.urls"

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
                # Exposes `current_tenant` & `is_tenant_site` to all templates
                "core.tenancy.context_processors.tenant_context",
            ],
        },
    },
]

WSGI_APPLICATION = "saascourse.wsgi.application"


# Database
# Local: SQLite shared database with row-level tenant_id scoping
# Production: PostgreSQL with identical shared database row-level isolation
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Cache configuration:
# LocMem for local dev, Redis in production
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "tenant-saas-cache",
    }
}

# Domains representing the root/marketing platform
TENANT_MAIN_DOMAINS = [
    PLATFORM_MAIN_DOMAIN,
    "localhost",
    "127.0.0.1",
]


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media uploads (Avatars, Course thumbnails)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth URL routing
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"
