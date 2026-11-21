"""购物车服务：写入路径统一在这里做可售性与数量校验。

为什么不在序列化器里做：可售性依赖 SKU 当前库存与商品状态，属于业务规则；
放在服务层才能被「结算」「创建订单」复用，避免同一规则写两遍后漂移。
"""
from django.db import IntegrityError, transaction
from rest_framework import status

from apps.catalog.models import SKU
from common.exceptions import BusinessError

from .models import MAX_QUANTITY, MIN_QUANTITY, CartItem


def _get_or_create_locked(user, sku, quantity: int, selected: bool):
    """同 SKU 只有一行；两个并发 POST 撞唯一约束时回退为更新，而不是报 500。"""
    try:
        with transaction.atomic():
            return CartItem.objects.select_for_update().get_or_create(
                user=user, sku=sku, defaults={"quantity": quantity, "selected": selected}
            )
    except IntegrityError:
        return CartItem.objects.select_for_update().get(user=user, sku=sku), False


def _sellable_sku(sku_id: str) -> SKU:
    """取 SKU 并校验「可加入购物车」。下架商品与停用 SKU 一律拒绝。"""
    sku = SKU.objects.select_related("product").filter(pk=sku_id).first()
    if sku is None:
        raise BusinessError("SKU_NOT_FOUND", "商品规格不存在", status.HTTP_404_NOT_FOUND)
    product = sku.product
    if not sku.is_active or product.status != product.Status.ACTIVE:
        raise BusinessError("SKU_UNAVAILABLE", "该商品已下架，无法加入购物车", status.HTTP_400_BAD_REQUEST)
    return sku


def _validate_quantity(quantity: int) -> int:
    if quantity < MIN_QUANTITY or quantity > MAX_QUANTITY:
        raise BusinessError(
            "INVALID_QUANTITY",
            f"数量需在 {MIN_QUANTITY} 至 {MAX_QUANTITY} 之间",
            status.HTTP_400_BAD_REQUEST,
        )
    return quantity


@transaction.atomic
def put_item(user, sku_id: str, quantity: int, selected: bool = True) -> CartItem:
    """新增或更新购物车项：同 SKU 只有一行，数量按「设置为指定值」处理。"""
    quantity = _validate_quantity(quantity)
    sku = _sellable_sku(sku_id)
    if sku.stock_available < quantity:
        raise BusinessError(
            "INSUFFICIENT_STOCK",
            f"库存不足，当前仅剩 {sku.stock_available} 件",
            status.HTTP_400_BAD_REQUEST,
        )

    item, created = _get_or_create_locked(user, sku, quantity, selected)
    if not created:
        item.quantity = quantity
        item.selected = selected
        item.save(update_fields=["quantity", "selected", "updated_at"])
    return item


@transaction.atomic
def patch_item(user, item: CartItem, *, quantity=None, selected=None) -> CartItem:
    """部分更新。越权由视图层的 queryset 过滤保证（拿不到别人的行）。"""
    if quantity is not None:
        quantity = _validate_quantity(quantity)
        if item.sku.stock_available < quantity:
            raise BusinessError(
                "INSUFFICIENT_STOCK",
                f"库存不足，当前仅剩 {item.sku.stock_available} 件",
                status.HTTP_400_BAD_REQUEST,
            )
        item.quantity = quantity
    if selected is not None:
        item.selected = selected
    item.save()
    return item


def remove_item(user, item: CartItem) -> None:
    item.delete()
