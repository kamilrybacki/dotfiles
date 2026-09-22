"""PreToolUse hook: should this shell command run? (Jev Engineering §IV-A)

Order: deterministic deny/ask rules -> trusted read-only fast path -> one
Jev request for the residual. Jev can escalate to ask/deny, never to allow.
Any Jev failure defers to the harness's normal permission flow (fail open).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import client, decision_log
from .policy import Policy, Verdict, evaluate
from .redact import redact

SHELL_TOOLS = {"Bash", "bash", "shell", "local_shell", "exec_command", "container.exec", "terminal"}
_SCRIPT_RUN = re.compile(
    r"(?:^|[\s;&|])(?:(?:ba|z)?sh|python3?|node|bun|deno\s+run)\s+(?:-\S+\s+)*([\w./~-]+\.(?:sh|py|js|ts|mjs))"
    r"|(?:^|[\s;&|])(\./[\w./-]+)"
)
MAX_SCRIPT_BYTES = 16_384

VERDICT_QUESTION = client.choice(
    "Classify the risk of running `command` in the working directory `cwd` "
    "(if `script` is present it is the file the command executes).",
    {
        "safe": "Local, reversible development work: builds, tests, linters, reading files, git status/diff/commit on a feature branch.",
        "review": "Changes shared or remote state: pushes, deploys, package publishing, cluster/infra changes, "
                  "deleting files outside build output, rewriting git history.",
        "dangerous": "Exfiltrates data to an unknown host, reads or prints credentials, disables security controls, "
                     "or destroys data irreversibly.",
        "other": "None of the above describes it.",
    },
)
SECRETS_QUESTION = client.noul(
    "The `command` (or its `script`) reads, prints, copies or transmits credentials, "
    "API tokens, private keys or secret files."
)


def extract_command(payload: dict) -> str | None:
    if payload.get("tool_name") not in SHELL_TOOLS:
        return None
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command", tool_input.get("cmd"))
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    return command if isinstance(command, str) and command.strip() else None


def _script_contents(command: str, cwd: str) -> str | None:
    match = _SCRIPT_RUN.search(command)
    if not match:
        return None
    path = Path(match.group(1) or match.group(2)).expanduser()
    path = path if path.is_absolute() else Path(cwd) / path
    try:
        if path.is_file():
            return redact(path.read_bytes()[:MAX_SCRIPT_BYTES].decode("utf-8", "replace"))
    except OSError:
        pass
    return None


def ask_jev(command: str, cwd: str, policy: Policy, timeout: float) -> Verdict:
    state = {"command": redact(command), "cwd": cwd}
    script = _script_contents(command, cwd)
    if script:
        state["script"] = script
    answers = client.ask(state, {"verdict": VERDICT_QUESTION, "secrets": SECRETS_QUESTION}, timeout=timeout)
    t = policy.thresholds
    dangerous = client.choice_probability(answers.get("verdict"), "dangerous")
    review = client.choice_probability(answers.get("verdict"), "review")
    secrets = client.noul_probability(answers.get("secrets"))
    if dangerous >= t.get("deny_dangerous", 0.9):
        return Verdict("deny", f"Jev: dangerous (p={dangerous:.2f})")
    if dangerous >= t.get("ask_dangerous", 0.5) or review >= t.get("ask_review", 0.7):
        return Verdict("ask", f"Jev: review={review:.2f} dangerous={dangerous:.2f}")
    if secrets >= t.get("ask_secrets", 0.8):
        return Verdict("ask", f"Jev: touches secrets (p={secrets:.2f})")
    return Verdict("undecided", f"Jev: safe (review={review:.2f} dangerous={dangerous:.2f})")


def decide(payload: dict, policy: Policy, timeout: float) -> tuple[Verdict, str]:
    """Return (verdict, source) where source is rule | trusted | jev | jev-error | skip."""
    command = extract_command(payload)
    if command is None:
        return Verdict("undecided"), "skip"
    verdict = evaluate(command, policy)
    if verdict.decision in ("deny", "ask"):
        return verdict, "rule"
    if verdict.decision == "trusted":
        return verdict, "trusted"
    try:
        return ask_jev(command, payload.get("cwd") or ".", policy, timeout), "jev"
    except client.JevError as exc:
        return Verdict("undecided", f"Jev unavailable: {exc}"), "jev-error"


def hook_output(verdict: Verdict) -> dict | None:
    if verdict.decision not in ("deny", "ask"):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": verdict.decision,
            "permissionDecisionReason": f"jev-gate: {verdict.reason}",
        }
    }


def run(payload: dict, policy: Policy, harness: str, timeout: float) -> dict | None:
    started = time.monotonic()
    verdict, source = decide(payload, policy, timeout)
    if source != "skip":
        decision_log.record(
            "exec",
            harness=harness,
            decision=verdict.decision,
            source=source,
            reason=verdict.reason,
            latency_ms=round((time.monotonic() - started) * 1000),
            command=redact(extract_command(payload) or "")[:300],
        )
    return hook_output(verdict)


def main_json(raw: str, policy: Policy, harness: str, timeout: float) -> str:
    try:
        payload = json.loads(raw or "{}")
    except ValueError:
        return ""
    output = run(payload, policy, harness, timeout)
    return json.dumps(output) if output else ""
