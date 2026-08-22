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
  05-hermes-conventions.md   targets: hermesagent               (Hermes only)
  40-hermes-facts.md         targets: hermesagent               (Hermes only)
```

Every rule is `root: true`, so all rules for one target combine into a single
inlined file (needed for Codex/Hermes, which cannot `@import`). Filename prefixes
(`05`,`10`,`20`,…) control section order within each file.

## Targets → live files

| Target        | rulesync target | Written to                              | How it ships |
|---------------|-----------------|-----------------------------------------|--------------|
| Claude Code   | `claudecode`    | `~/.claude/CLAUDE.md`                    | direct (global) |
| Codex         | `codexcli`      | `~/.codex/AGENTS.md`                     | direct (`-o ~/.codex`) |
| Hermes        | `hermesagent`   | `helm/charts/hermes/files/AGENTS.md`    | staged → commit + PR → ArgoCD → ConfigMap → PVC |

`rulesync.jsonc` sets `delete: false` so the hand-maintained `~/.claude/rules/`
tree (Claude-only language rules) is NEVER pruned by rulesync.

## Commands

```bash
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

## Bare-install contract

A fresh CLI agent needs only: this dotfiles sync + a reachable Cellarette (:8788 proxy).
`npm install && npm run agents:sync` gives it rules + MCP(cellarette) + our skills;
`plugins/restore.sh` re-adds the marketplaces + plugins.

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
