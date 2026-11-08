"""Monitor: health probes on an interval -> incident detector.

No human in the loop (DESIGN §1.1): sustained probe failure opens an
incident and hands it to the engine in a worker thread.
"""

from __future__ import annotations

import threading
import time

from . import engine, sandbox
from .config import settings
from .models import Incident

_state = {"healthy": True, "detail": "starting", "failures": 0, "last_probe": 0.0}
_stop = threading.Event()


def fleet_status() -> dict:
    return dict(_state)


def _loop() -> None:
    while not _stop.is_set():
        ok, detail = sandbox.probe_health()
        _state.update({"healthy": ok, "detail": detail, "last_probe": time.time()})
        if ok:
            _state["failures"] = 0
        else:
            _state["failures"] += 1
            if (
                _state["failures"] >= settings.probe_failure_threshold
                and engine.active_incident() is None
            ):
                inc = Incident()
                threading.Thread(target=engine.handle_incident, args=(inc,), daemon=True).start()
                _state["failures"] = 0
        _stop.wait(settings.probe_interval_s)


def start() -> threading.Thread:
    t = threading.Thread(target=_loop, daemon=True, name="monitor")
    t.start()
    return t
