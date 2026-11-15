"""共享 pytest fixtures。

约定：
- 每个用例自建用户，用户名带随机后缀，禁止依赖 seed_demo 的数据。
- ``auth_client`` 用 force_authenticate，不经过登录接口；
  需要验证登录/刷新链路的用例请用 ``api_client`` 走真实请求。
"""
from __future__ import annotations

import itertools
import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

DEFAULT_PASSWORD = "TestPass2026"

_counter = itertools.count(1)


def unique_username(prefix: str = "tester") -> str:
    """符合 UsernameValidator（小写字母/数字/下划线，4-32 位）的唯一用户名。"""
    return f"{prefix}_{next(_counter):03d}_{uuid.uuid4().hex[:4]}"


@pytest.fixture
def api_client() -> APIClient:
    """未认证的 DRF 客户端。"""
    return APIClient()


@pytest.fixture
def make_user(db):
    """返回一个工厂函数，便于一个用例里创建多个用户。"""

    def _make(username: str | None = None, password: str = DEFAULT_PASSWORD, **extra):
        User = get_user_model()
        return User.objects.create_user(
            username=username or unique_username(),
            password=password,
            **extra,
        )

    return _make


@pytest.fixture
def user(make_user):
    """默认测试用户。"""
    return make_user()


@pytest.fixture
def auth_client(user) -> APIClient:
    """已认证客户端，跳过登录接口直连视图。"""
    client = APIClient()
    client.force_authenticate(user=user)
    return client
