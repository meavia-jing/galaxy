"""Uniform JSON envelope: {"data": ..., "request_id": ...}."""
from rest_framework.renderers import JSONRenderer

from .middleware import get_request_id


class EnvelopeJSONRenderer(JSONRenderer):
    """Wrap successful payloads in `data` and keep error payloads intact."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        request_id = get_request_id()

        if response is None:
            return super().render(data, accepted_media_type, renderer_context)

        status = response.status_code
        if status == 204:
            return b""
        if status >= 400:
            payload = data
            if isinstance(data, dict) and "error" in data:
                payload = dict(data)
            else:
                payload = {
                    "error": {
                        "code": "ERROR",
                        "message": "请求失败",
                        "fields": data if isinstance(data, dict) else {},
                    }
                }
            payload["request_id"] = request_id
        else:
            payload = {"data": data, "request_id": request_id}

        return super().render(payload, accepted_media_type, renderer_context)
