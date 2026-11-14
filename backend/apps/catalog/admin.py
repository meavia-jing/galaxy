from django.contrib import admin

from .models import Category, Product, ProductImage, SKU
from .views import invalidate_catalog_cache


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class SKUInline(admin.TabularInline):
    model = SKU
    extra = 1
    fields = ("sku_code", "attributes", "price", "stock_total", "stock_reserved", "is_active")
    readonly_fields = ("stock_reserved",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    list_editable = ("sort_order", "is_active")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_catalog_cache()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "is_featured", "created_at")
    list_filter = ("status", "is_featured", "category")
    search_fields = ("title", "slug", "subtitle")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [SKUInline, ProductImageInline]
    actions = ["make_active", "make_archived"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_catalog_cache()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        invalidate_catalog_cache()

    @admin.action(description="上架所选商品")
    def make_active(self, request, queryset):
        queryset.update(status=Product.Status.ACTIVE)
        invalidate_catalog_cache()

    @admin.action(description="下架所选商品")
    def make_archived(self, request, queryset):
        queryset.update(status=Product.Status.ARCHIVED)
        invalidate_catalog_cache()


@admin.register(SKU)
class SKUAdmin(admin.ModelAdmin):
    list_display = ("sku_code", "product", "price", "stock_total", "stock_reserved", "is_active")
    list_filter = ("is_active",)
    search_fields = ("sku_code", "product__title")
    readonly_fields = ("stock_reserved",)

    def save_model(self, request, obj, form, change):
        if obj.stock_total < obj.stock_reserved:
            obj.stock_total = obj.stock_reserved
        super().save_model(request, obj, form, change)
        invalidate_catalog_cache()
