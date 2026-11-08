"""Policy gate: the tool allowlist and refusal rules (DESIGN §1.3, §2).

The executor may run ONLY these tools, ONLY against the sandbox fleet.
Anything else — however the request is phrased, whoever (or whatever)
proposes it — is refused and written to the audit timeline. The refusal is a
feature: it is the containment moment the challenge asks to see.
"""

from __future__ import annotations

ALLOWLIST: dict[str, str] = {
    "read_logs": "Read recent logs of a sandbox service.",
    "check_health": "Probe a sandbox service's health endpoint.",
    "check_disk": "Report disk usage inside the sandbox service's data area.",
    "restart_service": "Restart a sandbox service container.",
    "clear_temp_files": "Delete temp/filler files inside the sandbox data area.",
    "rollback_deploy": "Restore the sandbox service's last-known-good release.",
    "run_health_suite": "Run the independent health + error-rate suite.",
}

ALLOWED_SERVICES = {"shopfront"}


class PolicyViolation(Exception):
    def __init__(self, tool: str, reason: str):
        super().__init__(reason)
        self.tool = tool
        self.reason = reason


def check_tool(tool: str, args: dict | None = None) -> None:
    """Raise PolicyViolation if this tool call may not execute."""
    if tool not in ALLOWLIST:
        raise PolicyViolation(
            tool,
            f"Tool '{tool}' is not on the NightShift allowlist. "
            "The agent's mandate covers a fixed set of sandbox operations only; "
            "everything else is refused and logged.",
        )
    service = (args or {}).get("service", "shopfront")
    if service not in ALLOWED_SERVICES:
        raise PolicyViolation(
            tool,
            f"Service '{service}' is outside the sandbox fleet the agent may touch.",
        )


def kill_switch_active(path: str) -> bool:
    import os

    return os.path.exists(path)
