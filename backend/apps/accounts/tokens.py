"""Token helpers: embed auth_version so tokens die on logout/password change."""
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken


def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh["auth_version"] = user.auth_version
    access = refresh.access_token
    access["auth_version"] = user.auth_version
    return refresh, access


class ShopTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login by username + password; adds auth_version claims and user payload."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["auth_version"] = user.auth_version
        return token

    def validate(self, attrs):
        username = (attrs.get("username") or "").strip().lower()
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        data = super().validate({"username": username, "password": attrs.get("password")})
        if user is not None and user.must_change_password:
            data["must_change_password"] = True
        data["user"] = {
            "id": str(user.id) if user else None,
            "username": user.username if user else username,
            "nickname": user.nickname if user else "",
            "role": user.role if user else "user",
        }
        return data
