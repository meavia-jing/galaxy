"""Error payloads: {"error": {"code","message","fields"}, "request_id": ...}."""
import logging

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .errors import DEFAULT_CODES, is_dependency_failure

logger = logging.getLogger(__name__)

FIELD_MSG = "该字段不合法"


def _fields_from_detail(detail):
    if isinstance(detail, dict):
        out = {}
        for key, value in detail.items():
            if key == "non_field_errors":
                continue
            # 通用错误的 payload 是 {"detail": "字符串"}；但这里 detail 也可能是
            # 地址模型的真实字段名，其值是列表，不能当作通用消息丢弃。
            if key == "detail" and isinstance(value, str):
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
        # Unhandled exceptions must still honour the API contract: JSON envelope,
        # no traceback. A dead dependency maps to 503, everything else to 500.
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if is_dependency_failure(exc)
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        code, message = DEFAULT_CODES[status_code]
        logger.exception(
            "unhandled API error request_id=%s status=%s exc=%r",
            request_id,
            status_code,
            exc,
        )
        return Response(
            {
                "error": {"code": code, "message": message, "fields": {}},
                "request_id": request_id,
            },
            status=status_code,
        )

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
