"""测试环境设置。

与 development 的唯一区别：为了测试可重复与快速，做以下覆盖。
数据库仍连接真实 MariaDB（默认 test_shop），不使用 SQLite，
因为行锁、事务隔离、约束报错等行为必须与开发/生产一致。
"""
from .development import *  # noqa: F401,F403

DEBUG = False
# Django 测试客户端的 Host 是 testserver，DEBUG=False 时必须放行
ALLOWED_HOSTS = ["*"]

# 测试库里没有真实密码，用 MD5 哈希可把登录类用例从 ~0.3 秒降到 ~0.001 秒
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# 缓存默认用进程内缓存，避免测试写脏开发用的 Redis db 1。
# 需要验证 Redis 行为的用例请用 override_settings(CACHES=...) 单独指定。
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "shop-test-cache",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

REFRESH_COOKIE_SECURE = False

# 测试库会被频繁创建/销毁，长连接会阻塞 DROP DATABASE
for _alias in DATABASES:  # noqa: F405
    DATABASES[_alias]["CONN_MAX_AGE"] = 0
