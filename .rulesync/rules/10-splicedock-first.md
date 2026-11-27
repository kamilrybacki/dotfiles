---
root: true
targets: ["claudecode", "codexcli"]
description: "Splicedock-first tool selection policy (shared: Claude Code + Codex)"
globs: ["**/*"]
---
## Tool Selection Policy — Splicedock First

**Before reaching for `Bash`, `WebFetch`, or any built-in, check whether a Splicedock MCP tool exists for the task.** Splicedock is the homelab tool aggregator — it bundles every backend behind one MCP server. Available tool families:

| Need | Splicedock tool |
|------|----------------|
| Read/write secrets | `vault__*` |
| Query metrics, logs, dashboards | `grafana__*` |
| Inspect ArgoCD apps, k8s state | `argocd__*` |
| Search personal docs/notes | `obsidian__*` |
| Look up library/framework docs | `context7__*` |
| Cross-session knowledge graph | `memory__*` |
| Homelab/project knowledge base (gotchas, past decisions, research) | `openviking__*` |
| Step-by-step reasoning scratchpad | `sequential_thinking__*` |
| Headless browser, web scraping, JS sites | `lightpanda__*` |
| Run GitHub CLI (issues/PRs/repos) — all repos live under the private `kamilrybacki` account since 2026-10-12 (Forgejo abandoned; the old `kamilandrzejrybacki-inc` GitHub org is archived, never use it) | `gh__help` then `gh__run` |
| Run Codex CLI from inside Claude | `codex__help` then `codex__run` |

**Rules:**
1. **Search splicedock tools first.** If the task fits a category above, use the splicedock tool — do NOT shell out to `curl`, `kubectl`, `gh`, etc.
2. **CLI passthroughs (`gh`, `codex`):** call `<name>__help` once to learn the subcommand schema, then `<name>__run` with typed argv. Do not use raw `Bash gh ...`.
3. **Bash is a last resort** for tasks that genuinely don't fit any MCP category (file system manipulation, build/test runners, local dev servers).
4. **If a tool seems missing**, ask the user before improvising with `Bash` — splicedock tools are added frequently and a new backend may exist.
5. **Combine several calls with Code Mode.** When a task needs more than one splicedock tool (for example ArgoCD state plus Grafana metrics plus a Vault read), send ONE `code_mode__execute` script instead of one round trip per tool. It runs `tools.call(name, args)` calls, so independent ones can go in parallel with `Promise.all` (up to 4 concurrent, 50 calls, 30 s, 64 KiB result), and the script filters and joins the data so only a small summary returns to the context. Every call still uses your profile and normal approvals; side effects are never replayed. Use `tools.search(query)` to find tool names.
