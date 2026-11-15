"""[INT-ERR-*][I01-T03] 错误信封与缓存故障降级。

覆盖：限流器缓存故障 fail-open、分类/横幅缓存回源、未捕获异常与依赖故障
（Redis 停机）都返回 JSON 信封而不是 Django 的 HTML 错误页。
"""
from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError

from common.middleware import EnvelopeErrorMiddleware
from tests.support.broken_cache import BROKEN_CACHES

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login/"
CATEGORIES_URL = "/api/v1/categories/"
BANNERS_URL = "/api/v1/banners/"


@pytest.fixture(autouse=True)
def _clean_cache():
    """每条用例从空缓存开始，结束后也清掉限流历史。"""
    try:
        cache.clear()
    except Exception:  # noqa: BLE001 - 用例本身会切到坏缓存
        pass
    yield
    try:
        cache.clear()
    except Exception:  # noqa: BLE001
        pass


def _raise(exc):
    def _inner(*args, **kwargs):
        raise exc

    return _inner


@override_settings(CACHES=BROKEN_CACHES)
def test_login_fails_open_when_cache_is_down(api_client, make_user, caplog):
    """[INT-ERR-05][I02-T01] 缓存不可用时登录仍可用（限流降级放行）。"""
    user = make_user()
    with caplog.at_level("WARNING"):
        response = api_client.post(
            LOGIN_URL,
            {"username": user.username, "password": "TestPass2026"},
            format="json",
        )

    assert response.status_code == 200, response.content
    assert response.json()["data"]["access"]
    assert any("throttle bypassed" in record.message for record in caplog.records)


def test_login_is_rate_limited_when_cache_is_healthy(api_client, make_user):
    """[INT-ERR-05][I02-T01] 超过 30/min 返回 429 与 RATE_LIMITED 信封。"""
    user = make_user()
    payload = {"username": user.username, "password": "wrong-password"}
    codes = [
        api_client.post(LOGIN_URL, payload, format="json").status_code
        for _ in range(31)
    ]

    assert codes[:30] == [401] * 30
    assert codes[-1] == 429


@override_settings(CACHES=BROKEN_CACHES)
def test_categories_fall_back_to_database(api_client):
    """[INT-CAT-08][I03-T05] Redis 停机时分类接口回源，不返回 500。"""
    response = api_client.get(CATEGORIES_URL)

    assert response.status_code == 200, response.content
    assert isinstance(response.json()["data"], list)


@override_settings(CACHES=BROKEN_CACHES)
def test_banners_fall_back_to_database(api_client):
    """[INT-CMS-04][I03-T05] Redis 停机时横幅接口回源，不返回 500。"""
    response = api_client.get(BANNERS_URL)

    assert response.status_code == 200, response.content
    assert isinstance(response.json()["data"], list)


@override_settings(CACHES=BROKEN_CACHES)
def test_cache_invalidation_is_safe_when_cache_is_down():
    """[INT-CAT-08][I03-T05] 后台写操作触发的缓存失效不因 Redis 停机而抛错。"""
    from apps.catalog.views import invalidate_catalog_cache
    from apps.cms.views import invalidate_cms_cache

    assert invalidate_catalog_cache() is None
    assert invalidate_cms_cache() is None


def test_400_envelope(api_client):
    """[INT-ERR-01][I01-T03] 400 信封含 code/message/fields 与 request_id。"""
    response = api_client.get("/api/v1/products/", {"sort": "not-allowed"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_SORT"
    assert body["error"]["message"]
    assert body["request_id"] == response["X-Request-ID"]


def test_401_envelope(api_client):
    """[INT-ERR-02][I01-T03] 未登录访问受保护接口返回 401 信封。"""
    response = api_client.get("/api/v1/users/me/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_403_envelope(api_client):
    """[INT-ERR-03][I01-T03] 缺少 CSRF 头返回 403 CSRF_FAILED 信封。"""
    response = api_client.post("/api/v1/auth/refresh/", {}, format="json")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_404_envelope(api_client):
    """[INT-ERR-04][I01-T03] 不存在的商品返回 404 NOT_FOUND 信封。"""
    response = api_client.get("/api/v1/products/999999/")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["request_id"]


def test_unhandled_exception_returns_envelope(api_client, monkeypatch):
    """[INT-ERR-06][I01-T03] 未捕获异常返回 500 信封，不泄露栈与文件路径。"""
    monkeypatch.setattr(
        "apps.catalog.views.selectors.active_categories",
        _raise(RuntimeError("boom-marker")),
    )

    response = api_client.get(CATEGORIES_URL)

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["fields"] == {}
    assert body["request_id"]
    raw = response.content.decode()
    assert "Traceback" not in raw
    assert "boom-marker" not in raw
    assert ".py" not in raw


def test_dependency_failure_returns_503(api_client, monkeypatch):
    """[INT-ERR-07][I01-T03] 依赖服务不可用映射为 503 DEPENDENCY_UNAVAILABLE。"""
    monkeypatch.setattr(
        "apps.catalog.views.selectors.active_categories",
        _raise(RedisConnectionError("redis down")),
    )

    response = api_client.get(CATEGORIES_URL)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


def test_envelope_middleware_covers_api_paths():
    """[INT-ERR-06][I01-T03] DRF 之外的异常同样返回 JSON 信封与请求 ID。"""
    request = RequestFactory().get("/api/v1/whatever/")
    request.request_id = "rid-middleware"

    response = EnvelopeErrorMiddleware(lambda _request: None).process_exception(
        request, RuntimeError("boom")
    )

    assert response.status_code == 500
    assert response["X-Request-ID"] == "rid-middleware"
    assert b"INTERNAL_ERROR" in response.content


def test_envelope_middleware_ignores_non_api_paths():
    """[INT-ERR-06][I01-T03] 非 API 路径保持 Django 默认行为。"""
    request = RequestFactory().get("/admin/")
    request.request_id = "rid-admin"

    assert EnvelopeErrorMiddleware(lambda _request: None).process_exception(
        request, RuntimeError("boom")
    ) is None

