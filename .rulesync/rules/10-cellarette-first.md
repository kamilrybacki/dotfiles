---
root: true
targets: ["claudecode", "codexcli"]
description: "Cellarette-first tool selection policy (shared: Claude Code + Codex)"
globs: ["**/*"]
---
## Tool Selection Policy — Cellarette First

**Before reaching for `Bash`, `WebFetch`, or any built-in, check whether a Cellarette MCP tool exists for the task.** Cellarette is the homelab tool aggregator — it bundles every backend behind one MCP server. Available tool families:

| Need | Cellarette tool |
|------|----------------|
| Read/write secrets | `vault__*` |
| Query metrics, logs, dashboards | `grafana__*` |
| Inspect ArgoCD apps, k8s state | `argocd__*` |
| Search personal docs/notes | `obsidian__*`, `distillery__*` |
| Look up library/framework docs | `context7__*` |
| Cross-session knowledge graph | `memory__*` |
| Homelab/project knowledge base (gotchas, past decisions, research) | `openviking__*` |
| Step-by-step reasoning scratchpad | `sequential_thinking__*` |
| Headless browser, web scraping, JS sites | `lightpanda__*` |
| Run GitHub CLI (issues/PRs/repos) | `gh__help` then `gh__run` |
| Run Codex CLI from inside Claude | `codex__help` then `codex__run` |

**Rules:**
1. **Search cellarette tools first.** If the task fits a category above, use the cellarette tool — do NOT shell out to `curl`, `kubectl`, `gh`, etc.
2. **CLI passthroughs (`gh`, `codex`):** call `<name>__help` once to learn the subcommand schema, then `<name>__run` with typed argv. Do not use raw `Bash gh ...`.
3. **Bash is a last resort** for tasks that genuinely don't fit any MCP category (file system manipulation, build/test runners, local dev servers).
4. **If a tool seems missing**, ask the user before improvising with `Bash` — cellarette tools are added frequently and a new backend may exist.
