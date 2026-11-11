"""Metadata-only audit records for authenticated mutations."""
import json
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path


class MutationAudit:
    def __init__(self, path, *, retention_days=None):
        if retention_days is not None and (type(retention_days) is not int or retention_days < 1):
            raise ValueError("Audit retention must be a positive number of days.")
        self.path = Path(path)
        self.retention_days = retention_days
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS mutation_audit (
                id INTEGER PRIMARY KEY, started_at INTEGER NOT NULL, finished_at INTEGER,
                tenant_id TEXT NOT NULL, caller_id TEXT NOT NULL, request_id TEXT NOT NULL,
                operation TEXT NOT NULL, targets TEXT NOT NULL, outcome TEXT NOT NULL)""")

    @contextmanager
    def record(self, context, operation, targets):
        now = int(time.time())
        with closing(sqlite3.connect(self.path)) as conn, conn:
            if self.retention_days is not None:
                conn.execute("DELETE FROM mutation_audit WHERE finished_at < ?",
                             (now - self.retention_days * 86400,))
            event = conn.execute("""INSERT INTO mutation_audit
                (started_at, tenant_id, caller_id, request_id, operation, targets, outcome)
                VALUES (?, ?, ?, ?, ?, ?, 'started')""",
                (now, context.tenant_id, context.caller_id, context.request_id, operation,
                 json.dumps(targets))).lastrowid
        result = {}
        outcome = "error"
        try:
            yield result
            outcome = result.get("status") or "returned"
        finally:
            with closing(sqlite3.connect(self.path)) as conn, conn:
                conn.execute("UPDATE mutation_audit SET finished_at = ?, outcome = ? WHERE id = ?",
                             (int(time.time()), outcome, event))
