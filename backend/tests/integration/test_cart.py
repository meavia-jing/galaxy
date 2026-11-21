"""I04-T01 购物车：同 SKU 合并、数量边界、越权隔离、下架/缺货提示。

每条 docstring 首行格式：``[用例ID][任务ID] 验证点``（用例矩阵 §9 规则 3）。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.cart.models import CartItem
from apps.catalog.models import Category, Product, SKU

pytestmark = pytest.mark.django_db

CART_ITEMS_URL = "/api/v1/cart-items/"


@pytest.fixture
def category(db):
    return Category.objects.create(name="测试分类", slug="test-cat-cart")


@pytest.fixture
def product(category):
    return Product.objects.create(
        category=category,
        title="测试商品",
        slug="test-product-cart",
        status=Product.Status.ACTIVE,
    )


@pytest.fixture
def sku(product):
    return SKU.objects.create(
        product=product, sku_code="CART-SKU-1", price=Decimal("99.00"), stock_total=10
    )


def test_same_sku_keeps_single_row(auth_client, user, sku):
    """[INT-CART-01][I04-T01] 同用户同 SKU 重复加入只保留一行。"""
    for quantity in (1, 3, 5):
        response = auth_client.post(
            CART_ITEMS_URL, {"sku_id": str(sku.pk), "quantity": quantity}, format="json"
        )
        assert response.status_code == 201

    assert CartItem.objects.filter(user=user).count() == 1
    row = CartItem.objects.get(user=user)
    # 数量是「设置为指定值」，不是累加：1 → 3 → 5 而不是 9。
    assert row.quantity == 5


def test_quantity_bounds(auth_client, user, sku):
    """[INT-CART-02][I04-T01] 数量超出 1..99 被拒且不入库。"""
    too_small = auth_client.post(
        CART_ITEMS_URL, {"sku_id": str(sku.pk), "quantity": 0}, format="json"
    )
    assert too_small.status_code == 400
    assert "quantity" in too_small.data["error"]["fields"]

    too_large = auth_client.post(
        CART_ITEMS_URL, {"sku_id": str(sku.pk), "quantity": 100}, format="json"
    )
    assert too_large.status_code == 400
    assert too_large.data["error"]["code"] == "INVALID_QUANTITY"

    assert CartItem.objects.filter(user=user).count() == 0


def test_other_user_cart_is_invisible(auth_client, make_user, sku):
    """[INT-CART-03][I04-T01] A 不可读取、修改、删除 B 的购物车项。"""
    owner = make_user()
    item = CartItem.objects.create(user=owner, sku=sku, quantity=2)

    assert auth_client.get(CART_ITEMS_URL).data == []

    patch = auth_client.patch(f"{CART_ITEMS_URL}{item.pk}/", {"quantity": 9}, format="json")
    assert patch.status_code == 404

    delete = auth_client.delete(f"{CART_ITEMS_URL}{item.pk}/")
    assert delete.status_code == 404

    item.refresh_from_db()
    assert item.quantity == 2


def test_unavailable_product_is_reported_not_silently_allowed(auth_client, user, sku):
    """[INT-CART-04][I04-T01] 下架商品不能加入；已在车内的下架项要给出原因且不可结算。"""
    product = sku.product
    product.status = Product.Status.ARCHIVED
    product.save(update_fields=["status"])

    rejected = auth_client.post(
        CART_ITEMS_URL, {"sku_id": str(sku.pk), "quantity": 1}, format="json"
    )
    assert rejected.status_code == 400
    assert rejected.data["error"]["code"] == "SKU_UNAVAILABLE"

    # 下架前已入车：列表仍可见，但标记 available=false 且给出原因。
    product.status = Product.Status.ACTIVE
    product.save(update_fields=["status"])
    CartItem.objects.create(user=user, sku=sku, quantity=1)
    product.status = Product.Status.ARCHIVED
    product.save(update_fields=["status"])

    summary = auth_client.get("/api/v1/cart/")
    assert summary.status_code == 200
    assert summary.data["has_unavailable"] is True
    assert summary.data["selected_count"] == 0
    assert summary.data["items"][0]["available"] is False
    assert summary.data["items"][0]["unavailable_reason"] == "商品已下架"


def test_out_of_stock_is_blocked(auth_client, user, sku):
    """[INT-CART-05][I04-T01] 库存不足时拒绝，并提示剩余数量。"""
    sku.stock_total = 2
    sku.save(update_fields=["stock_total"])

    response = auth_client.post(
        CART_ITEMS_URL, {"sku_id": str(sku.pk), "quantity": 3}, format="json"
    )
    assert response.status_code == 400
    assert response.data["error"]["code"] == "INSUFFICIENT_STOCK"
    assert "2" in response.data["error"]["message"]


def test_summary_subtotal_uses_server_price(auth_client, sku):
    """[INT-CART-06][I04-T01] 小计由服务端按 SKU 现价计算，前端传什么都不影响。"""
    auth_client.post(
        CART_ITEMS_URL,
        {"sku_id": str(sku.pk), "quantity": 2, "unit_price": "0.01"},
        format="json",
    )

    summary = auth_client.get("/api/v1/cart/")
    assert summary.data["subtotal"] == "198.00"
    assert summary.data["selected_count"] == 1


def test_delete_removes_row(auth_client, sku):
    """[INT-CART-07][I04-T01] 删除购物车项后列表为空。"""
    created = auth_client.post(
        CART_ITEMS_URL, {"sku_id": str(sku.pk), "quantity": 1}, format="json"
    )
    item_id = created.data["id"]

    assert auth_client.delete(f"{CART_ITEMS_URL}{item_id}/").status_code == 204
    assert auth_client.get(CART_ITEMS_URL).data == []
