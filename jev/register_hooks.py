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
        "shell_matcher": "Bash",
    },
    "codex": {
        "path": Path.home() / ".codex" / "hooks.json",
        "timeout": 5000,  # milliseconds, matching the existing graft hooks
        "shell_matcher": "Bash|shell|local_shell|exec_command",
    },
}


def _entries(harness: str, cfg: dict) -> dict[str, dict]:
    def hook(mode: str) -> dict:
        return {"type": "command", "command": f"{GATE} --harness {harness} {mode}", "timeout": cfg["timeout"]}

    return {
        "PreToolUse": {"matcher": cfg["shell_matcher"], "hooks": [hook("exec")]},
        "UserPromptSubmit": {"hooks": [hook("context")]},
    }


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
        for event, entry in _entries(harness, cfg).items():
            hooks[event] = [*hooks.get(event, []), entry]
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
