#!/usr/bin/env python3
"""Deterministic sensitivity classifier. No LLM, no external classifier. Used by cross-review and gen-validate.

Tier: any rule hit -> "restricted"; no hit -> "standard".
Restricted data may go only to first-party models. It must never go to OpenCode Go,
open-weight, or China-hosted endpoints. These rules are the only gate.

Rules:
- path globs: infra (helm, charts, ansible, argocd, terraform, k8s, .github/workflows,
  Dockerfile, compose), secrets (.env, *secret*, *credential*, keys, vault, sops),
  network (wireguard, caddy, cloudflared, iptables, ufw, /etc)
- content regexes: private keys, API tokens, private IPv4 (192.168.x.x, 10.x.x.x)

Callers classify the EXACT outgoing payload, not a summary of it.

CLI:
  sensitivity.py git --repo DIR --base REF           paths + full diff text (base...HEAD)
  sensitivity.py payload --repo DIR --base REF --text-file FILE
                                                     paths + the exact outgoing prompt text
  sensitivity.py files PATH...                       paths + file contents

Prints JSON: {"tier": "standard|restricted", "reasons": [...]}. Never prints matched values.
"""
import argparse
import fnmatch
import json
import os
import re
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
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("API key (sk-)", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private IP address", re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b|\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
]


TOKEN_SPLIT = re.compile(r"[\s\"'`<>()\[\]{},;=]+")


def path_labels(path):
    """Rule categories a path matches. Never returns the path itself."""
    p = path.lower()
    base = os.path.basename(p)
    labels = []
    for label, pats in (("infra", INFRA), ("secrets", SECRETS), ("network", NETWORK)):
        if any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(base, pat) for pat in pats):
            labels.append(label)
    return labels


def path_hits(path):
    return [f"restricted: {label} path {path}" for label in path_labels(path)]


def token_path_hits(label, text):
    """Path-like tokens inside free text (decoded strings, diffs, prompts, outputs).
    A token counts only if it contains '/' or '.', so prose words stay clear.
    Reasons name the category, never the token."""
    found = set()
    for tok in TOKEN_SPLIT.split(text):
        t = re.sub(r"^[ab]/", "", tok.rstrip("."))
        if "/" in t or "." in t:
            found.update(path_labels(t))
    return [f"restricted: {cat} path-like token in {label}" for cat in sorted(found)]


def content_hits(label, text):
    return [f"restricted: {name} in {label}" for name, rx in CONTENT if rx.search(text)]


def classify(paths, texts):
    """paths: file paths in the payload. texts: [(label, full text sent)]."""
    reasons = []
    for p in paths:
        reasons += path_hits(p)
    for label, text in texts:
        reasons += content_hits(label, text)
        reasons += token_path_hits(label, text)
    return {"tier": "restricted" if reasons else "standard", "reasons": reasons}


def git_paths(repo, base):
    # -z: NUL-separated, unquoted names (no C-quoting of non-ASCII or special chars).
    # --no-renames: both old and new names are listed, so a rename out of a restricted path shows.
    out = subprocess.check_output(
        ["git", "-C", repo, "diff", "-z", "--no-renames", "--name-only", f"{base}...HEAD"])
    return [p for p in out.decode("utf-8", errors="surrogateescape").split("\0") if p]


def git_diff(repo, base):
    return subprocess.check_output(["git", "-C", repo, "diff", f"{base}...HEAD"], text=True)


def decoded_strings(obj):
    """Every string in a decoded JSON value, including object keys."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from decoded_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from decoded_strings(v)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    g = sub.add_parser("git")
    g.add_argument("--repo", required=True)
    g.add_argument("--base", required=True)
    pl = sub.add_parser("payload")
    pl.add_argument("--repo", required=True)
    pl.add_argument("--base", required=True)
    pl.add_argument("--text-file", required=True)
    f = sub.add_parser("files")
    f.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)
    if a.mode == "git":
        report = classify(git_paths(a.repo, a.base), [("diff", git_diff(a.repo, a.base))])
    elif a.mode == "payload":
        with open(a.text_file, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        report = classify(git_paths(a.repo, a.base), [("outgoing prompt", text)])
    else:
        texts = []
        for p in a.paths:
            with open(p, encoding="utf-8", errors="replace") as fh:
                texts.append((os.path.basename(p), fh.read()))
        report = classify(a.paths, texts)
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
