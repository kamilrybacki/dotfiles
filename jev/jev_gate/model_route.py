"""Model routing for T3 Code delegation: two Jev questions -> provider, model, effort.

Question 1 - role (the model family): design -> Claude, implement -> opencode DeepSeek,
review -> codex GPT, mechanical -> Pi, answer -> no delegation (reply in the conversation).
Question 2 - criticality (the effort level): trivial/limited/material/critical ->
low/medium/high/max. Implementation gets an adversarial GPT review except at low effort.
Restricted work (route.classify) never goes to opencode, Pi, Haiku or Luna.
Fails safe: Jev unreachable -> design role, medium effort, restricted.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from . import client, route
from .redact import redact

FIELD_CHARS = 1500
QUANTILE = 0.7          # effort = lowest level whose cumulative probability reaches this
P_MAX = 0.5             # `max` effort also needs P(critical) >= this, otherwise `high`
P_OTHER_UNSURE = 0.5    # P(other) at or above this means Jev could not classify
P_MECHANICAL_PI = 0.7   # Pi only when the task is clearly mechanical
EFFORTS = ["low", "medium", "high", "max"]
LEVELS = ["trivial", "limited", "material", "critical"]
ROLES = ["answer", "design", "implement", "review", "mechanical"]
DELEGATED_ROLES = ("implement", "review", "mechanical")
UNSURE_ROLE, UNSURE_EFFORT = "design", 1

QUESTIONS = {
    "role": client.choice(
        "Which kind of work produces the requested deliverable? Judge the deliverable, not the "
        "topic. A task that asks to build or change code from a clear goal is implement even if "
        "some local decisions are needed; it is design only when the approach itself is still open.",
        {
            "answer": "A conversational reply with no artifact: a question about facts or status, "
                      "a quick explanation, a yes/no, an acknowledgement or a short follow-up "
                      "choice. Example: 'why is this hook still on?', 'ok, do it', 'thanks'.",
            "design": "Decide how something should be done or explain it in depth: plan, "
                      "decompose, choose an architecture, propose a technical solution, "
                      "investigate a cause, research, write docs or prose. Example: propose a "
                      "schema for structured outputs and the order to build it.",
            "implement": "Write, change, fix, refactor or test code or config whose goal and "
                         "approach are known. Example: add a CSV export following the existing "
                         "export pattern; fix the failing test in parser.py.",
            "review": "Critically check an existing change, patch, plan or artifact for bugs, "
                      "security and design flaws. Example: review this diff before merge.",
            "mechanical": "Apply a fully specified, repetitive transformation whose exact result "
                          "follows from the instruction, with no design choice. Examples: rename "
                          "a function everywhere; replace every print call with logger.info; sort "
                          "imports; bump a version string; translate comments; reformat a list.",
            "other": "The deliverable cannot be identified from the description.",
        },
    ),
    "criticality": client.choice(
        "How costly would an incorrect result be once it is used, after normal tests and review? "
        "Judge impact and reversibility, not difficulty or length. Choose the highest level that "
        "applies.",
        {
            "trivial": "Throwaway or cosmetic; a mistake is obvious and costs nothing. Example: "
                       "a scratch script, a typo, renaming a local variable.",
            "limited": "A mistake is caught by tests or the user and reverted easily; no users "
                       "affected. Example: an internal helper, docs, a dev-only tool.",
            "material": "A mistake could break a feature, a workflow or other people's work, but "
                        "recovery is bounded. Example: a new user-facing feature, a public API "
                        "change, a CI pipeline change.",
            "critical": "A mistake could expose secrets, bypass authorization, lose durable data, "
                        "move money, or cause a broad outage. Example: auth checks, a destructive "
                        "migration, production infra.",
            "other": "Intended use is too unclear to judge the impact.",
        },
    ),
}


def _codex(model: str, effort: str) -> dict:
    return {"providerInstanceId": "codex", "model": model, "options": {"reasoningEffort": effort}}


def _claude(model: str, effort: str) -> dict:
    return {"providerInstanceId": "claudeAgent", "model": model, "options": {"effort": effort}}


def _opencode(model: str, variant: str) -> dict:
    return {"providerInstanceId": "opencode", "model": model, "options": {"variant": variant}}


PI = {"providerInstanceId": "pi", "model": "default"}
# Family -> target per effort level (low, medium, high, max).
CLAUDE = [_claude("claude-haiku-5-5", "medium"), _claude("claude-sonnet-5-5", "medium"),
          _claude("claude-sonnet-5-5", "high"), _claude("claude-opus-5-5", "high")]
# Astra, Fable and the top efforts (xhigh, max) are never routed: the operator confirms them.
GPT = [_codex("gpt-6-luna", "medium"), _codex("gpt-6.1-terra", "medium"),
       _codex("gpt-6.1-sol", "high"), _codex("gpt-6.1-sol", "high")]
DEEPSEEK = [_opencode("opencode-go/deepseek-v4.1-flash", "low"),
            _opencode("opencode-go/deepseek-v4.1-flash", "high"),
            _opencode("opencode-go/deepseek-v4-pro", "high"),
            _opencode("opencode-go/deepseek-v4-pro", "high")]
# Restricted work: first-party models only, no Haiku/Luna.
CLAUDE_RESTRICTED = [CLAUDE[1]] + CLAUDE[1:]
GPT_RESTRICTED = [GPT[1]] + GPT[1:]
CODEX_IMPLEMENT = [GPT[1], GPT[1], GPT[2], GPT[3]]
RESTRICTED_FORBIDDEN_PROVIDERS = ("opencode", "pi")
RESTRICTED_FORBIDDEN_MODELS = re.compile(r"haiku|luna", re.IGNORECASE)
CONFIRM_MODELS = re.compile(r"astra|fable", re.IGNORECASE)
CONFIRM_EFFORTS = ("xhigh", "max")
EFFORT_KEYS = ("effort", "reasoningEffort", "variant")

_URL = re.compile(r"\w+://\S+")
_PATH_TOKEN = re.compile(r"(?:~|\.{0,2})?/?(?:[\w.@-]+/)+[\w.@-]+|[\w-]+\.(?:py|ts|tsx|js|go|rs|ya?ml|json|toml|md|sh|tf|env\w*)\b")


def paths_in(text: str, limit: int = 20) -> list[str]:
    """Path-like tokens in free text, so the sensitivity rules see the files a prompt names."""
    found = []
    for token in _PATH_TOKEN.findall(_URL.sub(" ", text)):
        if token not in found:
            found.append(token)
    return found[:limit]


def violates_restricted(target: dict | None) -> bool:
    if not target:
        return False
    return (target.get("providerInstanceId") in RESTRICTED_FORBIDDEN_PROVIDERS
            or bool(RESTRICTED_FORBIDDEN_MODELS.search(str(target.get("model", "")))))


def confirmation_reason(target: dict | None) -> str | None:
    """The strongest models (Astra, Fable) and top efforts (xhigh, max) need the operator's OK."""
    if not target:
        return None
    model = str(target.get("model") or "")
    if CONFIRM_MODELS.search(model):
        return f"strongest model {model}"
    options = target.get("options") if isinstance(target.get("options"), dict) else {}
    for key in EFFORT_KEYS:
        value = str(options.get(key) or target.get(key) or "").lower()
        if value in CONFIRM_EFFORTS:
            return f"top effort {key}={value}"
    return None


