---
root: true
targets: ["claudecode", "codexcli", "hermesagent"]
description: "Jev decision layer: typed per-turn harness decisions (shared: Claude Code + Codex + Hermes)"
globs: ["**/*"]
---

## Jev Decision Layer (TypeSafe System One)

**Jev** (`jev-latest`, TypeSafe) is the homelab's typed decision model. It does not write
code. It answers typed questions about a state: `choice` (one of ≤255 options, with
probabilities), `score` (2–10 ordered levels) and `noul` (a calibrated yes/no probability).
Principle: **the context window is assembled on purpose, not accumulated by accident.**
Treat context, tools, permissions and routing as per-turn decisions.

**What is wired in:**
- **Exec gate** (Claude Code + Codex, PreToolUse on shell): `jev-gate exec` runs local
  deny/ask rules (`~/Code/dotfiles/jev/policy.json`) first, then asks Jev about any
  command that is not plainly read-only. It can only return **deny** or **ask**, never
  allow. A `jev-gate:` reason on a blocked command is a policy decision. Don't
  rephrase the command to get around it; tell the user, or change the plan.
- **Conditional instructions** (Claude Code + Codex, UserPromptSubmit): fragments in
  `~/.config/jev/fragments/*.md` are injected when their `when:` condition holds. They
  re-appear on every matching prompt, so compaction cannot drop them. A durable,
  area-specific gotcha belongs in a fragment (with a precise `when:`), not in this
  global file.
- **Typed decisions on demand:** `jev-gate ask` (stdin `{"state", "questions"}`) on
  workstations, or the cellarette tool **`jev__ask`** (Hermes, Paperclip agents, any MCP client).
- **Sensitivity routing:** `jev-gate route --task … --file …` returns `open` /
  `standard` / `restricted`. Secrets, `.env`, infra config and network topology are
  **restricted**: they go to first-party frontier models only, never to cheap or open
  endpoints. When unsure, treat it as restricted.

**Habits this implies (all agents):**
- **Retrieval dominates cost.** Read the few relevant lines, not whole files. Search
  structurally (Graft, ast-grep) before reading. Summarise long command output down
  to what the current question needs.
- **Routing is priced per context rebuild, not per token.** Hand a cheaper model or a
  sub-agent a small, purpose-built context and take back a compact result. Never hand
  over the full transcript.
- **Deduplicate subgoals.** Before spawning a sub-task, check it isn't already done or
  in flight.
- **Keep read-only and write work apart.** Background and review tasks are read-only.
  Share one retrieval pass among them instead of repeating it.

**Using Jev well:** give every `choice` an `other` escape option. Never reuse a threshold
tuned on a `noul` for a `choice`. Treat `score` levels as ordered, not metric. Batch all
questions about one state into one request. **Never put secrets in `state`**:
`jev-gate` redacts, but `jev__ask` sends what you give it.
