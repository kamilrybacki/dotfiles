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
- **Ansible, not ArgoCD, owns:** the edge (Caddy `secure-homelab-access` role — a public
  host = add the route + Authelia forward-auth snippet, then an operator runs the caddy
  role), k8s Secrets (the `k8s-secrets` role reads Vault `secret/homelab/*` + control-machine
  files), and the NAS exports (`nas-setup/roles/nfs`). You cannot run ansible or ssh the NAS —
  stage the git change and ask the operator to apply.
- **Nodes:** lw-c1 (192.168.0.107, worker/agent, most CPU), lw-c2 (.240, worker/agent — YOU
  run here), lw-c3 (.108, **SOLE control-plane / k3s server**; c1+c2 are agents only),
  lw-main (.111, edge Caddy + Vault :8200), lw-nas (.115), lw-pi (.109, standalone RPi).
  Traefik VIP .50, k8s API VIP .60. Edge path: Internet → Cloudflare tunnel → Caddy →
  Authelia → Traefik VIP → cluster; hosts are `*.kamilandrzejrybacki.dpdns.org`.
- **Control-plane / datastore resilience.** k3s datastore = external Postgres on lw-nas
  (`192.168.0.115:5432`, kine). c3 is the ONLY control-plane node. So **lw-nas is a hard SPOF:
  if the NAS is down, the k3s API + every hosted service is down** (datastore unreachable →
  c3's k3s can't start → API VIP .60 unannounced → all ingress 502s). Multi-server CP-HA is
  supported in ansible IaC (`infrastructure/k3s-cluster-setup`, on `main`) but **NOT applied** —
  do not assume HA. If you observe a cluster-wide outage, suspect the NAS first.
- **SSH to homelab hosts = the cellarette `ssh__run` tool. NEVER a local ssh.** Your own pod
  has NO ssh client and you CANNOT install one (you run as uid 1001, no sudo — do not try apt,
  do not look for `/usr/bin/ssh`, `~/.ssh`, or a local key; they are irrelevant). To run a
  command on lw-main / lw-c1 / lw-c2 / lw-c3 / lw-nas / **lw-pi**, call the `ssh__run` tool with
  the host as the first arg and **NO `cwd`** (a `cwd` from your filesystem does not exist in the
  cellarette pod). Example: `ssh__run` with `["lw-pi", "docker ps -a && df -h /mnt/media"]`.
  The ssh client, key, and host config all live in the cellarette pod — `ssh__run` IS your
  access. `spawn ssh ENOENT` means you tried to run ssh locally or passed a bad cwd — switch to
  `ssh__run` without cwd. **lw-pi (192.168.0.109) is a standalone Raspberry Pi, NOT a k8s node**,
  so kubectl cannot reach it — always use `ssh__run`.
- **NAS (lw-nas .115) was SSD-migrated 2026-07-13: mergerfs is RETIRED**, the 4×500G pool
  disks removed; k3s datastore = external Postgres on the SSD. NFS exports now:
  `/mnt/pool`, `/mnt/pool/k8s-nfs` (k8s dynamic storage), `/mnt/storage`, `/mnt/disks/archive`,
  `/opt/knowledge-vault/content` (ro). Anything that was only on the old pool is gone.
- **NAS fragility + auto-recovery (2026-09-09).** lw-nas serves `.115` (datastore + NFS) over a
  USB **WiFi** dongle; its wired NIC (eno1) is unplugged — so a WiFi drop or power blip can down
  the whole cluster (see resilience note above). An external watchdog on lw-pi (cron, every 2 min)
  pings the NAS and, on down, fires Wake-on-LAN + alerts the operator via ntfy.sh — so an
  unattended NAS loss self-recovers in ~4 min. The operator also has a `homelab-recover` script on
  lw-main and off-NAS `k3s_state` DB backups (lw-main + lw-pi, every 6h). You cannot run these
  (no NAS/host access beyond `ssh__run`); just don't assume a brief cluster blip is permanent.
- **Obsidian vault:** files at `/opt/knowledge-vault/content` on lw-nas (research notes in
  `.../research/`). Served interactively via the Obsidian Local REST API
  `https://192.168.0.115:27124/vault/...` (self-signed → verify off; key `obsidian-mcp-secret`)
  — that is how obsidian-mcp reads it, NOT NFS by default. A read-only NFS export exists for
  static-site builds.
- **Your managed config** (config.yaml, AGENTS.md, SOUL.md, USER.md, redact-patterns.txt) is
  re-seeded to the `~/.hermes` PVC on pod restart whenever the chart version differs (old copy
  saved as `.prev`). MEMORY.md is agent-owned: seeded only if absent, never overwritten. So a
  chart edit to AGENTS.md takes effect after the operator restarts the pod.

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
