"""Ubuntu 24.04 production settings (Nginx + Gunicorn + systemd)."""
from .base import *  # noqa: F401,F403
from .base import env, env_bool, env_list

DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
REFRESH_COOKIE_SECURE = True

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

if env("DJANGO_SECRET_KEY", "") in {"", "dev-only-insecure-key-change-me"}:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")
