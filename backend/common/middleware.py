"""Request id propagation and per-request log context."""
import logging
import uuid
from contextvars import ContextVar

from django.utils.deprecation import MiddlewareMixin

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
