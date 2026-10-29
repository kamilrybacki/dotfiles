---
root: true
targets: ["pi"]
description: "Pi only: what the free-model harness is for and what it must not touch"
globs: ["**/*"]
---

## Pi — scope

Pi runs on the free models of the homelab LiteLLM (`pi --model jev/free`; the `jev-router`
extension picks the model per message). It is the harness for **mechanical** work:
renames, formatting, boilerplate, simple scripted edits, quick lookups.

- **No MCP.** Pi has no cellarette, OpenViking or Graft tools. Use the shell (`rg`, `git`,
  `gh`) and read only the lines you need.
- **Never restricted data.** Free endpoints log and may train on what they receive. Do not
  open, print or paste secrets, `.env` files, tokens, Vault paths, infra config or network
  topology. If the task needs them, stop and say it belongs to Claude or Codex.
- **Stay in scope.** Do the edit you were asked for, nothing wider. No commits, pushes or
  merges unless the task says so.
