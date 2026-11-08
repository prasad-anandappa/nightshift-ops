"""NightShift Ops control plane — FastAPI app.

Serves the dashboard, the state API the dashboard polls, the chaos panel
(human-operated "break the world" controls), the ask-the-agent endpoint
(every request passes the policy gate), and the kill switch.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from . import audit, engine, executor, monitor, planner, sandbox
from .config import settings
from .memory import store
from .models import AskRequest, AskResponse, ToolResult
from .policy import PolicyViolation, check_tool

app = FastAPI(title="NightShift Ops")

_DASHBOARD = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")


@app.on_event("startup")
def _startup() -> None:
    os.makedirs(settings.reports_dir, exist_ok=True)
    engine.hydrate()
    audit.hydrate()
    monitor.start()
    audit.record("plan", "NightShift Ops control plane started; monitor live.")


@app.get("/health")
def health():
    return {"status": "ok", "service": "nightshift-control-plane"}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open(os.path.normpath(_DASHBOARD)) as fh:
        return fh.read()


@app.get("/api/state")
def state():
    active = engine.active_incident()
    return {
        "fleet": monitor.fleet_status(),
        "service_state": sandbox.service_state(),
        "kill_switch": executor.kill_switch_on(),
        "active_incident": active.model_dump() if active else None,
        "incidents": [
            i.model_dump()
            for i in sorted(engine.incidents.values(), key=lambda x: x.opened_at, reverse=True)[:8]
        ],
        "audit": audit.recent(120),
        "memory": store.memory_snapshot(),
    }


@app.post("/api/chaos/{kind}")
def chaos(kind: str):
    actions = {
        "bad_deploy": sandbox.chaos_bad_deploy,
        "kill_process": sandbox.chaos_kill_process,
        "fill_disk": sandbox.chaos_fill_disk,
        "reset": sandbox.chaos_reset,
    }
    if kind not in actions:
        raise HTTPException(404, f"unknown chaos action {kind}")
    ok, msg = actions[kind]()
    audit.record("ask", f"Chaos panel: {kind} -> {'ok' if ok else 'failed'}: {msg}")
    return {"ok": ok, "message": msg}


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    audit.record("ask", f"Operator request: {req.request!r}")
    try:
        proposal = planner.propose_for_request(req.request)
    except Exception as exc:
        raise HTTPException(502, f"planner error: {exc}")
    tool = str(proposal.get("tool", ""))
    args = proposal.get("args") or {}
    rationale = str(proposal.get("rationale", ""))
    try:
        check_tool(tool, args)
    except PolicyViolation as pv:
        audit.record(
            "refusal",
            f"REFUSED operator request {req.request!r}: model proposed '{tool}' — {pv.reason}",
            tool=tool,
            request=req.request,
        )
        return AskResponse(
            executed=False,
            refused=True,
            proposed_tool=tool,
            message=(
                f"Refused. The request would require '{tool}', which is outside the "
                f"agent's allowlist. {pv.reason} Nothing was executed; the refusal "
                "is on the audit timeline."
            ),
        )
    result: ToolResult = executor.run_tool(tool, args, incident_id=None)
    return AskResponse(
        executed=result.ok,
        refused=False,
        proposed_tool=tool,
        message=f"{tool} executed ({rationale}): {result.output[:300]}",
    )


@app.post("/api/kill")
def kill(payload: dict):
    on = bool(payload.get("on"))
    if on:
        with open(settings.kill_switch_file, "w") as fh:
            fh.write("engaged by operator\n")
        audit.record("kill", "Kill switch ENGAGED by operator.")
    else:
        try:
            os.remove(settings.kill_switch_file)
        except FileNotFoundError:
            pass
        audit.record("kill", "Kill switch released by operator.")
    return {"kill_switch": on}


@app.get("/api/incidents/{incident_id}/report", response_class=PlainTextResponse)
def incident_report(incident_id: str):
    path = os.path.join(settings.reports_dir, f"incident-{incident_id}.md")
    if not os.path.exists(path):
        raise HTTPException(404, "report not found")
    return FileResponse(path, media_type="text/markdown")
