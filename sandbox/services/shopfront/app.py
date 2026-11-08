"""Shopfront — the deliberately breakable demo service.

A tiny storefront served with the Python standard library only. It keeps a
release version and a data area with a fixed quota, and it fails the way real
services fail:

- a "bad deploy" flips the release to `broken`  -> every request 500s,
  /health goes red, ERROR lines hit the logs;
- its data area filling past quota              -> writes fail with
  "No space left on device", /health goes red;
- the process being killed                      -> connections refused.

Control endpoints (used by the chaos panel and by the agent's one control
tool, rollback) live under /__chaos and /__control. The service holds no
credentials of any kind.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA_DIR = os.environ.get("DATA_DIR", "/data")
QUOTA = int(os.environ.get("DATA_QUOTA_BYTES", str(64 * 1024 * 1024)))
PORT = int(os.environ.get("PORT", "8080"))

_state = {"version": "v1.4.2-good", "requests": 0, "errors": 0}
_lock = threading.Lock()


def data_bytes() -> int:
    total = 0
    for root, _dirs, files in os.walk(DATA_DIR):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def disk_full() -> bool:
    return data_bytes() > QUOTA


def broken() -> bool:
    return _state["version"].endswith("broken")


def log(msg: str) -> None:
    print(msg, flush=True)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, ctype: str = "text/html") -> None:
        payload = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        with _lock:
            _state["requests"] += 1
        if self.path == "/health":
            if broken():
                log("ERROR healthcheck failed: release v1.5.0-broken crashed on boot (config key 'paymnt_gateway' not found)")
                self._send(503, json.dumps({"status": "unhealthy", "reason": "bad release"}), "application/json")
                return
            if disk_full():
                log("ERROR healthcheck failed: data area over quota — writes failing with 'No space left on device'")
                self._send(503, json.dumps({"status": "unhealthy", "reason": "disk full"}), "application/json")
                return
            self._send(200, json.dumps({"status": "ok", "version": _state["version"]}), "application/json")
            return
        if self.path == "/__state":
            self._send(
                200,
                json.dumps(
                    {
                        "service": "shopfront",
                        "version": _state["version"],
                        "data_bytes": data_bytes(),
                        "data_quota_bytes": QUOTA,
                        "requests": _state["requests"],
                        "errors": _state["errors"],
                    }
                ),
                "application/json",
            )
            return
        # storefront root
        if broken():
            with _lock:
                _state["errors"] += 1
            log("ERROR GET / -> 500 Internal Server Error: TypeError in release v1.5.0-broken (checkout handler 'paymnt_gateway' undefined)")
            self._send(500, "<h1>500 — Shopfront is down</h1><p>Something in the latest release broke checkout.</p>")
            return
        if disk_full():
            with _lock:
                _state["errors"] += 1
            log("ERROR GET / -> 500: OSError [Errno 28] No space left on device while writing session cache")
            self._send(500, "<h1>500 — Shopfront is down</h1><p>Storage is full.</p>")
            return
        self._send(
            200,
            "<h1>🌙 NightShift Demo Shopfront</h1>"
            f"<p>Release {_state['version']} — all systems nominal.</p>"
            "<p>Demo fleet for NightShift Ops. Break it from the control "
            "plane's chaos panel and watch the agent fix it.</p>",
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/__chaos/bad_deploy":
            with _lock:
                _state["version"] = "v1.5.0-broken"
            log("WARN deploy pipeline: release v1.5.0-broken promoted to production")
            self._send(200, json.dumps({"ok": True, "version": _state["version"]}), "application/json")
            return
        if self.path == "/__control/rollback":
            with _lock:
                _state["version"] = "v1.4.2-good"
            log("INFO rollback: release restored to v1.4.2-good")
            self._send(200, json.dumps({"ok": True, "version": _state["version"]}), "application/json")
            return
        self._send(404, "not found", "text/plain")

    def log_message(self, fmt: str, *args) -> None:  # keep stdout for app logs
        log(f"access: {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    log(f"shopfront listening on :{PORT}, release {_state['version']}, data quota {QUOTA} bytes")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