def needs_confirmation(target: dict | None) -> bool:
    return confirmation_reason(target) is not None


def ask_jev(state: dict, timeout: float) -> dict[str, dict[str, float]]:
    """Return {question: {option: probability}}; questions Jev did not answer are absent."""
    try:
        answers = client.ask(state, QUESTIONS, timeout=timeout)
    except client.JevError:
        return {}
    probabilities = {}
    for name, answer in answers.items():
        probs = answer.get("probabilities") if isinstance(answer, dict) else None
        if name in QUESTIONS and isinstance(probs, dict):
            probabilities[name] = {k: float(v) for k, v in probs.items() if isinstance(v, (int, float))}
    return probabilities


def pick_role(probs: dict[str, float]) -> tuple[str, str | None]:
    if not probs or probs.get("other", 0.0) >= P_OTHER_UNSURE:
        return UNSURE_ROLE, "role unclear -> design (the orchestrator decides)"
    role = max(ROLES, key=lambda r: probs.get(r, 0.0))
    if role == "mechanical" and probs.get("mechanical", 0.0) < P_MECHANICAL_PI:
        return "implement", "mechanical but not clearly -> implement"
    return role, None


def pick_effort(probs: dict[str, float]) -> tuple[int, str | None]:
    """Lowest criticality level whose cumulative probability (without `other`) reaches QUANTILE."""
    weights = [probs.get(level, 0.0) for level in LEVELS]
    total = sum(weights)
    if total <= 0 or probs.get("other", 0.0) >= P_OTHER_UNSURE:
        return UNSURE_EFFORT, "criticality unclear -> medium"
    cumulative, level = 0.0, 0
    for level, weight in enumerate(weights):
        cumulative += weight / total
        if cumulative >= QUANTILE:
            break
    if level == 3 and probs.get("critical", 0.0) < P_MAX:
        return 2, "max capped: P(critical) < 0.5"
    return level, None


