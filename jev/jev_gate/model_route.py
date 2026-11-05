"""Model routing for T3 Code delegation: two Jev questions -> provider, model, tier.

Question 1 - role (the model family): design -> Claude, implement -> opencode DeepSeek,
review -> codex GPT, mechanical -> Pi, answer -> no delegation (reply in the conversation).
Question 2 - criticality (trivial/limited/material/critical). Criticality sets how strong
the review is; the implementer's tier follows the role (see TIER). Tiers:
  T1 cheap (Pi, DeepSeek flash, Haiku, Luna)   T2 default (Sonnet, Terra, flash high)
  T3 strong (Opus, Sol high)                    T4 Astra/Fable/xhigh/max: operator confirms
Implementation is reviewed by the other vendor except when trivial. Every route carries an
`escalate` target one tier up, used once after a failed test or a rejected review.
Budget (budget.py): pressure on the target's subscription lowers non-critical work by up to
two tiers and, when a provider is burning, moves the work to the other vendor.
Restricted work (route.classify) never goes to opencode, Pi or Luna.
Fails safe: Jev unreachable -> design role, medium effort, restricted.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from . import budget, client, route
from .redact import redact

FIELD_CHARS = 1500
QUANTILE = 0.5          # effort = lowest level whose cumulative probability reaches this
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
# Ladders indexed by tier (1-3); index 0 is unused. Astra, Fable and the top efforts
# (xhigh, max) are T4 and never routed: the operator confirms them.
CLAUDE = [None, _claude("claude-haiku-5-5", "medium"), _claude("claude-sonnet-5-5", "medium"),
          _claude("claude-opus-5-5", "high")]
GPT = [None, _codex("gpt-6-luna", "medium"), _codex("gpt-6.1-terra", "medium"),
       _codex("gpt-6.1-sol", "high")]
DEEPSEEK = [None, _opencode("opencode-go/deepseek-v4.1-flash", "low"),
            _opencode("opencode-go/deepseek-v4.1-flash", "high"), GPT[3]]
# Restricted work: first-party models only; Haiku is allowed, Luna is not.
CLAUDE_RESTRICTED = CLAUDE
GPT_RESTRICTED = [None, GPT[2], GPT[2], GPT[3]]
IMPLEMENT_RESTRICTED = [None, CLAUDE[1], GPT[2], GPT[3]]
# Tier per role and criticality (trivial, limited, material, critical).
TIER = {"implement": (1, 1, 2, 2), "design": (2, 2, 3, 3), "review": (1, 1, 2, 3)}
REVIEW_TIER = (None, 1, 2, 3)   # reviewer of an implementation; trivial work is not reviewed
MAX_BUDGET_DROP = 2
BUDGET_FLOOR = {"design": 2}   # design never drops below Sonnet/Terra
RESTRICTED_FORBIDDEN_PROVIDERS = ("opencode", "pi")
RESTRICTED_FORBIDDEN_MODELS = re.compile(r"luna", re.IGNORECASE)
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
        return UNSURE_EFFORT, "criticality unclear -> limited"
    cumulative, level = 0.0, 0
    for level, weight in enumerate(weights):
        cumulative += weight / total
        if cumulative >= QUANTILE:
            break
    if level == 3 and probs.get("critical", 0.0) < P_MAX:
        return 2, "max capped: P(critical) < 0.5"
    return level, None


def _ladder(family: str, restricted: bool) -> list:
    if family == "claude":
        return CLAUDE_RESTRICTED if restricted else CLAUDE
    if family == "gpt":
        return GPT_RESTRICTED if restricted else GPT
    return IMPLEMENT_RESTRICTED if restricted else DEEPSEEK


VENDORS = {"claudeAgent": "claude", "codex": "gpt", "opencode": "deepseek", "pi": "pi"}


def _other(target: dict | None) -> str:
    """Family of another vendor: Codex work goes to Claude, everything else to GPT."""
    return "claude" if VENDORS.get((target or {}).get("providerInstanceId")) == "gpt" else "gpt"


def _budget_tier(tier: int, level: int, pressure: int, floor: int = 1) -> tuple[int, str | None]:
    """Critical work is never lowered; everything else drops one tier per pressure level."""
    lowered = max(min(floor, tier), tier - min(pressure, MAX_BUDGET_DROP))
    if level == 3 or lowered == tier:
        return tier, None
    return lowered, f"budget pressure {pressure} -> T{tier} lowered to T{lowered}"


def plan(role: str, level: int, restricted: bool, pressures: dict | None = None) -> dict:
    """Targets for a role at a criticality level, after budget pressure.

    Returns target, fallback (other vendor, same tier), review (other vendor than the
    implementer), escalate (one tier up, same ladder), tier and budget reasons.
    """
    pressures = pressures or {}
    empty = {"target": None, "fallback": None, "review": None, "escalate": None,
             "tier": 0, "review_tier": 0, "reasons": []}
    if role == "answer":
        return empty
    if role == "mechanical":
        if restricted:
            return {**empty, "target": CLAUDE[1], "fallback": GPT_RESTRICTED[1],
                    "escalate": CLAUDE[2], "tier": 1}
        return {**empty, "target": PI, "fallback": CLAUDE[1], "escalate": CLAUDE[2], "tier": 1}
    family = {"design": "claude", "review": "gpt"}.get(role, "implement")
    ladder = _ladder(family, restricted)
    tier, reasons = TIER[role][level], []
    current = ladder[tier]
    current_pressure = pressures.get(current["providerInstanceId"], {})
    if current_pressure.get("pace") == "ahead":
        # Prefer a known provider on/under pace at the same quality tier. Never
        # treat missing quota data as headroom and never escape restricted ladders.
        alternatives = []
        for candidate_family in ("claude", "gpt"):
            candidate_ladder = _ladder(candidate_family, restricted)
            candidate = candidate_ladder[tier]
            state = pressures.get(candidate["providerInstanceId"], {})
            if (candidate["providerInstanceId"] != current["providerInstanceId"]
                    and state.get("pace") in ("under", "on") and state.get("level", 0) < 3):
                alternatives.append((0 if state["pace"] == "under" else 1, candidate_ladder))
        if alternatives:
            _, ladder = min(alternatives, key=lambda item: item[0])
            reasons.append(
                f"{current['providerInstanceId']} ahead of T3 pace -> "
                f"{ladder[tier]['providerInstanceId']} at same tier"
            )
    if budget.level_of(pressures, ladder[tier]) >= 3:
        other = _ladder(_other(ladder[tier]) if family != "implement" else "claude", restricted)
        other_state = pressures.get(other[tier]["providerInstanceId"], {})
        other_known = other_state.get("pace") in ("under", "on")
        if (budget.level_of(pressures, other[tier]) < 3
                and (current_pressure.get("source") != "t3" or other_known)):
            reasons.append(f"{ladder[tier]['providerInstanceId']} quota burning -> other vendor")
            ladder = other
    unlowered = tier
    tier, reason = _budget_tier(tier, level, budget.level_of(pressures, ladder[tier]),
                                BUDGET_FLOOR.get(role, 1))
    reasons += [reason] if reason else []
    target = ladder[tier]
    if tier != unlowered and budget.level_of(pressures, target) >= 3:
        # Mixed-vendor ladders (restricted implement): the lower rung may sit on a burning vendor.
        alt = _ladder(_other(target), restricted)[tier]
        if budget.level_of(pressures, alt) < 3:
            target = alt
            reasons.append(f"lowered rung on a burning vendor -> {alt['providerInstanceId']}")
        else:
            tier, target = unlowered, ladder[unlowered]
            reasons.append("lowered rung on a burning vendor -> tier kept")
    fallback = _ladder(_other(target), restricted)[tier]
    escalate = ladder[tier + 1] if tier < 3 else None
    review, review_tier = None, 0
    if role == "implement" and REVIEW_TIER[level]:
        reviewers = _ladder(_other(target), restricted)
        base = REVIEW_TIER[level]
        reviewer_state = pressures.get(reviewers[base]["providerInstanceId"], {})
        if level != 3 and reviewer_state.get("pace") == "ahead":
            mine = VENDORS.get(target["providerInstanceId"])
            for review_family in ("claude", "gpt"):
                alt = _ladder(review_family, restricted)
                alt_state = pressures.get(alt[base]["providerInstanceId"], {})
                if (VENDORS.get(alt[base]["providerInstanceId"]) != mine and alt is not reviewers
                        and alt_state.get("pace") in ("under", "on")
                        and alt_state.get("level", 0) < 3):
                    reasons.append(f"review: {reviewers[base]['providerInstanceId']} ahead of T3 pace "
                                   f"-> {alt[base]['providerInstanceId']} at same tier")
                    reviewers = alt
                    break
        if level != 3 and budget.level_of(pressures, reviewers[base]) >= 3:
            # Burning reviewer vendor: another vendor (never the implementer's) at full tier.
            mine = VENDORS.get(target["providerInstanceId"])
            for family in ("claude", "gpt"):
                alt = _ladder(family, restricted)
                alt_state = pressures.get(alt[base]["providerInstanceId"], {})
                if (VENDORS.get(alt[base]["providerInstanceId"]) != mine and alt is not reviewers
                        and budget.level_of(pressures, alt[base]) < 3
                        and (reviewer_state.get("source") != "t3"
                             or alt_state.get("pace") in ("under", "on"))):
                    reasons.append(f"review: {reviewers[base]['providerInstanceId']} quota burning "
                                   f"-> {alt[base]['providerInstanceId']}")
                    reviewers = alt
                    break
        review_tier, reason = _budget_tier(REVIEW_TIER[level], level,
                                           budget.level_of(pressures, reviewers[REVIEW_TIER[level]]))
        reasons += [f"review: {reason}"] if reason else []
        review = reviewers[review_tier]
    return {"target": target, "fallback": fallback, "review": review, "escalate": escalate,
            "tier": tier, "review_tier": review_tier, "reasons": reasons}


def targets(role: str, level: int, restricted: bool) -> tuple[dict | None, dict | None, dict | None]:
    """(target, fallback, reviewer) without budget pressure."""
    routed = plan(role, level, restricted)
    return routed["target"], routed["fallback"], routed["review"]


def _pressures() -> dict:
    try:
        return budget.pressure()
    except Exception:  # noqa: BLE001 - budget awareness must never break routing
        return {}


def decide(task: str, files: list[str] | None = None, *, deliverable: str = "unknown",
           scope: str = "unknown", history: str = "none", timeout: float = 15.0) -> dict:
    task = redact(task)[:FIELD_CHARS]
    files = list(files or []) or paths_in(f"{task}\n{history}")
    state = {"task": task, "deliverable": deliverable[:FIELD_CHARS],
             "scope": scope[:FIELD_CHARS], "history": redact(history)[:FIELD_CHARS]}
    with ThreadPoolExecutor(max_workers=3) as pool:
        probs_future = pool.submit(ask_jev, state, timeout)
        # A short follow-up ("ok, do it") is judged together with the task it continues.
        sensitivity_task = task if history == "none" else f"{task}\n{state['history']}"
        tier_future = pool.submit(route.classify, sensitivity_task, files[:20], timeout)
        pressure_future = pool.submit(_pressures)
        probs, tier = probs_future.result(), tier_future.result()
        pressures = pressure_future.result()
    sensitivity = tier.get("tier", "restricted")
    restricted = sensitivity == "restricted"
    role, role_reason = pick_role(probs.get("role", {}))
    level, effort_reason = pick_effort(probs.get("criticality", {}))
    reasons = [r for r in (role_reason, effort_reason) if r]
    if restricted and role in ("implement", "mechanical"):
        reasons.append("restricted -> no opencode/Pi/Luna")
    routed = plan(role, level, restricted, pressures)
    return {
        "role": role,
        "effort": EFFORTS[level],
        "criticality": ("trivial", "limited", "material", "critical")[level],
        "tier": routed["tier"],
        "review_tier": routed["review_tier"],
        "sensitivity": sensitivity,
        "sensitivity_source": tier.get("source"),
        "target": routed["target"],
        "fallback": routed["fallback"],
        "review": routed["review"],
        "escalate": routed["escalate"],
        "budget": {k: v.get("level", 0) for k, v in pressures.items()},
        "pace": {k: {field: v.get(field) for field in ("pace", "gap", "window", "source")}
                 for k, v in pressures.items() if v.get("source") == "t3"},
        "used": {k: {"window": v.get("window"), "used": v.get("used"), "projected": v.get("projected")}
                 for k, v in pressures.items()},
        "reasons": reasons + routed["reasons"],
        "probabilities": {q: {k: round(v, 2) for k, v in p.items()} for q, p in probs.items()},
    }
