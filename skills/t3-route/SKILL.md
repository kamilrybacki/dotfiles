---
name: t3-route
description: Start a T3 Code thread for a task on the agent the user picks (claude, codex, opencode_kimi, pi_free). Jev advice from /route is optional. Hard rules refuse open and cheap routes for infra, secrets and infra repos. Use when the user says "/t3-route", "dispatch this to T3", or "start a T3 thread for X".
---

# /t3-route <task> [--repo DIR] [--route KEY]

Starts one T3 Code thread. The USER chooses the route. Jev only advises.

Script: `~/.claude/skills/t3-route/t3-route.py` (from this repo: `skills/t3-route/t3-route.py`).

## Steps

1. **Task file.** Write the full task to a scratch file (`$TASK`). The raw text stays
   local; it goes only to the chosen T3 agent.
2. **Route.** If the user named a route, use it. Otherwise run `/route` steps (summary,
   `route.py question`, `jev__ask`, `route.py format`) and show Jev's advice. Then ask the
   user which route. Never pick for them.
3. **Plan.** Run:
   `python3 ~/.claude/skills/t3-route/t3-route.py dispatch --route KEY --repo DIR --task-file $TASK [--base REF --branch NAME] [--title T] [--review]`
   Without `--yes` it starts nothing and prints the route, repo and exact command.
   Use `--base main --branch <name>` to run in a new worktree instead of the project folder.
4. **Confirm.** Show the plan to the user and STOP. Re-run with `--yes` only after the user
   says yes to that exact plan. Never add `--yes` on your own.
5. **Report.** Print the thread result. With `--review` the script waits for the run and
   then tells you to run `/cross-review <base-ref>` from a Claude thread on that branch.
   Reviewers are never chained automatically.

## Hard rules (in the script, no override flag)

`opencode_kimi` and `pi_free` are refused when any of these hits:

- the task text matches the `/route` overrides (infra, secret, vault, helm, token, ssh, prod, ...);
- `sensitivity.classify` marks the task text restricted (keys, tokens, private IPs, infra paths);
- the repo is helm, ansible, argocd-apps, n8n-workflows, cellarette or dotfiles;
- the repo tracks secrets or network files (by `sensitivity.path_labels`).

A refused route stays refused: offer `claude` or `codex`. `other` is never dispatched.

## Config

`~/.config/t3-route/routes.json` overrides the shipped `routes.json` per route key:

```json
{"routes": {"pi_free": {"model": "<LiteLLM free or cheap model slug>"}}}
```

- `pi_free` has no default model and refuses until one is set. Pi uses only LiteLLM free
  or cheap models.
- `claude` has no model by default, so T3 uses its own default provider and model.
- `t3_bin` (or env `T3_BIN`) sets the T3 Code CLI. Default: newest
  `~/.t3/runtime/versions/*/t3`. `/usr/local/bin/t3` is a different tool (Tigris) and is refused.

If T3 does not know the repo yet, the script runs `t3 project add <repo>` once and retries.
