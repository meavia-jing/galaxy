"""Public catalog queries. Only on-shelf products are visible to everyone."""
from decimal import Decimal

from django.db.models import Min, Prefetch, Q
from django.db.models.functions import Coalesce

from .models import Category, Product, ProductImage, SKU

SORT_WHITELIST = {
    "newest": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
    "price_asc": ("price_min", "id"),
    "price_desc": ("-price_min", "-id"),
}

PRODUCT_LIST_QS = (
    Product.objects.filter(status=Product.Status.ACTIVE)
    .select_related("category")
    .prefetch_related(
        Prefetch("skus", queryset=SKU.objects.filter(is_active=True)),
        Prefetch("images", queryset=ProductImage.objects.order_by("sort_order", "id")),
    )
)


def active_categories():
    return Category.objects.filter(is_active=True).order_by("sort_order", "id")


def product_list(*, category_slug: str = "", keyword: str = "", sort: str = "newest"):
    """Return a queryset of visible products; sorting is whitelisted."""
    qs = PRODUCT_LIST_QS
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if keyword:
        qs = qs.filter(
            Q(title__icontains=keyword)
            | Q(subtitle__icontains=keyword)
            | Q(description__icontains=keyword)
        )

    if sort in {"price_asc", "price_desc"}:
        # 兜底值必须是 Decimal：Coalesce 不接受 DecimalField 与 IntegerField 混用，
        # 否则 price_asc/price_desc 会抛 FieldError 变成 500。
        qs = qs.annotate(
            price_min=Coalesce(
                Min("skus__price", filter=Q(skus__is_active=True)),
                Decimal("0.00"),
            )
        )
    ordering = SORT_WHITELIST.get(sort, SORT_WHITELIST["newest"])
    return qs.order_by(*ordering)


def product_detail(pk: int):
    return PRODUCT_LIST_QS.filter(pk=pk).first()
