"""Engine: the detect -> plan -> act -> verify -> report loop.

One incident at a time. If verification fails, the incident reopens and is
re-planned once with the failure as evidence; after that it is marked FAILED
and reported honestly — the agent never fakes a close.
"""

from __future__ import annotations

import threading
import time

from . import audit, executor, planner, reporter, sandbox
from .memory import store
from .models import Incident, IncidentStatus
from .verifier import verify

incidents: dict[str, Incident] = {}
_active_lock = threading.Lock()
_active_id: str | None = None


def active_incident() -> Incident | None:
    with _active_lock:
        return incidents.get(_active_id) if _active_id else None


def register(inc: Incident) -> None:
    incidents[inc.id] = inc
    store.save_incident(inc)


def hydrate() -> None:
    """Reload persisted incidents after a control-plane restart."""
    for payload in store.list_incidents():
        try:
            inc = Incident.model_validate(payload)
            incidents[inc.id] = inc
        except Exception:
            continue


def handle_incident(inc: Incident) -> Incident:
    """Run the full loop for a fresh incident. Blocking — call in a thread."""
    global _active_id
    with _active_lock:
        _active_id = inc.id
    try:
        return _run(inc)
    finally:
        with _active_lock:
            if _active_id == inc.id:
                _active_id = None


def _run(inc: Incident) -> Incident:
    inc.evidence = sandbox.gather_evidence()
    inc.signature = sandbox.classify(inc.evidence)
    audit.record(
        "detected",
        f"Incident {inc.id}: {inc.signature.value} on {inc.service} — "
        f"{inc.evidence.get('health_probe')}",
        inc.id,
        signature=inc.signature.value,
        evidence={k: str(v)[:300] for k, v in inc.evidence.items()},
    )
    register(inc)

    for round_no in (1, 2):
        if executor.kill_switch_on():
            inc.status = IncidentStatus.HALTED
            audit.record("kill", "Kill switch engaged — incident handling halted.", inc.id)
            break
        inc.status = IncidentStatus.PLANNING
        register(inc)
        try:
            inc.plan = planner.build_plan(inc)
        except Exception as exc:
            inc.status = IncidentStatus.FAILED
            audit.record("plan", f"Planner failed: {exc}", inc.id)
            break
        audit.record(
            "plan",
            f"Diagnosis: {inc.plan.diagnosis} | Steps: "
            + " → ".join(s.tool for s in inc.plan.steps)
            + (" (fix recalled from memory)" if inc.plan.recalled_from_memory else ""),
            inc.id,
            diagnosis=inc.plan.diagnosis,
            steps=[s.model_dump() for s in inc.plan.steps],
        )
        if inc.plan.recalled_from_memory:
            audit.record(
                "memory",
                f"Proven fix for '{inc.signature.value}' recalled from memory.",
                inc.id,
            )

        inc.status = IncidentStatus.ACTING
        register(inc)
        for step in inc.plan.steps:
            if executor.kill_switch_on():
                inc.status = IncidentStatus.HALTED
                audit.record("kill", "Kill switch engaged mid-plan — halting.", inc.id)
                break
            result = executor.run_tool(step.tool, step.args, inc.id, round_no=round_no)
            inc.results.append(result)
            # give restarts/deploys a moment to take effect
            if step.tool in ("restart_service", "rollback_deploy"):
                time.sleep(2)
        if inc.status == IncidentStatus.HALTED:
            break

        inc.status = IncidentStatus.VERIFYING
        register(inc)
        inc.verification = verify()
        audit.record(
            "verify",
            f"Verification {'PASSED' if inc.verification['passed'] else 'FAILED'}: "
            f"health={inc.verification['health_checks']} error_rate={inc.verification['error_rate']}",
            inc.id,
            verification=inc.verification,
        )
        if inc.verification["passed"]:
            inc.status = IncidentStatus.CLOSED
            inc.closed_at = time.time()
            raw_tools = [r.tool for r in inc.results if r.ok and not r.refused]
            # A replan round may legitimately re-apply a fix (the double-break
            # case); the stored proven fix is the effective sequence, so
            # collapse consecutive duplicates before recording it.
            tools_used = [t for i, t in enumerate(raw_tools) if i == 0 or t != raw_tools[i - 1]]
            if tools_used:
                store.record_proven_fix(inc.signature.value, tools_used)
                audit.record(
                    "memory",
                    f"Proven fix stored for '{inc.signature.value}': {' → '.join(tools_used)}",
                    inc.id,
                )
            break
        if round_no == 1:
            inc.status = IncidentStatus.REOPENED
            inc.evidence["verification_failure"] = str(inc.verification)
            audit.record("verify", "Incident reopened — re-planning with verification evidence.", inc.id)
            register(inc)
            continue
        inc.status = IncidentStatus.FAILED

    register(inc)
    inc.report_path = reporter.write_report(inc)
    audit.record("report", f"Incident report written: {inc.report_path}", inc.id)
    register(inc)
    return inc
