"""[INT-CMS-*][I03-T04] CMS 内容页可见性集成用例。

草稿与撤回对公开接口不可见，发布后立即可读。Redis 停机回源见
``test_error_contract.py`` 的 INT-CMS-04。
"""
from __future__ import annotations

import pytest

from apps.cms.models import ContentPage, PublishStatus

pytestmark = pytest.mark.django_db

PAGE_URL = "/api/v1/pages/{slug}/"


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
