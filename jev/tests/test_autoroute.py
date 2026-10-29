import json

import pytest

from jev_gate import autoroute, model_route

IMPLEMENT = {"role": {"probabilities": {"implement": 0.9, "design": 0.1}},
             "criticality": {"probabilities": {"limited": 0.8, "material": 0.2}}}
ANSWER = {"role": {"probabilities": {"answer": 0.9, "design": 0.1}},
          "criticality": {"probabilities": {"trivial": 0.9, "limited": 0.1}}}


def _answers(role_crit):
    def reply(body):
        questions = body.get("questions", {})
        if "role" in questions:
            return role_crit
        return {name: {"type": "choice", "choice": "standard", "confidence": 0.9,
                       "probabilities": {"open": 0.1, "standard": 0.9, "restricted": 0.0}}
                for name in questions}
    return reply


@pytest.fixture()
def t3(monkeypatch, tmp_path):
    monkeypatch.setenv("T3CODE_THREAD_ID", "0b6f6a1e-1111-2222-3333-444455556666")
    monkeypatch.setenv("JEV_AUTOROUTE_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("JEV_AUTOROUTE_CONFIG", str(tmp_path / "auto-route.json"))
    return tmp_path


def _prompt(text, session="s1"):
    return autoroute.run_prompt({"prompt": text, "session_id": session}, "claude", 2.0)


def _delegate(target, session="s1"):
    return autoroute.run_delegate({"session_id": session, "tool_name": "mcp__t3-code__delegate_task",
                                   "tool_input": {"task": "x", "target": target}}, "claude")


def test_paths_in_ignores_urls():
    found = model_route.paths_in("fix jev/register_hooks.py, see https://x.io/a/b and parser.py")
    assert found == ["jev/register_hooks.py", "parser.py"]


def test_inactive_outside_t3_and_in_delegated_threads(monkeypatch, t3):
    monkeypatch.delenv("T3CODE_THREAD_ID")
    assert not autoroute.active()
    monkeypatch.setenv("T3CODE_THREAD_ID", "thread:delegated-task:abc")
    assert not autoroute.active()
    monkeypatch.setenv("T3CODE_THREAD_ID", "abc")
    (t3 / "auto-route.json").write_text(json.dumps({"enabled": False}))
    assert not autoroute.active()


def test_prompt_routes_and_delegate_enforces(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    out = _prompt("add a CSV export to the report helper")
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "role=implement" in text and "opencode" in text
    assert _delegate(model_route.DEEPSEEK[1]) is None
    assert _delegate(model_route.GPT[1]) is None  # the reviewer
    denied = _delegate(model_route.CLAUDE[3])
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "deepseek" in denied["hookSpecificOutput"]["permissionDecisionReason"]


def test_missing_target_is_denied_for_delegated_roles(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    assert _delegate(None)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_short_follow_up_carries_the_previous_route(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    fake_jev.answers = _answers(ANSWER)
    out = _prompt("ok, do it")
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "Reply directly" in text and "earlier task" in text and "deepseek" in text
    assert _delegate(model_route.CLAUDE[3])["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_answer_without_history_injects_reply_directly(fake_jev, t3):
    fake_jev.answers = _answers(ANSWER)
    out = _prompt("why is this hook on?")
    assert "Reply directly" in out["hookSpecificOutput"]["additionalContext"]
    assert _delegate(model_route.CLAUDE[3]) is None


def test_override_lifts_routing_but_not_restricted(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    assert _prompt("zrób to na opusie, bez routingu") is None
    assert _delegate(model_route.CLAUDE[3]) is None
    autoroute.save_state("s1", {"override": True, "sensitivity": "restricted"})
    assert _delegate(model_route.DEEPSEEK[1])["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_restricted_prompt_never_goes_to_opencode(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    out = _prompt("rotate the token in ~/.config/app/.env and fix vault policy")
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "sensitivity=restricted" in text and "opencode" not in text.split("Restricted")[0]
    assert _delegate(model_route.DEEPSEEK[1])["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert _delegate(model_route.CODEX_IMPLEMENT[1]) is None


def test_dead_jev_fails_safe(dead_jev, t3):
    out = _prompt("add a CSV export")
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "role=design" in text and "sensitivity=restricted" in text
    assert _delegate(model_route.CLAUDE[1]) is None  # design is not enforced


def test_slash_commands_and_no_state_are_ignored(fake_jev, t3):
    assert _prompt("/auto-route") is None
    assert _delegate(model_route.CLAUDE[3], session="never-seen") is None


def test_main_json_tolerates_garbage(t3):
    assert autoroute.main_json("not json", "prompt", "claude", 1.0) == ""


def test_follow_up_sensitivity_sees_the_previous_task(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    _prompt("ta, rób")
    tier_requests = [r["body"] for r in fake_jev.requests if "tier" in r["body"].get("questions", {})]
    assert "add a CSV export" in json.dumps(tier_requests[-1]["state"])


def _edit(session="s1"):
    autoroute.run_edit({"session_id": session, "tool_name": "Edit"})


def _stop(session="s1", active=False):
    return autoroute.run_stop({"session_id": session, "stop_hook_active": active}, "claude")


def test_stop_nudges_once_when_delegated_work_was_done_inline(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    assert _stop() is None  # no edits yet: maybe a clarifying question
    _edit()
    _edit()
    out = _stop()
    assert out["decision"] == "block" and "2 edits" in out["reason"] and "deepseek" in out["reason"]
    assert _stop() is None  # once per prompt


def test_stop_allows_after_delegation_or_when_already_continuing(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    _edit()
    assert _stop(active=True) is None
    assert _delegate(model_route.DEEPSEEK[1]) is None
    assert _stop() is None


def test_stop_ignores_answers_carried_routes_and_overrides(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    fake_jev.answers = _answers(ANSWER)
    _prompt("why that format?")  # carried route, but this prompt is an answer
    _edit()
    assert _stop() is None
    _prompt("bez routingu, just fix it")
    _edit()
    assert _stop() is None


def test_main_json_dispatches_stop(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    autoroute.main_json(json.dumps({"session_id": "s1"}), "edit", "claude", 2.0)
    assert json.loads(autoroute.main_json(json.dumps({"session_id": "s1"}), "stop", "claude", 2.0))["decision"] == "block"


def test_routing_never_picks_astra_or_fable():
    tables = [model_route.CLAUDE, model_route.GPT, model_route.DEEPSEEK, model_route.CODEX_IMPLEMENT,
              model_route.CLAUDE_RESTRICTED, model_route.GPT_RESTRICTED]
    assert not any(model_route.needs_confirmation(t) for table in tables for t in table)
    assert model_route.GPT[2]["model"] == "gpt-6.1-sol"


@pytest.mark.parametrize("model", ["gpt-6-astra", "claude-fable-5-1", "fable"])
def test_strongest_models_always_ask(fake_jev, t3, model):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("bez routingu: refactor the parser")
    out = _delegate({"providerInstanceId": "codex", "model": model})
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    # Also with routing switched off and for the native Agent tool.
    (t3 / "auto-route.json").write_text(json.dumps({"enabled": False}))
    out = autoroute.run_delegate({"session_id": "s1", "tool_name": "Agent",
                                  "tool_input": {"prompt": "x", "model": model}}, "claude")
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_agent_tool_without_strong_model_is_not_routed(fake_jev, t3):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("add a CSV export")
    assert autoroute.run_delegate({"session_id": "s1", "tool_name": "Agent",
                                   "tool_input": {"prompt": "x", "model": "sonnet"}}, "claude") is None


@pytest.mark.parametrize("tool_name,tool_input", [
    ("mcp__t3-code__delegate_task", {"target": {"providerInstanceId": "codex", "model": "gpt-6.1-sol",
                                                "options": {"reasoningEffort": "xhigh"}}}),
    ("mcp__t3-code__delegate_task", {"target": {"providerInstanceId": "claudeAgent", "model": "claude-opus-5-5",
                                                "options": {"effort": "max"}}}),
    ("mcp__t3-code__delegate_task", {"target": {"providerInstanceId": "opencode", "model": "x",
                                                "options": {"variant": "max"}}}),
    ("Agent", {"prompt": "x", "model": "opus", "effort": "xhigh"}),
])
def test_top_efforts_always_ask(fake_jev, t3, tool_name, tool_input):
    fake_jev.answers = _answers(IMPLEMENT)
    _prompt("bez routingu: refactor the parser")
    out = autoroute.run_delegate({"session_id": "s1", "tool_name": tool_name, "tool_input": tool_input}, "claude")
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_routing_never_picks_top_efforts():
    tables = [model_route.CLAUDE, model_route.GPT, model_route.DEEPSEEK, model_route.CODEX_IMPLEMENT]
    assert not any(model_route.confirmation_reason(t) for table in tables for t in table)


def test_clearly_mechanical_goes_to_pi_borderline_to_implement():
    threshold = model_route.P_MECHANICAL_PI
    assert model_route.pick_role({"mechanical": threshold, "implement": 1 - threshold}) == ("mechanical", None)
    role, reason = model_route.pick_role({"mechanical": threshold - 0.01, "implement": 1.01 - threshold})
    assert role == "implement" and reason
    assert model_route.targets("mechanical", 0, restricted=False)[0] == model_route.PI
    assert model_route.targets("mechanical", 0, restricted=True)[0]["providerInstanceId"] == "codex"
