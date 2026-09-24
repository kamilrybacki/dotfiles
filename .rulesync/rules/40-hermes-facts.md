---
root: true
targets: ["hermesagent"]
description: "Hermes homelab infrastructure facts + joint-research protocol"
globs: ["**/*"]
---
## Homelab infrastructure (facts)

- **Deploy flow.** Helm charts live in `kamilandrzejrybacki-inc/helm`. To deploy a
  chart you must ALSO add an ArgoCD Application to the SEPARATE repo
  `kamilandrzejrybacki-inc/argocd-apps` at `apps/<name>.yaml` (ArgoCD auto-syncs `main`,
  prune+selfHeal). A helm commit alone deploys nothing without that app entry.
- **Git forge = self-hosted Forgejo (since 2026-09-25).** The `kamilandrzejrybacki-inc`
  org moved off GitHub; the GitHub org is ARCHIVED (read-only) — never push there and never
  use `gh`/`gh__run` for org repos (both still fine for personal `kamilrybacki` repos).
  Clone/push over the LAN endpoint `http://192.168.0.115:3000/kamilandrzejrybacki-inc/<repo>.git`
  (your git credential helper covers it as `homelab-agents`); UI at
  `https://git.kamilandrzejrybacki.dpdns.org`. Default branches are protected: push is
  allowed, force-push and branch deletion are not. PRs go through the Forgejo API
  (`/api/v1/repos/<org>/<repo>/pulls`), not GitHub.
- **Ansible, not ArgoCD, owns:** the edge (Caddy `secure-homelab-access` role — a public
  host = add the route + Authelia forward-auth snippet, then an operator runs the caddy
  role), the few k8s Secrets ESO cannot deliver (`k8s-secrets` role: vault-mcp-token, Codex/Claude
  auth files from the control machine), and the NAS exports (`nas-setup/roles/nfs`). You cannot
  run ansible or ssh the NAS — stage the git change and ask the operator to apply.
- **Secrets (since 2026-09-09).** Vault is the single source of truth, laid out by ISSUER:
  `secret/homelab/<issuer>/<credential>` with one leaf per consumer (e.g. `github/hermes#token`,
  `discord/hermes-bot#token`, `postgres/n8n#password`); fields use a closed vocabulary (token,
  api_key, password, client_secret, refresh_token, webhook_url, private_key, cert, encryption_key,
  salt, signing_key). Rules + runbook: `ansible/security/vault-setup/VAULT-TAXONOMY.md`. k8s
  Secrets are delivered by External Secrets Operator from `argocd-apps/secrets/eso/<ns>/` (the
  `eso-secrets` ArgoCD app; sops files are retired); a new k8s Secret = a Vault leaf + an entry in
  `ansible/security/vault-setup/migrate/eso/manifest.yaml` → `generate.py`. A restricted tier
  (wireguard, pihole, cloudflare, machines, k3s, and specific power paths like
  `postgres/k3s-datastore`, `hashicorp-vault/{root,unseal}`, `authelia/admin`) is denied to the
  agents/k8s policies. The old flat `secret/homelab/<service>` layout is gone — never recreate it.
- **Topology, cluster, storage, observability, accepted risks: DO NOT keep a copy here.**
  They are canonical in OpenViking at
  `viking://resources/homelab-knowledge/homelab-canonical-state.md`, and YOU re-verify that
  document against live systems every morning at 06:15 UTC (cron `homelab-knowledge-refresh`).
  `openviking__read` it before answering any homelab question. Four parallel copies of these
  facts is what made them rot through September 2026 — if a fact is missing or wrong, fix it
  THERE, not here. What stays in this file is only what is specific to you as an agent.
- **The two facts you must not get wrong, repeated here because they are load-bearing:**
  the k3s datastore is external Postgres on lw-db (`192.168.0.115:5432`, kine) and lw-db is a
  hard SPOF — if the NAS is down, the API and every hosted service are down, CP-HA
  notwithstanding. On a cluster-wide outage, suspect the NAS first. And you run inside the
  cluster on lw-c2.
