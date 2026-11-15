"""Request id propagation and per-request log context."""
import logging
import uuid
from contextvars import ContextVar

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .errors import DEFAULT_CODES, is_dependency_failure

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return request_id_ctx.get()


class RequestIDMiddleware(MiddlewareMixin):
    """Attach a request id to the request, the log context and the response."""

    header = "HTTP_X_REQUEST_ID"

    def process_request(self, request):
        incoming = request.META.get(self.header, "").strip()
        request_id = incoming[:64] if incoming else uuid.uuid4().hex
        request.request_id = request_id
        request_id_ctx.set(request_id)

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", "-")
        response["X-Request-ID"] = request_id
        return response

    def process_exception(self, request, exception):
        logging.getLogger("django.request").exception(
            "unhandled exception request_id=%s path=%s",
            getattr(request, "request_id", "-"),
            request.path,
        )
        return None


class EnvelopeErrorMiddleware(MiddlewareMixin):
    """Last-resort JSON envelope for API paths, outside DRF's exception handler.

    DRF covers everything inside a view; this catches failures raised before the
    view (middleware, URL resolution) so an API client never receives Django's
    HTML error page. Non-API paths keep Django's default behaviour.
    """

    api_prefixes = ("/api/", "/health/")

    def process_exception(self, request, exception):
        if not request.path.startswith(self.api_prefixes):
            return None

        request_id = getattr(request, "request_id", "-")
        status_code = 503 if is_dependency_failure(exception) else 500
        code, message = DEFAULT_CODES[status_code]
        logging.getLogger("django.request").exception(
            "unhandled exception request_id=%s path=%s status=%s",
            request_id,
            request.path,
            status_code,
        )
        response = JsonResponse(
            {
                "error": {"code": code, "message": message, "fields": {}},
                "request_id": request_id,
            },
            status=status_code,
        )
        response["X-Request-ID"] = request_id
        return response
