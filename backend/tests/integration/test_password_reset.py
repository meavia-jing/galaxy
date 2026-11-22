"""[INT-AUTH-09~11][I02-T03] 后台人工重置密码、AuditLog 与强制改密。

管理员通过 Django Admin action 重置密码后：
1. 旧密码立即失效，旧 access/refresh 全部失效（auth_version+1）；
2. 用户被标记 must_change_password，只能访问 /users/me/ 与改密接口；
3. 审计日志只追加，记录操作人、资源与脱敏后的变更（密码记为 ***）。
"""
from __future__ import annotations

import secrets

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog
from tests.conftest import DEFAULT_PASSWORD, unique_username

pytestmark = pytest.mark.django_db

User = get_user_model()
LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
CSRF_URL = "/api/v1/auth/csrf/"
ME_URL = "/api/v1/users/me/"
ADDRESSES_URL = "/api/v1/addresses/"
CHANGE_PASSWORD_URL = "/api/v1/users/me/change-password/"
ADMIN_USERS_URL = "/admin/accounts/user/"

TEMPORARY_PASSWORD = "TempPass2026x"
NEW_PASSWORD = "FreshPass2026x"


@pytest.fixture
def admin_user(make_user):
    return make_user(
        username=unique_username("admin"),
        role=User.Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def admin_client(admin_user) -> Client:
    client = Client()
    client.force_login(admin_user)
    return client


def _login(client: APIClient, username: str, password: str):
    return client.post(LOGIN_URL, {"username": username, "password": password}, format="json")


def _csrf(client: APIClient) -> dict:
    client.get(CSRF_URL)
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _bearer(access: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access}"}


def _reset_via_admin(client: Client, user, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "token_urlsafe", lambda _size: TEMPORARY_PASSWORD)
    response = client.post(
        ADMIN_USERS_URL,
        {
            "action": "reset_password",
            "_selected_action": [str(user.pk)],
        },
        follow=True,
    )
    assert response.status_code == 200, response.content


def test_admin_reset_writes_audit_and_shows_password_once(
    admin_client, admin_user, make_user, monkeypatch
):
    """[INT-AUTH-09][I02-T03] 重置生成随机临时密码、强制改密并写审计。"""
    target = make_user()
    previous_version = target.auth_version

    _reset_via_admin(admin_client, target, monkeypatch)

    target.refresh_from_db()
    assert target.must_change_password is True
    assert target.auth_version == previous_version + 1
    assert target.check_password(TEMPORARY_PASSWORD)
    assert not target.check_password(DEFAULT_PASSWORD)

    log = AuditLog.objects.get(action="user.password_reset", resource_id=str(target.pk))
    assert log.actor_id == admin_user.pk
    assert log.resource_type == "user"
    assert log.request_id
    assert log.changes["password"] == "***"
    assert log.changes["must_change_password"] is True
    assert log.changes["auth_version"] == {
        "from": previous_version,
        "to": previous_version + 1,
    }


def test_pending_password_change_only_allows_identity_and_change(
    api_client, make_user, monkeypatch
):
    """[INT-AUTH-10][I02-T03] 临时密码登录后业务接口 403，改密后恢复。"""
    user = make_user()
    admin = make_user(
        username=unique_username("admin"),
        role=User.Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )
    admin_client = Client()
    admin_client.force_login(admin)
    _reset_via_admin(admin_client, user, monkeypatch)

    login = _login(api_client, user.username, TEMPORARY_PASSWORD)
    assert login.status_code == 200, login.content
    payload = login.json()["data"]
    assert payload["must_change_password"] is True
    access = payload["access"]

    identity = api_client.get(ME_URL, **_bearer(access))
    assert identity.status_code == 200
    assert identity.json()["data"]["must_change_password"] is True

    blocked = api_client.get(ADDRESSES_URL, **_bearer(access))
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "FORBIDDEN"

    blocked_patch = api_client.patch(ME_URL, {"nickname": "改名"}, format="json", **_bearer(access))
    assert blocked_patch.status_code == 403

    changed = api_client.post(
        CHANGE_PASSWORD_URL,
        {"old_password": TEMPORARY_PASSWORD, "new_password": NEW_PASSWORD},
        format="json",
        **_bearer(access),
    )
    assert changed.status_code == 200, changed.content
    assert changed.json()["data"]["user"]["must_change_password"] is False

    user.refresh_from_db()
    assert user.must_change_password is False

    new_access = changed.json()["data"]["access"]
    assert api_client.get(ADDRESSES_URL, **_bearer(new_access)).status_code == 200
    # 改密同时提升 auth_version，旧 access 立即失效
    assert api_client.get(ME_URL, **_bearer(access)).status_code == 401


def test_admin_reset_invalidates_existing_sessions(
    admin_client, api_client, make_user, monkeypatch
):
    """[INT-AUTH-11][I02-T03] 重置后旧 access 与旧 refresh 均失效。"""
    user = make_user()
    login = _login(api_client, user.username, DEFAULT_PASSWORD)
    assert login.status_code == 200, login.content
    old_access = login.json()["data"]["access"]
    old_refresh = api_client.cookies["refresh_token"].value

    _reset_via_admin(admin_client, user, monkeypatch)

    assert api_client.get(ME_URL, **_bearer(old_access)).status_code == 401

    api_client.cookies["refresh_token"] = old_refresh
    refreshed = api_client.post(REFRESH_URL, {}, format="json", **_csrf(api_client))
    assert refreshed.status_code == 401
    assert refreshed.json()["error"]["code"] == "UNAUTHORIZED"
