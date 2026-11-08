# NightShift Ops

> The on-call agent that fixes the 3 a.m. failure before you wake up — detects,
> diagnoses, repairs and *verifies* production incidents inside a disposable
> Vultr sandbox, with a full audit trail and a kill switch.

Built for the **Vultr: Agent Rush Hackathon** (lablab.ai), Challenge 1 —
**Blast Radius Zero** · Online build Nov 3–8, 2026.

> ⚠️ SCAFFOLD — created Nov 3, 2026 ahead of the 15:00 UTC kickoff.
> Module files are placeholders with TODO markers; implementation starts at kickoff.
> Full design: `../DESIGN.md` · Build plan: `../BUILD-EXECUTION-2026-11-03.md`

## What it does

TODO (kickoff): finalise from DESIGN.md §1 — detect → plan → act → verify loop,
allowlisted tools only, independent verification, Managed PostgreSQL memory,
incident reports in Object Storage, audit timeline + kill switch dashboard.

## How Vultr is used (required by the challenge brief)

| Vultr service | Role |
|---|---|
| Cloud Compute | Control-plane instance (agent + dashboard) and a disposable sandbox instance |
| Serverless Inference | All agent LLM calls (diagnosis, fix plan, report drafting) — OpenAI-compatible, `https://api.vultrinference.com/v1` |
| Managed Databases (PostgreSQL) | Agent memory: incidents, fault signatures, proven fixes; audit/run store |
| Object Storage | Incident reports, log snapshots, demo assets |
| Cloud Firewall | Sandbox containment: inbound = control plane + operator only, restricted egress |
| Snapshots | Golden sandbox image → disposable rebuild in minutes |

TODO (Nov 7): architecture diagram, deployment notes, public demo URL.

## Quick start (judge runbook — target < 15 minutes)

TODO (Nov 7): local mock mode (no Vultr account needed) + full Vultr deploy path,
honest about which steps need an account.

## Repository layout

- `agent/` — control-plane FastAPI service (monitor, planner, executor, verifier, memory, reporter)
- `sandbox/` — the breakable world: demo services + chaos panel (runs ONLY in the sandbox)
- `dashboard/` — incident timeline / plan / tool-call UI with kill switch
- `infra/` — provisioning + firewall + snapshot notes/scripts
- `tests/` — unit + end-to-end incident drills
- `docs/` — submission notes

## License

MIT — see `LICENSE`.
