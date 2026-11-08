"""Memory: incidents, audit records and proven fixes.

Sprint implementation uses SQLite on the control plane (zero extra services to
provision overnight); the schema mirrors the DESIGN's Managed-PostgreSQL
intent — fault signature -> proven fix — and this store is the seam where the
managed database drops in.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time


class Store:
    def __init__(self, path: str | None = None):
        if path is None:
            from .config import settings

            path = settings.db_path
        self.path = path
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY, service TEXT, signature TEXT,
                    status TEXT, opened_at REAL, closed_at REAL,
                    payload TEXT
                );
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL,
                    incident_id TEXT, kind TEXT, message TEXT, data TEXT
                );
                CREATE TABLE IF NOT EXISTS proven_fixes (
                    signature TEXT PRIMARY KEY, tools TEXT,
                    successes INTEGER DEFAULT 0, last_used REAL
                );
                """
            )

    def save_incident(self, inc) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO incidents VALUES (?,?,?,?,?,?,?)",
                (
                    inc.id,
                    inc.service,
                    inc.signature.value,
                    inc.status.value,
                    inc.opened_at,
                    inc.closed_at,
                    inc.model_dump_json(),
                ),
            )

    def add_audit(self, ev) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO audit (ts, incident_id, kind, message, data) VALUES (?,?,?,?,?)",
                (ev.ts, ev.incident_id, ev.kind, ev.message, json.dumps(ev.data)),
            )

    def record_proven_fix(self, signature: str, tools: list[str]) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO proven_fixes (signature, tools, successes, last_used)
                VALUES (?,?,1,?)
                ON CONFLICT(signature) DO UPDATE SET
                    tools=excluded.tools,
                    successes=successes+1,
                    last_used=excluded.last_used
                """,
                (signature, json.dumps(tools), time.time()),
            )

    def recall_fix(self, signature: str) -> list[str] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT tools FROM proven_fixes WHERE signature=?", (signature,)
            ).fetchone()
        return json.loads(row["tools"]) if row else None

    def list_incidents(self, limit: int = 8) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT payload FROM incidents ORDER BY opened_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def list_audit(self, limit: int = 120) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, incident_id, kind, message, data FROM audit ORDER BY seq DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "ts": r["ts"],
                "incident_id": r["incident_id"],
                "kind": r["kind"],
                "message": r["message"],
                "data": json.loads(r["data"] or "{}"),
            }
            for r in rows
        ]

    def memory_snapshot(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT signature, tools, successes, last_used FROM proven_fixes ORDER BY last_used DESC"
            ).fetchall()
        return [dict(r) for r in rows]


store = Store()
