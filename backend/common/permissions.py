"""Shared permission classes."""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwner(BasePermission):
    """Object must expose `user_id` (or `user`) equal to the request user."""

    message = "无权访问该资源"

    def has_object_permission(self, request, view, obj):
        owner_id = getattr(obj, "user_id", None)
        if owner_id is None:
            owner = getattr(obj, "user", None)
            owner_id = getattr(owner, "id", None)
        # 没有归属字段的对象一律拒绝，避免「漏判即放行」。
        return owner_id is not None and owner_id == getattr(request.user, "id", None)


class IsOperatorOrReadOnly(BasePermission):
    message = "需要运营权限"

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, "user", None)
        if not (user and getattr(user, "is_authenticated", False)):
            return False
        # 用 getattr 兜底：用户模型缺少该属性时应当拒绝，而不是 500。
        return bool(getattr(user, "is_operator", False))


class IsStaff(BasePermission):
    message = "需要管理员权限"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and getattr(user, "is_authenticated", False)):
            return False
        return bool(getattr(user, "is_staff_allowed", False))
