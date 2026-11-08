"""Audit timeline: every plan, tool call, result, refusal and verification
outcome is one append-only record (DESIGN §2). Stored in SQLite, mirrored in
memory for fast dashboard reads."""

from __future__ import annotations

import threading

from .memory import store
from .models import AuditEvent

_lock = threading.Lock()
_events: list[AuditEvent] = []
_MAX = 500


def record(kind: str, message: str, incident_id: str | None = None, **data) -> AuditEvent:
    ev = AuditEvent(kind=kind, message=message, incident_id=incident_id, data=data)
    with _lock:
        _events.append(ev)
        if len(_events) > _MAX:
            del _events[: len(_events) - _MAX]
    try:
        store.add_audit(ev)
    except Exception:
        pass  # audit persistence must never crash the agent loop
    return ev


def recent(limit: int = 120) -> list[dict]:
    with _lock:
        return [e.model_dump() for e in _events[-limit:]][::-1]


def hydrate() -> None:
    """Reload the persisted timeline after a control-plane restart."""
    rows = store.list_audit(_MAX)
    with _lock:
        _events.clear()
        for row in reversed(rows):  # oldest first
            _events.append(AuditEvent(**row))
