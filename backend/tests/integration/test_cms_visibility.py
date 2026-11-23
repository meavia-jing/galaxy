"""[INT-CMS-*][I03-T04] CMS 内容页可见性集成用例。

草稿与撤回对公开接口不可见，发布后立即可读。Redis 停机回源见
``test_error_contract.py`` 的 INT-CMS-04。
"""
from __future__ import annotations

import pytest
from django.core.cache import cache

from apps.cms.models import Banner, ContentPage, PublishStatus
from apps.cms.views import BANNER_CACHE_KEY, CACHE_TTL
from tests.support.cache_timetravel import remaining_ttl, require_locmem, travel

pytestmark = pytest.mark.django_db

PAGE_URL = "/api/v1/pages/{slug}/"
BANNERS_URL = "/api/v1/banners/"


@pytest.fixture(autouse=True)
def _clean_cache():
    """横幅列表有 60 秒缓存，逐例清空避免相互污染。"""
    cache.clear()
    yield
    cache.clear()


def make_page(slug: str, status: str, body: str = "正文内容") -> ContentPage:
    return ContentPage.objects.create(slug=slug, title=f"页面-{slug}", body=body, status=status)


def test_draft_page_is_not_public(api_client):
    """[INT-CMS-01][I03-T04] 草稿页面公开访问返回 404。"""
    page = make_page("draft-page", PublishStatus.DRAFT)

    response = api_client.get(PAGE_URL.format(slug=page.slug))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_published_page_is_readable(api_client):
    """[INT-CMS-02][I03-T04] 发布后立即返回 200，正文可见。"""
    page = make_page("about-us", PublishStatus.DRAFT, body="关于我们正文")
    page.status = PublishStatus.PUBLISHED
    page.save(update_fields=["status", "updated_at"])

    response = api_client.get(PAGE_URL.format(slug=page.slug))

    assert response.status_code == 200, response.content
    body = response.json()["data"]
    assert body["title"] == page.title
    assert body["body"] == "关于我们正文"


def test_withdrawn_page_disappears_immediately(api_client):
    """[INT-CMS-03][I03-T04] 撤回后立即 404，无需等待缓存过期。"""
    page = make_page("promo", PublishStatus.PUBLISHED)
    assert api_client.get(PAGE_URL.format(slug=page.slug)).status_code == 200

    page.status = PublishStatus.WITHDRAWN
    page.save(update_fields=["status", "updated_at"])

    response = api_client.get(PAGE_URL.format(slug=page.slug))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    '<img src=x onerror="alert(1)">',
    '<a href="javascript:alert(1)">click</a>',
    "<iframe src=\"https://evil.example.com\"></iframe>",
    "<style>body{display:none}</style>",
    '<svg onload="alert(1)"></svg>',
    "<div onclick=\"alert(1)\">点我</div>",
]


def test_model_save_sanitizes_body():
    """[INT-CMS-05][I03-T04] 任何写入路径经模型 save() 都会被净化。"""
    page = make_page("xss-save", PublishStatus.PUBLISHED, body="<p>正常</p><script>alert(1)</script>")

    page.refresh_from_db()

    assert page.body == "<p>正常</p>"


def test_public_page_never_returns_script(api_client):
    """[INT-CMS-06][I03-T04] 攻击载荷入库后，公开接口输出不含可执行片段。"""
    page = make_page("xss-public", PublishStatus.PUBLISHED, body="".join(XSS_PAYLOADS))

    response = api_client.get(PAGE_URL.format(slug=page.slug))

    assert response.status_code == 200
    body = response.json()["data"]["body"]
    assert "<script" not in body
    assert "onerror" not in body
    assert "javascript:" not in body
    assert "<iframe" not in body
    assert "<svg" not in body
    assert "onclick" not in body
    # 文本内容保留，只去掉危险外壳
    assert "点我" in body and "click" in body


def test_legacy_row_is_sanitized_on_read(api_client):
    """[INT-CMS-07][I03-T04] 迁移前写入的原始 HTML，读侧仍要净化。"""
    page = make_page("legacy", PublishStatus.PUBLISHED, body="<p>旧数据</p>")
    # 绕过模型 save()，模拟净化上线前的历史行
    ContentPage.objects.filter(pk=page.pk).update(
        body="<p>旧数据</p><img src=x onerror=alert(1)>"
    )

    response = api_client.get(PAGE_URL.format(slug=page.slug))

    body = response.json()["data"]["body"]
    assert body.startswith("<p>旧数据</p>")
    assert "onerror" not in body


def test_normal_rich_text_round_trips(api_client):
    """[INT-CMS-08][I03-T04] 合法排版标签与链接不被误伤。"""
    rich = (
        "<h2>活动规则</h2>"
        "<p><strong>满减</strong>与<em>折扣</em>不叠加。</p>"
        '<ul><li>第一档</li><li>第二档</li></ul>'
        '<a href="/pages/faq/" title="常见问题">查看 FAQ</a>'
    )
    page = make_page("rich", PublishStatus.PUBLISHED, body=rich)

    response = api_client.get(PAGE_URL.format(slug=page.slug))

    body = response.json()["data"]["body"]
    assert "<h2>活动规则</h2>" in body
    assert "<strong>满减</strong>" in body
    assert "<em>折扣</em>" in body
    assert '<a href="/pages/faq/" title="常见问题"' in body
    assert body == page.body


# ---------------- 横幅 60 秒 TTL 兜底（时间旅行） ----------------


def make_banner(title: str) -> Banner:
    return Banner.objects.create(title=title, image_path="/media/demo/banner.png")


def test_banner_cache_ttl_is_really_60_seconds(api_client):
    """[INT-CMS-09][I03-T05] 横幅缓存写入 60 秒 TTL，不是永久也不是 0。"""
    require_locmem()
    assert CACHE_TTL == 60, "TTL 常量被改动，需同步验收文档与架构说明"

    make_banner("首屏轮播")
    assert api_client.get(BANNERS_URL).status_code == 200

    ttl = remaining_ttl(cache, BANNER_CACHE_KEY)
    assert ttl is not None, "横幅列表没有被缓存"
    assert 55 <= ttl <= 60, f"写入的 TTL 不是 60 秒，实际剩余 {ttl}"


def test_banner_cache_falls_back_after_60_seconds(api_client):
    """[INT-CMS-10][I03-T05] 时间旅行 61 秒：绕过 Admin 改库，改动也会自动可见。"""
    require_locmem()
    banner = make_banner("旧标题")
    assert [item["title"] for item in api_client.get(BANNERS_URL).json()["data"]] == ["旧标题"]

    # 直接改库，不触发 invalidate_cms_cache，模拟「失效钩子漏了」或进程刚重启
    Banner.objects.filter(pk=banner.pk).update(title="新标题")

    # 59 秒：还没到点，仍是旧值（证明缓存真的在起作用）
    with travel(59):
        assert [item["title"] for item in api_client.get(BANNERS_URL).json()["data"]] == [
            "旧标题"
        ]

    with travel(61):
        assert [item["title"] for item in api_client.get(BANNERS_URL).json()["data"]] == [
            "新标题"
        ]
