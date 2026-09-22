"""Minimal stdlib client for TypeSafe's System One API (the Jev model).

Wire format: POST {base}/v1/systemone with {"model", "state", "questions"};
the reply carries one typed answer per question id. See
https://docs.rs/typesafe-jev for the canonical types.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
KEY_ENV = "TYPESAFE_API_KEY"
KEY_FILE = Path.home() / ".config" / "jev" / "api_key"


class JevError(Exception):
    """Any failure talking to Jev. Callers fail open on it."""


def load_api_key() -> str:
    key = os.environ.get(KEY_ENV, "").strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text().strip()
    except OSError as exc:
        raise JevError(f"no API key: set {KEY_ENV} or write {KEY_FILE}") from exc


def ask(state: object, questions: dict, *, model: str | None = None, timeout: float = 2.0) -> dict:
    """Evaluate `questions` against `state`; return the `answers` map."""
    if not questions:
        return {}
    base = os.environ.get("JEV_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    body = json.dumps({
        "model": model or os.environ.get("JEV_MODEL", DEFAULT_MODEL),
        "state": state,
        "questions": questions,
    }).encode()
    request = urllib.request.Request(
        f"{base}/v1/systemone",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {load_api_key()}",
            "Content-Type": "application/json",
            "User-Agent": "jev-gate/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise JevError(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise JevError(type(exc).__name__) from exc
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise JevError("reply has no answers map")
    return answers


def choice(instructions: str, criteria: dict[str, str | None]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def noul(instructions: str) -> dict:
    return {"type": "noul", "instructions": instructions}


def choice_probability(answer: dict | None, option: str) -> float:
    if not answer:
        return 0.0
    return float(answer.get("probabilities", {}).get(option, 0.0))


def noul_probability(answer: dict | None) -> float:
    if not answer:
        return 0.0
    return float(answer.get("noul", 0.0))