def targets(role: str, level: int, restricted: bool) -> tuple[dict | None, dict | None, dict | None]:
    """Return (target, capacity fallback, reviewer) for a role at an effort level."""
    claude = CLAUDE_RESTRICTED if restricted else CLAUDE
    gpt = GPT_RESTRICTED if restricted else GPT
    if role == "answer":
        return None, None, None
    if role == "mechanical":
        if restricted:
            return gpt[level], claude[level], None
        return PI, CLAUDE[0], None
    if role == "design":
        return claude[level], gpt[level], None
    if role == "review":
        return gpt[level], claude[level], None
    # implement: DeepSeek writes, GPT reviews; restricted -> codex writes, Claude reviews.
    reviewer = None if level == 0 else (claude[level] if restricted else gpt[level])
    if restricted:
        return CODEX_IMPLEMENT[level], claude[level], reviewer
    return DEEPSEEK[level], claude[level], reviewer


def decide(task: str, files: list[str] | None = None, *, deliverable: str = "unknown",
           scope: str = "unknown", history: str = "none", timeout: float = 15.0) -> dict:
    task = redact(task)[:FIELD_CHARS]
    files = list(files or []) or paths_in(f"{task}\n{history}")
    state = {"task": task, "deliverable": deliverable[:FIELD_CHARS],
             "scope": scope[:FIELD_CHARS], "history": redact(history)[:FIELD_CHARS]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        probs_future = pool.submit(ask_jev, state, timeout)
        # A short follow-up ("ok, do it") is judged together with the task it continues.
        sensitivity_task = task if history == "none" else f"{task}\n{state['history']}"
        tier_future = pool.submit(route.classify, sensitivity_task, files[:20], timeout)
        probs, tier = probs_future.result(), tier_future.result()
    sensitivity = tier.get("tier", "restricted")
    restricted = sensitivity == "restricted"
    role, role_reason = pick_role(probs.get("role", {}))
    level, effort_reason = pick_effort(probs.get("criticality", {}))
    reasons = [r for r in (role_reason, effort_reason) if r]
    if restricted and role in ("implement", "mechanical"):
        reasons.append("restricted -> no opencode/Pi; codex implements, Claude reviews")
    target, fallback, review = targets(role, level, restricted)
    return {
        "role": role,
        "effort": EFFORTS[level],
        "sensitivity": sensitivity,
        "sensitivity_source": tier.get("source"),
        "target": target,
        "fallback": fallback,
        "review": review,
        "reasons": reasons,
        "probabilities": {q: {k: round(v, 2) for k, v in p.items()} for q, p in probs.items()},
    }
