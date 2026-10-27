#!/usr/bin/env python3
"""Sensitivity classifier shared by cross-review (rank.sh) and gen-validate.

Tier = max(deterministic rules, jev). Rules:
- Deterministic RESTRICTED always wins (path globs and content regexes below).
- jev "restricted" from a confident verdict also wins.
- jev "uncertain" (source jev-uncertain) or unavailable is NOT an allow. The caller
  decides. cross-review treats it as standard when deterministic rules are clear.
  gen-validate requires an explicit operator-confirmed --data-class open flag.

CLI:
  sensitivity.py git --repo DIR --base REF [--task T]     (changed files + added lines)
  sensitivity.py files [--task T] PATH...                 (paths + their contents)

Prints JSON: {"tier", "deterministic", "jev", "uncertain", "reasons": [...]}.
Never prints matched secret values or IP addresses.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys

INFRA = [
    "helm/*", "*/helm/*", "charts/*", "*/charts/*", "ansible/*", "*/ansible/*",
    "argocd*", "*/argocd*", "*terraform*", "*.tf", "*.tfvars", "*k8s*", "*kube*",
    ".github/workflows/*", "dockerfile*", "*/dockerfile*", "*docker-compose*",
    "*compose*.yml", "*compose*.yaml",
]
SECRETS = [
    ".env", ".env.*", "*/.env", "*/.env.*", "*secret*", "*credential*",
    "*.pem", "*.key", "id_*", "*/id_*", "*vault*", "*sops*",
]
NETWORK = [
    "*wireguard*", "*wg*.conf", "*caddy*", "*cloudflared*", "*iptables*", "*ufw*",
    "etc/*", "*/etc/*",
]
CONTENT = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("API key (sk-)", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private IP address", re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b|\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
]
JEV_TIERS = ("open", "standard", "restricted")


def path_reason(path):
    p = path.lower()
    base = os.path.basename(p)
    for label, pats in (("infra", INFRA), ("secrets", SECRETS), ("network", NETWORK)):
        for pat in pats:
            if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(base, pat):
                return f"deterministic restricted: {label} path {path}"
    return None


def content_reasons(label, text):
    return [f"deterministic restricted: {name} in {label}"
            for name, rx in CONTENT if rx.search(text)]


def jev_verdict(task, paths, cwd=None):
    """Returns (tier, note). tier is open|standard|restricted|uncertain."""
    if not shutil.which("jev-gate"):
        return "uncertain", "jev-gate unavailable"
    cmd = ["jev-gate", "route", "--task", task]
    for p in paths:
        cmd += ["--file", p]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    try:
        obj = json.loads(r.stdout)
    except ValueError:
        return "uncertain", "jev output unparsable"
    tier, source = obj.get("tier", ""), obj.get("source", "")
    if source == "jev-uncertain" or tier not in JEV_TIERS:
        return "uncertain", source or "no source"
    return tier, source


def classify(task, paths, texts, cwd=None):
    reasons = [r for r in (path_reason(p) for p in paths) if r]
    for label, text in texts:
        reasons += content_reasons(label, text)
    deterministic = "restricted" if reasons else "clear"
    jev, note = jev_verdict(task, paths, cwd=cwd)
    uncertain = jev == "uncertain"
    if deterministic == "restricted":
        tier = "restricted"
    elif jev == "restricted":
        tier = "restricted"
        reasons.append(f"jev restricted ({note})")
    elif uncertain:
        tier = "standard"
        reasons.append(f"jev uncertain ({note}) -> deterministic: standard "
                       f"(no restricted path or content found)")
    else:
        tier = jev
        reasons.append(f"jev {jev} ({note})")
    return {"tier": tier, "deterministic": deterministic, "jev": jev,
            "uncertain": uncertain, "reasons": reasons}


def git_inputs(repo, base):
    names = subprocess.check_output(
        ["git", "-C", repo, "diff", "--name-only", f"{base}...HEAD"], text=True).split()
    diff = subprocess.check_output(["git", "-C", repo, "diff", f"{base}...HEAD"], text=True)
    added = "\n".join(l[1:] for l in diff.splitlines()
                      if l.startswith("+") and not l.startswith("+++"))
    return names, [("added lines", added)]


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    g = sub.add_parser("git")
    g.add_argument("--repo", required=True)
    g.add_argument("--base", required=True)
    g.add_argument("--task", default="cross-review")
    f = sub.add_parser("files")
    f.add_argument("--task", default="files")
    f.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)
    if a.mode == "git":
        paths, texts = git_inputs(a.repo, a.base)
        report = classify(a.task, paths, texts, cwd=a.repo)
    else:
        texts = []
        for p in a.paths:
            with open(p, encoding="utf-8", errors="replace") as fh:
                texts.append((os.path.basename(p), fh.read()))
        report = classify(a.task, a.paths, texts)
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
