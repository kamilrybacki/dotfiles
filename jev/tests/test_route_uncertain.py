import pytest

from jev_gate import client, route


def _stub(monkeypatch, probabilities, choice, confidence):
    answer = {"choice": choice, "confidence": confidence, "probabilities": probabilities}
    monkeypatch.setattr(client, "ask", lambda *a, **k: {"tier": answer})


def test_open_standard_split_becomes_standard(monkeypatch):
    _stub(monkeypatch, {"open": 0.53, "standard": 0.45, "restricted": 0.0, "other": 0.02}, "open", 0.53)
    result = route.classify("bump the version string", [], 5)
    assert (result["tier"], result["source"]) == ("standard", "jev-open-or-standard")


@pytest.mark.parametrize("probabilities", [
    {"open": 0.45, "standard": 0.40, "restricted": 0.10, "other": 0.05},  # real restricted mass
    {"open": 0.45, "standard": 0.30, "restricted": 0.0, "other": 0.25},   # unreadable task
    {"open": 0.40, "standard": 0.15, "restricted": 0.0, "other": 0.19},   # not enough mass
    {"open": 0.55, "standard": 0.45},                                     # no restricted estimate
])
def test_other_doubt_stays_restricted(monkeypatch, probabilities):
    _stub(monkeypatch, probabilities, "open", max(probabilities.values()))
    assert route.classify("task", [], 5)["tier"] == "restricted"


def test_restricted_path_wins_before_jev(monkeypatch):
    _stub(monkeypatch, {"open": 0.99, "standard": 0.0, "restricted": 0.0, "other": 0.01}, "open", 0.99)
    assert route.classify("task", [".env.local"], 5)["source"] == "rule"
