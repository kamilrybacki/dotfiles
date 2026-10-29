# jev-gate — Jev decision layer for every agent harness

Implements the harness-level ideas from *Jev Engineering for Coding Agents*
(TypeSafe, Sept 2026) on top of TypeSafe's System One API (`jev-latest`).
Jev does not write code. It answers typed questions (`choice`, `score`, `noul`)
at the harness's high-frequency decision points.

| Paper section | Here | Harnesses |
|---|---|---|
| §IV-A programmable permissions | `jev-gate exec` PreToolUse hook + `policy.json` | **not registered** since 2026-10-29 (operator: jev-gate must never block) |
| §VIII conditional instructions | `jev-gate context` UserPromptSubmit hook + `fragments/*.md` | Claude Code, Codex CLI |
| §IX security-aware routing (Table IV) | `jev-gate route` → `open`/`standard`/`restricted` | any dispatcher |
| model auto-route (skill `auto-route`) | `jev-gate model-route`; hooks `jev-gate autoroute prompt` (UserPromptSubmit, injects route) and `autoroute delegate` (PreToolUse on `mcp__t3-code__delegate_task`, denies an off-route model; also on `Agent`: Astra, Fable or effort xhigh/max always ask the operator to confirm) | T3 top-level threads: Claude Code (both), Codex (prompt only) |
| generic typed decisions | `jev-gate ask`, cellarette `jev__ask` | Hermes, Paperclip agents, any MCP client |

## Safety properties

- **Only tightens.** `exec` returns `deny` or `ask`, or stays silent. It never
  returns `allow`, so it cannot widen a harness's own permission rules.
- **Deterministic first.** `deny`/`ask` regexes and a read-only fast path run
  locally. Jev only sees the residual commands.
- **Redacted egress.** Commands, prompts and inspected scripts go through
  `redact.py` before they leave the host. Unit tests cover this.
- **Fails open (hooks), fails closed (route).** If the API is down, slow (2s
  default, `JEV_TIMEOUT`) or the key is missing, hooks print nothing and the
  harness behaves exactly as before. `route` falls back to `restricted`; the only exception is a split between
  `open` and `standard` with P(restricted) < 0.05 and P(other) < 0.2, which
  becomes `standard` (never `open`).
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

## Auto-route

- Active only when `T3CODE_THREAD_ID` is a top-level T3 thread id (not `thread:delegated-task:…`).
- Per-session state lives in `~/.local/state/jev/autoroute/<session>.json` (7-day TTL). A follow-up
  question keeps the previous route, so a later `delegate_task` for that task is still allowed.
- Override for one prompt: "bez routingu" / "bez delegowania" / "auto-route off". This does not
  lift the restricted ban (opencode, Pi, Haiku, Luna).
- Stop enforcement (Claude Code): `autoroute edit` (PostToolUse on Edit/Write/MultiEdit/NotebookEdit)
  counts inline edits. `autoroute stop` blocks the end of the turn once (`decision: block`) when a delegated role
  edited files and never called delegate_task. It never fires when `stop_hook_active` is set, so it cannot loop.
- **Astra, Fable and top efforts need confirmation.** The routing tables never pick Astra, Fable, `xhigh` or `max` (reviews go to `gpt-6.1-sol` · high). Any `delegate_task` or `Agent` call with an Astra/Fable model or an `effort`/`reasoningEffort`/`variant` of `xhigh`/`max` returns `ask`, even with an override or routing off.
- Kill switch: `~/.config/jev/auto-route.json` `{"enabled": false}` (env `JEV_AUTOROUTE_CONFIG`).
- Each prompt makes two concurrent Jev calls (role/effort + sensitivity), about 0.5 s total. On any error the
  hooks print nothing.

## Tuning

- `policy.json` `mode` (or env `JEV_EXEC_MODE`):
  - `advisory` (default): only `deny` rules block. `ask` rules and Jev verdicts
    are only logged (`source: rule-advisory` / `jev-advisory`), and Jev runs in
    a detached background process. There is no added latency and no prompts,
    which keeps auto mode usable.
  - `enforce`: `ask` rules prompt, and Jev can ask or deny synchronously
    (~0.7s per command).
  - `off`: `deny` rules only, with no Jev call.
- `policy.json`: `thresholds` (Jev probabilities → ask/deny), deny/ask regexes,
  `trusted_commands`.
- `JEV_MODEL` pins a version (e.g. `jev-1.13.0`) once thresholds are tuned.
  `jev-latest` can shift behaviour.
- `JEV_CONTEXT_THRESHOLD` (default 0.6) sets the noul cut-off for fragments.
- Review `decisions.jsonl` before tightening thresholds.
