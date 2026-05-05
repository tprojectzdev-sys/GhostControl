"""Append-only JSONL audit log.

One line per event. Designed so a human can `tail -f audit.jsonl` and so a
log shipper can parse it. No locks beyond Python's GIL — single-process
deploy on Railway / Fly is the supported topology.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from typing import Any, Iterable


_LOG_LOCK = threading.Lock()
_RECENT: deque[dict[str, Any]] = deque(maxlen=200)


def _now_ms() -> int:
    return int(time.time() * 1000)


def write_event(path: str, **fields: Any) -> dict[str, Any]:
    """Append a JSON line to the audit log and return the event dict.

    Always sets ts_ms and event keys; extra keys are passed through.
    """
    event = {"ts_ms": _now_ms(), **fields}
    line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    with _LOG_LOCK:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        _RECENT.append(event)
    return event


def recent(limit: int = 50) -> list[dict[str, Any]]:
    """Most recent events, newest last. Cheap to read; for the dashboard."""
    with _LOG_LOCK:
        items = list(_RECENT)
    return items[-limit:]


def replay_recent_from_disk(path: str, limit: int = 200) -> None:
    """Backfill the in-memory ring buffer on startup so the dashboard's
    `/v1/audit` returns history across restarts."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            tail = _tail_lines(f, limit)
        with _LOG_LOCK:
            _RECENT.clear()
            for line in tail:
                line = line.strip()
                if not line:
                    continue
                try:
                    _RECENT.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _tail_lines(f: Iterable[str], n: int) -> list[str]:
    """Pull the last n lines from an iterable text file. Memory-bounded."""
    buf: deque[str] = deque(maxlen=n)
    for line in f:
        buf.append(line)
    return list(buf)
