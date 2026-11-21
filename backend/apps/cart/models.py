"""购物车。

设计要点：
- 同一个用户 + 同一个 SKU 只允许一行，由数据库唯一约束兜底，不靠应用层「先查再写」。
- ``quantity`` 表达「想要的件数」而非增量，与架构 §5 的「设置为指定值」一致。
- 购物车不存价格与库存：价格会变、库存会变，结算时必须从 SKU 现读，
  否则用户能靠旧缓存价下单（I04-T02 的 409 PRICE_CHANGED 依赖这一点）。
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

MIN_QUANTITY = 1
MAX_QUANTITY = 99


class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="用户",
    )
    sku = models.ForeignKey(
        "catalog.SKU",
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="SKU",
    )
    quantity = models.PositiveSmallIntegerField(
        "数量",
        default=1,
        validators=[MinValueValidator(MIN_QUANTITY), MaxValueValidator(MAX_QUANTITY)],
    )
    selected = models.BooleanField("结算时勾选", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "cart_item"
        verbose_name = "购物车项"
        verbose_name_plural = "购物车项"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "sku"], name="cart_item_user_sku_uniq"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=MIN_QUANTITY, quantity__lte=MAX_QUANTITY),
                name="cart_item_quantity_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.sku_id} x{self.quantity}"

    @property
    def line_amount(self):
        return self.sku.price * self.quantity
