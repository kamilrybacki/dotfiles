"""Security-aware routing (Jev Engineering §IX, Table IV).

Classifies which data-sensitivity tier a subtask falls in, so a dispatcher can
pick an eligible model. Fails CLOSED: a Jev error, a restricted path, any real
chance of restricted data or an unreadable task -> restricted. The one exception:
when Jev only hesitates between open and standard (restricted negligible), the
result is standard, never open.
"""

from __future__ import annotations

import re

from . import client
from .redact import redact

TIERS = {
    "open": "any model, cheapest first",
    "standard": "vetted providers only",
    "restricted": "first-party frontier models only",
}
_RESTRICTED_PATHS = re.compile(
    r"(^|/)(\.env[\w.-]*|secrets?/|.*\.enc\.ya?ml|.*sops.*|.*\.pem|.*\.key|id_\w+|"
    r"ansible/.*vars.*|argocd-apps/|.*vault.*|.*credentials.*)",
    re.IGNORECASE,
)
P_RESTRICTED_NEGLIGIBLE = 0.05  # below this, open-vs-standard doubt is not restricted doubt
P_OTHER_MAX = 0.2

QUESTION = client.choice(
    "Which data-sensitivity tier do the `task` and the `files` it will touch fall into?",
    {
        "open": "Public docs, open-source dependencies, generic questions with no private code or data.",
        "standard": "Ordinary private application code and non-secret configuration.",
        "restricted": "Secrets, credentials, .env files, infrastructure config, network topology, personal data.",
        "other": "Cannot tell from the given information.",
    },
)


def classify(task: str, files: list[str], timeout: float, min_confidence: float = 0.6) -> dict:
    hits = [f for f in files if _RESTRICTED_PATHS.search(f)]
    if hits:
        return _result("restricted", "rule", {"matched": hits[:10]})
    try:
        answers = client.ask({"task": redact(task)[:8_000], "files": files[:200]}, {"tier": QUESTION}, timeout=timeout)
    except client.JevError as exc:
        return _result("restricted", "jev-error", {"error": str(exc)})
    answer = answers.get("tier") or {}
    tier = answer.get("choice")
    probabilities = answer.get("probabilities")
    if tier not in TIERS or float(answer.get("confidence", 0.0)) < min_confidence:
        if _private_not_restricted(probabilities, min_confidence):
            return _result("standard", "jev-open-or-standard", {"probabilities": probabilities})
        return _result("restricted", "jev-uncertain", {"probabilities": probabilities})
    return _result(tier, "jev", {"probabilities": probabilities})


def _private_not_restricted(probs, min_confidence: float) -> bool:
    """Jev split between open and standard with no real restricted mass."""
    if not isinstance(probs, dict):
        return False
    p = {k: float(v) for k, v in probs.items() if isinstance(v, (int, float))}
    return ("restricted" in p and p["restricted"] < P_RESTRICTED_NEGLIGIBLE
            and p.get("other", 1.0) < P_OTHER_MAX
            and p.get("open", 0.0) + p.get("standard", 0.0) >= min_confidence)


def _result(tier: str, source: str, extra: dict) -> dict:
    return {"tier": tier, "eligible": TIERS[tier], "source": source, **extra}
