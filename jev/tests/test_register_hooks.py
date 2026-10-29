import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from register_hooks import TARGETS, updated_config  # noqa: E402

EXISTING = {
    "model": "x",
    "hooks": {
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk-rewrite.sh"}]}],
    },
}


def test_adds_hooks_and_keeps_existing():
    new = updated_config(EXISTING, "claude", TARGETS["claude"], remove=False)
    groups = new["hooks"]["PreToolUse"]
    assert [g["matcher"] for g in groups] == ["Bash", "mcp__t3-code__delegate_task|Agent"]  # no shell exec gate
    assert groups[1]["hooks"][0]["command"].endswith("autoroute delegate")
    prompt_hooks = [h["command"] for h in new["hooks"]["UserPromptSubmit"][0]["hooks"]]
    assert prompt_hooks[0].endswith("context") and prompt_hooks[1].endswith("autoroute prompt")
    assert new["model"] == "x"
    assert new["hooks"]["PostToolUse"][0]["hooks"][0]["command"].endswith("autoroute edit")
    assert new["hooks"]["Stop"][0]["hooks"][0]["command"].endswith("autoroute stop")


def test_is_idempotent_and_does_not_mutate_input():
    once = updated_config(EXISTING, "claude", TARGETS["claude"], remove=False)
    twice = updated_config(once, "claude", TARGETS["claude"], remove=False)
    assert once == twice
    assert len(EXISTING["hooks"]) == 1


def test_remove_restores_original():
    added = updated_config(EXISTING, "codex", TARGETS["codex"], remove=False)
    assert updated_config(added, "codex", TARGETS["codex"], remove=True) == EXISTING


def test_drops_a_previously_registered_exec_gate():
    gate = {"type": "command", "command": "/home/x/.local/bin/jev-gate --harness claude exec"}
    old = {"hooks": {"PreToolUse": [*EXISTING["hooks"]["PreToolUse"], {"matcher": "Bash", "hooks": [gate]}]}}
    new = updated_config(old, "claude", TARGETS["claude"], remove=False)
    assert all("exec" not in h["command"] for g in new["hooks"]["PreToolUse"] for h in g["hooks"])


def test_codex_gets_the_prompt_hook_only():
    new = updated_config({}, "codex", TARGETS["codex"], remove=False)
    assert not {"PreToolUse", "PostToolUse", "Stop"} & set(new["hooks"])
    assert new["hooks"]["UserPromptSubmit"][0]["hooks"][1]["timeout"] == 15000
