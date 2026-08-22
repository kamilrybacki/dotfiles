---
name: gh-axi
description: >
  Operate GitHub through gh-axi (TOON-output wrapper over the gh CLI) — issues, pull
  requests, workflow runs, releases, repos, labels, Projects v2, search, and raw API.
  Use whenever a task touches GitHub: listing/filing issues, reviewing PRs, checking CI,
  triggering workflows, cutting releases. Prefer gh-axi over raw `gh`.
user-invocable: false
author: Kun Chen (kunchenguid)
metadata:
  hermes:
    tags: [github, git, ci, pull-requests, releases]
    category: devops
---

# gh-axi (homelab)

Agent-ergonomic wrapper around the GitHub CLI. Prefer it over raw `gh` for GitHub operations —
output is token-efficient TOON with contextual `help:` next-step hints.

> **Provenance:** `kunchenguid/gh-axi` **v0.1.27** (MIT). Pinned homelab install.

## Two ways to run it (both pinned, both reuse existing `gh` auth)

1. **Local CLI (this machine):** the pinned binary is on PATH — invoke `gh-axi <command>`
   directly. **Do not** use `npx -y gh-axi` (that pulls an unpinned version at runtime).
2. **In-cluster via cellarette MCP:** the `gh__run` / `gh__help` tools run gh-axi server-side
   with a hardened deny policy. Same command surface; some mutations are blocked at the proxy.

gh-axi shells out to `gh`, which must be authenticated (`gh auth login`, already done as
`kamilrybacki`) or have `GH_TOKEN` set. **No second credential** — it reuses gh's auth. If a
command fails with an auth/scope error, **ask the user** to run the `gh auth login` /
`gh auth refresh -s <scope>` command gh-axi prints — never launch an interactive login yourself.

## Command surface

`gh-axi` (no args) = dashboard. Commands: `issue`, `pr`, `run`, `workflow`, `release`,
`repo`, `label`, `project`, `secret`, `variable`, `search`, `api`. Target another repo by
putting `--repo owner/name` **after** the command. Run `gh-axi <command> --help` for usage.

## Capability policy (homelab — follow this)

**Allowed autonomously (read-only):** the dashboard; `issue list/view`, `pr list/view/checks/diff`,
`run list/view` (incl. `--log-failed` for CI debugging), `workflow list/view`, `release list/view`,
`repo view`, `label list`, `project` (read), `search`. Investigate freely.

**Allowed only when the user directly requests it:** `issue create`, issue/PR comments,
`pr create`, re-running ordinary CI. Do these only on an explicit ask, and report what you did.

**Require explicit human approval every time (do NOT do autonomously):**
- `pr merge`
- `release create` / publishing releases
- `run cancel` / `run delete` / cancelling or deleting workflow runs
- `workflow enable` / `workflow disable`
- repository configuration, branch-protection changes
- `secret` / `variable` set/delete, and raw `api` writes

The cellarette MCP path **enforces** most of these denials at the proxy (pr create/merge,
release *, run cancel/delete/rerun, secret/variable, raw api, setup/update are blocked). The
local CLI does **not** enforce them — you must follow the policy yourself. When in doubt, stop
and ask.

## Tips

- Output is TOON; pipe through `grep`/`head` only when a list is very long.
- Mutations are idempotent — re-running a failed one is safe.
- Secret values are stdin-only (`echo -n "<v>" | gh-axi secret set <name>`) — never via `--body`
  (flags are visible in argv). (And secret writes need approval anyway — see policy.)
- Multi-line bodies: write to a UTF-8 file, pass `--body-file <path>`.
