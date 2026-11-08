# shopfront (demo service)

A deliberately breakable storefront — the stand-in "production service" the
agent watches. Python standard library only; no dependencies, no secrets.

- `GET /` — storefront page (500s when broken or disk-full, with the kind of
  log lines a real incident produces)
- `GET /health` — 200 `{"status": "ok"}` when healthy; 503 with a reason
  when the release is broken or the data area is over quota
- `GET /__state` — version, data bytes vs quota, request/error counters
  (the agent's evidence surface)
- `POST /__chaos/bad_deploy` — promote the broken release (chaos panel only)
- `POST /__control/rollback` — restore the last-known-good release (this is
  the endpoint the agent's `rollback_deploy` tool calls)

State: release version is in-process; data usage is measured from the real
files in `/data` against `DATA_QUOTA_BYTES` (64 MiB in compose). Process
kill and disk fill are inflicted from outside the container (Docker stop /
filler file) — see `../../chaos/README.md`.
