"""Error payloads: {"error": {"code","message","fields"}, "request_id": ...}."""
import logging

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

DEFAULT_CODES = {
    status.HTTP_400_BAD_REQUEST: ("INVALID_REQUEST", "请求参数不正确"),
    status.HTTP_401_UNAUTHORIZED: ("UNAUTHORIZED", "请先登录"),
    status.HTTP_403_FORBIDDEN: ("FORBIDDEN", "没有操作权限"),
    status.HTTP_404_NOT_FOUND: ("NOT_FOUND", "资源不存在"),
    status.HTTP_409_CONFLICT: ("CONFLICT", "状态冲突"),
    status.HTTP_429_TOO_MANY_REQUESTS: ("RATE_LIMITED", "请求过于频繁，请稍后再试"),
    status.HTTP_503_SERVICE_UNAVAILABLE: ("DEPENDENCY_UNAVAILABLE", "依赖服务暂不可用"),
}

FIELD_MSG = "该字段不合法"


def _fields_from_detail(detail):
    if isinstance(detail, dict):
        out = {}
        for key, value in detail.items():
            if key in {"detail", "non_field_errors"}:
                continue
            if isinstance(value, (list, tuple)):
                out[key] = " ".join(str(item) for item in value)
            elif isinstance(value, dict):
                out[key] = " ".join(str(item) for item in value.values())
            else:
                out[key] = str(value)
        return out
    return {}


def _message_from_detail(detail, status_code: int):
    if isinstance(detail, dict):
        for key in ("detail", "non_field_errors"):
            if key in detail:
                value = detail[key]
                if isinstance(value, (list, tuple)):
                    return str(value[0]) if value else FIELD_MSG
                return str(value)
        return DEFAULT_CODES.get(status_code, ("ERROR", "请求失败"))[1]
    if isinstance(detail, (list, tuple)) and detail:
        return str(detail[0])
    return str(detail)


def api_exception_handler(exc, context):
    if isinstance(exc, ObjectDoesNotExist):
        exc = exceptions.NotFound()
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    if isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    request_id = getattr(context.get("request"), "request_id", "-")

    if response is None:
        logger.exception("unhandled API error request_id=%s", request_id)
        return None

    code, default_message = DEFAULT_CODES.get(
        response.status_code,
        ("ERROR", "请求失败"),
    )
    detail = response.data
    if isinstance(detail, dict) and "error" in detail and isinstance(detail["error"], dict):
        payload = {
            "error": {
                "code": detail["error"].get("code", code),
                "message": detail["error"].get("message", default_message),
                "fields": detail["error"].get("fields", {}),
            },
            "request_id": request_id,
        }
        response.data = payload
        return response

    explicit_code = getattr(exc, "default_code", None)
    if isinstance(explicit_code, str) and explicit_code.isupper():
        code = explicit_code

    response.data = {
        "error": {
            "code": code,
            "message": _message_from_detail(detail, response.status_code),
            "fields": _fields_from_detail(detail),
        },
        "request_id": request_id,
    }
    return response


class BusinessError(exceptions.APIException):
    """Domain error carrying a stable error code for the frontend."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, code: str, message: str, status_code: int | None = None, fields=None):
        if status_code is not None:
            self.status_code = status_code
        self.detail = {"error": {"code": code, "message": message, "fields": fields or {}}}
