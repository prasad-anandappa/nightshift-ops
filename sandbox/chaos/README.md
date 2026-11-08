# Chaos — reproducible faults, on demand

Three faults, each detected by the monitor, each reversible by exactly the
allowlisted tool a real on-call engineer would reach for:

| Fault | How it is inflicted | Signature | Fix tool |
|---|---|---|---|
| Ship bad deploy | `POST /__chaos/bad_deploy` on shopfront flips its release to `v1.5.0-broken` (every request 500s, health red, ERROR logs) | `bad_deploy` | `rollback_deploy` |
| Kill process | `docker stop nightshift-shopfront` | `process_down` | `restart_service` |
| Fill disk | 96 MB filler written to the service's data area (quota 64 MiB) → writes fail with *No space left on device* | `disk_pressure` | `clear_temp_files` |

The chaos controls are operated by the human (dashboard **Chaos panel** or
`POST /api/chaos/{bad_deploy|kill_process|fill_disk|reset}` on the control
plane). The agent has no access to them — it only gets the seven allowlisted
operational tools, which is precisely the asymmetry the demo exists to show.
`reset` restores a clean fleet (start container, clear filler, roll back).
