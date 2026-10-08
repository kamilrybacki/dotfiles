---
root: true
targets: ["claudecode", "codexcli"]
description: "optimAIzr: token-spend analysis of this agent's own Claude Code / Codex logs (local agents on lw-main)"
globs: ["**/*"]
---

## Token spend: optimAIzr

`optimaizr` (pinned, installed by `npm run agents:sync` into `~/.local/bin`) reads this
machine's own Claude Code transcripts (`~/.claude/projects`) and Codex rollouts
(`~/.codex/sessions`). It reports where the tokens go, at API list prices, and what to fix.
It is local-only: it reads token counts, never prompts, and sends nothing anywhere.

- **When to use it:** before or after a long or expensive task, when the operator asks
  about usage, quota or cost, or when a session feels slow or bloated. Run
  `optimaizr --json` (machine-readable), or `optimaizr sessions` / `optimaizr why` for
  the detail. Quote its numbers; never estimate cost yourself.
- **Read-only by default.** `optimaizr apply <rule>` changes `~/.claude/settings.json` or
  `~/.codex/config.toml`. Only run it when the operator asks, and say how to `undo` it.
  Never `verify`, which replays requests on a paid API key. Never enable its Jev egress
  (`OPTIMAIZR_JEV`).
- **Habits it rewards** (the operator's sessions spend about 2/3 on re-reading context):
  compact or `/clear` with a handoff note when you change topic, and keep tool output
  small (grep/head instead of cat; offset+limit on big files).
- The Paperclip agents get the same analysis weekly through the
  `paperclip-optimaizr-report` CronJob. Do not run it inside the Paperclip pod.
