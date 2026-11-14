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
        return owner_id == getattr(request.user, "id", None)


class IsOperatorOrReadOnly(BasePermission):
    message = "需要运营权限"

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_operator)


class IsStaff(BasePermission):
    message = "需要管理员权限"

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff_allowed)
