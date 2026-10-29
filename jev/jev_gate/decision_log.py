"""Append-only JSONL log of every gate decision (already redacted)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

LOG_PATH = Path(os.environ.get("JEV_LOG", Path.home() / ".local" / "state" / "jev" / "decisions.jsonl"))


def record(event: str, **fields: object) -> None:
    entry = {"ts": round(time.time(), 3), "event": event, **fields}
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as handle:
            handle.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass  # logging must never break the harness
