"""Planner: Vultr Serverless Inference call -> diagnosis + ordered fix plan.

The plan may only reference allowlisted tools; the policy gate re-checks every
step before execution regardless of what the model proposed. A proven fix
recalled from memory is offered to the model as the preferred sequence.
"""

from __future__ import annotations

from . import llm
from .memory import store
from .models import Incident, Plan, PlanStep
from .policy import ALLOWLIST

_SYSTEM = """You are NightShift Ops, an autonomous on-call SRE agent operating
inside a disposable sandbox. Given incident evidence from a monitored service,
produce a diagnosis and an ordered fix plan.

Rules:
- Reply with ONLY a JSON object: {"diagnosis": string, "steps": [{"tool": string, "args": {}, "why": string}]}
- Steps may ONLY use these tools: __TOOLS__
- Every step's "why" must cite the observed evidence it responds to.
- Prefer the smallest fix that addresses the diagnosis. Read-only diagnosis
  steps (read_logs, check_disk, check_health) come first when the cause is
  not already certain.
- Never propose tools outside the list, shell commands, or data operations.
"""


def build_plan(incident: Incident) -> Plan:
    recalled = store.recall_fix(incident.signature.value)
    tools_desc = ", ".join(f"{k} ({v})" for k, v in ALLOWLIST.items())
    evidence = "\n".join(f"- {k}: {v}" for k, v in incident.evidence.items())
    memory_hint = ""
    if recalled:
        memory_hint = (
            f"\nMemory: this fault signature ({incident.signature.value}) was "
            f"fixed before with this proven tool sequence: {recalled}. "
            "Prefer it unless the evidence contradicts it."
        )
    raw = llm.chat(
        [
            {"role": "system", "content": _SYSTEM.replace("__TOOLS__", tools_desc)},
            {
                "role": "user",
                "content": (
                    f"Service: {incident.service}\n"
                    f"Fault signature: {incident.signature.value}\n"
                    f"Evidence:\n{evidence}{memory_hint}"
                ),
            },
        ]
    )
    data = llm.extract_json(raw)
    steps = [
        PlanStep(tool=s.get("tool", ""), args=s.get("args") or {}, why=s.get("why", ""))
        for s in data.get("steps", [])
    ]
    return Plan(
        diagnosis=str(data.get("diagnosis", "No diagnosis returned.")),
        steps=steps,
        recalled_from_memory=bool(recalled),
    )


def propose_for_request(request_text: str) -> dict:
    """Translate a free-text operator request into the single tool the model
    believes would carry it out. The policy gate — not the model — decides
    whether it may run."""
    tools_desc = ", ".join(ALLOWLIST.keys())
    raw = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "You translate an operator's request for an autonomous SRE "
                    "agent into the ONE tool that would carry it out. The agent "
                    f"normally only supports: {tools_desc}. If the request "
                    "needs an operation outside that set, name the operation "
                    "the request would require anyway (e.g. delete_database, "
                    "drop_table, read_file, run_shell) — a separate policy "
                    "gate will decide if it is allowed. Reply ONLY with JSON: "
                    '{"tool": string, "args": {}, "rationale": string}'
                ),
            },
            {"role": "user", "content": request_text},
        ],
        max_tokens=300,
    )
    return llm.extract_json(raw)
