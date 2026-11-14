"""Address domain services.

Default-address bookkeeping must be serialized per user: every write locks the
user row first (``SELECT ... FOR UPDATE``), then rewrites ``is_default`` inside
the same transaction. That keeps "at most one default address per user" true
even when two requests switch defaults concurrently, on MariaDB and MySQL alike
(neither supports a partial unique index).
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status

from common.exceptions import BusinessError

from .models import Address

MAX_ADDRESSES_PER_USER = 20

User = get_user_model()


def _lock_user(user) -> None:
    """Serialize address writes for one user until the transaction commits."""
    User.objects.select_for_update().get(pk=user.pk)


def _promote_newest_default(user, exclude_pk: int | None = None) -> None:
    queryset = Address.objects.filter(user=user, is_default=False)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    candidate = queryset.order_by("-updated_at", "-id").first()
    if candidate is not None:
        Address.objects.filter(pk=candidate.pk).update(is_default=True)


@transaction.atomic
def create_address(user, data: dict) -> Address:
    _lock_user(user)
    existing = Address.objects.filter(user=user)
    count = existing.count()
    if count >= MAX_ADDRESSES_PER_USER:
        raise BusinessError(
            "ADDRESS_LIMIT",
            f"最多保存 {MAX_ADDRESSES_PER_USER} 个收货地址，请先删除不用的地址",
            status.HTTP_400_BAD_REQUEST,
        )

    want_default = bool(data.pop("is_default", False)) or count == 0
    address = Address.objects.create(user=user, is_default=False, **data)
    if want_default:
        existing.update(is_default=False)
        address.is_default = True
        address.save(update_fields=["is_default", "updated_at"])
    return address


@transaction.atomic
def update_address(user, address: Address, data: dict) -> Address:
    _lock_user(user)
    # 刷新被锁事务内的最新状态，避免并发切换默认地址时用旧值覆盖
    address.refresh_from_db()

    want_default = data.pop("is_default", None)
    for field, value in data.items():
        setattr(address, field, value)

    if want_default is True:
        Address.objects.filter(user=user).exclude(pk=address.pk).update(is_default=False)
        address.is_default = True
    elif want_default is False and address.is_default:
        # 不允许把唯一的默认地址直接取消：否则用户失去默认项
        if Address.objects.filter(user=user).exclude(pk=address.pk).exists():
            address.is_default = False
            _promote_newest_default(user, exclude_pk=address.pk)
        else:
            address.is_default = True

    address.save()
    return address


@transaction.atomic
def delete_address(user, address: Address) -> None:
    _lock_user(user)
    was_default = address.is_default
    address_pk = address.pk
    address.delete()
    if was_default:
        _promote_newest_default(user, exclude_pk=address_pk)
