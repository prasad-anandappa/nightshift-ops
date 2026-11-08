# Infrastructure — what is actually provisioned

All provisioning was done through the Vultr API on the author's existing
Vultr account (Nov 7, 2026).

| Item | Detail |
|---|---|
| Instance | `nightshift-ops` — id `3734a89f-e0e5-4ff1-b5c3-58d2b36b8b35`, plan `vc2-2c-4gb` (2 vCPU / 4 GB), Ubuntu 24.04 LTS, region **dfw** (Dallas), IP **155.138.254.23**, $20/mo ($0.027/hr) |
| Serverless Inference | Subscription `nightshift-ops` — id `2f82dbc2-d902-44f4-8569-e9b06d0dfd05`, active. Models in use: `deepseek-v4.1-flash-1017` (primary), `qwen3.8-flash-next` (fallback) |
| Host firewall | ufw active, default deny incoming; **22/tcp + 80/tcp open** — nothing else. The Vultr image ships ufw deny-by-default; port 80 was opened deliberately for the demo |
| Sandbox exposure | The shopfront container binds **127.0.0.1:8081** only — never public. Only the control plane (port 80) faces the internet |
| Services | `nightshift.service` (systemd: uvicorn on :80, `Restart=always`, env from `/opt/nightshift/app.env`, mode 600) + Docker container `nightshift-shopfront` (compose, caps 256 MB / 0.5 CPU) |
| State | SQLite at `/opt/nightshift/nightshift.db`; incident reports at `/opt/nightshift/reports/`; both survive restarts (verified) |
| Account note | The account also runs the author's pre-existing production VPS (Bangalore) — untouched by this project. The hackathon's $200 kickoff credit requires a *new* account on a new email (founder step, pending); this build runs on the existing account's balance, ~$0.65/day at current scope |

## Lifecycle

- **Reset the world:** dashboard → *Reset fleet* (restarts the container,
  clears filler/temp data, rolls back the release) — the sandbox is
  disposable by design.
- **Rebuild from scratch:** re-provision an instance, install
  `docker.io docker-compose-v2 python3-venv`, copy the repo to
  `/opt/nightshift/nightshift-ops`, `docker compose up -d --build` in
  `sandbox/`, create the venv + `pip install -r requirements.txt`, drop the
  env file, enable the systemd unit. ≈ 10 minutes.
- **Keep-alive rule:** the control plane stays up after submission —
  judges must be able to open the demo URL.
