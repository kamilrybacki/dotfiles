---
root: true
targets: ["claudecode", "codexcli"]
description: "OpenViking KB consult policy (shared: Claude Code + Codex)"
globs: ["**/*"]
---
## Knowledge Base — OpenViking (consult before web search / trial-and-error)

**OpenViking is the homelab context DB** — accumulated gotchas, past decisions, infra facts, and Hermes's research notes, as a `viking://` virtual FS. Access via cellarette `openviking__*` tools (present in the `workspace` profile).

- **START HERE for any homelab question:** `viking://resources/homelab-knowledge/homelab-canonical-state.md` is the SINGLE canonical description of the homelab — hosts, cluster, GitOps, secrets, observability, what runs, the agent layer, accepted risks, conventions and gotchas. Hermes re-verifies it against live systems every morning at 06:15 UTC, so it carries a trustworthy "last verified" date. Read it before answering, and do NOT create a second copy of those facts anywhere; if something is missing or wrong, fix it there.
- **Consult it EARLY** on any homelab / infra / personal-project task, before reaching for WebSearch/Exa or trial-and-error. `openviking__search "<topic>"` (semantic) or `openviking__grep` / `openviking__glob` for exact strings. A 2-second lookup often surfaces a gotcha already paid for once.
- **KB layout:** `viking://resources/homelab-knowledge/` (per-project facts + gotchas, mirrors `~/.claude` memory), `viking://resources/session-knowledge/` (mined cross-session lessons), `viking://resources/research/` (Hermes research-cron output).
- **Contribute back: MANDATORY.** Every durable, reusable lesson (a gotcha, root cause, decision + why, working runbook; not session trivia) goes to OpenViking in the SAME turn you learn it: `openviking__write` (`mode: append`) or `openviking__edit` into the matching `viking://resources/homelab-knowledge/<area>-gotchas.md`. Whenever you save a memory file under `~/.claude/.../memory/`, mirror its durable content to OpenViking before ending the turn. OpenViking is what every other agent (Hermes, the Paperclip company, Codex) can see; local memory is private to one tool. **REDACT secrets first** (never write tokens/keys/passwords).
- If `openviking__*` isn't in the active profile, skip silently — don't block on it.
