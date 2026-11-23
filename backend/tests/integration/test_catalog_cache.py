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
from apps.catalog.models import Category, Product, ProductImage, SKU
from apps.catalog.views import CATEGORY_CACHE_KEY, CATEGORY_CACHE_TTL
from tests.support.cache_timetravel import remaining_ttl, require_locmem, travel

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


# ---------------- 60 秒 TTL 兜底（时间旅行） ----------------
#
# 前面几条证明「写入时主动失效」有效；这里证明「即使忘了失效、或进程重启后
# 缓存里还有旧值」，60 秒之后也一定会回源。两条路径是互补的兜底关系。


def test_category_cache_ttl_is_really_60_seconds(api_client):
    """[INT-CAT-09][I03-T05] 缓存条目真的带 60 秒 TTL，不是永久也不是 0。"""
    require_locmem()
    assert CATEGORY_CACHE_TTL == 60, "TTL 常量被改动，需同步验收文档与架构说明"

    make_category("分类")
    assert api_client.get(CATEGORIES_URL).status_code == 200

    ttl = remaining_ttl(cache, CATEGORY_CACHE_KEY)
    assert ttl is not None, "分类列表没有被缓存（缓存层失效）"
    assert 55 <= ttl <= 60, f"写入的 TTL 不是 60 秒，实际剩余 {ttl}"


def test_category_cache_still_serves_stale_within_ttl(api_client):
    """[INT-CAT-10][I03-T05] 30 秒内仍命中缓存（证明兜底不是「每次都回源」）。"""
    require_locmem()
    category = make_category("原名")
    assert api_client.get(CATEGORIES_URL).status_code == 200

    # 绕过 Admin 直接改库，不触发缓存失效，模拟「没人主动失效」的场景
    Category.objects.filter(pk=category.pk).update(name="改名")

    with travel(30):
        payload = api_client.get(CATEGORIES_URL).json()["data"]

    assert [item["name"] for item in payload] == ["原名"]


def test_category_cache_falls_back_after_60_seconds(api_client):
    """[INT-CAT-11][I03-T05] 时间旅行 61 秒：无任何失效操作，改动也自动可见。"""
    require_locmem()
    category = make_category("原名")
    assert api_client.get(CATEGORIES_URL).status_code == 200

    Category.objects.filter(pk=category.pk).update(name="改名")

    with travel(61):
        payload = api_client.get(CATEGORIES_URL).json()["data"]

    assert [item["name"] for item in payload] == ["改名"]
    # 回源后重新写回缓存（TTL 数值本身由 INT-CAT-09 断言，这里只证明「又存了」）
    assert remaining_ttl(cache, CATEGORY_CACHE_KEY) is not None


# ---------------- 列表查询次数不随商品数增长（N+1 防护） ----------------


def _seed_products(category: Category, count: int, offset: int = 0) -> None:
    for index in range(offset, offset + count):
        product = make_product(category, f"批量商品{index}", skus=("10.00", "20.00"))
        ProductImage.objects.create(
            product=product, path=f"/media/demo/bulk-{index}.png", sort_order=0
        )


def _list_queries(api_client) -> tuple[int, int]:
    """清空缓存后请求一次列表，返回（SQL 条数，返回的 total）。"""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    cache.clear()
    with CaptureQueriesContext(connection) as ctx:
        response = api_client.get(LIST_URL, {"sort": "price_asc"})
    return len(ctx), response.json()["data"]["total"]


def test_list_query_count_is_constant(api_client):
    """[INT-CAT-12][I03-T05] 商品数 3 → 12，列表 SQL 条数不变（无 N+1）。

    列表每行要取分类名、最低/最高价、首图；若 select_related/prefetch_related
    写漏，查询数会随行数线性增长。这里比较 4 倍数据量前后的 SQL 条数。
    """
    category = make_category()
    _seed_products(category, 3)
    small_queries, small_total = _list_queries(api_client)

    _seed_products(category, 9, offset=3)  # 总数 12，是前者的 4 倍
    big_queries, big_total = _list_queries(api_client)

    assert (small_total, big_total) == (3, 12)
    assert big_queries == small_queries, (
        f"查询数随商品数增长：3 条 {small_queries} 次 → 12 条 {big_queries} 次"
    )
    # 绝对上界：计数 + 主查询 + 分类/规格/图片预取，超过就是写漏了预取
    assert big_queries <= 8, f"列表用掉 {big_queries} 条 SQL，疑似 N+1"


def test_detail_query_count_is_constant(api_client):
    """[INT-CAT-13][I03-T05] 详情页规格数与查询次数无关（首个/第五个 SKU 同价）。"""
    category = make_category()
    one = make_product(category, "单规格商品", skus=("10.00",))
    many = make_product(category, "多规格商品", skus=("10.00", "20.00", "30.00", "40.00", "50.00"))
    ProductImage.objects.create(product=many, path="/media/demo/many.png")

    def queries_for(pk: int) -> int:
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            assert api_client.get(DETAIL_URL.format(pk=pk)).status_code == 200
        return len(ctx)

    assert queries_for(many.pk) == queries_for(one.pk)
