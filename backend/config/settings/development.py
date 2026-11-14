"""Windows 11 local development settings."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

# Local HTTP: refresh cookie cannot be Secure.
REFRESH_COOKIE_SECURE = False

INTERNAL_IPS = ["127.0.0.1"]
