from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "nickname", "email", "role",
            "must_change_password", "date_joined",
        ]
        read_only_fields = fields

    def get_id(self, obj) -> str:
        return str(obj.pk)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=32)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)
    nickname = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    def validate_username(self, value: str) -> str:
        username = value.strip().lower()
        from .models import USERNAME_RE

        if not USERNAME_RE.match(username):
            raise serializers.ValidationError("用户名只能包含小写字母、数字和下划线，长度 4-32")
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError("该用户名已被使用")
        return username

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            nickname=validated_data.get("nickname", "")[:50],
            email=validated_data.get("email", ""),
        )


class ProfileSerializer(serializers.ModelSerializer):
    """Only whitelisted fields are writable; role/is_active are server-controlled."""

    class Meta:
        model = User
        fields = ["id", "username", "nickname", "email", "role"]
        read_only_fields = ["id", "username", "role"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_old_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("原密码不正确")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value, self.context["request"].user)
        if value == self.initial_data.get("old_password"):
            raise serializers.ValidationError("新密码不能与原密码相同")
        return value
