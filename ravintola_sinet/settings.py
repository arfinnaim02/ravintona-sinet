"""Django settings for the Ravintola Sinet project (development)."""

from __future__ import annotations
import dj_database_url
import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _
import cloudinary
import cloudinary.uploader
import cloudinary.api

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-change-this-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"

# Comma-separated in Render env: "ravintona-sinet.onrender.com,www.yourdomain.com"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Cloudinary (for media uploads)
    "cloudinary",
    "cloudinary_storage",

    "restaurant",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ravintola_sinet.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # keep even if you mostly use app templates
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "restaurant.context_processors.restaurant_settings",

            ],
        },
    },
]

WSGI_APPLICATION = "ravintola_sinet.wsgi.application"



DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DEBUG and not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required in production")

DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=not DEBUG,
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True


LANGUAGES = [
    ("en", _("English")),
    ("fi", _("Finnish")),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

USE_TZ = True

# Static
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Cloudinary config (media uploads)
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")

if not DEBUG and not CLOUDINARY_URL:
    raise RuntimeError("CLOUDINARY_URL is required in production")

CLOUDINARY_STORAGE = {"CLOUDINARY_URL": CLOUDINARY_URL}

STORAGES = {
    # Media (admin uploads)
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    # Static
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}



DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Custom restaurant constants ---
RESTAURANT_NAME = "Ravintola Sinet"
RESTAURANT_ADDRESS = "Joensuu, Finland"
RESTAURANT_PHONE = "+358 123 4567"
RESTAURANT_EMAIL = "info@sinet.fi"
RESTAURANT_OPENING_HOURS = "Mon–Sun 10:00–22:00"

# Restaurant location (Joensuu) — set exact later
RESTAURANT_LAT = 62.60242470943839
RESTAURANT_LNG = 29.762670098205916

# Delivery pricing rules (edit anytime)
DELIVERY_BASE_FEE = 3.00
DELIVERY_BASE_KM = 2.0
DELIVERY_PER_KM = 1.00
DELIVERY_MAX_FEE = 10.00
DELIVERY_MAX_RADIUS_KM = 10.0

NOMINATIM_USER_AGENT = "RavintolaSinetDelivery/1.0 (dev-local)"
# If you have a contact email, even better:
# NOMINATIM_USER_AGENT = "RavintolaSinetDelivery/1.0 (contact@ravintolasinet.fi)"



MENU_ITEM_TAGS: list[tuple[str, str]] = [
    ("vegan", "Vegan"),
    ("vegetarian", "Vegetarian"),
    ("spicy", "Spicy"),
    ("gluten-free", "Gluten Free"),
    ("popular", "Popular"),
    ("wolt", "Wolt"),
]

MENU_ITEM_ALLERGENS: list[tuple[str, str]] = [
    ("milk", "Milk"),
    ("egg", "Egg"),
    ("peanut", "Peanut"),
    ("soy", "Soy"),
    ("tree-nut", "Tree Nut"),
    ("wheat", "Wheat"),
    ("fish", "Fish"),
    ("shellfish", "Shellfish"),
]

# Use the named route (safer than hardcoded path)
LOGIN_URL = "restaurant:admin_login"


CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]


MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))


if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"


CLOUDINARY_STORAGE = {
    "CLOUDINARY_URL": os.environ.get("CLOUDINARY_URL", "")
}


