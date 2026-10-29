"""Security-aware routing (Jev Engineering §IX, Table IV).

Classifies which data-sensitivity tier a subtask falls in, so a dispatcher can
pick an eligible model. Fails CLOSED: any doubt or Jev error -> restricted.
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
    if tier not in TIERS or float(answer.get("confidence", 0.0)) < min_confidence:
        return _result("restricted", "jev-uncertain", {"probabilities": answer.get("probabilities")})
    return _result(tier, "jev", {"probabilities": answer.get("probabilities")})


def _result(tier: str, source: str, extra: dict) -> dict:
    return {"tier": tier, "eligible": TIERS[tier], "source": source, **extra}
