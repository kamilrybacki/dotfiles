"""Idempotently register jev-gate hooks in Claude Code and Codex CLI configs.

Writes a timestamped backup next to each file before changing it.
Usage: register_hooks.py [--dry-run] [--remove]
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

MARKER = "jev-gate"
GATE = Path.home() / ".local" / "bin" / "jev-gate"
TARGETS = {
    "claude": {
        "path": Path.home() / ".claude" / "settings.json",
        "timeout": 5,  # seconds
        "route_timeout": 15,
        "delegate_tool": "mcp__t3-code__delegate_task",
        "edit_tools": "Edit|Write|MultiEdit|NotebookEdit",
    },
    "codex": {
        "path": Path.home() / ".codex" / "hooks.json",
        "timeout": 5000,  # milliseconds, matching the existing graft hooks
        "route_timeout": 15000,
        "delegate_tool": None,  # Codex has no PreToolUse hook for MCP tools: injection only
    },
}


ROUTE_JEV_TIMEOUT_S = 8


def _entries(harness: str, cfg: dict) -> dict[str, list[dict]]:
    def hook(mode: str, timeout: int, jev_timeout: str = "") -> dict:
        return {"type": "command", "command": f"{GATE} --harness {harness}{jev_timeout} {mode}", "timeout": timeout}

    route_flag = f" --timeout {ROUTE_JEV_TIMEOUT_S}"
    # The exec gate (shell PreToolUse) is intentionally not registered: jev-gate must never
    # block the operator's commands. Re-running this script removes a previously registered
    # one. The only PreToolUse hook is the auto-route check on T3 delegate_task.
    entries = {"UserPromptSubmit": [{"hooks": [hook("context", cfg["timeout"]),
                                               hook("autoroute prompt", cfg["route_timeout"], route_flag)]}]}
    if cfg.get("delegate_tool"):
        entries["PreToolUse"] = [{"matcher": f"{cfg['delegate_tool']}|Agent",
                                  "hooks": [hook("autoroute delegate", cfg["timeout"])]}]
    if cfg.get("delegate_tool") and cfg.get("edit_tools"):
        # Stop enforcement needs both signals: inline edits and delegate_task calls.
        entries["PostToolUse"] = [{"matcher": cfg["edit_tools"], "hooks": [hook("autoroute edit", cfg["timeout"])]}]
        entries["Stop"] = [{"hooks": [hook("autoroute stop", cfg["timeout"])]}]
    return entries


def _strip(groups: list[dict]) -> list[dict]:
    kept = []
    for group in groups:
        hooks = [h for h in group.get("hooks", []) if MARKER not in h.get("command", "")]
        if hooks:
            kept.append({**group, "hooks": hooks})
    return kept


def updated_config(config: dict, harness: str, cfg: dict, remove: bool) -> dict:
    hooks = {event: _strip(groups) for event, groups in config.get("hooks", {}).items()}
    if not remove:
        for event, entries in _entries(harness, cfg).items():
            hooks[event] = [*hooks.get(event, []), *entries]
    return {**config, "hooks": {event: groups for event, groups in hooks.items() if groups}}


def main(argv: list[str]) -> int:
    dry_run, remove = "--dry-run" in argv, "--remove" in argv
    for harness, cfg in TARGETS.items():
        path = cfg["path"]
        if not path.parent.is_dir():
            print(f"{harness}: {path.parent} missing, skipped")
            continue
        current = json.loads(path.read_text()) if path.exists() else {}
        new = updated_config(current, harness, cfg, remove)
        if new == current:
            print(f"{harness}: already up to date")
            continue
        if dry_run:
            print(f"{harness}: would update {path}")
            continue
        if path.exists():
            shutil.copy2(path, path.with_name(f"{path.name}.pre-jev-{int(time.time())}.bak"))
        path.write_text(json.dumps(new, indent=2) + "\n")
        print(f"{harness}: updated {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
