"""Import-safe error primitives shared by middleware, renderers and handlers.

This module must not import ``rest_framework.views`` (directly or transitively):
it is loaded while Django configures logging, before the app registry is ready.
"""
from django.db.utils import DatabaseError
from rest_framework import status

DEFAULT_CODES = {
    status.HTTP_400_BAD_REQUEST: ("INVALID_REQUEST", "请求参数不正确"),
    status.HTTP_401_UNAUTHORIZED: ("UNAUTHORIZED", "请先登录"),
    status.HTTP_403_FORBIDDEN: ("FORBIDDEN", "没有操作权限"),
    status.HTTP_404_NOT_FOUND: ("NOT_FOUND", "资源不存在"),
    status.HTTP_409_CONFLICT: ("CONFLICT", "状态冲突"),
    status.HTTP_429_TOO_MANY_REQUESTS: ("RATE_LIMITED", "请求过于频繁，请稍后再试"),
    status.HTTP_500_INTERNAL_SERVER_ERROR: ("INTERNAL_ERROR", "服务器内部错误"),
    status.HTTP_503_SERVICE_UNAVAILABLE: ("DEPENDENCY_UNAVAILABLE", "依赖服务暂不可用"),
}


def is_dependency_failure(exc) -> bool:
    """True when the root cause is an unavailable backing service (DB/Redis)."""
    if isinstance(exc, DatabaseError):
        return True
    try:
        from redis.exceptions import RedisError
    except ImportError:  # pragma: no cover - redis is optional for locmem dev setups
        return False
    return isinstance(exc, RedisError)
