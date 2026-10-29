"""Auto-route hooks for T3 Code: route every prompt with Jev, enforce it on delegate_task.

  prompt    UserPromptSubmit: classify the prompt (model_route.decide), store the decision
            for the session and inject the routed provider/model/effort as context.
  delegate  PreToolUse on mcp__t3-code__delegate_task: deny a delegation whose target is
            not the routed target, its capacity fallback or its reviewer. Any delegation
            to Astra or Fable (delegate_task or the native Agent tool) asks the operator
            to confirm, and so does any top effort (xhigh, max), even with routing off.
  edit      PostToolUse on Edit/Write/MultiEdit/NotebookEdit: count inline edits.
  stop      Stop: when the prompt was routed to delegation (implement/review/mechanical),
            files were edited in this thread and delegate_task was never called, block the
            stop once and ask the agent to delegate or say why it did the work inline.

Only top-level T3 threads are routed: T3CODE_THREAD_ID set and not a delegated child
(`thread:delegated-task:...`), so a delegated worker is never re-routed. Restricted work
is never delegated to opencode, Pi, Haiku or Luna, even with an override phrase.
Both hooks fail open: any error or a missing decision means no opinion.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from . import decision_log, model_route

CONFIG_PATH = Path.home() / ".config" / "jev" / "auto-route.json"
STATE_DIR = Path.home() / ".local" / "state" / "jev" / "autoroute"
STATE_TTL_S = 7 * 24 * 3600
MAX_PROMPT_CHARS = 1500
OVERRIDE = re.compile(r"bez\s+routingu|bez\s+delegowania|auto-?route\s+off|no\s+auto-?route", re.IGNORECASE)
DELEGATED_PREFIX = "thread:delegated-task:"
DELEGATE_TOOL = "mcp__t3-code__delegate_task"


def _config() -> dict:
    path = Path(os.environ.get("JEV_AUTOROUTE_CONFIG", CONFIG_PATH))
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def active() -> bool:
    """Route only top-level T3 threads, unless disabled in the config file."""
    thread = os.environ.get("T3CODE_THREAD_ID", "")
    if not thread or thread.startswith(DELEGATED_PREFIX):
        return False
    return _config().get("enabled", True) is not False


def _state_path(session_id: str) -> Path:
    safe = re.sub(r"[^\w.-]", "_", session_id or "unknown")[:128]
    return Path(os.environ.get("JEV_AUTOROUTE_STATE", STATE_DIR)) / f"{safe}.json"


def load_state(session_id: str) -> dict | None:
    try:
        data = json.loads(_state_path(session_id).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_state(session_id: str, state: dict) -> None:
    path = _state_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(path)
    cutoff = time.time() - STATE_TTL_S
    for old in path.parent.glob("*.json"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass


def _fmt(target: dict | None) -> str:
    return json.dumps(target, separators=(",", ":")) if target else "none"


def instruction(decision: dict) -> str:
    role, effort, sensitivity = decision["role"], decision["effort"], decision["sensitivity"]
    head = f"[auto-route] Jev routed this prompt: role={role}, effort={effort}, sensitivity={sensitivity}."
    if role == "answer":
        carried = decision.get("carried")
        if carried:
            return (head + " Reply directly in this thread. If you delegate the earlier task, its route "
                    f"still applies: target={_fmt(carried.get('target'))}, reviewer {_fmt(carried.get('review'))}.")
        return head + " Reply directly in this thread; no delegation needed."
    lines = [head]
    if role == "design":
        lines.append(f"Design/planning work: do it in this thread, or delegate it with delegate_task "
                     f"target={_fmt(decision['target'])} (capacity fallback {_fmt(decision['fallback'])}).")
    else:
        lines.append(f"Delegate the work with mcp__t3-code__delegate_task, target={_fmt(decision['target'])} "
                     f"(only if that provider is unavailable or out of quota: {_fmt(decision['fallback'])}).")
        if decision.get("review"):
            lines.append(f"Then an adversarial review of the result with target={_fmt(decision['review'])}.")
        lines.append("A PreToolUse hook denies delegate_task to any other model for this prompt.")
    if sensitivity == "restricted":
        lines.append("Restricted: never delegate to opencode, Pi, Haiku or Luna.")
    lines.append("The user can turn this off for one prompt with 'bez routingu'.")
    return "\n".join(lines)


def run_prompt(payload: dict, harness: str, timeout: float) -> dict | None:
    if not active():
        return None
    prompt = (payload.get("prompt") or "").strip()
    session_id = payload.get("session_id") or "unknown"
    if not prompt or prompt.startswith("/"):
        return None
    started = time.monotonic()
    if OVERRIDE.search(prompt):
        previous = load_state(session_id) or {}
        save_state(session_id, {"override": True, "sensitivity": previous.get("sensitivity", "standard"),
                                "role": "override", "prompt_role": "override", "ts": time.time()})
        decision_log.record("autoroute", harness=harness, role="override")
        return None
    previous = load_state(session_id)
    history = "none"
    if previous and previous.get("task"):
        history = f"previous prompt (role {previous.get('role')}): {previous['task'][:500]}"
    decision = model_route.decide(prompt[:MAX_PROMPT_CHARS], history=history, timeout=timeout)
    task = model_route.redact(prompt)[:MAX_PROMPT_CHARS]
    stored = decision
    if (decision["role"] == "answer" and previous and not previous.get("override")
            and previous.get("role") in model_route.DELEGATED_ROLES):
        # A question or "ok" between steps: reply directly, but a delegation of the earlier
        # task still has to follow that task's route.
        stored = {k: previous.get(k) for k in ("role", "effort", "sensitivity", "target", "fallback", "review")}
        decision = {**decision, "carried": stored}
        task = previous.get("task", "")
    save_state(session_id, {**{k: stored.get(k) for k in ("role", "effort", "sensitivity", "target",
                                                          "fallback", "review")},
                            "task": task, "prompt_role": decision["role"], "delegated": False,
                            "inline_edits": 0, "stop_nudged": False, "ts": time.time()})
    decision_log.record("autoroute", harness=harness, role=decision["role"], effort=decision["effort"],
                        sensitivity=decision["sensitivity"], carried=bool(decision.get("carried")),
                        latency_ms=round((time.monotonic() - started) * 1000))
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": instruction(decision)}}


def _same(requested: dict, allowed: dict | None) -> bool:
    if not allowed or requested.get("providerInstanceId") != allowed.get("providerInstanceId"):
        return False
    return allowed.get("model") in (None, "default") or requested.get("model") == allowed.get("model")


def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def check_delegate(tool_input: dict, state: dict | None) -> str | None:
    """Return a denial reason, or None when the delegation is allowed."""
    if not state:
        return None
    requested = tool_input.get("target") if isinstance(tool_input.get("target"), dict) else {}
    if state.get("sensitivity") == "restricted" and model_route.violates_restricted(requested):
        return ("auto-route: this work is restricted (secrets, infra config or network topology); "
                "it must not go to opencode, Pi, Haiku or Luna. Use a first-party Claude or GPT model.")
    if state.get("override") or state.get("role") not in model_route.DELEGATED_ROLES:
        return None
    allowed = [state.get(k) for k in ("target", "fallback", "review") if state.get(k)]
    if any(_same(requested, a) for a in allowed):
        return None
    return (f"auto-route: Jev routed this prompt as role={state.get('role')}, effort={state.get('effort')}. "
            f"Delegate with target={_fmt(state.get('target'))} (capacity fallback {_fmt(state.get('fallback'))}"
            f", reviewer {_fmt(state.get('review'))}). Requested: {_fmt(requested) if requested else 'no target'}. "
            "Retry with the routed target; only the user can lift this (by saying 'bez routingu').")


def _ask(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                   "permissionDecisionReason": reason}}


def _requested_target(tool_input: dict) -> dict:
    target = tool_input.get("target")
    if isinstance(target, dict):
        return target
    # Native Agent tool: model and effort sit at the top level of the input.
    return {k: tool_input[k] for k in ("model", "effort") if tool_input.get(k)}


def run_delegate(payload: dict, harness: str) -> dict | None:
    tool_input = payload.get("tool_input") or {}
    target = _requested_target(tool_input)
    confirm = model_route.confirmation_reason(target)
    if not active() or payload.get("tool_name", DELEGATE_TOOL) != DELEGATE_TOOL:
        if confirm:
            return _ask(f"auto-route: {confirm} needs the operator's confirmation.")
        return None
    state = load_state(payload.get("session_id") or "unknown")
    reason = check_delegate(tool_input, state)
    decision_log.record("autoroute-delegate", harness=harness, allowed=reason is None,
                        provider=target.get("providerInstanceId"), model=target.get("model"))
    if reason:
        return _deny(reason)
    if state:
        save_state(payload.get("session_id") or "unknown", {**state, "delegated": True})
    if confirm:
        return _ask(f"auto-route: {confirm} needs the operator's confirmation.")
    return None


def run_edit(payload: dict) -> None:
    if not active():
        return
    session_id = payload.get("session_id") or "unknown"
    state = load_state(session_id)
    if state and state.get("prompt_role") in model_route.DELEGATED_ROLES:
        save_state(session_id, {**state, "inline_edits": int(state.get("inline_edits") or 0) + 1})


def check_stop(state: dict | None) -> str | None:
    """Return the reminder for a turn that did delegated-role work inline, else None."""
    if (not state or state.get("override") or state.get("prompt_role") not in model_route.DELEGATED_ROLES
            or state.get("delegated") or state.get("stop_nudged") or not state.get("inline_edits")):
        return None
    review = f" and a review by {_fmt(state.get('review'))}" if state.get("review") else ""
    return (f"[auto-route] Jev routed this prompt as role={state.get('role')}, effort={state.get('effort')}: "
            f"delegate_task to {_fmt(state.get('target'))}{review}. This thread edited files "
            f"({state.get('inline_edits')} edits) and never called delegate_task. Before finishing, either "
            "delegate the remaining work or the review to the routed target, or, if inline work was the "
            "right call (a tiny change, or the user asked for it), tell the user in one line why routing "
            "was skipped. This reminder fires once per prompt.")


def run_stop(payload: dict, harness: str) -> dict | None:
    if not active() or payload.get("stop_hook_active"):
        return None
    session_id = payload.get("session_id") or "unknown"
    state = load_state(session_id)
    reason = check_stop(state)
    if not reason:
        return None
    save_state(session_id, {**state, "stop_nudged": True})
    decision_log.record("autoroute-stop", harness=harness, role=state.get("role"),
                        inline_edits=state.get("inline_edits"))
    return {"decision": "block", "reason": reason}


def main_json(raw: str, mode: str, harness: str, timeout: float) -> str:
    try:
        payload = json.loads(raw or "{}")
    except ValueError:
        return ""
    if mode == "prompt":
        output = run_prompt(payload, harness, timeout)
    elif mode == "delegate":
        output = run_delegate(payload, harness)
    elif mode == "stop":
        output = run_stop(payload, harness)
    else:
        output = run_edit(payload)
    return json.dumps(output) if output else ""
