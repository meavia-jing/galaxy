"""Cache access that degrades gracefully when the backend is unavailable.

Redis is an accelerator, never a source of truth. When the backend raises
(connection refused, timeout, ...), reads fall through to the database and
writes are skipped with a WARNING, so a cache outage costs latency instead of
turning public endpoints into 500s.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)


def cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception as exc:  # noqa: BLE001 - any backend failure must not break reads
        logger.warning("cache get failed key=%s error=%s", key, exc)
        return default


def cache_set(key, value, timeout: int) -> bool:
    try:
        cache.set(key, value, timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache set failed key=%s error=%s", key, exc)
        return False
    return True


def cache_delete(key) -> bool:
    try:
        cache.delete(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache delete failed key=%s error=%s", key, exc)
        return False
    return True


def cached(key, timeout: int, producer):
    """Return the cached value, or rebuild it and best-effort store it."""
    value = cache_get(key)
    if value is not None:
        return value
    value = producer()
    cache_set(key, value, timeout)
    return value
