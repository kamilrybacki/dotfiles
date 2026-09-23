"""jev-gate: shared Jev decision layer for every agent harness in the homelab.

  jev-gate exec     PreToolUse hook (stdin: hook JSON)  -> permission decision
  jev-gate context  UserPromptSubmit hook (stdin: hook JSON) -> conditional fragments
  jev-gate route    --task TEXT [--file PATH ...]        -> sensitivity tier JSON
  jev-gate ask      stdin: {"state":..., "questions":{...}} -> Jev answers JSON

Hooks always exit 0 and print nothing when they have no opinion, so a broken
gate or an unreachable API never blocks a session.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import client, context, exec_gate, route
from .policy import load_policy
from .redact import redact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-gate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--harness", default=os.environ.get("JEV_HARNESS", "unknown"))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("JEV_TIMEOUT", "2.0")))
    sub = parser.add_subparsers(dest="mode", required=True)
    exec_parser = sub.add_parser("exec")
    exec_parser.add_argument("--policy", type=Path, default=None)
    sub.add_parser("context")
    sub.add_parser("audit", help="internal: background Jev verdict for advisory mode")
    route_parser = sub.add_parser("route")
    route_parser.add_argument("--task", required=True)
    route_parser.add_argument("--file", action="append", default=[])
    sub.add_parser("ask")
    return parser


def _hook(mode: str, args: argparse.Namespace, raw: str) -> str:
    if mode == "exec":
        return exec_gate.main_json(raw, load_policy(args.policy), args.harness, args.timeout)
    return context.main_json(raw, args.harness, args.timeout)


def _ask(raw: str, timeout: float) -> int:
    request = json.loads(raw)
    state = request.get("state", "")
    state = redact(state) if isinstance(state, str) else json.loads(redact(json.dumps(state)))
    try:
        answers = client.ask(state, request["questions"], model=request.get("model"), timeout=timeout)
    except client.JevError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps({"answers": answers}))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mode in ("exec", "context"):
        try:
            output = _hook(args.mode, args, sys.stdin.read())
        except Exception as exc:  # noqa: BLE001 - a hook must never break the harness
            print(f"jev-gate {args.mode}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 0
        if output:
            print(output)
        return 0
    if args.mode == "audit":
        try:
            exec_gate.audit(json.loads(sys.stdin.read() or "{}"), load_policy(), args.harness, max(args.timeout, 10.0))
        except Exception:  # noqa: BLE001 - detached; nothing to report to
            pass
        return 0
    if args.mode == "route":
        print(json.dumps(route.classify(args.task, args.file, args.timeout)))
        return 0
    return _ask(sys.stdin.read(), args.timeout)


if __name__ == "__main__":
    sys.exit(main())
