"""Tamper-evident audit logging.

Two layers make the log trustworthy:

1. **Storage you can't rewrite.** Entries go to stdout as structured JSON; on GKE,
   Cloud Logging collects them, and a log sink routes them to a Cloud Storage
   bucket with a *locked* retention policy (gcp/audit_sink.sh). Nobody, not even
   a project owner, can delete or overwrite an object before retention ends.
2. **Evidence if someone tries anyway.** Each entry includes the hash of the
   previous entry, so removing, reordering or editing any entry breaks the chain
   from that point on, and ``verify_chain`` finds where.

Each process keeps its own chain (``chain_id``, e.g. the pod name) because
replicas can't share a counter cheaply; the verifier checks each chain separately.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

GENESIS = "0" * 64


def _canonical(entry: dict[str, Any]) -> bytes:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str).encode()


def entry_hash(entry: dict[str, Any]) -> str:
    unsigned = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _stdout(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


class AuditLog:
    def __init__(self, chain_id: str, sink: Callable[[str], None] = _stdout,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.chain_id, self._sink, self._clock = chain_id, sink, clock
        self._seq, self._prev = 0, GENESIS
        self._lock = threading.Lock()

    def record(self, *, action: str, decision: str, actor: dict[str, Any] | None = None,
               resource: str | None = None, trace_id: str | None = None, **details: Any) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            entry = {
                "event_type": "audit",          # the log sink filters on this field
                "severity": "NOTICE",           # Cloud Logging reads severity from JSON logs
                "chain_id": self.chain_id,
                "seq": self._seq,
                "ts": self._clock().isoformat(),
                "action": action,
                "decision": decision,
                "actor": actor or {},
                "resource": resource,
                "trace_id": trace_id,
                "details": details,
                "prev_hash": self._prev,
            }
            entry["hash"] = entry_hash(entry)
            self._prev = entry["hash"]
            self._sink(json.dumps(entry, sort_keys=True, default=str))
            return entry

    def as_agent_audit(self) -> Callable[[dict[str, Any]], None]:
        """Adapter for Phase 5's policy callbacks (``audit=``)."""

        def audit(event: dict[str, Any]) -> None:
            self.record(action=event.get("event", "agent_event"), decision=event.get("decision", "info"),
                        actor={"agent": event.get("agent")}, resource=event.get("tool"),
                        **{k: v for k, v in event.items() if k not in {"event", "decision", "agent", "tool"}})

        return audit


def verify_chain(lines: Iterable[str]) -> dict[str, Any]:
    """Check every chain in a stream of audit lines. Returns ok + where it broke."""
    chains: dict[str, list[dict[str, Any]]] = {}
    for line in lines:
        if line.strip():
            entry = json.loads(line)
            if entry.get("event_type") == "audit":
                chains.setdefault(entry["chain_id"], []).append(entry)
    report: dict[str, Any] = {"ok": True, "chains": {}}
    for chain_id, entries in chains.items():
        entries.sort(key=lambda e: e["seq"])
        prev, problem = GENESIS, None
        for expected_seq, entry in enumerate(entries, start=1):
            if entry["seq"] != expected_seq:
                problem = f"missing entry before seq {entry['seq']}"
            elif entry["prev_hash"] != prev:
                problem = f"seq {entry['seq']} does not link to the previous entry"
            elif entry_hash(entry) != entry["hash"]:
                problem = f"seq {entry['seq']} was modified"
            if problem:
                break
            prev = entry["hash"]
        report["chains"][chain_id] = {"entries": len(entries), "problem": problem}
        report["ok"] = report["ok"] and problem is None
    return report


if __name__ == "__main__":  # python -m costpilot_security.audit < exported_audit.jsonl
    print(json.dumps(verify_chain(sys.stdin), indent=2))
