# NightShift Ops

> The on-call agent that fixes the 3 a.m. failure before you wake up — it
> detects, diagnoses, repairs and *verifies* production incidents inside a
> disposable sandbox, with a full audit trail and a kill switch.

Built for the **Vultr: Agent Rush Hackathon** (lablab.ai), Challenge 01 —
**Blast Radius Zero** · Online build Nov 3–8, 2026 · Author: Prasad Dimba Anandappa

## 🔴 Live demo

**http://155.138.254.23/** — the production control plane, running on Vultr
Cloud Compute. Open it, break the sandbox fleet from the chaos panel, and
watch the agent fix it on its own. Ask it to *"delete the orders database"*
and watch it refuse.

## What it does

A demo storefront service (`shopfront`) runs inside a Docker sandbox. It
fails the way real services fail — a bad deploy, a killed process, a full
disk. NightShift Ops handles the whole incident lifecycle with no human in
the loop:

1. **Detects** — a monitor probes the service every 2 s. Sustained failure
   opens an incident automatically and gathers evidence (health probe,
   error-rate sample, deploy version, disk usage, log tail).
2. **Plans** — the evidence goes to a Vultr Serverless Inference model,
   which returns a diagnosis (citing the evidence) and an ordered fix plan
   built only from the agent's allowlisted tools.
3. **Acts** — the executor runs the plan inside the sandbox only. Every step
   passes a policy gate (allowlist check) and a kill-switch check first, and
   mutating steps are idempotent per incident per plan round (a retry inside
   one round never double-applies; a later round may re-apply a fix).
4. **Verifies** — an independent verifier probes the service directly:
   health must be green on 3 consecutive checks **and** a 10-request error
   sample must be ≤ 10 % errors. The agent never grades its own homework; a
   failed verification reopens the incident and triggers one replan.
5. **Remembers + reports** — every step lands on a public audit timeline; a
   Markdown incident report is written per incident; and the proven fix for
   each fault signature is stored in agent memory, so a repeat fault is
   diagnosed with its proven fix recalled (this is visible in the live
   audit trail — the second bad deploy is fixed from memory).

### The safety model (the "Blast Radius Zero" part)

- **Allowlist, not instructions.** The agent can execute exactly seven
  tools (`read_logs`, `check_health`, `check_disk`, `restart_service`,
  `clear_temp_files`, `rollback_deploy`, `run_health_suite`), only against
  the sandbox fleet. Anything else a model — or a human typing in the
  ask-box — proposes is **refused and logged**. Try it live: the request
  *"delete the orders database"* is translated by the model to
  `delete_database`, and the policy gate refuses it. Nothing executes.
- **Kill switch.** Engaging it halts the agent before its next tool call,
  mid-incident if necessary. This is drilled live, not just drawn.
- **Secret hygiene.** The sandbox container holds no API keys or
  credentials. The inference key exists only in the control plane's
  environment file.
- **Contained blast radius.** The sandbox service is bound to loopback
  only, runs with CPU/memory caps, and its data volume can be wiped and
  reset from the dashboard ("Reset fleet"). The only public port on the
  host is the control plane itself.

## Architecture

```
┌─ Vultr Cloud Compute (vc2-2c-4gb, Dallas) ──────────────────────────┐
│  Control plane (FastAPI, systemd, :80)                              │
│   ├─ Monitor   probes → incident detector                           │
│   ├─ Planner   Vultr Serverless Inference → diagnosis + plan        │
│   ├─ Policy    allowlist gate + kill switch (checked per tool call) │
│   ├─ Executor  allowlisted tools only, idempotent mutations         │
│   ├─ Verifier  independent probes (health ×3 + error-rate sample)   │
│   ├─ Memory    SQLite store: incidents, audit, fault→proven fix     │
│   └─ Dashboard audit timeline · chaos panel · ask box · kill switch │
│                                                                     │
│  Sandbox (Docker, loopback :8081, caps: 256 MB / 0.5 CPU)           │
│   └─ shopfront — deliberately breakable demo storefront             │
└─────────────────────────────────────────────────────────────────────┘
   LLM: Vultr Serverless Inference — deepseek-v4.1-flash-1017 (primary),
        qwen3.8-flash-next (fallback), model ID in one env var
```

The hackathon design targets a two-instance topology (control plane +
separate disposable sandbox instance, Managed PostgreSQL memory, Object
Storage reports, Vultr Cloud Firewall). The shipped build co-locates the
planes on one instance with the sandbox as a hardened Docker boundary,
SQLite in the memory seam, reports served from disk, and host firewall
(ufw: only 22 + 80 open) — the containment properties above are the ones
actually enforced by the running system, and the seams (`agent/memory.py`,
`agent/sandbox.py`) are where the managed services drop in.

## How Vultr is used

| Vultr service | Used | Role |
|---|---|---|
| Cloud Compute | ✅ | The instance above hosts control plane + sandbox; provisioned via the Vultr API |
| Serverless Inference | ✅ | **All** LLM calls (diagnosis, planning, request translation) — OpenAI-compatible `https://api.vultrinference.com/v1`; subscription provisioned via the Vultr API |
| Vultr API | ✅ | Instance + inference-subscription provisioning |
| Managed Databases / Object Storage / Cloud Firewall | ⛔ not in this build | Substituted as described in Architecture — not claimed |

## Quick start (judge runbook, < 15 min)

You need Docker and a Vultr Serverless Inference API key (any Vultr account
can create an inference subscription in the console or via
`POST https://api.vultr.com/v2/inference`).

```bash
git clone https://github.com/prasad-anandappa/nightshift-ops.git
cd nightshift-ops
cp .env.example .env            # set VULTR_INFERENCE_API_KEY
cd sandbox && docker compose up -d --build && cd ..
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
set -a; source .env; set +a
NIGHTSHIFT_DB=/tmp/nightshift.db NIGHTSHIFT_REPORTS=/tmp/reports \
  .venv/bin/uvicorn agent.main:app --port 8000
# open http://127.0.0.1:8000/ and press "Ship bad deploy"
```

Without an inference key the dashboard, monitor, chaos panel and policy
gate still run; only the planning step needs the key.

### Tests

```bash
python3 -m pytest tests/ -q     # 20 tests: policy gate, planner parsing,
                                # verifier rules, memory, executor refusals,
                                # classification, full engine loop (faked I/O)
```

The deployed system additionally passed live end-to-end drills on
2026-11-07/08 (bad deploy with memory recall on the repeat, process kill,
disk fill, forbidden-request refusal, kill-switch halt, restart
persistence, and a double-break drill — a second fault injected
mid-verification). Three real defects were found by the drills and fixed,
each with a regression test — see `tests/README.md`.

## Repository layout

- `agent/` — control-plane FastAPI service (monitor, planner, policy,
  executor, verifier, memory, reporter, engine)
- `sandbox/` — the breakable world: `shopfront` demo service + compose file
- `dashboard/` — the control-plane UI (single page, served by FastAPI)
- `infra/` — what was actually provisioned, and lifecycle notes
- `tests/` — unit tests + the live-drill record
- `docs/` — submission notes

## License

MIT — see `LICENSE`.
