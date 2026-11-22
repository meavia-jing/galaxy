"""Append-only audit helper shared by admin actions and future services."""
from __future__ import annotations

from .models import AuditLog


def record_audit(
    *,
    actor,
    action: str,
    resource_type: str,
    resource_id,
    request_id: str = "",
    changes: dict | None = None,
) -> AuditLog:
    """Write one audit row. ``changes`` must already be redacted."""
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        request_id=(request_id or "")[:64],
        changes=changes or {},
    )
