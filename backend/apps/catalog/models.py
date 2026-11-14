"""Catalog domain: Category -> Product (SPU) -> SKU."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Category(models.Model):
    parent = models.ForeignKey(
        "self", verbose_name="上级分类", null=True, blank=True,
        on_delete=models.PROTECT, related_name="children",
    )
    name = models.CharField("名称", max_length=64)
    slug = models.SlugField("标识", max_length=64, unique=True)
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_category"
        verbose_name = "分类"
        verbose_name_plural = "分类"
        ordering = ["sort_order", "id"]
        # 注意：MariaDB 11.5+ 不允许 CHECK 约束引用 AUTO_INCREMENT 列 id，
        # 因此「父分类不能是自己」放在 model.clean() 与 admin 校验中实现。

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "父分类不能是自己"})
        # 禁止循环：沿父链向上查找不能回到自己
        ancestor = self.parent
        seen = 0
        while ancestor is not None:
            seen += 1
            if seen > 10:
                raise ValidationError({"parent": "分类层级异常，疑似循环引用"})
            if self.pk and ancestor.pk == self.pk:
                raise ValidationError({"parent": "不能形成循环分类"})
            ancestor = ancestor.parent


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ACTIVE = "active", "已上架"
        ARCHIVED = "archived", "已下架"

    category = models.ForeignKey(
        Category, verbose_name="分类", on_delete=models.PROTECT, related_name="products"
    )
    title = models.CharField("标题", max_length=200)
    slug = models.SlugField("标识", max_length=200, unique=True)
    subtitle = models.CharField("副标题", max_length=200, blank=True, default="")
    description = models.TextField("描述", blank=True, default="")
    status = models.CharField(
        "状态", max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    is_featured = models.BooleanField("首页推荐", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_product"
        verbose_name = "商品"
        verbose_name_plural = "商品"
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["category", "status"], name="catalog_prod_cat_status_idx"),
            models.Index(fields=["status", "-created_at"], name="catalog_prod_status_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def cover_image(self):
        return self.images.order_by("sort_order", "id").first()


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, verbose_name="商品", on_delete=models.CASCADE, related_name="images"
    )
    path = models.CharField("图片地址", max_length=500)
    alt_text = models.CharField("替代文本", max_length=200, blank=True, default="")
    sort_order = models.IntegerField("排序", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "catalog_product_image"
        verbose_name = "商品图片"
        verbose_name_plural = "商品图片"
        ordering = ["sort_order", "id"]
        indexes = [models.Index(fields=["product", "sort_order"], name="catalog_img_prod_idx")]


class SKU(models.Model):
    product = models.ForeignKey(
        Product, verbose_name="商品", on_delete=models.CASCADE, related_name="skus"
    )
    sku_code = models.CharField("SKU 编码", max_length=64, unique=True)
    attributes = models.JSONField("规格", default=dict, blank=True)
    price = models.DecimalField(
        "价格", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    stock_total = models.PositiveIntegerField("库存总量", default=0)
    stock_reserved = models.PositiveIntegerField("占用库存", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_sku"
        verbose_name = "SKU"
        verbose_name_plural = "SKU"
        ordering = ["price", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(stock_reserved__lte=F("stock_total")),
                name="catalog_sku_reserved_lte_total",
            ),
            models.CheckConstraint(
                condition=Q(price__gte=0), name="catalog_sku_price_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.sku_code}"

    @property
    def stock_available(self) -> int:
        return max(self.stock_total - self.stock_reserved, 0)

    @property
    def attributes_text(self) -> str:
        return " / ".join(f"{key}: {value}" for key, value in (self.attributes or {}).items())
