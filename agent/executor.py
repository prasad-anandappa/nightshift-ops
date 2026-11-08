"""Executor: runs allowlisted tools inside the sandbox only.

Every call passes the policy gate first, checks the kill switch, and is
written to the audit timeline. Mutating tools are idempotent per
(incident, plan round, tool, args) — a retried step inside one round never
double-applies, while a later round may legitimately re-apply a fix.
"""

from __future__ import annotations

import json
import threading

from . import audit
from .config import settings
from .models import ToolResult
from .policy import PolicyViolation, check_tool, kill_switch_active
from .sandbox import TOOLS
from .verifier import verify

_MUTATING = {"restart_service", "clear_temp_files", "rollback_deploy"}
_executed: set[str] = set()
_lock = threading.Lock()


def kill_switch_on() -> bool:
    return kill_switch_active(settings.kill_switch_file)


def run_tool(
    tool: str,
    args: dict | None = None,
    incident_id: str | None = None,
    round_no: int = 1,
) -> ToolResult:
    args = args or {}
    # 1. Policy gate — refusal is a first-class, audited outcome.
    try:
        check_tool(tool, args)
    except PolicyViolation as pv:
        result = ToolResult(tool=tool, ok=False, refused=True, refusal_reason=pv.reason)
        audit.record(
            "refusal",
            f"REFUSED tool '{tool}': {pv.reason}",
            incident_id,
            tool=tool,
            reason=pv.reason,
        )
        return result
    # 2. Kill switch — checked before every single tool call.
    if kill_switch_on():
        result = ToolResult(tool=tool, ok=False, output="Kill switch is engaged; execution halted.")
        audit.record("kill", f"Kill switch blocked tool '{tool}'", incident_id, tool=tool)
        return result
    # 3. Idempotency for mutating tools — scoped to one plan round. A retry
    # inside the same round never double-applies; a later round (after a
    # failed verification, when the world may have changed again) must be
    # allowed to re-apply the fix.
    key = f"{incident_id}:r{round_no}:{tool}:{json.dumps(args, sort_keys=True)}"
    if tool in _MUTATING and incident_id:
        with _lock:
            if key in _executed:
                return ToolResult(tool=tool, ok=True, output="Already applied for this incident (idempotent skip).")
            _executed.add(key)
    audit.record("tool_call", f"→ {tool}({args})", incident_id, tool=tool, args=args)
    if tool == "run_health_suite":
        outcome = verify()
        result = ToolResult(
            tool=tool,
            ok=bool(outcome["passed"]),
            output=json.dumps(outcome),
        )
    else:
        fn = TOOLS.get(tool)
        if fn is None:  # allowlisted in policy but unimplemented — treat as refusal
            result = ToolResult(tool=tool, ok=False, refused=True, refusal_reason="Tool not implemented.")
        else:
            ok, output = fn(args)
            result = ToolResult(tool=tool, ok=ok, output=output)
    audit.record(
        "tool_result",
        f"← {tool}: {'ok' if result.ok else 'FAILED'} — {result.output[:240]}",
        incident_id,
        tool=tool,
        ok=result.ok,
    )
    return result
