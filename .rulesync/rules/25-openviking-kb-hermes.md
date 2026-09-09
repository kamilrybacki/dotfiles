---
root: true
targets: ["hermesagent"]
description: "OpenViking KB consult policy (Hermes variant)"
globs: ["**/*"]
---
## Knowledge base — OpenViking (consult first)

- **OpenViking is the homelab context DB** (`viking://` virtual FS) — accumulated gotchas,
  past decisions, infra facts, and your own research-cron output. Access via the cellarette
  `openviking__*` tools (in your `hermes-devops` profile: search, read, grep, glob, list, tree,
  find, write, add_resource, remember, forget, health).
- **Consult it EARLY** on any homelab / infra / research task — alongside your Obsidian research
  vault and memory, and BEFORE web tools or trial-and-error. `openviking__search "<topic>"`
  (semantic) or `openviking__grep` / `openviking__glob` for exact strings. A quick lookup often
  surfaces a gotcha already paid for once.
- **KB layout:** `viking://resources/homelab-knowledge/` (per-project facts + gotchas),
  `viking://resources/session-knowledge/` (mined cross-session lessons),
  `viking://resources/research/` (where your research crons write their findings).
- **Contribute back** durable, reusable lessons with `openviking__write` to `viking://resources/…`
  — **REDACT secrets first** (never write tokens/keys/passwords). Your research crons already do
  this for their findings; for interactive work it's optional.
- If `openviking__*` isn't in your profile or `openviking__health` is unhealthy, skip silently —
  never block a task on the KB being reachable.
- **Auth (infra fact):** OV's `/mcp` accepts only the OpenViking ROOT key; the in-cluster caddy
  sidecar (`:8000`) injects it for you, so `openviking__*` just works. If these tools ever start
  failing with `-32001 "Invalid API Key"`, it's a sidecar/key misconfig, not your call being wrong
  — flag the operator (fixed 2026-09-09: sidecar was injecting the USER key → 401). A one-off
  `"Invalid API Key"` that succeeds on retry is a known transient on the single-replica pilot; just
  retry.
