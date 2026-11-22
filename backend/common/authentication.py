"""JWT authentication that re-checks the database user on every request.

Access tokens carry `auth_version`; bumping the user's auth_version invalidates
every existing access token (logout, password change, disable, role downgrade).
"""
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.utils import get_md5_hash_password

# 管理员重置密码后，该用户只允许改密与退出（架构 3.3「认证与令牌」）。
# GET /users/me/ 保留为只读身份查询，前端据此提示并展示改密表单。
PENDING_PASSWORD_CHANGE_PATHS = {"/api/v1/users/me/"}
PENDING_PASSWORD_CHANGE_WRITE_PATHS = {"/api/v1/users/me/change-password/"}


class DatabaseBackedJWTAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate_header(self, request):
        return self.keyword

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed("认证头格式不正确")
        try:
            raw_token = header[1].decode()
        except UnicodeError:  # pragma: no cover
            raise exceptions.AuthenticationFailed("认证头格式不正确")

        try:
            token = UntypedToken(raw_token)
        except InvalidToken:
            raise exceptions.AuthenticationFailed("登录状态已失效")

        user_id = token.payload.get(jwt_settings.USER_ID_CLAIM)
        if user_id is None:
            raise exceptions.AuthenticationFailed("登录状态已失效")

        User = get_user_model()
        try:
            user = User.objects.get(**{jwt_settings.USER_ID_FIELD: user_id})
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed("登录状态已失效")

        if not user.is_active:
            raise exceptions.AuthenticationFailed("账号已停用")

        token_version = token.payload.get("auth_version")
        if token_version != user.auth_version:
            raise exceptions.AuthenticationFailed("登录状态已失效，请重新登录")

        if jwt_settings.CHECK_REVOKE_TOKEN:
            revoke_hash = token.payload.get(jwt_settings.REVOKE_TOKEN_CLAIM)
            if revoke_hash != get_md5_hash_password(user.password):
                raise exceptions.AuthenticationFailed("登录状态已失效，请重新登录")

        if user.must_change_password:
            path = request.path
            read_only_identity = path in PENDING_PASSWORD_CHANGE_PATHS and (
                request.method in SAFE_METHODS
            )
            changing_password = path in PENDING_PASSWORD_CHANGE_WRITE_PATHS
            if not (read_only_identity or changing_password):
                raise exceptions.PermissionDenied("管理员已重置密码，请先修改临时密码")

        return (user, token)


# 导入即注册 OpenAPI 安全方案（drf-spectacular 靠 import 副作用收集扩展）。
from . import schema  # noqa: E402,F401
