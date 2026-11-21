from django.contrib import admin

from .models import CartItem


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("user", "sku", "quantity", "selected", "updated_at")
    list_filter = ("selected",)
    search_fields = ("user__username", "sku__sku_code")
    readonly_fields = ("created_at", "updated_at")
