from rest_framework import serializers

from .models import Category, Product, ProductImage, SKU


class CategorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent_id", "sort_order"]

    def get_id(self, obj) -> str:
        return str(obj.pk)


class ProductImageSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "path", "alt_text", "sort_order"]

    def get_id(self, obj) -> str:
        return str(obj.pk)


class SKUSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    stock_available = serializers.IntegerField(read_only=True)

    class Meta:
        model = SKU
        fields = ["id", "sku_code", "attributes", "price", "stock_available", "is_active"]

    def get_id(self, obj) -> str:
        return str(obj.pk)


class ProductListSerializer(serializers.ModelSerializer):
    """Card payload for lists; price range and cover are computed from prefetched data."""

    id = serializers.SerializerMethodField()
    price_min = serializers.SerializerMethodField()
    price_max = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "title", "slug", "subtitle", "category_id", "category_name",
            "price_min", "price_max", "cover_image", "is_featured",
        ]

    def get_id(self, obj) -> str:
        return str(obj.pk)

    def _active_skus(self, obj):
        skus = [sku for sku in obj.skus.all() if sku.is_active]
        return skus

    def get_price_min(self, obj) -> str:
        skus = self._active_skus(obj)
        return str(min((sku.price for sku in skus), default="0.00"))

    def get_price_max(self, obj) -> str:
        skus = self._active_skus(obj)
        return str(max((sku.price for sku in skus), default="0.00"))

    def get_cover_image(self, obj) -> str:
        images = list(obj.images.all())
        return images[0].path if images else ""


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    skus = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ["description", "images", "skus"]

    def get_skus(self, obj) -> list:
        return SKUSerializer(self._active_skus(obj), many=True).data
