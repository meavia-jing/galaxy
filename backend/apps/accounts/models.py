"""Custom user model — must exist before the first migration."""
import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

USERNAME_RE = re.compile(r"^[a-z0-9_]{4,32}$")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def normalize_username(self, username: str) -> str:
        return (username or "").strip().lower()

    def create_user(self, username: str, password: str | None = None, **extra):
        if not username:
            raise ValueError("用户名不能为空")
        username = self.normalize_username(username)
        user = self.model(username=username, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username: str, password: str | None = None, **extra):
        extra.setdefault("role", User.Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        return self.create_user(username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        USER = "user", "用户"
        OPERATOR = "operator", "运营"
        AGENT = "agent", "客服"
        ADMIN = "admin", "管理员"

    username = models.CharField(
        "用户名",
        max_length=32,
        unique=True,
        validators=[RegexValidator(USERNAME_RE, "用户名只能包含小写字母、数字和下划线，长度 4-32")],
    )
    nickname = models.CharField("昵称", max_length=50, blank=True, default="")
    email = models.EmailField("邮箱", blank=True, default="")
    role = models.CharField("角色", max_length=16, choices=Role.choices, default=Role.USER)
    is_active = models.BooleanField("启用", default=True)
    is_staff = models.BooleanField("可登录后台", default=False)
    must_change_password = models.BooleanField("需强制修改密码", default=False)
    auth_version = models.PositiveIntegerField("认证版本", default=1)
    date_joined = models.DateTimeField("注册时间", default=timezone.now)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "accounts_user"
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self) -> str:
        return self.username

    @property
    def display_name(self) -> str:
        return self.nickname or self.username

    @property
    def is_operator(self) -> bool:
        return self.role in {self.Role.OPERATOR, self.Role.ADMIN}

    @property
    def is_staff_allowed(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_agent(self) -> bool:
        return self.role == self.Role.AGENT

    def bump_auth_version(self) -> None:
        """Invalidate every issued access/refresh token for this user."""
        self.auth_version = models.F("auth_version") + 1
        self.save(update_fields=["auth_version", "updated_at"])
        self.refresh_from_db(fields=["auth_version"])
