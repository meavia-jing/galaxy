"""OpenAPI 补充定义。

drf-spectacular 认不出自定义认证类时，schema 里这些端点会缺少安全方案，
后台文档也就看不出「需要 Bearer」。这里显式登记。
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "common.authentication.DatabaseBackedJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
