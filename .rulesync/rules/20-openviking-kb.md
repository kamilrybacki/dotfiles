---
root: true
targets: ["claudecode", "codexcli"]
description: "OpenViking KB consult policy (shared: Claude Code + Codex)"
globs: ["**/*"]
---
## Knowledge Base — OpenViking (consult before web search / trial-and-error)

**OpenViking is the homelab context DB** — accumulated gotchas, past decisions, infra facts, and Hermes's research notes, as a `viking://` virtual FS. Access via cellarette `openviking__*` tools (present in the `workspace` profile).

- **Consult it EARLY** on any homelab / infra / personal-project task, before reaching for WebSearch/Exa or trial-and-error. `openviking__search "<topic>"` (semantic) or `openviking__grep` / `openviking__glob` for exact strings. A 2-second lookup often surfaces a gotcha already paid for once.
- **KB layout:** `viking://resources/homelab-knowledge/` (per-project facts + gotchas, mirrors `~/.claude` memory), `viking://resources/session-knowledge/` (mined cross-session lessons), `viking://resources/research/` (Hermes research-cron output).
- **Contribute back** a durable, reusable lesson (not session trivia) with `openviking__write` to `viking://resources/…` — **REDACT secrets first** (never write tokens/keys/passwords). Optional; complements `~/.claude` memory, does not replace it.
- If `openviking__*` isn't in the active profile, skip silently — don't block on it.
