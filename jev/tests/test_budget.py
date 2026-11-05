import json
import os
import time
from datetime import datetime, timezone

import pytest

from jev_gate import budget, model_route

NOW = 1_800_000_000.0
WEEK = 7 * 24 * 3600


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _window(used, elapsed_fraction, length=WEEK, wid="weekly"):
    return {"id": wid, "percentUsed": used, "windowSeconds": length,
            "resetsAt": _iso(NOW + (1 - elapsed_fraction) * length)}


def _cache(tmp_path, monkeypatch, providers, age=60):
    path = tmp_path / "quotas.json"
    path.write_text(json.dumps({"generatedAt": _iso(NOW - age), "providers": providers}))
    monkeypatch.setenv("JEV_QUOTA_CACHE", str(path))
    monkeypatch.setenv("JEV_USAGE_LOG", str(tmp_path / "usage.jsonl"))
    return path


def test_projection_and_levels():
    assert budget.project(_window(40, 0.5), NOW) == pytest.approx(80)
    assert budget.level(_window(30, 0.5), NOW) == 0
    assert budget.level(_window(45, 0.5), NOW) == 1
    assert budget.level(_window(55, 0.5), NOW) == 2
    assert budget.level(_window(70, 0.5), NOW) == 3
    assert budget.level(_window(91, 1.0), NOW) == 3       # used >= 90 is burning
    assert budget.level(_window(10, 0.05), NOW) == 0      # too early: pace is noise


def test_startsat_when_window_seconds_missing():
    w = {"percentUsed": 50, "startsAt": _iso(NOW - 3600), "resetsAt": _iso(NOW + 3600)}
    assert budget.project(w, NOW) == pytest.approx(100)


def test_missing_stale_or_garbage_cache_gives_no_pressure(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_QUOTA_CACHE", str(tmp_path / "nope.json"))
    assert budget.pressure(NOW) == {}
    _cache(tmp_path, monkeypatch, [{"provider": "claude", "windows": [_window(80, 0.5)]}],
           age=budget.MAX_AGE_S + 1)
    assert budget.pressure(NOW) == {}
    (tmp_path / "quotas.json").write_text("{not json")
    assert budget.pressure(NOW) == {}


def test_pressure_takes_worst_window_and_skips_model_windows(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, [
        {"provider": "claude", "windows": [_window(10, 0.5, wid="session"), _window(55, 0.5),
                                           _window(99, 0.5, wid="model:opus")]},
        {"provider": "codex", "state": {"stale": True}, "windows": [_window(99, 0.5)]},
    ])
    result = budget.pressure(NOW)
    assert set(result) == {"claudeAgent"}
    assert result["claudeAgent"]["level"] == 2 and result["claudeAgent"]["window"] == "weekly"


def test_snapshot_is_throttled(tmp_path, monkeypatch):
    _cache(tmp_path, monkeypatch, [{"provider": "claude", "windows": [_window(55, 0.5)]}])
    budget.pressure(NOW)
    budget.pressure(NOW)
    log = tmp_path / "usage.jsonl"
    assert len(log.read_text().splitlines()) == 1
    os.utime(log, (time.time() - budget.SNAPSHOT_EVERY_S - 1,) * 2)
    budget.pressure(NOW)
    assert len(log.read_text().splitlines()) == 2


def _p(**levels):
    return {k: {"level": v} for k, v in levels.items()}


def test_budget_lowers_non_critical_but_not_critical():
    material = model_route.plan("implement", 2, False, _p(opencode=1))
    assert material["tier"] == 1 and material["target"] == model_route.DEEPSEEK[1] and material["reasons"]
    critical = model_route.plan("implement", 3, False, _p(opencode=2))
    assert critical["tier"] == 2 and critical["target"] == model_route.DEEPSEEK[2]


def test_design_never_drops_below_sonnet():
    routed = model_route.plan("design", 2, False, _p(claudeAgent=2))
    assert routed["target"] == model_route.CLAUDE[2]
    assert model_route.plan("design", 2, False)["target"] == model_route.CLAUDE[3]


def test_burning_vendor_swaps_ladder():
    routed = model_route.plan("design", 3, False, _p(claudeAgent=3))
    assert routed["target"] == model_route.GPT[3]
    both = model_route.plan("design", 3, False, _p(claudeAgent=3, codex=3))
    assert both["target"]["providerInstanceId"] == "claudeAgent"


def test_review_tier_lowered_under_pressure():
    routed = model_route.plan("implement", 3, False, _p(codex=1))
    assert routed["review"] == model_route.GPT[3]          # critical: reviewer kept
    routed = model_route.plan("implement", 2, False, _p(codex=1))
    assert routed["review"] == model_route.GPT[1]


def test_restricted_never_routes_to_luna_opencode_or_pi():
    for role in ("implement", "design", "review", "mechanical"):
        for level in range(4):
            for pressures in ({}, _p(claudeAgent=3), _p(codex=3), _p(claudeAgent=2, codex=2)):
                routed = model_route.plan(role, level, True, pressures)
                for key in ("target", "fallback", "review", "escalate"):
                    t = routed[key]
                    if t:
                        assert t["providerInstanceId"] in ("claudeAgent", "codex"), (role, level, key)
                        assert "luna" not in t["model"], (role, level, key)


def test_every_routed_model_is_below_confirmation():
    for role in ("implement", "design", "review", "mechanical"):
        for level in range(4):
            for restricted in (False, True):
                routed = model_route.plan(role, level, restricted)
                for key in ("target", "fallback", "review", "escalate"):
                    if routed[key]:
                        assert not model_route.confirmation_reason(routed[key])


def test_lowered_rung_never_lands_on_burning_vendor():
    routed = model_route.plan("implement", 2, True, _p(codex=2, claudeAgent=3))
    assert routed["target"]["providerInstanceId"] == "codex"
    assert "luna" not in routed["target"]["model"]


def test_mechanical_escalates_one_tier_up():
    assert model_route.plan("mechanical", 0, False)["escalate"] == model_route.CLAUDE[2]


def test_burning_reviewer_vendor_swaps_to_another_non_implementer_vendor():
    routed = model_route.plan("implement", 2, False, _p(codex=3))
    assert routed["target"]["providerInstanceId"] == "opencode"
    assert routed["review"] == model_route.CLAUDE[2]       # not Luna on a burning codex
    assert any("review:" in r and "burning" in r for r in routed["reasons"])
    both = model_route.plan("implement", 2, False, _p(codex=3, claudeAgent=3))
    assert both["review"]["providerInstanceId"] == "codex"  # nowhere to go: lowered as before
    critical = model_route.plan("implement", 3, False, _p(codex=3))
    assert critical["review"] == model_route.GPT[3]          # critical review never moves
