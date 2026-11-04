#!/usr/bin/env python3
"""/t3-route dispatcher. Starts a T3 Code thread on the route the USER chose.

Jev only advises (see /route). This script applies the same hard rules as /route, plus
repo-level rules, and refuses an excluded route. No override flag exists.

  t3-route.py plan     --route KEY --repo DIR --task-file FILE [options]
  t3-route.py dispatch --route KEY --repo DIR --task-file FILE [options] [--yes]

Without --yes, dispatch prints the plan and the exact argv, then exits 0 without starting
anything. Options: --base REF (worktree base), --branch NAME (needs --base), --title T,
--wait, --review (implies --wait; prints the /cross-review follow-up).

Config: ~/.config/t3-route/routes.json (or T3_ROUTE_CONFIG) overrides the shipped
routes.json next to this script. T3 binary: T3_BIN, config "t3_bin", else the newest
~/.t3/runtime/versions/*/t3. /usr/local/bin/t3 is a different tool and is refused.
"""
import argparse
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REFUSED_BIN = Path("/usr/local/bin/t3")
# Repos that are infra or secret-bearing as a whole. Open and cheap routes never get them.
DENY_REPOS = {"helm", "ansible", "argocd-apps", "n8n-workflows", "cellarette", "dotfiles"}
# Tracked-file labels that make a whole worktree restricted. "infra" is left out on
# purpose: Dockerfiles and CI workflows would flag nearly every repo.
DENY_LABELS = {"secrets", "network"}
REVIEW_NOTE = ("\n\nWhen done: commit on this branch, then run /cross-review against the "
               "base ref. Do not push.")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


route = load("route", SKILLS / "route" / "route.py")
sensitivity = load("sensitivity", SKILLS / "cross-review" / "sensitivity.py")


def load_config():
    with open(HERE / "routes.json", encoding="utf-8") as fh:
        cfg = json.load(fh)
    user = Path(os.environ.get("T3_ROUTE_CONFIG", "~/.config/t3-route/routes.json")).expanduser()
    if user.is_file():
        with open(user, encoding="utf-8") as fh:
            extra = json.load(fh)
        for key, val in (extra.get("routes") or {}).items():
            cfg["routes"][key] = {**cfg["routes"].get(key, {}), **val}
        if extra.get("t3_bin"):
            cfg["t3_bin"] = extra["t3_bin"]
    return cfg


def t3_bin(cfg):
    raw = os.environ.get("T3_BIN") or cfg.get("t3_bin")
    if raw:
        path = Path(raw).expanduser()
    else:
        found = sorted(Path("~/.t3/runtime/versions").expanduser().glob("*/t3"),
                       key=lambda p: [int(x) if x.isdigit() else x for x in p.parent.name.split(".")])
        if not found:
            raise SystemExit("t3-route: no T3 Code CLI under ~/.t3/runtime/versions; set T3_BIN")
        path = found[-1]
    if path.resolve() == REFUSED_BIN.resolve() or path == REFUSED_BIN:
        raise SystemExit("t3-route: /usr/local/bin/t3 is not T3 Code; set T3_BIN to the T3 runtime")
    if not os.access(path, os.X_OK):
        raise SystemExit(f"t3-route: {path} is not executable")
    return str(path)


def repo_reasons(repo):
    """Reasons the whole repo is off-limits for open and cheap routes. Never names files."""
    reasons = []
    if repo.name in DENY_REPOS:
        reasons.append(f"repo {repo.name} is infra or secret-bearing")
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"],
                         capture_output=True, text=True, check=True).stdout
    labels = set()
    for path in filter(None, out.split("\0")):
        labels |= set(sensitivity.path_labels(path)) & DENY_LABELS
    reasons += [f"repo tracks {label} files" for label in sorted(labels)]
    return reasons


def excluded(task, repo):
    """Hard rules from /route plus repo rules. Any reason excludes opencode_kimi and pi_free."""
    reasons = []
    hits = sorted({m.lower() for m in route.OVERRIDE_RE.findall(task)})
    if hits:
        reasons.append(f"task mentions: {', '.join(hits)}")
    verdict = sensitivity.classify([], [("task", task)])
    if verdict["tier"] != "standard":
        reasons += [f"task text: {r}" for r in verdict["reasons"]]
    return reasons + repo_reasons(repo)


