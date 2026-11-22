"""购物车序列化。

响应里必须带上「能不能买」的判定，而不是只给数量和价格：
前端要据此把下架/缺货项标红并禁止结算（I04-T01 验收清单第 4 条）。
"""
from rest_framework import serializers

from .models import CartItem


class CartItemSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    sku_id = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    product_title = serializers.CharField(source="sku.product.title", read_only=True)
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    attributes = serializers.JSONField(source="sku.attributes", read_only=True)
    unit_price = serializers.DecimalField(
        source="sku.price", max_digits=12, decimal_places=2, coerce_to_string=True, read_only=True
    )
    stock_available = serializers.IntegerField(source="sku.stock_available", read_only=True)
    line_amount = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()
    unavailable_reason = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id", "sku_id", "product_id", "product_title", "sku_code", "attributes",
            "unit_price", "quantity", "line_amount", "selected",
            "stock_available", "available", "unavailable_reason",
        ]

    def get_id(self, obj) -> str:
        return str(obj.pk)

    def get_sku_id(self, obj) -> str:
        return str(obj.sku_id)

    def get_product_id(self, obj) -> str:
        return str(obj.sku.product_id)

    def get_line_amount(self, obj) -> str:
        return str(obj.line_amount)

    def get_unavailable_reason(self, obj) -> str:
        sku = obj.sku
        if sku.product.status != sku.product.Status.ACTIVE:
            return "商品已下架"
        if not sku.is_active:
            return "该规格已停用"
        if sku.stock_available <= 0:
            return "已售罄"
        if sku.stock_available < obj.quantity:
            return f"库存仅剩 {sku.stock_available} 件"
        return ""

    def get_available(self, obj) -> bool:
        return self.get_unavailable_reason(obj) == ""


class CartItemWriteSerializer(serializers.Serializer):
    """写入载荷。数量下限/上限在服务层统一报 INVALID_QUANTITY，这里只做类型校验。"""

    sku_id = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    selected = serializers.BooleanField(required=False, default=True)


class CartItemPatchSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(required=False)
    selected = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("请提供 quantity 或 selected")
        return attrs


class CartSummarySerializer(serializers.Serializer):
    """`GET /cart/` 的响应形态，供 OpenAPI 使用（不是 ModelSerializer）。"""

    items = CartItemSerializer(many=True)
    selected_count = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    has_unavailable = serializers.BooleanField()
