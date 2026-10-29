#!/usr/bin/env python3
"""Pick a T3 Code provider/model/effort for one task, using two Jev questions.

Usage: route.py "<task>" [--deliverable D] [--scope S] [--history H] [--file PATH ...]
       (or the task on stdin)

Thin wrapper over `jev-gate model-route` (jev/jev_gate/model_route.py), the same routing the
auto-route hooks use, so the skill and the hook enforcement never disagree:
  role        answer -> reply directly, design -> Claude, implement -> DeepSeek via opencode,
              review -> GPT via codex, mechanical -> Pi
  criticality -> effort low / medium / high / max
Restricted work never goes to opencode, Pi, Haiku or Luna. Prints one JSON object.
Fails safe: Jev unreachable -> design role, medium effort, restricted.
"""

import subprocess
import sys

JEV_TIMEOUT_S = "40"

if __name__ == "__main__":
    try:
        sys.exit(subprocess.run(["jev-gate", "--timeout", JEV_TIMEOUT_S, "model-route", *sys.argv[1:]],
                                check=False).returncode)
    except OSError as exc:
        print(f'{{"error": "jev-gate not runnable: {exc}"}}')
        sys.exit(1)
