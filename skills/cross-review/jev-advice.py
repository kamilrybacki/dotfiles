#!/usr/bin/env python3
"""Jev advisory for /cross-review. ADVISORY ONLY: never a gate, never lowers the rank.

Jev is third-party (TypeSafe). It receives ONLY metadata: file paths, per-file +/- line
counts, deterministic rank reasons, and a summary of at most 3 plain sentences written by the
agent without code. It never receives the diff, code or secrets. The agent calls the MCP
tool mcp__cellarette__jev__ask itself. This script builds the request and reads the answer.
Failure, low confidence or a missing answer means "ignored", and the review continues.

  jev-advice.py rank-state --repo DIR --base REF --rank N --tier T --summary TEXT [--reason R]...
      Prints the JSON request {"state", "questions"}. Refuses (exit 3) when tier is restricted.
  jev-advice.py rank-result --rank N --answer FILE
      Prints "Jev raised rank X->Y (conf Z)" or "Jev advisory ignored (reason)".
      The last line is rank=<N> (raised or unchanged). Feed the raised rank to rank.sh --min-rank.
"""
import argparse
import json
import re
import subprocess
import sys

CONF_MIN = 0.7
CRITERIA = ["trivial", "normal", "high"]


def check_summary(text):
    """At most 3 plain sentences, no code markers. Returns the cleaned text or raises."""
    text = text.strip()
    if not text or len(text) > 600 or "\n" in text or "`" in text:
        raise SystemExit("jev-advice: summary must be 1-3 plain sentences, under 600 chars, no code or newlines")
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(sentences) > 3:
        raise SystemExit("jev-advice: summary has more than 3 sentences")
    return text


def rank_question():
    return {"risk": {
        "type": "score",
        "instructions": ("How risky is this change to get right? trivial = docs, comments or tests only. "
                         "normal = routine feature or bugfix. high = security, auth, infra, migrations, "
                         "public contracts or large change."),
        "criteria": CRITERIA,
    }}


def cmd_rank_state(a):
    if a.tier == "restricted":
        print("jev-advice: tier is restricted. Do NOT call Jev.", file=sys.stderr)
        return 3
    summary = check_summary(a.summary)
    out = subprocess.check_output(["git", "-C", a.repo, "diff", "--numstat", f"{a.base}...HEAD"], text=True)
    files = []
    for line in out.splitlines():
        add, dele, path = line.split("\t", 2)
        if add == "-":
            files.append(f"{path} (binary)")
        else:
            files.append(f"{path} +{add} -{dele}")
    state = "\n".join([
        "Change metadata (no code):",
        "Files (path, added lines, deleted lines):",
        *[f"- {f}" for f in files],
        f"Deterministic rank: {a.rank}",
        "Rank reasons:",
        *[f"- {r}" for r in a.reason],
        f"Summary: {summary}",
    ])
    print(json.dumps({"state": state, "questions": rank_question()}, indent=2))
    return 0


def load_answers(path):
    with open(path, encoding="utf-8") as fh:
        obj = json.load(fh)
    return obj.get("answers", obj) if isinstance(obj, dict) else {}


def cmd_rank_result(a):
    rank = a.rank
    try:
        ans = load_answers(a.answer).get("risk") or {}
        score = float(ans["score"])
        conf = float(ans["confidence"])
    except (OSError, ValueError, KeyError, TypeError):
        print("Jev advisory ignored (no usable answer)")
        print(f"rank={rank}")
        return 0
    cand = min(max(round(score) + 1, 1), len(CRITERIA))
    if conf < CONF_MIN:
        print(f"Jev advisory ignored (low confidence {conf:.2f} < {CONF_MIN})")
    elif cand <= rank:
        print(f"Jev advisory ignored (Jev suggests {CRITERIA[cand - 1]}; not above deterministic rank {rank})")
    else:
        print(f"Jev raised rank {rank}->{cand} (conf {conf:.2f})")
        rank = cand
    print(f"rank={rank}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("rank-state")
    s.add_argument("--repo", required=True)
    s.add_argument("--base", required=True)
    s.add_argument("--rank", type=int, required=True)
    s.add_argument("--tier", required=True)
    s.add_argument("--summary", required=True)
    s.add_argument("--reason", action="append", default=[])
    r = sub.add_parser("rank-result")
    r.add_argument("--rank", type=int, required=True)
    r.add_argument("--answer", required=True)
    a = ap.parse_args(argv)
    return cmd_rank_state(a) if a.cmd == "rank-state" else cmd_rank_result(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
