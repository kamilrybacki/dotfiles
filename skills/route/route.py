#!/usr/bin/env python3
"""/route helper. Jev is ADVISORY ONLY. It never starts anything.

Jev is third-party. The question carries only a plain-language summary written by the agent
(at most 3 sentences, no code, no secrets). The raw task text stays local and is only used
for the hard overrides below.

  route.py question --summary TEXT
      Prints the JSON request {"state", "questions"} for mcp__cellarette__jev__ask.
  route.py format --task-file FILE --answer FILE
      Prints sorted probabilities, confidence and a recommendation, with hard overrides applied first.
"""
import argparse
import json
import re
import sys

OPTIONS = {
    "claude": "first-party Claude: infra, secrets and customer data are allowed",
    "codex": "first-party Codex (OpenAI): code and review, infra and secrets allowed",
    "opencode_kimi": "open model (Kimi K3, OpenCode Go): code without infra or secrets only",
    "pi_free": "Pi on free or cheap LiteLLM models: bulk, trivial and data tasks only",
    "other": "none of these",
}
# Hard overrides: these tasks never go to opencode_kimi or pi_free, whatever Jev says.
OVERRIDE_RE = re.compile(
    r"\b(infra|infrastructure|secret|secrets|vault|helm|ansible|network|networking|firewall|"
    r"wireguard|caddy|cloudflared|kubernetes|k8s|argocd|terraform|credential|credentials|"
    r"password|passwords|token|tokens|ssh|customer|customers|prod|production)\b", re.I)
OPEN_OR_CHEAP = ("opencode_kimi", "pi_free")
CONF_MIN = 0.5


def check_summary(text):
    text = text.strip()
    if not text or len(text) > 600 or "\n" in text or "`" in text:
        raise SystemExit("route: summary must be 1-3 plain sentences, under 600 chars, no code or newlines")
    if len([s for s in re.split(r"[.!?]+", text) if s.strip()]) > 3:
        raise SystemExit("route: summary has more than 3 sentences")
    return text


def cmd_question(a):
    state = check_summary(a.summary)
    q = {"owner": {
        "type": "choice",
        "instructions": "Which agent should do this task? Consider cost, data sensitivity and capability.",
        "criteria": OPTIONS,
    }}
    print(json.dumps({"state": state, "questions": q}, indent=2))
    return 0


def cmd_format(a):
    with open(a.task_file, encoding="utf-8") as fh:
        task = fh.read()
    with open(a.answer, encoding="utf-8") as fh:
        obj = json.load(fh)
    ans = (obj.get("answers", obj) or {}).get("owner") or {}
    probs = ans.get("probabilities") or {}
    conf = ans.get("confidence")
    if not isinstance(probs, dict) or not probs or conf is None:
        print("Jev answer unusable. Agent recommendation required, with reasons.")
        return 0
    conf = float(conf)
    hits = sorted({m.lower() for m in OVERRIDE_RE.findall(task)})
    excluded = set(OPEN_OR_CHEAP) if hits else set()
    print("Jev routing (advisory only, not a decision):")
    for k, p in sorted(probs.items(), key=lambda kv: -float(kv[1])):
        mark = "  [excluded]" if k in excluded else ""
        print(f"  {k:<14} {float(p):.2f}{mark}")
    print(f"Jev confidence: {conf:.2f}")
    if hits:
        print(f"Hard override: excluded {', '.join(sorted(excluded))} (task mentions: {', '.join(hits)})")
    remaining = {k: float(p) for k, p in probs.items() if k not in excluded}
    if conf < CONF_MIN:
        print("Jev is unsure. Give the agent's own recommendation, with reasons.")
        return 0
    if not remaining:
        print("No allowed option left after overrides. Agent recommendation required.")
        return 0
    best = max(remaining, key=remaining.get)
    print(f"Recommendation: {best} (Jev {remaining[best]:.2f}, after overrides)")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("question")
    q.add_argument("--summary", required=True)
    f = sub.add_parser("format")
    f.add_argument("--task-file", required=True)
    f.add_argument("--answer", required=True)
    a = ap.parse_args(argv)
    return cmd_question(a) if a.cmd == "question" else cmd_format(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
