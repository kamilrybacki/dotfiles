#!/usr/bin/env python3
"""Install the Claude Code home pieces that rulesync does not model.

  claude-home.py sync     merge claude-home/settings.json into ~/.claude/settings.json,
                          copy hooks, RTK.md and the rules/ tree
  claude-home.py check    read-only drift report (exit 1 on drift)
  claude-home.py url      print the cellarette MCP URL this host uses
  claude-home.py render-mcp <mcp.jsonc> <claudecode|codexcli>
                          rewrite the cellarette line of a STAGED copy of
                          .rulesync/mcp.jsonc for this host and agent

The settings merge is additive and idempotent. It never touches permissions,
sandbox, autoMode, skipDangerousModePermissionPrompt or any env key it does not
own (e.g. a CELLARETTE_MCP_TOKEN already there). Preferences (model, effort,
statusLine, ...) are only set when absent, so /model choices survive a sync.
"""
import copy
import filecmp
import json
import os
import shutil
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "claude-home"
HOME = Path.home()
CLAUDE = HOME / ".claude"
SETTINGS = CLAUDE / "settings.json"

EDGE_URL = "https://cellarette-mcp.kamilandrzejrybacki.dpdns.org/mcp?profile=workspace"
HOOK_FILES = ["rtk-rewrite.sh", "ov-mirror-reminder.sh"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def host_overlay() -> dict:
    host = os.environ.get("CLAUDE_HOME_HOST") or socket.gethostname().split(".")[0]
    return load_json(SRC / "hosts" / f"{host}.json")


def expand(cmd: str) -> str:
    return os.path.expanduser(cmd.replace("$HOME", str(HOME)))


def merge_hooks(current: dict, wanted: dict) -> dict:
    """Append each wanted hook group unless its command is already registered
    for that event (compared after $HOME/~ expansion)."""
    hooks = copy.deepcopy(current)
    for event, groups in wanted.items():
        if event.startswith("$"):
            continue
        have = {expand(h.get("command", "")) for g in hooks.get(event, []) for h in g.get("hooks", [])}
        for group in groups:
            new = copy.deepcopy(group)
            for h in new["hooks"]:
                h["command"] = expand(h["command"])
            if all(h["command"] in have for h in new["hooks"]):
                continue
            hooks.setdefault(event, []).append(new)
            have.update(h["command"] for h in new["hooks"])
    return hooks


def merged_settings(current: dict) -> dict:
    base = load_json(SRC / "settings.json")
    out = copy.deepcopy(current)
    for key, value in base["preferences"].items():
        out.setdefault(key, copy.deepcopy(value))
    for key in ("enabledPlugins", "extraKnownMarketplaces"):
        out[key] = {**out.get(key, {}), **base[key]}
    out["env"] = {**out.get("env", {}), **base["env"]}
    wanted = dict(base["hooks"])
    if shutil.which("jcodemunch-mcp"):
        for event, groups in base["jcodemunchHooks"].items():
            if not event.startswith("$"):
                wanted[event] = wanted.get(event, []) + groups
    out["hooks"] = merge_hooks(out.get("hooks", {}), wanted)
    return out


def file_pairs() -> list[tuple[Path, Path]]:
    """(source, destination) for every file this script installs."""
    pairs = [(SRC / "hooks" / f, CLAUDE / "hooks" / f) for f in HOOK_FILES]
    pairs.append((SRC / "RTK.md", CLAUDE / "RTK.md"))
    # Vendored snapshot of the everything-claude-code rules (common + languages),
    # so a new host does not depend on whichever plugin version it pulls.
    rules = SRC / "rules"
    pairs += [(f, CLAUDE / "rules" / f.relative_to(rules)) for f in sorted(rules.rglob("*.md"))]
    return pairs


def sync() -> int:
    copied = 0
    for src, dst in file_pairs():
        if dst.exists() and filecmp.cmp(src, dst, shallow=False):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    print(f"claude-home: {copied} file(s) updated under {CLAUDE}")

    current = load_json(SETTINGS)
    new = merged_settings(current)
    if new == current:
        print("claude-home: settings.json unchanged")
        return 0
    CLAUDE.mkdir(parents=True, exist_ok=True)
    if SETTINGS.exists():
        shutil.copy2(SETTINGS, SETTINGS.with_name("settings.json.pre-sync"))
    tmp = SETTINGS.with_name("settings.json.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(new, indent=2) + "\n")
    os.replace(tmp, SETTINGS)
    changed = sorted(k for k in new if new.get(k) != current.get(k))
    print(f"claude-home: settings.json merged ({', '.join(changed)}); backup settings.json.pre-sync")
    return 0


def check() -> int:
    rc = 0
    for src, dst in file_pairs():
        if not (dst.exists() and filecmp.cmp(src, dst, shallow=False)):
            print(f"DRIFT  claude-home: {dst}")
            rc = 1
    current = load_json(SETTINGS)
    new = merged_settings(current)
    for key in sorted(k for k in new if new.get(k) != current.get(k)):
        print(f"DRIFT  claude-home: settings.json .{key}")
        rc = 1
    if rc == 0:
        print("ok     claude-home")
    return rc


def cellarette_url() -> str:
    return os.environ.get("CELLARETTE_MCP_URL") or host_overlay().get("cellaretteUrl") or EDGE_URL


def render_mcp(path: str, target: str) -> int:
    """Pin the cellarette server to this host's URL. Claude Code keeps the
    headersHelper (it decides per URL whether to send the token); Codex has no
    headersHelper, so it gets bearer_token_env_var for the edge and nothing for
    localhost (the :8788 aggregator rejects any Authorization header)."""
    if target not in ("claudecode", "codexcli"):
        sys.exit(f"render-mcp: unknown target {target}")
    url = cellarette_url()
    entry = {"type": "http", "url": url}
    if target == "claudecode":
        entry["headersHelper"] = "cellarette-headers"
    elif url.startswith("https://"):
        entry["bearer_token_env_var"] = "CELLARETTE_MCP_TOKEN"
    src = Path(path)
    lines = src.read_text().splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if line.lstrip().startswith('"cellarette":')]
    if len(hits) != 1:
        sys.exit(f"render-mcp: expected exactly one cellarette line in {path}, found {len(hits)}")
    i = hits[0]
    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    comma = "," if lines[i].rstrip().endswith(",") else ""
    lines[i] = f'{indent}"cellarette": {json.dumps(entry)}{comma}\n'
    src.write_text("".join(lines))
    print(f"cellarette ({target}): {url}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["render-mcp"] and len(sys.argv) == 4:
        sys.exit(render_mcp(sys.argv[2], sys.argv[3]))
    commands = {"sync": sync, "check": check, "url": lambda: print(cellarette_url()) or 0}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(f"usage: {sys.argv[0]} {{sync|check|url|render-mcp <mcp.jsonc> <target>}}")
    sys.exit(commands[sys.argv[1]]())
