---
root: true
targets: ["hermesagent"]
description: "Hermes workspace conventions"
globs: ["**/*"]
---
# Workspace conventions

- Homelab is GitOps: helm charts -> argocd-apps -> ArgoCD. Never kubectl-mutate
  what ArgoCD manages; change git instead.
- Secrets live in Vault / SopsSecret, never in images or plaintext.
- Push notifications go via ntfy, not new bots.
- Prefer cellarette MCP tools (gh, grafana, argocd, obsidian, exa) over raw shell
  where one exists.
- **Code navigation = Graft, not raw grep/read.** When you clone a repo to work on it,
  run `graft build .` ONCE (builds a git-ignored `graft/` cache — regenerable, never commit
  it). Then navigate with the CLI instead of `rg`/`cat`:
  `graft ask "<question>"` (ranked nodes + exact file:line, source inlined — usually the whole
  answer), `graft callers <symbol>` (`--direction out` for callees, `--depth all` for blast
  radius), `graft grep <regex>` (hits grouped by enclosing symbol), `graft skeleton <file>`
  (signatures-only API surface), `graft map` (repo orientation). Config-only repos (pure
  YAML/Jsonnet/SQL) have empty graphs — fall back to `rg`/read there.
