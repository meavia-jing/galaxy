"""[UNIT-PERM-*][I01-T03] 公共权限基类。

为什么单独测：`common/permissions.py` 是给后续迭代（I02 用户中心、I06 优惠券）复用的
基类，当前没有视图直接使用它。没有测试的复用基类等于未验证的承诺——等到 I02 才发现
`IsOwner` 对 `user` 属性模型不生效，代价会转移到一个业务任务上。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory

from common.permissions import IsOperatorOrReadOnly, IsOwner, IsStaff


@pytest.fixture
def factory() -> APIRequestFactory:
    return APIRequestFactory()


def make_request(factory, method="get", **user_attrs):
    request = factory.get("/") if method == "get" else factory.post("/")
    request.user = SimpleNamespace(**{"id": 1, "is_authenticated": True, **user_attrs})
    return request


class TestIsOwner:
    """[UNIT-PERM-01][I01-T03] 对象级归属校验。"""

    def test_allows_user_id_match(self, factory):
        obj = SimpleNamespace(user_id=7)
        request = make_request(factory, id=7)
        assert IsOwner().has_object_permission(request, None, obj) is True

    def test_rejects_other_users_object(self, factory):
        obj = SimpleNamespace(user_id=8)
        request = make_request(factory, id=7)
        assert IsOwner().has_object_permission(request, None, obj) is False

    def test_reads_nested_user_relation(self, factory):
        """模型暴露 `user` 关联而不是 `user_id` 时也必须能判定。"""
        obj = SimpleNamespace(user=SimpleNamespace(id=7))
        request = make_request(factory, id=7)
        assert IsOwner().has_object_permission(request, None, obj) is True

    def test_denies_when_object_has_no_owner(self, factory):
        """无归属字段的对象一律拒绝，避免「漏判即放行」。"""
        obj = SimpleNamespace(name="no-owner")
        request = make_request(factory, id=7)
        assert IsOwner().has_object_permission(request, None, obj) is False

    def test_message_is_chinese(self):
        assert IsOwner.message == "无权访问该资源"


class TestIsOperatorOrReadOnly:
    """[UNIT-PERM-02][I01-T03] 写操作需运营权限，读操作公开。"""

    @pytest.mark.parametrize("method", ["get", "head", "options"])
    def test_safe_methods_allowed_even_for_anonymous(self, factory, method):
        request = factory.get("/")
        request.user = SimpleNamespace(is_authenticated=False, is_operator=False)
        assert IsOperatorOrReadOnly().has_permission(request, None) is True

    def test_write_requires_operator(self, factory):
        request = make_request(factory, method="post", is_operator=False)
        assert IsOperatorOrReadOnly().has_permission(request, None) is False

    def test_operator_can_write(self, factory):
        request = make_request(factory, method="post", is_operator=True)
        assert IsOperatorOrReadOnly().has_permission(request, None) is True

    def test_anonymous_write_denied(self, factory):
        request = factory.post("/")
        request.user = SimpleNamespace(is_authenticated=False, is_operator=True)
        assert IsOperatorOrReadOnly().has_permission(request, None) is False


class TestIsStaff:
    """[UNIT-PERM-03][I01-T03] 后台接口需 staff 权限。"""

    def test_staff_allowed(self, factory):
        request = make_request(factory, is_staff_allowed=True)
        assert IsStaff().has_permission(request, None) is True

    def test_non_staff_denied(self, factory):
        request = make_request(factory, is_staff_allowed=False)
        assert IsStaff().has_permission(request, None) is False

    def test_anonymous_denied(self, factory):
        request = factory.get("/")
        request.user = SimpleNamespace(is_authenticated=False, is_staff_allowed=True)
        assert IsStaff().has_permission(request, None) is False

    def test_missing_attribute_denied(self, factory):
        """用户模型没有该属性时不得抛异常，而是拒绝。"""
        request = factory.get("/")
        request.user = SimpleNamespace(is_authenticated=True)
        assert IsStaff().has_permission(request, None) is False
