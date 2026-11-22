"""CMS: banners and content pages (draft / published / withdrawn)."""
from django.db import models

from common.sanitizer import sanitize_html


class PublishStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    PUBLISHED = "published", "已发布"
    WITHDRAWN = "withdrawn", "已撤回"


class Banner(models.Model):
    title = models.CharField("标题", max_length=120)
    image_path = models.CharField("图片地址", max_length=500)
    target_url = models.CharField("跳转链接", max_length=500, blank=True, default="")
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cms_banner"
        verbose_name = "轮播"
        verbose_name_plural = "轮播"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.title


class ContentPage(models.Model):
    slug = models.SlugField("标识", max_length=64, unique=True)
    title = models.CharField("标题", max_length=200)
    body = models.TextField("正文", blank=True, default="")
    status = models.CharField(
        "状态", max_length=16, choices=PublishStatus.choices, default=PublishStatus.DRAFT
    )
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cms_content_page"
        verbose_name = "内容页面"
        verbose_name_plural = "内容页面"
        ordering = ["slug"]

    def save(self, *args, **kwargs):
        # 单一收口点：后台、shell、脚本任何写入路径都过同一净化函数。
        self.body = sanitize_html(self.body)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title
