---
root: true
targets: ["claudecode", "codexcli", "hermesagent"]
description: "Operator preference: use the local REA lab methodology for every reverse-engineering task"
globs: ["**/*"]
---

## Reverse engineering — mandatory methodology

Standing operator instruction, effective 2026-10-27: whenever asked to reverse
engineer anything (including reverse engineering, reversing, RE, decompilation,
protocol analysis or inżynieria wsteczna), use the methodology established in
the **Homelabowe Przygody Reverse Engineering Lab**.

On the workstation, start by reading:
`/home/kamil/.t3/projects/homelabowe-przygody/docs/workflow.md`
and the relevant sections of that project's `README.md`.
Use its pinned tools through `scripts/rea` and `uv run --frozen re-lab` where
applicable. Run them from the lab directory or use absolute paths.

The required sequence is **question → evidence → hypothesis → verification**:
- Define a concrete research question and record the artifact's provenance,
  version and SHA-256.
- Retain evidence with file offsets/addresses and tool/provider versions;
  separate observations, interpretations, confidence and limitations.
- Start with static triage; use REA/Ghidra for native analysis and REA's static
  application workflow for JavaScript/Electron when appropriate.
- Store each investigation as a case with `input/`, `evidence/`, `notes/` and
  `reconstruction/`; validate reconstructed behavior against reference behavior.
- Preserve original artifacts and evidence. Triage does not execute the target;
  runtime investigation requires an appropriate environment for that target.

This applies across projects. If this local checkout is unavailable (for example
inside a remote agent container), retain the sequence above, retrieve the lab
workflow through available shared sources, and report missing tools or access
instead of claiming to have used them. Adapt tools to the target while preserving
the methodology. Explicit newer operator instructions take precedence.
