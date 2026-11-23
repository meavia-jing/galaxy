"""测试用的「时间旅行」工具：不改系统时钟，只让缓存后端以为时间前进了。

为什么不用 freezegun：它会 patch 全局 ``time.time``，影响日志、``created_at``、
JWT 过期判断等一大片行为，测试面太宽；本项目要验证的只有一件事——
缓存条目到点后是否会被当作不存在。因此只替换
``django.core.cache.backends.locmem`` 模块内的 ``time`` 引用。

局限（写清楚，避免误用）：只对 ``LocMemCache`` 有效。Redis 的过期判断在
服务端，客户端改时间没用；真机口径见 ``docs/acceptance/I03/I03-T05.md`` 的
停 Redis / TTL 实测记录。
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest import mock

from django.core.cache import caches
from django.core.cache.backends import locmem
from django.core.cache.backends.locmem import LocMemCache


class _ShiftedTime:
    """把 ``time.time()`` 整体偏移 ``offset`` 秒，其余属性透传。"""

    def __init__(self, real, offset: float) -> None:
        self._real = real
        self._offset = offset

    def time(self) -> float:
        return self._real.time() + self._offset

    def __getattr__(self, name):
        return getattr(self._real, name)


def require_locmem() -> LocMemCache:
    """返回真实的默认缓存后端；不是 LocMemCache 时跳过当前用例。

    注意：``django.core.cache.cache`` 是 ``ConnectionProxy`` 而不是后端本身，
    直接 ``isinstance`` 永远为 False，必须经 ``caches["default"]`` 取。
    """
    backend = caches["default"]
    if not isinstance(backend, LocMemCache):  # pragma: no cover - 换后端时才触发
        import pytest

        pytest.skip("时间旅行只对 LocMemCache 有效，当前后端为 " + type(backend).__name__)
    return backend


@contextmanager
def travel(seconds: float):
    """让 LocMemCache 的过期比较认为「现在」是 ``seconds`` 秒之后。"""
    with mock.patch.object(locmem, "time", _ShiftedTime(locmem.time, seconds)):
        yield


def remaining_ttl(cache, key: str) -> float | None:
    """读出某键剩余寿命（秒）；键不存在返回 None。

    读的是 LocMemCache 的 ``_expire_info``（绝对到期时间戳）。没有公开 API
    能查单个键的剩余 TTL，而这正是本任务要证明的东西，故直接读内部结构。
    ``cache`` 传 ``ConnectionProxy`` 或真实后端都可以。

    注意 ``_expire_info`` 的键是 ``make_key()`` 处理过的（带 ``:版本:`` 与前缀），
    传业务用的原始 key 时要先转换，否则永远查不到。
    """
    expire_info = cache._expire_info  # noqa: SLF001 - 见 docstring
    for candidate in (key, cache.make_key(key)):
        if expire_info.get(candidate) is not None:
            return expire_info[candidate] - locmem.time.time()
    return None
