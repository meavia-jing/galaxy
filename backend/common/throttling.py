"""Throttles that fail open when their cache backend is unavailable."""
import logging

from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger(__name__)


class ResilientScopedRateThrottle(ScopedRateThrottle):
    """Rate limiting must never take authentication down with it.

    ``ScopedRateThrottle`` reads and writes the Django cache. With Redis down
    those calls raise ``ConnectionError`` and DRF turns the request into a 500
    before the view (and its exception handler) ever runs. Failing open keeps
    the endpoint usable; the outage is visible in the WARNING log.
    """

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception as exc:  # noqa: BLE001 - cache outages must fail open
            logger.warning(
                "throttle bypassed scope=%s path=%s error=%r",
                getattr(view, "throttle_scope", "-"),
                request.path,
                exc,
            )
            return True
