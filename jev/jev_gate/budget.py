"""Subscription budget pressure from T3's provider snapshots and quota-axi.

quota-axi (status line) writes ~/.cache/quota-axi/quotas.json every few minutes with the
Claude, Codex and OpenCode Go windows (percentUsed, resetsAt, windowSeconds). For each
window we project the usage at reset from the pace so far (used / elapsed fraction) and
map the worst window of a provider to a pressure level:

  0 - on pace (projection < 80 %)        no change
  1 - tight   (projection < 100 %)       non-critical work one tier lower
  2 - over    (projection < 130 %)       two tiers lower
  3 - burning (projection >= 130 % or used >= 90 %)  prefer another vendor

Fresh T3 snapshots take precedence for each provider. T3 pace uses its exact
used-percent minus elapsed-window calculation with a ±5 percentage point band.
Missing, stale or unavailable T3 data falls back to quota-axi for that provider.
Without either source routing behaves exactly as without budget awareness. Snapshots are appended to
~/.local/state/jev/usage.jsonl (at most every SNAPSHOT_EVERY_S) for trends over time.
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

CACHE_PATH = Path.home() / ".cache" / "quota-axi" / "quotas.json"
T3_CACHE_DIR = Path.home() / ".t3" / "caches"
USAGE_LOG = Path.home() / ".local" / "state" / "jev" / "usage.jsonl"
MAX_AGE_S = 30 * 60
SNAPSHOT_EVERY_S = 10 * 60
MIN_ELAPSED = 0.15        # earlier than this in a window the pace is noise: use percentUsed only
THRESHOLDS = (80.0, 100.0, 130.0)
USED_BURNING = 90.0
# quota-axi provider -> T3 providerInstanceId
PROVIDERS = {"claude": "claudeAgent", "codex": "codex", "opencode-go": "opencode"}
T3_WINDOWS = {
    "codex": {"primary", "secondary"},
    "claudeAgent": {"five_hour", "seven_day"},
    "opencode": {"go_rolling", "go_weekly", "go_monthly"},
}


def _ts(value) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def project(window: dict, now: float) -> float | None:
    """Projected percent used at reset, or None when the window has no usage number."""
    used = window.get("percentUsed")
    if (isinstance(used, bool) or not isinstance(used, (int, float))
            or not math.isfinite(used) or not 0 <= used <= 100):
        return None
    resets, length = _ts(window.get("resetsAt")), window.get("windowSeconds")
    starts = _ts(window.get("startsAt"))
    if resets and not isinstance(length, (int, float)) and starts:
        length = resets - starts
    if (not resets or isinstance(length, bool) or not isinstance(length, (int, float))
            or not math.isfinite(length) or length <= 0):
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
    if not generated or generated > now + 60 or now - generated > MAX_AGE_S:
        return None
    return data


def _worst(windows: list, now: float) -> dict | None:
    worst = None
    for window in windows:
        if not isinstance(window, dict) or str(window.get("id", "")).startswith("model:"):
            continue
        reset = _ts(window.get("resetsAt"))
        if reset is not None and reset <= now:
            continue
        projected = project(window, now)
        if projected is None:
            continue
        entry = {"level": level(window, now), "window": window.get("id"),
                 "used": window.get("percentUsed"), "projected": round(projected)}
        if worst is None or (entry["level"], entry["projected"]) > (worst["level"], worst["projected"]):
            worst = entry
    return worst


def _t3_worst(provider: str, data: dict, now: float) -> dict | None:
    """Use the same elapsed-time / used-percent gap and ±5 pp as T3's pace icon."""
    if (data.get("instanceId") != provider or data.get("driver") != provider
            or data.get("enabled") is not True):
        return None
    limits = data.get("usageLimits")
    if not isinstance(limits, dict) or limits.get("unavailable"):
        return None
    checked = _ts(limits.get("checkedAt"))
    if checked is None or checked > now + 60 or now - checked > MAX_AGE_S:
        return None
    windows = limits.get("windows")
    if not isinstance(windows, list):
        return None
    worst = None
    for window in windows:
        if (not isinstance(window, dict) or not isinstance(window.get("id"), str)
                or window["id"] not in T3_WINDOWS[provider]):
            continue
        used = window.get("usedPercent")
        if (isinstance(used, bool) or not isinstance(used, (int, float))
                or not math.isfinite(used) or not 0 <= used <= 100):
            continue
        reset = _ts(window.get("resetsAt"))
        if reset is not None and reset <= now:
            continue
        minutes = window.get("windowDurationMins")
        pace, gap, projected = None, None, float(used)
        if (reset is not None and isinstance(minutes, (int, float))
                and not isinstance(minutes, bool) and math.isfinite(minutes) and minutes > 0):
            elapsed = max(0.0, min(1.0, 1.0 - (reset - now) / (minutes * 60)))
            gap = used - elapsed * 100
            pace = "ahead" if gap > 5 else "under" if gap < -5 else "on"
            if elapsed >= MIN_ELAPSED:
                projected = used / elapsed
        severity = 3 if used >= USED_BURNING else (
            max(1, sum(projected >= t for t in THRESHOLDS)) if pace == "ahead" else 0
        )
        if pace is None and severity == 0:
            continue
        entry = {"level": severity, "window": window["id"], "used": used,
                 "projected": round(projected), "pace": pace,
                 "gap": round(gap, 1) if gap is not None else None, "source": "t3"}
        # Prefer an ahead window over an on/under/unknown window at equal severity.
        rank = (severity, 1 if pace == "ahead" else 0, gap if gap is not None else -101)
        if worst is None or rank > worst[0]:
            worst = (rank, entry)
    return worst[1] if worst else None


def _t3_pressures(now: float) -> dict[str, dict]:
    directory = Path(os.environ.get("JEV_T3_PROVIDER_CACHE", T3_CACHE_DIR))
    result = {}
    for provider in T3_WINDOWS:
        try:
            data = json.loads((directory / f"{provider}.json").read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            entry = _t3_worst(provider, data, now)
            if entry is not None:
                result[provider] = entry
    return result


def pressure(now: float | None = None) -> dict[str, dict]:
    """{providerInstanceId: {"level": 0-3, "window": id, "used": %, "projected": %}}."""
    now = time.time() if now is None else now
    data = _load(Path(os.environ.get("JEV_QUOTA_CACHE", CACHE_PATH)), now)
    result = {}
    providers = (data or {}).get("providers")
    for provider in providers if isinstance(providers, list) else []:
        if not isinstance(provider, dict):
            continue
        raw_name = provider.get("provider")
        name = PROVIDERS.get(raw_name) if isinstance(raw_name, str) else None
        state = provider.get("state")
        if not name or (isinstance(state, dict) and state.get("stale")):
            continue
        windows = provider.get("windows")
        worst = _worst(windows if isinstance(windows, list) else [], now)
        if worst:
            result[name] = worst
    # T3's snapshots describe the actual instances routed by this server. Use
    # them only when fresh; otherwise retain quota-axi as the per-provider fallback.
    result.update(_t3_pressures(now))
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
