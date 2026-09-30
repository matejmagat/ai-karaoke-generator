from datetime import timedelta
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-local-development-only")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "corsheaders",
    "drf_spectacular",
    "rest_framework",
    "catalog",
    "library",
    "users",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# Honour X-Forwarded-* headers when running behind the bundled nginx proxy.
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", False)
if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=int(os.getenv("JWT_ACCESS_TOKEN_HOURS", "24"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "30"))),
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Karaoke Generator API",
    "DESCRIPTION": "API for karaoke songs, playlists, libraries, and audio-processing jobs.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.getenv("SQLITE_PATH", str(BASE_DIR / "db.sqlite3"))),
        }
    }
AUTH_USER_MODEL = "users.User"

MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))

LYRICS_ALIGN_SERVICE_URL = os.getenv("LYRICS_ALIGN_SERVICE_URL", "http://localhost:8001")
LYRICS_ALIGN_REQUEST_TIMEOUT_SECONDS = float(os.getenv("LYRICS_ALIGN_REQUEST_TIMEOUT_SECONDS", "60"))
LYRICS_ALIGN_JOB_TIMEOUT_SECONDS = float(os.getenv("LYRICS_ALIGN_JOB_TIMEOUT_SECONDS", "3600"))
LYRICS_ALIGN_POLL_INTERVAL_SECONDS = float(os.getenv("LYRICS_ALIGN_POLL_INTERVAL_SECONDS", "2"))

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = os.getenv("STATIC_URL", "/static/")
STATIC_ROOT = Path(os.getenv("STATIC_ROOT", str(BASE_DIR / "staticfiles")))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
