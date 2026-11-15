"""[INT-CAT-*][I03-T02/T05] 商品目录集成用例。

覆盖游客可见范围、分类/关键词筛选、四种白名单排序、非法排序、下架详情，
以及后台改分类/改价后缓存立即失效。数据全部由用例自建，不依赖 seed_demo。
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.contrib import admin
from django.core.cache import cache
from django.test import RequestFactory

from apps.catalog.admin import CategoryAdmin, SKUAdmin
from apps.catalog.models import Category, Product, SKU

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/products/"
DETAIL_URL = "/api/v1/products/{pk}/"
CATEGORIES_URL = "/api/v1/categories/"


@pytest.fixture(autouse=True)
def _clean_cache():
    """分类列表有 60 秒缓存，逐例清空避免相互污染。"""
    cache.clear()
    yield
    cache.clear()


def make_category(name: str = "数码", **extra) -> Category:
    return Category.objects.create(
        name=name, slug=f"cat-{uuid.uuid4().hex[:8]}", **extra
    )


def make_product(
    category: Category,
    title: str,
    *,
    status: str = Product.Status.ACTIVE,
    skus: tuple[tuple[str, str], ...] = (),
    **extra,
) -> Product:
    product = Product.objects.create(
        category=category,
        title=title,
        slug=f"p-{uuid.uuid4().hex[:10]}",
        status=status,
        **extra,
    )
    for price in skus:
        SKU.objects.create(
            product=product,
            sku_code=f"sku-{uuid.uuid4().hex[:8]}",
            price=Decimal(price),
            stock_total=10,
        )
    return product


def titles(response) -> list[str]:
    return [item["title"] for item in response.json()["data"]["items"]]


def test_guest_sees_only_active_products(api_client):
    """[INT-CAT-01][I03-T02] 游客列表只含 active，草稿与下架不可见。"""
    category = make_category()
    visible = make_product(category, "可见商品")
    make_product(category, "草稿商品", status=Product.Status.DRAFT)
    make_product(category, "已下架商品", status=Product.Status.ARCHIVED)

    response = api_client.get(LIST_URL)

    assert response.status_code == 200, response.content
    assert titles(response) == [visible.title]
    assert response.json()["data"]["total"] == 1


def test_filter_by_category_slug(api_client):
    """[INT-CAT-02][I03-T02] category 参数只返回该分类下的上架商品。"""
    phones = make_category("手机")
    books = make_category("图书")
    make_product(phones, "手机 A")
    make_product(books, "图书 A")

    response = api_client.get(LIST_URL, {"category": phones.slug})

    assert response.status_code == 200
    assert titles(response) == ["手机 A"]


def test_keyword_search_is_case_insensitive(api_client):
    """[INT-CAT-03][I03-T02] 关键词命中标题或副标题，且不区分大小写。"""
    category = make_category()
    make_product(category, "Galaxy Phone X")
    make_product(category, "Nebula Tablet", subtitle="Galaxy 生态配件")
    make_product(category, "Unrelated Item")

    by_title = api_client.get(LIST_URL, {"keyword": "GALAXY PHONE"})
    by_subtitle = api_client.get(LIST_URL, {"keyword": "galaxy 生态"})
    miss = api_client.get(LIST_URL, {"keyword": "not-exist-keyword"})

    assert titles(by_title) == ["Galaxy Phone X"]
    assert titles(by_subtitle) == ["Nebula Tablet"]
    assert titles(miss) == []


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("newest", ["贵商品", "中商品", "便宜商品"]),
        ("oldest", ["便宜商品", "中商品", "贵商品"]),
        ("price_asc", ["便宜商品", "中商品", "贵商品"]),
        ("price_desc", ["贵商品", "中商品", "便宜商品"]),
    ],
)
def test_whitelisted_sort_orders(api_client, sort, expected):
    """[INT-CAT-04][I03-T02] 四种白名单排序顺序正确。"""
    category = make_category()
    make_product(category, "便宜商品", skus=("10.00",))
    make_product(category, "中商品", skus=("20.00",))
    make_product(category, "贵商品", skus=("30.00",))

    response = api_client.get(LIST_URL, {"sort": sort})

    assert response.status_code == 200, response.content
    assert titles(response) == expected


def test_non_whitelisted_sort_is_rejected(api_client):
    """[INT-CAT-05][I03-T02] 非白名单排序返回 400 INVALID_SORT。"""
    response = api_client.get(LIST_URL, {"sort": "rating"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_SORT"


def test_detail_hides_archived_and_exposes_no_stock(api_client):
    """[INT-CAT-06][I03-T02] 下架详情 404；无 SKU 商品不暴露库存字段。"""
    category = make_category()
    archived = make_product(
        category, "下架商品", status=Product.Status.ARCHIVED, skus=("10.00",)
    )
    no_sku = make_product(category, "无规格商品")

    hidden = api_client.get(DETAIL_URL.format(pk=archived.pk))
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "NOT_FOUND"

    detail = api_client.get(DETAIL_URL.format(pk=no_sku.pk))
    assert detail.status_code == 200, detail.content
    body = detail.json()["data"]
    assert body["skus"] == []
    assert body["price_min"] == "0.00"
    assert "stock_total" not in body
    assert "stock_available" not in body
    assert "status" not in body


def test_admin_category_change_invalidates_cache(api_client):
    """[INT-CAT-07][I03-T05] 后台改分类名后立即生效，不等 60 秒 TTL。"""
    category = make_category("旧名称")
    first = api_client.get(CATEGORIES_URL)
    assert [item["name"] for item in first.json()["data"]] == ["旧名称"]

    category.name = "新名称"
    CategoryAdmin(Category, admin.site).save_model(
        RequestFactory().get("/admin/"), category, None, change=True
    )

    second = api_client.get(CATEGORIES_URL)
    assert [item["name"] for item in second.json()["data"]] == ["新名称"]


def test_admin_price_change_is_visible_immediately(api_client):
    """[INT-CAT-07][I03-T05] 后台改 SKU 价格后立即 GET 即见新价。"""
    category = make_category()
    product = make_product(category, "改价商品", skus=("10.00",))
    sku = product.skus.first()

    before = api_client.get(DETAIL_URL.format(pk=product.pk))
    assert before.json()["data"]["price_min"] == "10.00"

    sku.price = Decimal("88.50")
    SKUAdmin(SKU, admin.site).save_model(
        RequestFactory().get("/admin/"), sku, None, change=True
    )

    after = api_client.get(DETAIL_URL.format(pk=product.pk))
    assert after.json()["data"]["price_min"] == "88.50"
