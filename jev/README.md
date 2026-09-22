# jev-gate — Jev decision layer for every agent harness

Implements the harness-level ideas from *Jev Engineering for Coding Agents*
(TypeSafe, Sept 2026) on top of TypeSafe's System One API (`jev-latest`).
Jev does not write code. It answers typed questions (`choice`, `score`, `noul`)
at the harness's high-frequency decision points.

| Paper section | Here | Harnesses |
|---|---|---|
| §IV-A programmable permissions | `jev-gate exec` PreToolUse hook + `policy.json` | Claude Code, Codex CLI |
| §VIII conditional instructions | `jev-gate context` UserPromptSubmit hook + `fragments/*.md` | Claude Code, Codex CLI |
| §IX security-aware routing (Table IV) | `jev-gate route` → `open`/`standard`/`restricted` | any dispatcher |
| generic typed decisions | `jev-gate ask`, cellarette `jev__ask` | Hermes, teammates, any MCP client |

## Safety properties

- **Only tightens.** `exec` returns `deny` or `ask`, or stays silent. It never
  returns `allow`, so it cannot widen a harness's own permission rules.
- **Deterministic first.** `deny`/`ask` regexes and a read-only fast path run
  locally. Jev only sees the residual commands.
- **Redacted egress.** Commands, prompts and inspected scripts go through
  `redact.py` before they leave the host. Unit tests cover this.
- **Fails open (hooks), fails closed (route).** If the API is down, slow (2s
  default, `JEV_TIMEOUT`) or the key is missing, hooks print nothing and the
  harness behaves exactly as before. `route` falls back to `restricted`.
- **Audit log.** Every decision goes to `~/.local/state/jev/decisions.jsonl`
  (redacted, command truncated to 300 chars).

## Install (lw-main / any workstation)

```bash
./jev/install.sh        # symlinks bin + fragments, registers hooks (backs up configs)
jev-key-sync            # Vault secret/homelab/typesafe/jev -> ~/.config/jev/api_key (0600)
./jev/install.sh --remove   # unregister hooks
```

Tests: `cd jev && python3 -m pytest -q tests`.

## Conditional fragments

`fragments/*.md` have front matter:

```
---
name: helm-argocd
when: editing Helm charts, ArgoCD applications, ...   # asked to Jev as a noul
paths: */Code/helm*, */Code/argocd-apps*              # cwd glob pins it without a Jev call
---
body injected as additionalContext
```

A fragment is re-injected on every prompt where its condition holds, so
compaction cannot summarise it away. Keep them short. The injected total is
capped at 6000 chars.

## Tuning

- `policy.json`: `thresholds` (Jev probabilities → ask/deny), deny/ask regexes,
  `trusted_commands`.
- `JEV_MODEL` pins a version (e.g. `jev-1.13.0`) once thresholds are tuned.
  `jev-latest` can shift behaviour.
- `JEV_CONTEXT_THRESHOLD` (default 0.6) sets the noul cut-off for fragments.
- Review `decisions.jsonl` before tightening thresholds.
