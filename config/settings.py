import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(key, default=""):
    return os.environ.get(key, default)


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("CSRF_TRUSTED_ORIGINS").split(",") if o]
SITE_URL = env("SITE_URL", "http://127.0.0.1:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context.site",
    ]},
}]

# ---- Database: MySQL -------------------------------------------------------
if env("DB_ENGINE", "mysql") == "sqlite":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", "LetsPublic"),
        "USER": env("DB_USER", "root"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "3306"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    }}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# ---- Email -----------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "587") or 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "LetsPublic <no-reply@LetsPublic.local>")
EMAIL_TIMEOUT = 10

# ---- Razorpay --------------------------------------------------------------
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET")

# Advertisement slot price PER WEEK in INR (separate from subscription plans)
AD_PRICING = {  # per week
    "hero":      {"INR": 4999, "USD": 59},
    "spotlight": {"INR": 2499, "USD": 29},
    "cat_first": {"INR": 1999, "USD": 24},
    "cat_third": {"INR": 1299, "USD": 15},
    "sidebar":   {"INR": 1499, "USD": 18},
}
AD_HOLD_MINUTES = 15  # an unpaid booking blocks the slot this long



if env("USE_R2", "0") == "1":
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {
            "bucket_name": env("R2_BUCKET"),
            "endpoint_url": f"https://{env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
            "access_key": env("R2_ACCESS_KEY_ID"),
            "secret_key": env("R2_SECRET_ACCESS_KEY"),
            "region_name": "auto",
            "signature_version": "s3v4",
            "custom_domain": env("R2_PUBLIC_DOMAIN"),   # e.g. pub-xxxx.r2.dev or cdn.yourdomain.com
            "querystring_auth": False,
            "file_overwrite": False,
        }},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

PASSWORD_RESET_TIMEOUT = 3600   # reset links expire after 1 hour
CONTACT_EMAIL = env("CONTACT_EMAIL", "support@LetsPublic.local")


PAGE_SIZES = {"products": 12, "top": 15, "mine": 8, "queue": 10, "TopProductLimit": 10}

print('env("SOCIAL_LINKEDIN"', env("SOCIAL_LINKEDIN"))

SOCIAL_LINKS = {   # leave a value empty to hide that icon
    "facebook":  env("SOCIAL_FACEBOOK",  "https://facebook.com/"),
    "x":         env("SOCIAL_X",         "https://x.com/"),
    "instagram": env("SOCIAL_INSTAGRAM", ""),
    "linkedin":  env("SOCIAL_LINKEDIN",  ""),
    "youtube":   env("SOCIAL_YOUTUBE",   ""),
}

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

EMAIL_VERIFY_HOURS = 24
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True