"""A cache backend that behaves like Redis with the server stopped."""
from django.core.cache.backends.base import BaseCache
from redis.exceptions import ConnectionError as RedisConnectionError


class BrokenCache(BaseCache):
    """Every operation raises the same exception the real backend would."""

    def __init__(self, location, params=None):
        super().__init__(params or {})
        self.location = location

    @staticmethod
    def _down(*args, **kwargs):
        raise RedisConnectionError("cache backend unavailable")

    get = get_many = set = set_many = add = delete = delete_many = touch = clear = has_key = incr = decr = _down


BROKEN_CACHES = {
    "default": {
        "BACKEND": "tests.support.broken_cache.BrokenCache",
        "LOCATION": "broken",
    }
}
