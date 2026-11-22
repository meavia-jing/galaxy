import secrets

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .audit import record_audit
from .models import Address, AuditLog, User

TEMP_PASSWORD_BYTES = 12


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "nickname", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "nickname", "email")
    ordering = ("-date_joined",)
    readonly_fields = ("auth_version", "date_joined", "updated_at", "last_login")
    actions = ("reset_password",)

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

    @admin.action(description="重置密码为随机临时密码并强制下次改密")
    def reset_password(self, request, queryset):
        """Admin-only reset: generate a one-time password, revoke old sessions.

        The plaintext temporary password is shown once in the admin message and
        is never stored in the audit log (``password`` is redacted to ``***``).
        """
        for user in queryset:
            temporary_password = secrets.token_urlsafe(TEMP_PASSWORD_BYTES)
            previous_version = user.auth_version
            user.set_password(temporary_password)
            user.must_change_password = True
            user.auth_version = previous_version + 1
            user.save(
                update_fields=[
                    "password",
                    "must_change_password",
                    "auth_version",
                    "updated_at",
                ]
            )
            record_audit(
                actor=request.user,
                action="user.password_reset",
                resource_type="user",
                resource_id=user.pk,
                request_id=getattr(request, "request_id", ""),
                changes={
                    "password": "***",
                    "must_change_password": True,
                    "auth_version": {
                        "from": previous_version,
                        "to": user.auth_version,
                    },
                },
            )
            self.message_user(
                request,
                f"{user.username} 的密码已重置，临时密码：{temporary_password}"
                "（仅显示这一次，请转交本人；登录后必须修改）",
                level=messages.WARNING,
            )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "resource_type", "resource_id", "request_id")
    list_filter = ("action", "resource_type")
    search_fields = ("action", "resource_type", "resource_id", "request_id", "actor__username")
    list_select_related = ("actor",)
    readonly_fields = (
        "actor",
        "action",
        "resource_type",
        "resource_id",
        "request_id",
        "changes",
        "created_at",
    )
    ordering = ("-created_at", "-id")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("recipient", "user", "phone", "province", "city", "district", "is_default")
    list_filter = ("is_default", "province")
    search_fields = ("recipient", "phone", "user__username", "detail")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    ordering = ("-is_default", "-updated_at")
