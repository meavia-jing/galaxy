from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "nickname", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "nickname", "email")
    ordering = ("-date_joined",)
    readonly_fields = ("auth_version", "date_joined", "updated_at", "last_login")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("资料", {"fields": ("nickname", "email", "role")}),
        ("权限", {"fields": ("is_active", "is_staff", "is_superuser", "auth_version")}),
        ("安全", {"fields": ("must_change_password",)}),
        ("时间", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "nickname", "role", "password1", "password2"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if change and "password" in form.changed_data:
            obj.auth_version += 1
        super().save_model(request, obj, form, change)
