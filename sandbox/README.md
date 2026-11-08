# Sandbox — the breakable world (runs ONLY on the disposable Vultr sandbox instance)

Docker Compose fleet of demo services the agent is allowed to operate on.
The agent's credentials reach only this instance; it is firewalled
(inbound = control plane + operator IP) and rebuildable from a Vultr
snapshot — that disposability is what makes real fix actions safe.

TODO (Nov 4): compose file with resource limits (time/memory caps per the
live challenge brief), health endpoints, structured logs.
TODO: NO secrets inside the sandbox (live brief: secret hygiene).
