"""[INT-API-*][I01-T03] OpenAPI 契约完备性。

为什么要有这条：`manage.py spectacular` 的警告只是打印，不会让任何测试失败，
所以 schema 退化（端点缺响应体、认证方案缺失、路径参数类型丢失）可以悄悄发生。
这里把「0 警告」和「关键端点 + 安全方案存在」变成断言。
"""
from __future__ import annotations

import pytest
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator

pytestmark = pytest.mark.django_db

# 验收清单要求「API 变更有 OpenAPI 契约」；这些是本迭代已交付的对外端点。
EXPECTED_PATHS = [
    "/api/v1/auth/register/",
    "/api/v1/auth/login/",
    "/api/v1/auth/refresh/",
    "/api/v1/auth/logout/",
    "/api/v1/users/me/",
    "/api/v1/users/me/change-password/",
    "/api/v1/addresses/",
    "/api/v1/categories/",
    "/api/v1/products/",
    "/api/v1/banners/",
    "/api/v1/cart-items/",
    "/api/v1/cart/",
    "/health/live/",
    "/health/ready/",
]


@pytest.fixture(scope="module")
def schema() -> dict:
    # 生成一次即可；SchemaGenerator 不依赖数据库内容，只读视图与序列化器定义。
    return SchemaGenerator().get_schema(request=None, public=True)


def test_schema_generates_without_warnings():
    """[INT-API-01][I01-T03] schema 生成无错误、无警告。

    drf-spectacular 把诊断信息记在模块级单例 GENERATOR_STATS 上（不是生成器实例），
    所以用「生成前快照 → 生成后比较」的方式断言新增项，避免受同进程其他用例影响。
    """
    before_warn = len(GENERATOR_STATS._warn_cache)
    before_err = len(GENERATOR_STATS._error_cache)

    schema = SchemaGenerator().get_schema(request=None, public=True)

    assert schema["openapi"].startswith("3.")
    new_warnings = list(GENERATOR_STATS._warn_cache)[before_warn:]
    new_errors = list(GENERATOR_STATS._error_cache)[before_err:]
    assert new_errors == [], f"schema 生成有错误：{new_errors}"
    assert new_warnings == [], f"schema 生成有警告：{new_warnings}"


def test_expected_paths_are_documented(schema):
    """[INT-API-02][I01-T03] 已交付端点全部出现在契约中。"""
    documented = set(schema["paths"])
    missing = [p for p in EXPECTED_PATHS if p not in documented]
    assert missing == [], f"契约缺少端点：{missing}"


def test_jwt_security_scheme_is_declared(schema):
    """[INT-API-03][I01-T03] 自定义认证类被登记为 Bearer 方案，否则文档看不出需登录。"""
    scheme = schema["components"]["securitySchemes"]["jwtAuth"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"


def test_protected_endpoint_requires_auth_in_schema(schema):
    """[INT-API-04][I01-T03] 受保护端点在契约里标注了安全要求。"""
    me = schema["paths"]["/api/v1/users/me/"]["get"]
    assert {"jwtAuth": []} in me["security"]


def test_public_endpoint_has_no_auth_requirement(schema):
    """[INT-API-05][I01-T03] 公开端点不强制认证，避免文档误导调用方。"""
    products = schema["paths"]["/api/v1/products/"]["get"]
    assert not products.get("security") or products["security"] == [{}]


def test_product_list_documents_sort_enum(schema):
    """[INT-API-06][I01-T03] 排序白名单在契约中可枚举，非白名单值返回 400。"""
    params = schema["paths"]["/api/v1/products/"]["get"]["parameters"]
    sort_param = next(p for p in params if p["name"] == "sort")
    enum_values = sort_param["schema"].get("enum") or []
    assert set(enum_values) == {"newest", "oldest", "price_asc", "price_desc"}
