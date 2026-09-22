"""UserPromptSubmit hook: conditional instructions (Jev Engineering §VIII).

Each fragment in the fragments dir carries a `when:` condition and optional
`paths:` globs. A path match on the cwd pins the fragment without a Jev call;
the rest are asked as one batched Jev request (one noul per fragment). Chosen
fragments are re-injected on every prompt whose condition holds, so compaction
can never summarise them away.
"""

from __future__ import annotations

import fnmatch
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from . import client, decision_log
from .redact import redact

DEFAULT_DIR = Path.home() / ".config" / "jev" / "fragments"
MAX_PROMPT_CHARS = 8_000
MAX_INJECT_CHARS = 6_000


@dataclass(frozen=True)
class Fragment:
    name: str
    when: str
    paths: tuple[str, ...]
    body: str


def parse_fragment(path: Path) -> Fragment | None:
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    header, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip().strip("\"'")
    if not meta.get("when"):
        return None
    paths = tuple(p.strip() for p in meta.get("paths", "").split(",") if p.strip())
    return Fragment(meta.get("name", path.stem), meta["when"], paths, body.strip())


def load_fragments(directory: Path) -> list[Fragment]:
    if not directory.is_dir():
        return []
    parsed = (parse_fragment(p) for p in sorted(directory.glob("*.md")))
    return [f for f in parsed if f is not None]


def _path_match(fragment: Fragment, cwd: str) -> bool:
    return any(fnmatch.fnmatch(cwd, glob) or fnmatch.fnmatch(cwd + "/", glob) for glob in fragment.paths)


def select(fragments: list[Fragment], prompt: str, cwd: str, threshold: float, timeout: float) -> tuple[list[Fragment], str]:
    pinned = [f for f in fragments if _path_match(f, cwd)]
    candidates = [f for f in fragments if f not in pinned]
    if not candidates or not prompt.strip():
        return pinned, "paths"
    questions = {
        f"f{i}": client.noul(f"The user's `prompt` (working in `cwd`) concerns: {f.when}")
        for i, f in enumerate(candidates)
    }
    state = {"prompt": redact(prompt)[:MAX_PROMPT_CHARS], "cwd": cwd}
    try:
        answers = client.ask(state, questions, timeout=timeout)
    except client.JevError:
        return pinned, "jev-error"
    chosen = [f for i, f in enumerate(candidates) if client.noul_probability(answers.get(f"f{i}")) >= threshold]
    return pinned + chosen, "jev"


def render(fragments: list[Fragment]) -> str:
    blocks, used = [], 0
    for fragment in fragments:
        block = f"## Conditional instructions: {fragment.name}\n{fragment.body}"
        if used + len(block) > MAX_INJECT_CHARS:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


def run(payload: dict, harness: str, timeout: float) -> dict | None:
    started = time.monotonic()
    directory = Path(os.environ.get("JEV_FRAGMENTS", DEFAULT_DIR))
    threshold = float(os.environ.get("JEV_CONTEXT_THRESHOLD", "0.6"))
    cwd = payload.get("cwd") or os.getcwd()
    chosen, source = select(load_fragments(directory), payload.get("prompt") or "", cwd, threshold, timeout)
    decision_log.record(
        "context", harness=harness, source=source, fragments=[f.name for f in chosen],
        latency_ms=round((time.monotonic() - started) * 1000),
    )
    text = render(chosen)
    if not text:
        return None
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


def main_json(raw: str, harness: str, timeout: float) -> str:
    try:
        payload = json.loads(raw or "{}")
    except ValueError:
        return ""
    output = run(payload, harness, timeout)
    return json.dumps(output) if output else ""
