# Sandbox — the breakable world

A Docker Compose fleet of demo services the agent is allowed to operate on.
Sprint fleet: **one service, wired completely** — `shopfront`, a tiny
storefront (Python standard library only) that fails the way real services
fail. The pattern repeats per service; one complete loop beats three stubs.

Containment, as actually configured in `docker-compose.yml`:

- the container binds **127.0.0.1:8081** — reachable from the control plane
  on the same host, never from the internet;
- resource caps on the service: **256 MB memory, 0.5 CPU**;
- the service holds **no secrets** — no API keys, no credentials, nothing
  worth stealing (secret hygiene per the challenge brief);
- its data lives in a named volume (`shopdata`) the lifecycle drill can
  wipe; the dashboard's *Reset fleet* restores a clean world in seconds;
- `restart: "no"` — if the process is killed, it stays dead until the
  agent (or a human) restarts it. That is what makes the kill drill real.

Run it: `docker compose up -d --build` → service on http://127.0.0.1:8081
(`/` storefront, `/health`, `/__state`).
