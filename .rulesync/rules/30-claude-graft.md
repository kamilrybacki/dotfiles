---
root: true
targets: ["claudecode"]
description: "Graft-first code navigation (Claude Code only)"
globs: ["**/*"]
---
## Code Exploration Policy — Graft First

**Graft is the primary code-navigation layer** for every repo under `~/Code`. Each repo has a local
graph (`graft/`, git-ignored) built by `graft build`; the six `graft_*` MCP tools answer from it.
Reach for Graft before Read/Grep/Glob/Bash for finding and understanding code.
**Exception:** Use `Read` when you need to edit a file — the harness requires a `Read` before `Edit`/`Write`.
Use Graft to *find and understand* code, then `Read` only the specific file you're about to modify.

**Graft MCP tools (primary path):**
- question → ranked nodes with `file:line` + source inlined → `graft_find_code` (usually the whole answer, no follow-up Read)
- one file's API surface (all signatures, no bodies) → `graft_file_api`
- callers / callees of a symbol, N levels (blast radius) → `graft_trace_calls` (`direction: out` for callees)
- every regex hit, grouped by enclosing symbol → `graft_find_all`
- first look at an unfamiliar repo (clusters, hubs, hotspots) → `graft_repo_map`
- has the graph drifted from the code → `graft_check_freshness` (rebuild with `graft build` if stale)

CLI equivalents when shell is easier: `graft ask "<question>"`, `graft callers <fn>`, `graft viz`.
Graft's post-edit hook re-syncs the graph automatically after edits — no manual re-index needed.

**jCodemunch / Serena — fallback only**, for capabilities Graft does not cover:
- database columns (dbt/SQLMesh) → `search_columns`
- unreachable / dead code → `find_dead_code`
- class hierarchy → `get_class_hierarchy`
- LSP-exact rename/reference safety → Serena `find_referencing_symbols`, `rename_symbol`
Do NOT open with `plan_turn` / `resolve_repo` / `search_symbols` anymore — Graft is the default. Use
jCodemunch only when the query maps to one of the fallback capabilities above.

**Config-only repos** (argocd-apps, dbt, dotfiles, grafana-dashboards, homelab-alerting, homelab-watchdog)
have empty graphs (no parseable code) — Graft won't help there; use Grep/Read directly.

@RTK.md