- **SSH to homelab hosts = the cellarette `ssh__run` tool. NEVER a local ssh.** Your own pod
  has NO ssh client and you CANNOT install one (you run as uid 1001, no sudo — do not try apt,
  do not look for `/usr/bin/ssh`, `~/.ssh`, or a local key; they are irrelevant). To run a
  command on lw-main / lw-c1 / lw-c2 / lw-c3 / lw-db / **lw-pi**, call the `ssh__run` tool with
  the host as the first arg and **NO `cwd`** (a `cwd` from your filesystem does not exist in the
  cellarette pod). Example: `ssh__run` with `["lw-pi", "docker ps -a && df -h /mnt/media"]`.
  The ssh client, key, and host config all live in the cellarette pod — `ssh__run` IS your
  access. `spawn ssh ENOENT` means you tried to run ssh locally or passed a bad cwd — switch to
  `ssh__run` without cwd. **lw-pi (192.168.0.109) is a standalone Raspberry Pi, NOT a k8s node**,
  so kubectl cannot reach it — always use `ssh__run`.
- **NAS auto-recovery, because it changes how you react to an outage:** a watchdog on lw-pi
  pings lw-db every 2 minutes and, on down, fires Wake-on-LAN and alerts the operator via
  ntfy.sh, so an unattended NAS loss self-recovers in roughly 4 minutes. The operator also has
  a `homelab-recover` script on lw-main and off-NAS `k3s_state` backups every 6h. You cannot
  run any of it — just never assume a brief cluster blip is permanent.
- NAS storage layout, NFS exports and the Obsidian vault access path are in the canonical
  OpenViking document; read it rather than trusting a copy.
- **Your managed config** (config.yaml, AGENTS.md, SOUL.md, USER.md, redact-patterns.txt) is
  re-seeded to the `~/.hermes` PVC on pod restart whenever the chart version differs (old copy
  saved as `.prev`). MEMORY.md is agent-owned: seeded only if absent, never overwritten. So a
  chart edit to AGENTS.md takes effect after the operator restarts the pod.

## Teammates — consult a specialist or start a research run

The operator runs a roster of AI teammates (a separate service, ns `teammates`) reachable
through two cellarette tools in your profile:
- `teammates__consult` — ONE synchronous turn by a named teammate, reply comes back inline.
  Bots: `ops` (infra), `dev` (code), `security` (audit), `data` (metrics), `qa` (tests),
  `lead` (router), and the research crew `research-lead`, `trends`, `market`, `competition`,
  `customer`, `viability`. A turn can take minutes.
- `teammates__run` — START a workflow run and return at once (`workflow=validate`,
  `inputs={"idea": "..."}`). `validate` researches an idea across the five lenses and
  writes a report to OpenViking `viking://resources/research/validate-<slug>-<date>.md`;
  the run threads into `#research`. Only unattended-capable workflows are accepted.
- Use them when a cron or a conversation surfaces a concrete PRODUCT/MARKET opportunity
  (new category, unmet need, pricing/competitor shift) — that is the research crew's domain,
  not yours (you own tech/model/homelab knowledge). Hand off at most one item per cron run
  and say so in your report. Never hand off infra/deploy/git work this way.

## AI usage & quota — `#usage`

- The operator's model budget lives in ONE pinned, code-rendered card in Discord `#usage`:
  your Codex subscription windows (Session / Weekly, pulled from this pod's own login),
  the operator's Claude subscription windows (pushed hourly from their workstation), and
  LiteLLM real-money spend (24h / 7d / 30d, per model, from Prometheus). It refreshes
  hourly and on the operator's `/usage` slash command (owner-only; you cannot invoke it).
- Asked about quota, credits, "how much is left", or why a run stalled: point to `#usage`
  (or quote it if you can read the channel) — do NOT guess numbers and do NOT run
  `hermes usage` (no such command). Your teammate turns and crons draw on the SAME Codex
  weekly window shown there; LiteLLM routes (`litellm/deepseek` …) cost real money and show
  up in the $ rows.
- A quota/rate-limit error in a cron or a turn: report it in `#crons` as such and say the
  Weekly window in `#usage` is the thing to check — never retry in a loop.

## Joint-research protocol (Claude × Hermes)

Claude Code (the operator's other agent, posting via the cellarette-discord bot) may
@mention you in #hermes with a **joint-research brief**: a run id like `jr-<slug>-<n>`,
a topic, your subquestions, and a required completion marker. When you receive one:
- It is research/reflection ONLY — never take infra/deploy/git actions from a brief.
- Play to your strengths: check your Obsidian research vault + memory first, then your
  own web tools on YOUR subquestions (Claude covers the others in parallel).
- Answer in the requested format (`## Findings`, `## Sources` with URLs,
  `## Confidence & gaps`) and END your final message with the exact marker
  `JOINT-RESEARCH <run-id> COMPLETE` — Claude polls for it to merge the report.
- Partial findings before the stated deadline beat completeness after it.
- Claude will cross-examine your claims against its own; expect follow-up questions.
