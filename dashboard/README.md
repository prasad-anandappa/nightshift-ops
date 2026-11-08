# Dashboard UI

`index.html` — a single self-contained page served by the control plane at
`/`. It polls `/api/state` every 2 seconds and renders:

- **Fleet status** — live health, release version, data-vs-quota, counters
- **Chaos panel** — ship bad deploy · kill process · fill disk · reset fleet
- **Ask the agent** — free-text requests; allowlisted ones execute,
  everything else is refused in red, on the record (try the
  *forbidden request* button)
- **Kill switch** — engage/release; the executor checks it before every
  tool call
- **Agent memory** — fault signatures and their proven fixes, with counts
- **Incidents** — status per incident, with a link to the full Markdown
  incident report once closed
- **Audit timeline** — every detection, plan, tool call, verification,
  memory event, refusal and kill-switch action, newest first

No build step, no framework, no external assets — it loads identically
offline or in a judge's browser.
