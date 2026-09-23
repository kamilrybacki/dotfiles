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
    commands = [h["command"] for g in new["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert commands[0] == "rtk-rewrite.sh"
    assert commands[1].endswith("/.local/bin/jev-gate --harness claude exec")
    assert new["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"].endswith("context")
    assert new["model"] == "x"


def test_is_idempotent_and_does_not_mutate_input():
    once = updated_config(EXISTING, "claude", TARGETS["claude"], remove=False)
    twice = updated_config(once, "claude", TARGETS["claude"], remove=False)
    assert once == twice
    assert len(EXISTING["hooks"]) == 1


def test_remove_restores_original():
    added = updated_config(EXISTING, "codex", TARGETS["codex"], remove=False)
    assert updated_config(added, "codex", TARGETS["codex"], remove=True) == EXISTING
