---
root: true
targets: ["codexcli"]
description: "Graft-first code navigation (Codex only)"
globs: ["**/*"]
---
## Code Exploration Policy — Graft First

**Graft is the primary code-navigation layer** for every repo under `~/Code`. Each repo has a local
graph (`graft/`, git-ignored) built by `graft build`; the `graft_*` MCP tools (server `graft`)
answer from it. Reach for Graft before shell reads/greps for finding and understanding code.

- question → ranked nodes with `file:line` + source inlined → `graft_find_code`
- one file's API surface → `graft_file_api`
- callers / callees, blast radius → `graft_trace_calls` (`direction: out` for callees)
- every regex hit grouped by enclosing symbol → `graft_find_all`
- unfamiliar repo overview → `graft_repo_map`
- graph drift → `graft_check_freshness` (rebuild with `graft build` if stale)

CLI equivalents: `graft ask "<question>"`, `graft callers <fn>`.

**jCodemunch (server `jcodemunch`) — fallback only**, for what Graft does not cover:
`search_columns` (dbt/SQLMesh columns), `find_dead_code`, `get_class_hierarchy`.
Do not open with `plan_turn` / `resolve_repo` / `search_symbols`.

**Shell is allowed without asking** for read-only inspection (`rg`, `sed -n`, `head`, `ls`) when
Graft has no answer: config-only repos (argocd-apps, dbt, dotfiles, grafana-dashboards,
homelab-watchdog) have empty graphs, and non-code files (YAML, Markdown, JSON) are not indexed.
Keep output small: grep and line ranges, not whole files.

**Homelab tools** (Vault, Grafana, ArgoCD, kubectl, OpenViking, gh, Context7…) come from the
`cellarette` MCP server. If it is missing from the session, say so once and continue with what is
available; do not keep asking for it.

@RTK.md
