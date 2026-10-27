#!/usr/bin/env python3
"""Remove jev-gate hook entries from Claude Code and Codex hook configs.

  remove-jev-hooks.py [--dry-run] [FILE ...]

Default FILEs: ~/.claude/settings.json and ~/.codex/hooks.json. Missing files
are skipped. Every hook whose command contains "jev-gate" is removed; matcher
groups and event keys emptied by that removal are dropped. Everything else is
kept as it was. Before changing a file it is copied to <file>.bak-nojev (or a
timestamped name if that already exists). A file with no jev-gate hooks is
left untouched, so the script is idempotent. Stdlib only.

Port of the --remove logic in the retired jev/register_hooks.py.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

MARKER = "jev-gate"
DEFAULT_FILES = [Path.home() / ".claude" / "settings.json", Path.home() / ".codex" / "hooks.json"]


def _is_marked(hook: object) -> bool:
    return isinstance(hook, dict) and MARKER in str(hook.get("command", ""))


def count_marked(config: dict) -> int:
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    return sum(
        1
        for groups in hooks.values()
        if isinstance(groups, list)
        for group in groups
        if isinstance(group, dict)
        for hook in (group.get("hooks") or [])
        if _is_marked(hook)
    )


def strip_groups(groups: list) -> list:
    kept = []
    for group in groups:
        hooks = group.get("hooks") if isinstance(group, dict) else None
        if not isinstance(hooks, list) or not any(_is_marked(h) for h in hooks):
            kept.append(group)
            continue
        remaining = [h for h in hooks if not _is_marked(h)]
        if remaining:
            kept.append({**group, "hooks": remaining})
        # else: the group held only jev-gate hooks, so it is dropped
    return kept


def strip_config(config: dict) -> dict:
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return config
    new_hooks = {}
    for event, groups in hooks.items():
        if isinstance(groups, list) and groups:
            stripped = strip_groups(groups)
            if not stripped:
                continue  # event held only jev-gate groups
            groups = stripped
        new_hooks[event] = groups
    if new_hooks == hooks:
        return config
    return {**config, "hooks": new_hooks}


def _backup_path(path: Path) -> Path:
    backup = path.with_name(f"{path.name}.bak-nojev")
    if backup.exists():
        backup = path.with_name(f"{path.name}.bak-nojev.{int(time.time())}")
    return backup


def _write_atomic(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    tmp = path.with_name(f"{path.name}.tmp-nojev")
    tmp.write_text(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def process(path: Path, dry_run: bool) -> int:
    """Return 0 on success or no-op, 1 on error."""
    if not path.is_file():
        print(f"absent  {path}")
        return 0
    try:
        current = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error   {path}: cannot parse ({exc.__class__.__name__})", file=sys.stderr)
        return 1
    if not isinstance(current, dict):
        print(f"error   {path}: top level is not a JSON object", file=sys.stderr)
        return 1
    removed = count_marked(current)
    if removed == 0:
        print(f"clean   {path}: no jev-gate hooks")
        return 0
    new = strip_config(current)
    if dry_run:
        print(f"would   {path}: remove {removed} jev-gate hook(s)")
        return 0
    backup = _backup_path(path)
    shutil.copy2(path, backup)
    _write_atomic(path, json.dumps(new, indent=2) + "\n")
    print(f"removed {path}: {removed} jev-gate hook(s); backup {backup}")
    return 0


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    paths = [Path(a).expanduser() for a in argv if not a.startswith("--")] or DEFAULT_FILES
    rc = 0
    for path in paths:
        rc |= process(path, dry_run)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
