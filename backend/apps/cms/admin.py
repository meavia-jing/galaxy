from django.contrib import admin

from .models import Banner, ContentPage
from .views import invalidate_cms_cache


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("title", "sort_order", "is_active", "target_url")
    list_editable = ("sort_order", "is_active")
    search_fields = ("title",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_cms_cache()


@admin.register(ContentPage)
class ContentPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "published_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        invalidate_cms_cache()
