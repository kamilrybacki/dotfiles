import io
import json

from jev_gate import cli, context, route


def write_fragment(directory, name, when, paths="", body="BODY"):
    (directory / f"{name}.md").write_text(f"---\nname: {name}\nwhen: {when}\npaths: {paths}\n---\n{body}-{name}\n")


def test_path_match_pins_without_jev(fake_jev, tmp_path, monkeypatch):
    write_fragment(tmp_path, "helm", "helm charts", paths="*/Code/helm*")
    monkeypatch.setenv("JEV_FRAGMENTS", str(tmp_path))
    out = context.run({"prompt": "bump the chart", "cwd": "/home/k/Code/helm/charts"}, "t", 1)
    assert "BODY-helm" in out["hookSpecificOutput"]["additionalContext"]
    assert fake_jev.requests == []


def test_jev_selects_by_threshold(fake_jev, tmp_path, monkeypatch):
    write_fragment(tmp_path, "a-vault", "Vault secrets")
    write_fragment(tmp_path, "b-css", "front-end styling")
    monkeypatch.setenv("JEV_FRAGMENTS", str(tmp_path))
    fake_jev.answers = {"f0": {"type": "noul", "noul": 0.9}, "f1": {"type": "noul", "noul": 0.1}}
    out = context.run({"prompt": "rotate the n8n key in vault", "cwd": "/x"}, "t", 1)
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "BODY-a-vault" in text and "BODY-b-css" not in text
    assert len(fake_jev.requests) == 1


def test_context_fails_open(dead_jev, tmp_path, monkeypatch):
    write_fragment(tmp_path, "vault", "Vault secrets")
    monkeypatch.setenv("JEV_FRAGMENTS", str(tmp_path))
    assert context.run({"prompt": "anything", "cwd": "/x"}, "t", 0.3) is None


def test_fragment_without_when_is_ignored(tmp_path):
    (tmp_path / "x.md").write_text("no frontmatter")
    assert context.load_fragments(tmp_path) == []


def test_route_restricted_by_path_rule(fake_jev):
    result = route.classify("fix it", ["argocd-apps/apps/x.yaml"], 1)
    assert result["tier"] == "restricted" and result["source"] == "rule"
    assert fake_jev.requests == []


def test_route_uses_jev(fake_jev):
    fake_jev.answers = {"tier": {"type": "choice", "choice": "open", "confidence": 0.9, "probabilities": {"open": 0.9}}}
    assert route.classify("summarise the React docs", ["README.md"], 1)["tier"] == "open"


def test_route_fails_closed(dead_jev):
    assert route.classify("x", [], 0.3)["tier"] == "restricted"


def test_route_low_confidence_is_restricted(fake_jev):
    fake_jev.answers = {"tier": {"type": "choice", "choice": "open", "confidence": 0.3, "probabilities": {}}}
    assert route.classify("x", [], 1)["tier"] == "restricted"


def test_cli_hook_survives_garbage(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert cli.main(["exec"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_ask_redacts_state(fake_jev, monkeypatch, capsys):
    fake_jev.answers = {"q": {"type": "noul", "noul": 0.5}}
    request = {"state": "token ghp_" + "a" * 36, "questions": {"q": {"type": "noul", "instructions": "?"}}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request)))
    assert cli.main(["ask"]) == 0
    assert json.loads(capsys.readouterr().out)["answers"]["q"]["noul"] == 0.5
    assert "ghp_" not in json.dumps(fake_jev.requests[0]["body"])
