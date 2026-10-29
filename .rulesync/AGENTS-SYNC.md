# Agent instruction sync (rulesync)

One source of truth for every agent's instruction file, so shared policy blocks
(Cellarette-first, OpenViking KB, …) are written once and never hand-copied.

Powered by [rulesync](https://github.com/dyoshikawa/rulesync) — pinned in
`package.json`. The source lives in `.rulesync/rules/*.md`; rulesync renders each
agent's native file from it.

## Layout

```
.rulesync/rules/
  10-cellarette-first.md     targets: claudecode, codexcli      (shared)
  20-openviking-kb.md        targets: claudecode, codexcli      (shared)
  25-openviking-kb-hermes.md targets: hermesagent               (Hermes variant)
  30-claude-graft.md         targets: claudecode                (Claude only)
  30-codex-nav.md            targets: codexcli                  (Codex only)
  30-pi-scope.md             targets: pi                        (Pi only)
  05-hermes-conventions.md   targets: hermesagent               (Hermes only)
  40-hermes-facts.md         targets: hermesagent               (Hermes only)
  50-jev-decisions.md        targets: claudecode, codexcli, hermesagent, pi (shared; see jev/README.md)
```

Every rule is `root: true`, so all rules for one target combine into a single
inlined file (needed for Codex/Hermes, which cannot `@import`). Filename prefixes
(`05`,`10`,`20`,…) control section order within each file.

## Targets → live files

| Target        | rulesync target | Written to                              | How it ships |
|---------------|-----------------|-----------------------------------------|--------------|
| Claude Code   | `claudecode`    | `~/.claude/CLAUDE.md`                    | direct (global) |
| Codex         | `codexcli`      | `~/.codex/AGENTS.md`                     | direct (`-o ~/.codex`) |
| Pi            | `pi`            | `~/.pi/agent/AGENTS.md`                  | direct (`-o ~/.pi/agent`); `pi/extensions/*.ts` copied to `~/.pi/agent/extensions/` |
| Hermes        | `hermesagent`   | `helm/charts/hermes/files/AGENTS.md`    | staged → commit + PR → ArgoCD → ConfigMap → PVC |

`rulesync.jsonc` sets `delete: false` so the `~/.claude/rules/` tree (Claude-only
language rules, installed by `scripts/claude-home.py`) is NEVER pruned by rulesync.

## Commands

```bash
npm run agents:bootstrap  # new machine: prereqs, plugins, graft, jev, sync, secrets, verify
npm install            # once — installs the pinned rulesync
npm run agents:sync    # regenerate every agent file from .rulesync/
npm run agents:check   # drift guard: non-zero exit if any file is out of sync (CI / pre-commit)
```

Edit a shared block once in `.rulesync/rules/*.md`, run `agents:sync`. For Hermes,
the helm file is updated locally — commit + PR it; ArgoCD delivers it to the PVC.

## Skills & plugins (not rulesync)

- **Our hand-authored skills** live in `../skills/` (plain files, byte-faithful) and are
  cp'd to `~/.claude/skills/` by `agents:sync`. They are NOT routed through rulesync —
  its skill generator strips Claude-specific SKILL.md frontmatter (`args:`) and reformats
  `description`. `agents:check` diffs them for drift.
- **Third-party plugins** (design set, tdd, review, deep-research, grill-me, caveman, …)
  come from marketplaces and are declared in `../plugins/` (`marketplaces.txt` +
  `plugins.txt` + `restore.sh`). That is why `~/.claude/skills/` is mostly symlinks into
  plugin caches — those are plugin-owned, not vendored here.

## Claude Code home (not rulesync)

rulesync does not model `settings.json`, hooks or the rules tree, so
`scripts/claude-home.py` (run by `agents:sync`; `check` by `agents:check`) installs:

| Source | Installed to | How |
|--------|--------------|-----|
| `claude-home/settings.json` | `~/.claude/settings.json` | additive merge, backup `settings.json.pre-sync`, written 0600 |
| `claude-home/hooks/*` | `~/.claude/hooks/` | copied |
| `claude-home/RTK.md` | `~/.claude/RTK.md` | copied |
| `claude-home/rules/**` | `~/.claude/rules/` | copied (vendored everything-claude-code rules snapshot) |

The merge never touches `permissions`, `sandbox`, `autoMode`, the dangerous-mode
flag or env keys it does not own. Preferences (`model`, `effortLevel`, `statusLine`,
…) are set only when absent, so `/model` choices survive. jcodemunch hooks are
registered only when `jcodemunch-mcp` is on PATH.

## MCP: one config, any host

`.rulesync/mcp.jsonc` points the `cellarette` server at the public edge
(`https://cellarette-mcp.<domain>/mcp?profile=workspace`). Before rulesync runs,
`scripts/lib/stage-mcp.sh` copies `.rulesync/` to a temp dir and
`claude-home.py render-mcp` rewrites that one line per host and agent:

- URL: `$CELLARETTE_MCP_URL`, else `claude-home/hosts/<hostname -s>.json`
  (`cellaretteUrl`), else the edge. lw-main's overlay pins `http://localhost:8788/mcp?profile=default`.
- Claude Code: `headersHelper: cellarette-headers`. The helper sends `{}` to
  localhost (`:8788` rejects any Authorization header), a Bearer token to the
  edge host only, and refuses every other host.
- Codex: `bearer_token_env_var = "CELLARETTE_MCP_TOKEN"` for https URLs only.
  Export it in your shell rc from `~/.config/cellarette/token`.

The token lives only in `~/.config/cellarette/token` (0600), written by
`cellarette-token-sync` (from Vault `secret/homelab/cellarette/mcp`, or `--stdin`).
Gotchas: rulesync `-g` replaces each MCP server entry as a whole (stale fields
vanish), and passes unknown keys such as `bearer_token_env_var` through to Codex.
Claude Code runs a `headersHelper` only in a trusted workspace — accept the
trust dialog. The `workspace` profile has no lightpanda, silverbullet or codex
tools; those exist only on lw-main's local aggregator.

## Bare-install contract

A fresh machine needs only this repo and network access to the cellarette edge:
`npm run agents:bootstrap`, then the token. It gives rules + MCP (cellarette,
graft) + skills + plugins + hooks + settings, and prints what is left to do.

## Onboard a NEW agent

1. Add its rulesync target id to `targets` in `rulesync.jsonc` (rulesync supports
   cursor, cline, copilot, gemini, opencode, … — see `rulesync docs reference/supported-tools`).
2. Tag the shared blocks it should receive by adding its target to their
   `targets:` frontmatter; add any agent-specific rule as a new `NN-<agent>.md`
   with `targets: ["<id>"]`.
3. Add one `rulesync generate --targets <id> ...` line to `scripts/agents-sync.sh`
   (and the matching `--check` in `agents-check.sh`) pointing at its output path.
4. `npm run agents:sync`.

No renderer code to write — rulesync already knows each tool's native format.
