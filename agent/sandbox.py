"""Sandbox interface: the ONLY channel through which the agent touches the
world. Everything here is confined to the demo fleet's Docker container on
this host — fixed argv, no shell, no model-supplied commands. The sandbox
container holds no API keys or credentials (secret hygiene, per the brief).
"""

from __future__ import annotations

import subprocess

import httpx

from .config import settings
from .models import FaultSignature

BASE = settings.sandbox_service_url
CONTAINER = settings.sandbox_container


def _docker(*args: str, timeout: float = 30.0) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=timeout
        )
        out = (proc.stdout + proc.stderr).strip()
        return proc.returncode == 0, out[-2000:]
    except Exception as exc:
        return False, f"docker error: {exc}"


# ---------------------------------------------------------------- probes
def probe_health() -> tuple[bool, str]:
    try:
        r = httpx.get(f"{BASE}/health", timeout=3.0)
        if r.status_code == 200:
            return True, "health 200 OK"
        return False, f"health HTTP {r.status_code}: {r.text[:160]}"
    except Exception as exc:
        return False, f"health unreachable: {type(exc).__name__}"


def probe_error_rate(samples: int = 10) -> float:
    errors = 0
    for _ in range(samples):
        try:
            r = httpx.get(f"{BASE}/", timeout=3.0)
            if r.status_code >= 500:
                errors += 1
        except Exception:
            errors += 1
    return errors / samples


def service_state() -> dict:
    try:
        r = httpx.get(f"{BASE}/__state", timeout=3.0)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def gather_evidence() -> dict:
    ok, detail = probe_health()
    state = service_state()
    _, logs = tool_read_logs(30)
    evidence = {
        "health_probe": detail,
        "error_rate_sample": probe_error_rate(10) if ok or state else 1.0,
        "deploy_version": state.get("version", "unreachable"),
        "data_bytes": state.get("data_bytes", "unknown"),
        "data_quota_bytes": state.get("data_quota_bytes", "unknown"),
        "recent_logs": logs[-1200:],
    }
    return evidence


def classify(evidence: dict) -> FaultSignature:
    health = str(evidence.get("health_probe", ""))
    if "unreachable" in health:
        return FaultSignature.PROCESS_DOWN
    try:
        used = float(evidence.get("data_bytes", 0))
        quota = float(evidence.get("data_quota_bytes", 0))
        if quota and used > quota:
            return FaultSignature.DISK_PRESSURE
    except (TypeError, ValueError):
        pass
    if "broken" in str(evidence.get("deploy_version", "")):
        return FaultSignature.BAD_DEPLOY
    if float(evidence.get("error_rate_sample", 0)) >= 0.3:
        return FaultSignature.ERROR_SPIKE
    return FaultSignature.UNKNOWN


# ---------------------------------------------------------------- tools
def tool_read_logs(lines: int = 40) -> tuple[bool, str]:
    return _docker("logs", "--tail", str(lines), CONTAINER)


def tool_check_health() -> tuple[bool, str]:
    ok, detail = probe_health()
    return ok, detail


def tool_check_disk() -> tuple[bool, str]:
    ok, out = _docker("exec", CONTAINER, "du", "-sb", "/data")
    state = service_state()
    detail = f"du: {out} | service state: data_bytes={state.get('data_bytes')} quota={state.get('data_quota_bytes')}"
    return ok, detail


def tool_restart_service() -> tuple[bool, str]:
    return _docker("restart", CONTAINER, timeout=60.0)


def tool_clear_temp_files() -> tuple[bool, str]:
    return _docker(
        "exec", CONTAINER, "sh", "-c", "rm -f /data/filler.bin; rm -rf /data/tmp/*; true"
    )


def tool_rollback_deploy() -> tuple[bool, str]:
    try:
        r = httpx.post(f"{BASE}/__control/rollback", timeout=5.0)
        return r.status_code == 200, f"rollback -> HTTP {r.status_code}: {r.text[:200]}"
    except Exception as exc:
        return False, f"rollback failed: {exc}"


TOOLS = {
    "read_logs": lambda args: tool_read_logs(int(args.get("lines", 40))),
    "check_health": lambda args: tool_check_health(),
    "check_disk": lambda args: tool_check_disk(),
    "restart_service": lambda args: tool_restart_service(),
    "clear_temp_files": lambda args: tool_clear_temp_files(),
    "rollback_deploy": lambda args: tool_rollback_deploy(),
}


# ---------------------------------------------------------------- chaos
# The breakable world. These are operated by the human/demo panel — the
# agent itself has no access to them.
def chaos_bad_deploy() -> tuple[bool, str]:
    try:
        r = httpx.post(f"{BASE}/__chaos/bad_deploy", timeout=5.0)
        return r.status_code == 200, f"bad deploy shipped -> HTTP {r.status_code}"
    except Exception as exc:
        return False, f"chaos failed: {exc}"


def chaos_kill_process() -> tuple[bool, str]:
    return _docker("stop", CONTAINER, timeout=30.0)


def chaos_fill_disk() -> tuple[bool, str]:
    return _docker(
        "exec",
        CONTAINER,
        "sh",
        "-c",
        "dd if=/dev/zero of=/data/filler.bin bs=1M count=96 status=none; true",
        timeout=60.0,
    )


def chaos_reset() -> tuple[bool, str]:
    _docker("start", CONTAINER, timeout=30.0)
    tool_clear_temp_files()
    ok, msg = tool_rollback_deploy()
    return ok, f"fleet reset: {msg}"
