"""[INT-AUTH-*][I02-T01/T02/T03] 认证链路集成用例。

全部走真实 HTTP 端点（注册 → 登录 → 刷新 → 登出 → 改密），不使用
``force_authenticate``，以验证 Cookie、CSRF 与 ``auth_version`` 的联动。
"""
from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework.test import APIClient

from tests.conftest import DEFAULT_PASSWORD, unique_username

pytestmark = pytest.mark.django_db

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/users/me/"
CHANGE_PASSWORD_URL = "/api/v1/users/me/change-password/"

NEW_PASSWORD = "FreshPass2026x"
CSRF_URL = "/api/v1/auth/csrf/"


@pytest.fixture(autouse=True)
def _reset_throttle_cache():
    """限流计数存在 cache 里，逐例清空避免 30/min 跨用例累加。"""
    cache.clear()
    yield
    cache.clear()


def _login(client, username: str, password: str = DEFAULT_PASSWORD):
    return client.post(
        LOGIN_URL, {"username": username, "password": password}, format="json"
    )


def _csrf(client) -> dict:
    """取服务端下发的 csrftoken 并原样回填请求头（同真实前端行为）。

    不用固定字符串：服务端遇到格式非法的 csrftoken Cookie 会重新下发一个，
    固定值会让后续请求的 Cookie 与请求头不一致，误判为 CSRF 失败。
    """
    client.get(CSRF_URL)
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _bearer(access: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access}"}


def _refresh_cookie(client) -> str:
    return client.cookies["refresh_token"].value


def test_register_then_login(api_client):
    """[INT-AUTH-01][I02-T01] 注册返回 201 + access，refresh 只走 HttpOnly Cookie。"""
    username = unique_username("reg")
    registered = api_client.post(
        REGISTER_URL,
        {"username": username, "password": DEFAULT_PASSWORD, "nickname": "星友"},
        format="json",
    )

    assert registered.status_code == 201, registered.content
    body = registered.json()["data"]
    assert body["access"]
    assert body["user"]["username"] == username
    assert body["user"]["id"]
    assert _refresh_cookie(api_client)

    logged_in = _login(api_client, username)
    assert logged_in.status_code == 200, logged_in.content
    payload = logged_in.json()["data"]
    assert payload["access"]
    assert "refresh" not in payload, "refresh token 不应出现在响应体"
    assert payload["user"]["username"] == username


def test_duplicate_username_is_case_insensitive(api_client):
    """[INT-AUTH-02][I02-T01] 用户名归一为小写后重复注册被拒。"""
    username = unique_username("dup")
    first = api_client.post(
        REGISTER_URL,
        {"username": username.upper(), "password": DEFAULT_PASSWORD},
        format="json",
    )
    assert first.status_code == 201, first.content
    assert first.json()["data"]["user"]["username"] == username

    duplicate = api_client.post(
        REGISTER_URL,
        {"username": f"  {username.upper()}  ", "password": DEFAULT_PASSWORD},
        format="json",
    )

    assert duplicate.status_code == 400
    error = duplicate.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert "已被使用" in error["fields"]["username"]


@pytest.mark.parametrize(
    ("password", "fragment"),
    [
        ("Abc123!@#", "at least 10"),
        ("1234567890", "只包含数字"),
        ("password123", "太常见"),
    ],
)
def test_weak_passwords_are_rejected(api_client, password, fragment):
    """[INT-AUTH-03][I02-T01] 过短 / 纯数字 / 常见密码逐类被拒。"""
    response = api_client.post(
        REGISTER_URL,
        {"username": unique_username("weak"), "password": password},
        format="json",
    )

    assert response.status_code == 400
    fields = response.json()["error"]["fields"]
    assert fragment in fields["password"]


def test_refresh_rotates_access_and_cookie(api_client, make_user):
    """[INT-AUTH-04][I02-T02] refresh 换新 access，并旋转 refresh Cookie。"""
    user = make_user()
    login = _login(api_client, user.username)
    assert login.status_code == 200
    old_access = login.json()["data"]["access"]
    old_refresh = _refresh_cookie(api_client)

    response = api_client.post(REFRESH_URL, {}, format="json", **_csrf(api_client))

    assert response.status_code == 200, response.content
    new_access = response.json()["data"]["access"]
    assert new_access and new_access != old_access
    assert _refresh_cookie(api_client) != old_refresh
    assert api_client.get(ME_URL, **_bearer(new_access)).status_code == 200


def test_reusing_rotated_refresh_token_is_rejected(api_client, make_user):
    """[INT-AUTH-05][I02-T02] 已旋转的旧 refresh 复用返回 401，且有黑名单记录。"""
    user = make_user()
    login = _login(api_client, user.username)
    assert login.status_code == 200
    old_refresh = _refresh_cookie(api_client)

    rotated = api_client.post(REFRESH_URL, {}, format="json", **_csrf(api_client))
    assert rotated.status_code == 200
    assert BlacklistedToken.objects.count() >= 1

    api_client.cookies["refresh_token"] = old_refresh
    reused = api_client.post(REFRESH_URL, {}, format="json", **_csrf(api_client))

    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "UNAUTHORIZED"


def test_refresh_and_logout_require_csrf(api_client, make_user):
    """[INT-AUTH-06][I02-T02] 缺 X-CSRFToken 时 refresh / logout 均 403。"""
    user = make_user()
    assert _login(api_client, user.username).status_code == 200

    refresh = api_client.post(REFRESH_URL, {}, format="json")
    logout = api_client.post(LOGOUT_URL, {}, format="json")

    for response in (refresh, logout):
        assert response.status_code == 403, response.content
        assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_logout_invalidates_access_and_refresh(api_client, make_user):
    """[INT-AUTH-07][I02-T02] 登出提升 auth_version，旧 access 与旧 refresh 失效。"""
    user = make_user()
    login = _login(api_client, user.username)
    access = login.json()["data"]["access"]
    refresh = _refresh_cookie(api_client)

    logout = api_client.post(LOGOUT_URL, {}, format="json", **_csrf(api_client))
    assert logout.status_code == 200
    assert logout.json()["data"]["logged_out"] is True

    assert api_client.get(ME_URL, **_bearer(access)).status_code == 401

    api_client.cookies["refresh_token"] = refresh
    stale = api_client.post(REFRESH_URL, {}, format="json", **_csrf(api_client))
    assert stale.status_code == 401
    assert stale.json()["error"]["code"] == "UNAUTHORIZED"


def test_password_change_kills_other_devices(make_user):
    """[INT-AUTH-08][I02-T03] A 设备改密后，B 设备的 access 与 refresh 均失效。"""
    user = make_user()
    device_a, device_b = APIClient(), APIClient()

    login_a = _login(device_a, user.username)
    login_b = _login(device_b, user.username)
    b_access = login_b.json()["data"]["access"]
    b_refresh = _refresh_cookie(device_b)

    changed = device_a.post(
        CHANGE_PASSWORD_URL,
        {"old_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        format="json",
        **_bearer(login_a.json()["data"]["access"]),
    )
    assert changed.status_code == 200, changed.content
    assert changed.json()["data"]["access"]

    assert device_b.get(ME_URL, **_bearer(b_access)).status_code == 401

    device_b.cookies["refresh_token"] = b_refresh
    refused = device_b.post(REFRESH_URL, {}, format="json", **_csrf(device_b))
    assert refused.status_code == 401
    assert refused.json()["error"]["code"] == "UNAUTHORIZED"
