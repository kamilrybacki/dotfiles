"""Subscription budget pressure from the local quota-axi cache.

quota-axi (status line) writes ~/.cache/quota-axi/quotas.json every few minutes with the
Claude, Codex and OpenCode Go windows (percentUsed, resetsAt, windowSeconds). For each
window we project the usage at reset from the pace so far (used / elapsed fraction) and
map the worst window of a provider to a pressure level:

  0 - on pace (projection < 80 %)        no change
  1 - tight   (projection < 100 %)       non-critical work one tier lower
  2 - over    (projection < 130 %)       two tiers lower
  3 - burning (projection >= 130 % or used >= 90 %)  prefer another vendor

No cache, a stale cache or an unreadable file gives no pressure for any provider, so
routing behaves exactly as without budget awareness. Snapshots are appended to
~/.local/state/jev/usage.jsonl (at most every SNAPSHOT_EVERY_S) for trends over time.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

CACHE_PATH = Path.home() / ".cache" / "quota-axi" / "quotas.json"
USAGE_LOG = Path.home() / ".local" / "state" / "jev" / "usage.jsonl"
MAX_AGE_S = 30 * 60
SNAPSHOT_EVERY_S = 10 * 60
MIN_ELAPSED = 0.15        # earlier than this in a window the pace is noise: use percentUsed only
THRESHOLDS = (80.0, 100.0, 130.0)
USED_BURNING = 90.0
# quota-axi provider -> T3 providerInstanceId
PROVIDERS = {"claude": "claudeAgent", "codex": "codex", "opencode-go": "opencode"}


def _ts(value) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def project(window: dict, now: float) -> float | None:
    """Projected percent used at reset, or None when the window has no usage number."""
    used = window.get("percentUsed")
    if not isinstance(used, (int, float)):
        return None
    resets, length = _ts(window.get("resetsAt")), window.get("windowSeconds")
    starts = _ts(window.get("startsAt"))
    if resets and not isinstance(length, (int, float)) and starts:
        length = resets - starts
    if not resets or not isinstance(length, (int, float)) or length <= 0:
        return float(used)
    elapsed = 1.0 - max(0.0, resets - now) / length
    if elapsed < MIN_ELAPSED:
        return float(used)
    return float(used) / min(elapsed, 1.0)


def level(window: dict, now: float) -> int:
    projected = project(window, now)
    if projected is None:
        return 0
    if float(window["percentUsed"]) >= USED_BURNING:
        return 3
    return sum(projected >= t for t in THRESHOLDS)


def _load(path: Path, now: float) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    generated = _ts(data.get("generatedAt")) if isinstance(data, dict) else None
    if not generated or now - generated > MAX_AGE_S:
        return None
    return data


def _worst(windows: list, now: float) -> dict | None:
    worst = None
    for window in windows:
        if not isinstance(window, dict) or str(window.get("id", "")).startswith("model:"):
            continue
        projected = project(window, now)
        if projected is None:
            continue
        entry = {"level": level(window, now), "window": window.get("id"),
                 "used": window.get("percentUsed"), "projected": round(projected)}
        if worst is None or (entry["level"], entry["projected"]) > (worst["level"], worst["projected"]):
            worst = entry
    return worst


def pressure(now: float | None = None) -> dict[str, dict]:
    """{providerInstanceId: {"level": 0-3, "window": id, "used": %, "projected": %}}."""
    now = time.time() if now is None else now
    data = _load(Path(os.environ.get("JEV_QUOTA_CACHE", CACHE_PATH)), now)
    if not data:
        return {}
    result = {}
    for provider in data.get("providers") or []:
        if not isinstance(provider, dict):
            continue
        name = PROVIDERS.get(provider.get("provider"))
        if not name or (provider.get("state") or {}).get("stale"):
            continue
        worst = _worst(provider.get("windows") or [], now)
        if worst:
            result[name] = worst
    _snapshot(result, now)
    return result


def level_of(pressures: dict[str, dict], target: dict | None) -> int:
    if not target:
        return 0
    return int((pressures.get(target.get("providerInstanceId")) or {}).get("level", 0))


def _snapshot(result: dict, now: float) -> None:
    if not result:
        return
    path = Path(os.environ.get("JEV_USAGE_LOG", USAGE_LOG))
    try:
        if path.exists() and time.time() - path.stat().st_mtime < SNAPSHOT_EVERY_S:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps({"ts": round(now), "pressure": result}) + "\n")
    except OSError:
        pass