def build(a, cfg):
    repo = Path(a.repo).expanduser().resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"t3-route: {repo} is not a git repository")
    if a.route not in route.OPTIONS or a.route == "other":
        raise SystemExit(f"t3-route: route must be one of {', '.join(k for k in route.OPTIONS if k != 'other')}")
    if a.branch and not a.base:
        raise SystemExit("t3-route: --branch needs --base (T3 only names branches of new worktrees)")
    with open(a.task_file, encoding="utf-8") as fh:
        task = fh.read().strip()
    if not task:
        raise SystemExit("t3-route: task file is empty")
    blocked = excluded(task, repo) if a.route in route.OPEN_OR_CHEAP else []
    if blocked:
        print(f"t3-route: refused, {a.route} is excluded for this task:", file=sys.stderr)
        for r in blocked:
            print(f"  - {r}", file=sys.stderr)
        raise SystemExit("t3-route: pick claude or codex. No override flag exists.")
    spec = cfg["routes"].get(a.route) or {}
    provider, model = spec.get("provider"), spec.get("model")
    if spec.get("model_required") and not model:
        raise SystemExit(f"t3-route: route {a.route} has no model. Set routes.{a.route}.model "
                         "in ~/.config/t3-route/routes.json")
    if model and not provider:
        raise SystemExit(f"t3-route: route {a.route} sets model without provider")
    if not model:
        provider = None  # T3 takes --provider only with --model; use T3's own default
    review = a.review
    message = task + (REVIEW_NOTE if review and a.route == "claude" else "")
    argv = [t3_bin(cfg), "thread", "start"]
    if a.title:
        argv += ["--title", a.title]
    if provider:
        argv += ["--provider", provider, "--model", model]
    if a.base:
        argv += ["--worktree", a.base]
        if a.branch:
            argv += ["--branch", a.branch]
    if a.wait or review:
        argv += ["--wait", "--json"]
    argv += [str(repo), "-"]
    return {"route": a.route, "repo": repo, "argv": argv, "message": message, "review": review,
            "add_argv": [argv[0], "project", "add", str(repo)]}


def show(p):
    print(f"Route:   {p['route']}")
    print(f"Repo:    {p['repo']}")
    print(f"Command: {shlex.join(p['argv'])}   (task on stdin, {len(p['message'])} chars)")
    print(f"If T3 rejects the project: {shlex.join(p['add_argv'])}, then one retry")
    if p["review"]:
        print("Review:  after the run, /cross-review from a Claude thread on that branch")


def never_started(p, res):
    """True only when T3 rejected the project before starting a thread. A started thread
    prints to stdout, and under --wait exit 1/2 mean it ran, so a retry would run it twice."""
    if res.returncode == 0 or res.stdout.strip():
        return False
    if "--wait" in p["argv"] and res.returncode in (1, 2):
        return False
    return "project" in res.stderr.lower()


def run(p):
    res = subprocess.run(p["argv"], input=p["message"], text=True, capture_output=True)
    if never_started(p, res):
        print("t3-route: T3 does not know the project; registering it, then one retry", file=sys.stderr)
        add = subprocess.run(p["add_argv"], text=True, capture_output=True)
        sys.stderr.write(add.stdout + add.stderr)
        if add.returncode != 0:
            return add.returncode
        res = subprocess.run(p["argv"], input=p["message"], text=True, capture_output=True)
    sys.stdout.write(res.stdout)
    sys.stderr.write(res.stderr)
    if res.returncode == 2:
        print("t3-route: the thread is waiting for an answer; open it in T3 Code", file=sys.stderr)
    if p["review"] and res.returncode == 0:
        print("Next: open a Claude thread on the run's branch and run /cross-review <base-ref>.")
    return res.returncode


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "dispatch"):
        s = sub.add_parser(name)
        s.add_argument("--route", required=True)
        s.add_argument("--repo", required=True)
        s.add_argument("--task-file", required=True)
        s.add_argument("--base")
        s.add_argument("--branch")
        s.add_argument("--title")
        s.add_argument("--wait", action="store_true")
        s.add_argument("--review", action="store_true")
        if name == "dispatch":
            s.add_argument("--yes", action="store_true", help="actually start the thread")
    a = ap.parse_args(argv)
    p = build(a, load_config())
    show(p)
    if a.cmd == "plan" or not a.yes:
        if a.cmd == "dispatch":
            print("Not started. Re-run with --yes after the user confirms this plan.")
        return 0
    return run(p)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
