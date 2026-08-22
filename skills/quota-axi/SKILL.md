---
name: quota-axi
description: >
  Report local Claude / Codex (and Cursor/Copilot/Grok) subscription quota windows via the
  quota-axi CLI — remaining percentages, reset times, provider status, read from local auth
  sources. Read-only: no routing, recommendation, or provider mutation. Use before deciding
  whether it's safe to keep spending a provider's quota, or when the user asks about usage /
  rate limits / remaining quota.
user-invocable: false
author: Kun Chen (kunchenguid)
metadata:
  hermes:
    tags: [quota, rate-limits, claude, codex, cli]
    category: observability
---

# quota-axi (homelab)

Report local agent-provider **subscription** quota windows. Data only — it never routes,
recommends, proxies, logs in, imports cookies, or mutates provider state, and never launches
the Claude/Codex agent, so it cannot spend the quota it measures. TOON output.

> **Provenance:** `kunchenguid/quota-axi` **v0.1.5** (MIT). Pinned homelab install.
> Works with **subscription** auth (Claude OAuth `~/.claude/.credentials.json`, plan e.g.
> `max`; Codex ChatGPT OAuth `~/.codex/auth.json`, plan e.g. `plus`). It **rejects API keys**
> (`OPENAI_API_KEY`) — it is a subscription tool. On Linux there is no Keychain step.

## Run it — use `quota-axi-hl` (the corrected wrapper), not raw `quota-axi`

`quota-axi-hl` is a thin read-only wrapper that fixes quota-axi's stale window labels (see the
quirk below) so the output is correct for every consumer. Prefer it. Do **not** use unpinned
`npx -y quota-axi`.

- `quota-axi-hl` — compact output of every available provider's quota windows (labels corrected).
- `quota-axi-hl --provider claude` / `--provider codex` — scope to one.
- `quota-axi-hl --json` — normalized machine-readable schema (labels corrected).
- `quota-axi-hl auth` — check local auth-source availability **without printing secrets**
  (passes straight through to quota-axi).

Exit: 0 = at least one provider returned data; 1 = every provider failed; 2 = usage error.
A provider with no local auth reports `auth_required`/`unavailable` — that is the definitive
answer, not an error to retry.

## Homelab policy — telemetry ONLY, no routing

- Use quota-axi purely to **observe** headroom (report to the user, decide whether to pause
  heavy work). **Do not** wire its output into any automatic provider-switching / routing
  decision — auto-routing is **not enabled** in this rollout (future policy is documented but
  off by design; quota-axi itself never routes).
- Never surface tokens/cookies/auth-headers/credential paths — quota-axi already guarantees it
  sends credential values only to first-party endpoints and never prints/logs/caches them.
- Percentages are **not comparable across providers** — never claim one provider's % equals
  another's.

## Known quirk — Codex window is WEEKLY, mislabeled `five_hour` (fixed by the wrapper)

Codex removed its 5-hour window; it now has a single **weekly** quota window, but quota-axi@0.1.5
still stamps the legacy `id: "five_hour"`, `label: "session"` on it (the authoritative
`windowSeconds: 604800` = 7 days is correct). **`quota-axi-hl` fixes this** — it derives the
label from `windowSeconds`, so Codex shows `weekly` for every consumer. If you ever call raw
`quota-axi` directly, remember: trust `windowSeconds`/`resetsAt`, not the `five_hour` label —
Codex resets **weekly**, not in 5 hours. (Claude's genuine 5h + 7d windows are left untouched.)
