"""Deterministic command policy: evaluated locally before Jev is consulted.

The gate can only TIGHTEN the harness's own permission flow. `deny` and `ask`
rules produce a decision; `trusted` commands skip the Jev call and defer to
the harness. Nothing here ever returns "allow".
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

DEFAULT_POLICY = Path(__file__).resolve().parent.parent / "policy.json"
_SEGMENT_SPLIT = re.compile(r"\|\||&&|[;|\n]")
_REDIRECT = re.compile(r"(?<![0-9&])>|>>|\btee\b")
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_MUTATING_FLAGS = re.compile(r"\s-(delete|exec|execdir|ok|fprint\w*)\b")


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern
    reason: str


@dataclass(frozen=True)
class Policy:
    deny: tuple[Rule, ...]
    ask: tuple[Rule, ...]
    trusted_commands: frozenset[str]
    thresholds: dict


@dataclass(frozen=True)
class Verdict:
    decision: str  # "deny" | "ask" | "trusted" | "undecided"
    reason: str = ""


def _rules(entries: list[dict]) -> tuple[Rule, ...]:
    return tuple(Rule(re.compile(e["pattern"]), e["reason"]) for e in entries)


def load_policy(path: Path | None = None) -> Policy:
    raw = json.loads((path or DEFAULT_POLICY).read_text())
    return Policy(
        deny=_rules(raw.get("deny", [])),
        ask=_rules(raw.get("ask", [])),
        trusted_commands=frozenset(raw.get("trusted_commands", [])),
        thresholds=dict(raw.get("thresholds", {})),
    )


def _first_word(segment: str) -> str:
    try:
        words = shlex.split(segment, posix=True)
    except ValueError:
        return ""
    words = [w for w in words if not _ENV_ASSIGN.match(w)]
    return Path(words[0]).name if words else ""


def is_trusted(command: str, trusted: frozenset[str]) -> bool:
    """Every pipeline segment is a known read-only command and nothing is written."""
    if (not command.strip() or _REDIRECT.search(command) or "$(" in command or "`" in command \
            or _MUTATING_FLAGS.search(command)):
        return False
    segments = [s for s in _SEGMENT_SPLIT.split(command) if s.strip()]
    return all(_first_word(s) in trusted for s in segments)


def evaluate(command: str, policy: Policy) -> Verdict:
    for rule in policy.deny:
        if rule.pattern.search(command):
            return Verdict("deny", rule.reason)
    for rule in policy.ask:
        if rule.pattern.search(command):
            return Verdict("ask", rule.reason)
    if is_trusted(command, policy.trusted_commands):
        return Verdict("trusted")
    return Verdict("undecided")
