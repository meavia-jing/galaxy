"""[INT-ADR-*][I02-T04] 地址默认项与上限的并发证据。

`django.test.TestCase` 把用例包在事务里并回滚，`select_for_update()` 不会与
自身阻塞，无法证明行锁生效。本模块用 `transaction=True`（等价
`transactional_db`）让每个线程持有独立连接，真实并发争抢同一用户行。
"""
from __future__ import annotations

import threading
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import connections

from apps.accounts.models import Address
from apps.accounts.services import create_address, delete_address, update_address
from common.exceptions import BusinessError

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]

ADDRESS = {
    "recipient": "并发用户",
    "phone": "13900139000",
    "province": "广东省",
    "city": "深圳市",
    "district": "福田区",
    "detail": "并发路 1 号",
}
TIMEOUT = 20

User = get_user_model()


def make_user() -> User:
    return User.objects.create_user(
        username=f"conc_{uuid.uuid4().hex[:12]}", password="Concurrency2026!"
    )


def make_address(user, **overrides) -> Address:
    data = dict(ADDRESS)
    data.update(overrides)
    return Address.objects.create(user=user, **data)


def run_concurrently(*calls):
    """同时启动所有 callable，返回 [(status, value_or_exception), ...]。"""
    barrier = threading.Barrier(len(calls))
    results: list[tuple[str, object] | None] = [None] * len(calls)

    def worker(index: int, call) -> None:
        try:
            barrier.wait(timeout=TIMEOUT)
            results[index] = ("ok", call())
        except Exception as exc:  # noqa: BLE001 - 结果里保留异常供断言
            results[index] = ("error", exc)
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=worker, args=(index, call), daemon=True)
        for index, call in enumerate(calls)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=TIMEOUT)

    assert not any(thread.is_alive() for thread in threads), "线程超时，疑似死锁"
    return results


def test_int_adr_01_first_address_is_default_in_real_db():
    """[INT-ADR-01][I02-T04] 首个地址在真实库路径自动成为唯一默认项。"""
    user = make_user()

    address = create_address(user, dict(ADDRESS))

    assert address.is_default is True
    assert Address.objects.filter(user=user, is_default=True).count() == 1


def test_int_adr_02_concurrent_default_switch_keeps_exactly_one():
    """[INT-ADR-02][I02-T04] 两线程同时设不同地址为默认，最终恰好一条默认。"""
    user = make_user()
    first = make_address(user, is_default=True)
    second = make_address(user)

    def switch(pk):
        def call():
            address = Address.objects.get(pk=pk)
            return update_address(user, address, {"is_default": True})

        return call

    results = run_concurrently(switch(first.pk), switch(second.pk))

    assert [status for status, _ in results] == ["ok", "ok"], results
    assert Address.objects.filter(user=user, is_default=True).count() == 1


def test_int_adr_03_cross_user_access_is_isolated():
    """[INT-ADR-03][I02-T04] 真实库下越权读写他人地址仍被隔离。"""
    from rest_framework.test import APIClient

    owner = make_user()
    intruder = make_user()
    address = make_address(owner)

    client = APIClient()
    client.force_authenticate(intruder)
    listed = client.get("/api/v1/addresses/")
    detail = client.get(f"/api/v1/addresses/{address.pk}/")
    patched = client.patch(
        f"/api/v1/addresses/{address.pk}/", {"recipient": "黑客"}, format="json"
    )

    assert listed.status_code == 200
    assert listed.json()["data"] == []
    assert detail.status_code == 404
    assert patched.status_code == 404
    address.refresh_from_db()
    assert address.recipient == "并发用户"


def test_int_adr_04_concurrent_delete_default_and_create():
    """[INT-ADR-04][I02-T04] 并发删除默认项并新增，仍保留唯一默认且总数正确。"""
    user = make_user()
    default = make_address(user, is_default=True)
    make_address(user)

    def delete_default():
        address = Address.objects.get(pk=default.pk)
        delete_address(user, address)

    def add_address():
        return create_address(user, dict(ADDRESS, recipient="并发新增"))

    results = run_concurrently(delete_default, add_address)

    assert [status for status, _ in results] == ["ok", "ok"], results
    assert Address.objects.filter(user=user).count() == 2
    assert Address.objects.filter(user=user, is_default=True).count() == 1


def test_int_adr_05_concurrent_creates_respect_the_limit():
    """[INT-ADR-05][I02-T04] 已有 19 条时并发新增，只允许 1 条成功。"""
    user = make_user()
    for index in range(19):
        make_address(user, recipient=f"存量{index}")

    calls = [
        (lambda index=index: create_address(user, dict(ADDRESS, recipient=f"并发{index}")))
        for index in range(4)
    ]

    results = run_concurrently(*calls)

    successes = [value for status, value in results if status == "ok"]
    failures = [value for status, value in results if status == "error"]
    assert len(successes) == 1, results
    assert len(failures) == 3, results
    assert all(
        isinstance(exc, BusinessError)
        and exc.detail["error"]["code"] == "ADDRESS_LIMIT"
        for exc in failures
    )
    assert Address.objects.filter(user=user).count() == 20
