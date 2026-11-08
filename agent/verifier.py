"""Verifier: INDEPENDENT probes decide whether an incident may close.

The verifier talks to the service directly and never reads executor state —
the agent never grades its own homework (DESIGN §1.4). An incident closes
only on: health 200 on 3 consecutive checks AND a 10-request error-rate
sample at or below 10% errors.
"""

from __future__ import annotations

import time

from .sandbox import probe_error_rate, probe_health


def verify(rounds: int = 3, spacing_s: float = 1.0) -> dict:
    health_checks: list[str] = []
    passed = True
    for i in range(rounds):
        ok, detail = probe_health()
        health_checks.append(detail)
        if not ok:
            passed = False
            break
        if i < rounds - 1:
            time.sleep(spacing_s)
    error_rate = probe_error_rate(10)
    if error_rate > 0.1:
        passed = False
    return {
        "passed": passed,
        "health_checks": health_checks,
        "error_rate": error_rate,
        "rule": "health 200 x3 consecutive AND error_rate <= 0.10 over 10 requests",
    }
