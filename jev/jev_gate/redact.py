"""Scrub credentials from text before it leaves the homelab.

Patterns merge helm/charts/hermes/files/redact-patterns.txt with the
dotfiles pre-commit secret scanner, plus generic KEY=value assignments.
"""

from __future__ import annotations

import re

MASK = "[REDACTED]"

_TOKEN_PATTERNS = [
    r"tmx_[a-f0-9]{20,}",
    r"gh[pousr]_[A-Za-z0-9]{30,}",
    r"github_pat_[A-Za-z0-9_]{30,}",
    r"glpat-[A-Za-z0-9_-]{20,}",
    r"sbp_[a-f0-9]{30,}",
    r"mcp_[a-z0-9]{20,}",
    r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r"hvs\.[A-Za-z0-9_-]{20,}",
    r"sk-[A-Za-z0-9_-]{20,}",
    r"nvapi-[A-Za-z0-9_-]{20,}",
    r"gsk_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"[0-9]{9,10}:AA[A-Za-z0-9_-]{33,36}",
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----|$)",
]

_CONTEXTUAL = [
    # Authorization headers / bearer tokens: keep the scheme, drop the value.
    (re.compile(r"(?i)\b(bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{16,}"), r"\1 " + MASK),
    (re.compile(r"(?i)(x-[a-z-]*(?:token|key)\s*:\s*)\S+"), r"\1" + MASK),
    # FOO_TOKEN=..., password: ..., --api-key ...
    (re.compile(
        r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE_KEY)[A-Z0-9_]*)"
        r"(\s*[=:]\s*)(['\"]?)[^\s'\"]{6,}\3"
    ), r"\1\2\3" + MASK + r"\3"),
    (re.compile(r"(?i)(--(?:password|token|secret|api-key)[= ])\S+"), r"\1" + MASK),
    # user:password@host in URLs
    (re.compile(r"(://[^/\s:@]+:)[^@\s/]+@"), r"\1" + MASK + "@"),
]

_TOKENS = re.compile("|".join(f"(?:{p})" for p in _TOKEN_PATTERNS))


def redact(text: str) -> str:
    scrubbed = _TOKENS.sub(MASK, text)
    for pattern, replacement in _CONTEXTUAL:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed
